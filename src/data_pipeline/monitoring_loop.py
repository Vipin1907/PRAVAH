"""
monitoring_loop.py — Advanced continuous monitoring loop for the
multi-agent flash flood system.

Upgrades from the original:
  - Dynamic catchment list (from config, not hardcoded)
  - Health monitoring for all agents
  - Graceful degradation (if one catchment fails, others continue)
  - Metrics collection (avg prediction time, alert rate)
  - Structured logging throughout
  - Bias report generation
"""

import time
from collections import defaultdict
from typing import Dict, List, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from langgraph.types import Command

from flood_alert_agent import app
from alert_thresholds import CONFIG
from logger_config import get_agent_logger, write_audit_record
from responsible_ai import get_bias_report


log = get_agent_logger("supervisor")


# ── State Tracking ───────────────────────────────────────────────
PENDING_APPROVALS: Dict[str, dict] = {}
TICK_COUNT = 0

# metrics
METRICS = {
    "total_checks": 0,
    "total_alerts": 0,
    "total_errors": 0,
    "total_time_ms": 0,
    "alert_counts": defaultdict(int),  # by level
    "errors_by_catchment": defaultdict(int),
}


# ── Check Single Catchment ───────────────────────────────────────
def check_one_catchment(catchment_id: str) -> Optional[dict]:
    """
    Run the full multi-agent pipeline for one catchment.
    Returns the final state, or None if an error occurred.
    """
    config = {"configurable": {"thread_id": f"monitor-{catchment_id}-{int(time.time())}"}}
    state = {"catchment_id": catchment_id}

    start = time.time()

    try:
        result = app.invoke(state, config=config)
        elapsed = (time.time() - start) * 1000

        METRICS["total_checks"] += 1
        METRICS["total_time_ms"] += elapsed

        # check if paused for human approval
        if result.get("final_status") is None:
            alert_level = result.get("alert_level", "UNKNOWN")
            PENDING_APPROVALS[catchment_id] = {
                "config": config,
                "result": result,
                "timestamp": time.time(),
                "alert_level": alert_level,
            }
            METRICS["total_alerts"] += 1
            METRICS["alert_counts"][alert_level] += 1

            log.info(
                f"  ⏳ [{catchment_id}] {alert_level} ALERT — "
                f"PENDING HUMAN APPROVAL",
                extra={
                    "agent": "supervisor",
                    "catchment_id": catchment_id,
                    "alert_level": alert_level,
                },
            )
        else:
            status = result.get("final_status", "unknown")
            alert_level = result.get("alert_level", "GREEN")
            prob = result.get("probability", 0)

            if alert_level not in ("GREEN", "YELLOW"):
                METRICS["total_alerts"] += 1
                METRICS["alert_counts"][alert_level] += 1

            log.info(
                f"  ✅ [{catchment_id}] {alert_level} | "
                f"prob={prob:.2f} | status={status} | {elapsed:.0f}ms",
                extra={
                    "agent": "supervisor",
                    "catchment_id": catchment_id,
                    "alert_level": alert_level,
                    "probability": prob,
                    "latency_ms": int(elapsed),
                    "status": status,
                },
            )

        return result

    except Exception as e:
        elapsed = (time.time() - start) * 1000
        METRICS["total_errors"] += 1
        METRICS["errors_by_catchment"][catchment_id] += 1

        log.error(
            f"  ❌ [{catchment_id}] PIPELINE ERROR: {e} ({elapsed:.0f}ms)",
            extra={
                "agent": "supervisor",
                "catchment_id": catchment_id,
                "latency_ms": int(elapsed),
            },
        )

        write_audit_record(
            catchment_id=catchment_id,
            event_type="pipeline_error",
            data={"error": str(e), "elapsed_ms": elapsed},
            agent="supervisor",
        )

        return None


# ── Monitoring Tick ──────────────────────────────────────────────
def monitoring_tick():
    """
    Single monitoring cycle: checks all catchments and reports status.
    """
    global TICK_COUNT
    TICK_COUNT += 1

    log.info(
        f"\n{'═' * 55}",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  MONITORING TICK #{TICK_COUNT} @ {time.strftime('%H:%M:%S')}",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  Catchments: {len(CONFIG.watched_catchments)} | "
        f"Mode: {'DEMO' if CONFIG.tick_interval_seconds < 60 else 'PRODUCTION'}",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"{'═' * 55}",
        extra={"agent": "supervisor"},
    )

    results = {}
    errors = 0

    for cid in CONFIG.watched_catchments:
        result = check_one_catchment(cid)
        if result is not None:
            results[cid] = result
        else:
            errors += 1

    # summary
    log.info(
        f"\n{'─' * 40}",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  TICK #{TICK_COUNT} SUMMARY:",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  Checked: {len(CONFIG.watched_catchments)} | "
        f"OK: {len(results)} | Errors: {errors}",
        extra={"agent": "supervisor"},
    )

    if PENDING_APPROVALS:
        log.info(
            f"  ⏳ Pending approvals: {len(PENDING_APPROVALS)} — "
            f"{list(PENDING_APPROVALS.keys())}",
            extra={"agent": "supervisor"},
        )

    # check for stale pending approvals (auto-escalation)
    _check_escalation_timeouts()

    # periodic bias report (every 10 ticks)
    if TICK_COUNT % 10 == 0:
        _print_metrics()


