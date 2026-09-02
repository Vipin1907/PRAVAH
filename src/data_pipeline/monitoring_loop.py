"""
monitoring_loop.py — the piece that makes this "agentic" rather than a
one-shot script. Runs continuously, checking every catchment on a
schedule, and only pings a human when a real decision is needed.
"""

import time
from apscheduler.schedulers.blocking import BlockingScheduler
from langgraph.types import Command
from flood_alert_agent import app  # imports the graph from File 1

WATCHED_CATCHMENTS = ["catch_001", "catch_002", "catch_003"]
PENDING_APPROVALS = {}


def check_one_catchment(catchment_id: str):
    config = {"configurable": {"thread_id": catchment_id}}
    state = {
        "catchment_id": catchment_id,
        "threshold": 0.6,
        "min_conf": 0.6,
    }
    result = app.invoke(state, config=config)

    if "__interrupt__" in result:
        print(f"  -> [{catchment_id}] ALERT PENDING HUMAN APPROVAL")
        PENDING_APPROVALS[catchment_id] = {
            "config": config,
            "payload": result["__interrupt__"],
        }
    else:
        status = result.get("final_status", "unknown")
        print(f"  -> [{catchment_id}] status={status}, "
              f"probability={result.get('probability')}")


def monitoring_tick():
    print(f"\n=== Monitoring tick @ {time.strftime('%H:%M:%S')} ===")
    for cid in WATCHED_CATCHMENTS:
        check_one_catchment(cid)

    if PENDING_APPROVALS:
        print(f"\n  {len(PENDING_APPROVALS)} catchment(s) awaiting human approval: "
              f"{list(PENDING_APPROVALS.keys())}")


def resolve_pending(catchment_id: str, decision: str):
    """Call this when a human clicks approve/reject on the dashboard."""
    if catchment_id not in PENDING_APPROVALS:
        print(f"No pending approval for {catchment_id}")
        return
    config = PENDING_APPROVALS[catchment_id]["config"]
    final = app.invoke(Command(resume=decision), config=config)
    print(f"[{catchment_id}] resolved: {decision} -> {final.get('final_status')}")
    del PENDING_APPROVALS[catchment_id]


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(monitoring_tick, "interval", seconds=10, next_run_time=None)

    print("Starting monitoring loop (Ctrl+C to stop) ...")
    print("Demo mode: ticking every 10 seconds (production would be every 15-30 min)\n")

    monitoring_tick()
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nStopped.")