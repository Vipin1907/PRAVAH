"""
logger_config.py — Structured logging and audit trail for the
agentic flood alert system.

Every agent decision, data fetch, and human interaction is logged
in structured JSON format for:
  - Post-event forensic analysis
  - SIH demo audit trail
  - Real-time monitoring dashboard feed
"""

import logging
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional


# ── Directories ──────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
AUDIT_DIR = os.path.join(LOG_DIR, "audit_trail")
ALERT_DIR = os.path.join(LOG_DIR, "alerts")

for d in [LOG_DIR, AUDIT_DIR, ALERT_DIR]:
    os.makedirs(d, exist_ok=True)


# ── Structured JSON Formatter ────────────────────────────────────
class StructuredFormatter(logging.Formatter):
    """Outputs log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "agent": getattr(record, "agent", "system"),
            "catchment_id": getattr(record, "catchment_id", None),
            "event": record.getMessage(),
        }

        # attach any extra structured data passed via `extra={}`
        for key in ("probability", "confidence", "alert_level",
                     "data_quality", "decision", "reason",
                     "source", "latency_ms", "top_drivers",
                     "lead_time_hrs", "status"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


# ── Pretty Console Formatter (for demo) ─────────────────────────
class PrettyFormatter(logging.Formatter):
    """Coloured, human-readable console output for live demos."""

    AGENT_ICONS = {
        "data_ingestion": "[DATA]",
        "forecast": "[FORECAST]",
        "alert_decision": "[ALERT]",
        "dissemination": "[DISSEM]",
        "supervisor": "[SUPERVISOR]",
        "responsible_ai": "[AI_SAFETY]",
        "system": "[SYSTEM]",
        "human": "[HUMAN]",
    }
    LEVEL_COLORS = {
        "DEBUG": "",
        "INFO": "",
        "WARNING": "[WARN] ",
        "ERROR": "[ERROR] ",
        "CRITICAL": "[CRITICAL] ",
    }
    RESET = ""

    def format(self, record: logging.LogRecord) -> str:
        agent = getattr(record, "agent", "system")
        icon = self.AGENT_ICONS.get(agent, "[SYS]")
        color = self.LEVEL_COLORS.get(record.levelname, "")
        ts = datetime.now().strftime("%H:%M:%S")

        catchment = getattr(record, "catchment_id", "")
        catch_str = f" [{catchment}]" if catchment else ""

        return (
            f"[{ts}] {icon} {agent.upper()}{catch_str}"
            f"  {color}{record.getMessage()}{self.RESET}"
        )


# ── Logger Factory ───────────────────────────────────────────────
def get_agent_logger(agent_name: str) -> logging.Logger:
    """
    Returns a logger pre-configured with:
      - JSON file handler  (logs/agent_pipeline.jsonl)
      - Pretty console handler (stdout)
    """
    logger = logging.getLogger(f"flood_agent.{agent_name}")

    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # file handler — structured JSON lines
    fh = logging.FileHandler(
        os.path.join(LOG_DIR, "agent_pipeline.jsonl"),
        encoding="utf-8",
    )
    fh.setFormatter(StructuredFormatter())
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # console handler — pretty output
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(PrettyFormatter())
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)

    return logger


# ── Audit Trail Writer ───────────────────────────────────────────
def write_audit_record(
    catchment_id: str,
    event_type: str,
    data: dict,
    agent: str = "system",
) -> str:
    """
    Writes a permanent, immutable audit record to disk.
    Returns the path to the audit file.

    event_type examples:
      - "alert_issued"
      - "alert_approved"
      - "alert_rejected"
      - "data_quality_warning"
      - "fallback_activated"
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "catchment_id": catchment_id,
        "event_type": event_type,
        "agent": agent,
        "data": data,
    }

    filename = (
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        f"_{catchment_id}_{event_type}.json"
    )
    filepath = os.path.join(AUDIT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, default=str)

    return filepath


def save_alert_record(
    catchment_id: str,
    alert_level: str,
    cap_xml: str,
    state: dict,
) -> str:
    """Saves a complete alert record for post-event analysis."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "catchment_id": catchment_id,
        "alert_level": alert_level,
        "state_snapshot": {
            k: v for k, v in state.items()
            if not k.startswith("_")
        },
        "cap_xml": cap_xml,
    }

    filename = (
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        f"_{catchment_id}_{alert_level}.json"
    )
    filepath = os.path.join(ALERT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, default=str)

    return filepath
