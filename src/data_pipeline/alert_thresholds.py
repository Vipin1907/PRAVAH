"""
alert_thresholds.py — Multi-level alert classification and
system configuration.

Replaces the single binary threshold with a 5-tier alert system
aligned with NDMA / IMD standards:
  GREEN  → no action
  YELLOW → watchlist, auto-notify monitoring team
  ORANGE → elevated risk, human review within 30 min
  RED    → high risk, immediate human approval required
  EXTREME→ auto-disseminate, notify human after
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Alert Level Definitions ──────────────────────────────────────
@dataclass(frozen=True)
class AlertLevel:
    name: str
    color: str
    icon: str
    min_probability: float
    min_confidence: float
    requires_human_approval: bool
    auto_disseminate: bool
    escalation_timeout_min: Optional[int]  # auto-escalate after N min
    description: str


# ordered from lowest to highest severity
ALERT_LEVELS = [
    AlertLevel(
        name="GREEN",
        color="green",
        icon="🟢",
        min_probability=0.0,
        min_confidence=0.0,
        requires_human_approval=False,
        auto_disseminate=False,
        escalation_timeout_min=None,
        description="No significant flood risk. Routine monitoring.",
    ),
    AlertLevel(
        name="YELLOW",
        color="yellow",
        icon="🟡",
        min_probability=0.3,
        min_confidence=0.5,
        requires_human_approval=False,
        auto_disseminate=False,
        escalation_timeout_min=None,
        description="Watch: elevated rainfall. Monitoring team notified.",
    ),
    AlertLevel(
        name="ORANGE",
        color="orange",
        icon="🟠",
        min_probability=0.5,
        min_confidence=0.6,
        requires_human_approval=True,
        auto_disseminate=False,
        escalation_timeout_min=30,
        description="Alert: significant flood risk. Human review within 30 min.",
    ),
    AlertLevel(
        name="RED",
        color="red",
        icon="🔴",
        min_probability=0.7,
        min_confidence=0.7,
        requires_human_approval=True,
        auto_disseminate=False,
        escalation_timeout_min=15,
        description="Warning: high flood probability. Immediate human approval required.",
    ),
    AlertLevel(
        name="EXTREME",
        color="purple",
        icon="🟣",
        min_probability=0.85,
        min_confidence=0.8,
        requires_human_approval=False,
        auto_disseminate=True,
        escalation_timeout_min=None,
        description="Extreme: auto-disseminate. Human notified after the fact.",
    ),
]


def classify_alert(probability: float, confidence: float) -> AlertLevel:
    """
    Returns the highest matching alert level for given probability
    and confidence values.

    Iterates from EXTREME → GREEN, returning the first (highest)
    level whose thresholds are met.
    """
    for level in reversed(ALERT_LEVELS):
        if (probability >= level.min_probability and
                confidence >= level.min_confidence):
            return level
    return ALERT_LEVELS[0]  # GREEN fallback


# ── System Configuration ─────────────────────────────────────────
@dataclass
class PipelineConfig:
    """Central configuration for the entire agentic pipeline."""

    # catchments to monitor
    watched_catchments: List[str] = field(default_factory=lambda: [
        "catch_001", "catch_002", "catch_003", "catch_004",
        "catch_005", "catch_006", "catch_007",
    ])

    # monitoring schedule
    tick_interval_seconds: int = 10  # demo mode (production: 900 = 15 min)
    production_tick_seconds: int = 900

    # data quality
    max_data_age_hours: float = 6.0
    min_data_quality_score: float = 0.7

    # responsible AI
    max_red_alerts_per_catchment_24h: int = 2
    max_orange_alerts_per_catchment_24h: int = 5
    confidence_calibration_enabled: bool = True

    # dissemination
    webhook_url: Optional[str] = None  # set for real integration
    sms_enabled: bool = False  # demo mode: simulated
    email_enabled: bool = False

    # model
    model_path: Optional[str] = None  # path to trained XGBoost model
    use_rule_based_fallback: bool = True  # until ML model is ready

    # regions
    regions: List[str] = field(default_factory=lambda: [
        "uttarakhand", "assam",
    ])


# global config instance — import and use everywhere
CONFIG = PipelineConfig()