# ── Escalation Timeout Check ────────────────────────────────────
def _check_escalation_timeouts():
    """
    Check if any pending approvals have exceeded their escalation
    timeout. If so, auto-approve them.
    """
    now = time.time()
    to_escalate = []

    for cid, info in PENDING_APPROVALS.items():
        age_min = (now - info["timestamp"]) / 60
        level = info["alert_level"]

        # for demo, use 2 minutes instead of 15/30
        demo_timeout = 2.0  # minutes

        if age_min > demo_timeout:
            to_escalate.append(cid)
            log.warning(
                f"  ⚡ [{cid}] Auto-escalating after {age_min:.1f}min "
                f"(timeout={demo_timeout}min)",
                extra={
                    "agent": "supervisor",
                    "catchment_id": cid,
                    "alert_level": level,
                },
            )

    for cid in to_escalate:
        resolve_pending(cid, "auto_escalated")


# ── Resolve Pending Approval ────────────────────────────────────
def resolve_pending(catchment_id: str, decision: str) -> Optional[dict]:
    """
    Resolve a pending human approval.

    Args:
        catchment_id: which catchment to resolve
        decision: "approve" or "reject" or "auto_escalated"

    Returns:
        Final state, or None if no pending approval
    """
    if catchment_id not in PENDING_APPROVALS:
        log.warning(
            f"No pending approval for {catchment_id}",
            extra={"agent": "supervisor"},
        )
        return None

    info = PENDING_APPROVALS[catchment_id]
    config = info["config"]

    resume_value = "approve" if decision in ("approve", "auto_escalated") else decision

    try:
        final = app.invoke(Command(resume=resume_value), config=config)

        log.info(
            f"  👤 [{catchment_id}] Resolved: {decision} → "
            f"{final.get('final_status')}",
            extra={
                "agent": "supervisor",
                "catchment_id": catchment_id,
                "decision": decision,
                "status": final.get("final_status"),
            },
        )

        write_audit_record(
            catchment_id=catchment_id,
            event_type="approval_resolved",
            data={
                "decision": decision,
                "alert_level": info["alert_level"],
                "wait_time_sec": time.time() - info["timestamp"],
            },
            agent="human" if decision != "auto_escalated" else "supervisor",
        )

        del PENDING_APPROVALS[catchment_id]
        return final

    except Exception as e:
        log.error(
            f"Failed to resolve {catchment_id}: {e}",
            extra={"agent": "supervisor", "catchment_id": catchment_id},
        )
        return None


# ── Metrics ──────────────────────────────────────────────────────
def _print_metrics():
    """Print accumulated metrics and bias report."""
    log.info(
        f"\n{'═' * 50}",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  PIPELINE METRICS (after {TICK_COUNT} ticks)",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  Total checks: {METRICS['total_checks']}",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  Total alerts: {METRICS['total_alerts']}",
        extra={"agent": "supervisor"},
    )
    log.info(
        f"  Total errors: {METRICS['total_errors']}",
        extra={"agent": "supervisor"},
    )

    if METRICS["total_checks"] > 0:
        avg_time = METRICS["total_time_ms"] / METRICS["total_checks"]
        log.info(
            f"  Avg pipeline time: {avg_time:.0f}ms",
            extra={"agent": "supervisor"},
        )

    if METRICS["alert_counts"]:
        log.info(
            f"  Alert breakdown: {dict(METRICS['alert_counts'])}",
            extra={"agent": "supervisor"},
        )

    # bias report
    bias = get_bias_report()
    if bias:
        log.info(
            f"\n  BIAS REPORT:",
            extra={"agent": "supervisor"},
        )
        for cid, stats in bias.items():
            log.info(
                f"    {cid}: alert_rate={stats['alert_rate']:.1%}, "
                f"false_alarm_rate={stats['false_alarm_rate']:.1%}",
                extra={"agent": "supervisor"},
            )


# ── Main Entry Point ────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 60)
    print("  🌊 Flash Flood Agentic AI — Monitoring Loop")
    print(f"  Catchments: {len(CONFIG.watched_catchments)}")
    print(f"  Tick interval: {CONFIG.tick_interval_seconds}s (demo mode)")
    print("  Press Ctrl+C to stop")
    print("═" * 60)
    print()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        monitoring_tick,
        "interval",
        seconds=CONFIG.tick_interval_seconds,
        next_run_time=None,
    )

    # run first tick immediately
    monitoring_tick()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n")
        _print_metrics()
        print("\nStopped.")