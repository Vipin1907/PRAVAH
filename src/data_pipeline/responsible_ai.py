"""
responsible_ai.py — Guardrails, bias monitoring, and responsible
decision-making for the flood alert agent.

Implements:
  1. Confidence Calibration — adjusts raw model confidence using
     Platt scaling to prevent overconfident alerts
  2. Uncertainty Estimation — flags predictions outside the model's
     training distribution
  3. Alert Rate Limiting — prevents alert fatigue by capping the
     number of Red/Orange alerts per catchment per 24h
  4. Bias Monitoring — tracks per-catchment false alert rates to
     detect if certain areas are systematically over/under-alerted
  5. Human-Readable Explanations — generates plain-language
     explanations of why an alert was issued
"""

import os
import json
import time
import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from logger_config import get_agent_logger, write_audit_record
from alert_thresholds import CONFIG

log = get_agent_logger("responsible_ai")


# ── 1. Confidence Calibration (Platt Scaling) ────────────────────

def calibrate_confidence(
    raw_probability: float,
    raw_confidence: float,
    catchment_id: str = "unknown",
) -> Tuple[float, float]:
    """
    Apply Platt scaling to raw model outputs.

    Models (especially XGBoost) often produce poorly calibrated
    probabilities. This applies a logistic correction:
      calibrated = 1 / (1 + exp(-(A * raw + B)))

    where A and B are learned from validation data.

    For now, uses conservative defaults that slightly reduce
    overconfident predictions (A=1.2, B=-0.15). These should be
    re-estimated once Vipin's model produces validation outputs.
    """
    if not CONFIG.confidence_calibration_enabled:
        return raw_probability, raw_confidence

    # Platt scaling parameters (conservative defaults)
    A_prob, B_prob = 1.2, -0.15
    A_conf, B_conf = 1.1, -0.10

    cal_prob = 1.0 / (1.0 + math.exp(-(A_prob * raw_probability + B_prob)))
    cal_conf = 1.0 / (1.0 + math.exp(-(A_conf * raw_confidence + B_conf)))

    cal_prob = round(cal_prob, 3)
    cal_conf = round(cal_conf, 3)

    if abs(cal_prob - raw_probability) > 0.05:
        log.info(
            f"Calibrated: prob {raw_probability:.2f}->{cal_prob:.2f}, "
            f"conf {raw_confidence:.2f}->{cal_conf:.2f}",
            extra={
                "agent": "responsible_ai",
                "catchment_id": catchment_id,
                "probability": cal_prob,
                "confidence": cal_conf,
            },
        )

    return cal_prob, cal_conf


# ── 2. Anomaly / Out-of-Distribution Detection ──────────────────

# rough training-data ranges (from Uttarakhand + Assam datasets)
TRAINING_RANGES = {
    "rainfall_3d":          (0, 400),
    "rainfall_7d":          (0, 800),
    "soil_saturation_proxy":(0, 1.0),
    "slope_mean":           (0, 60),
    "flow_accumulation":    (0, 50000),
    "ndvi":                 (-0.2, 0.9),
}


def check_out_of_distribution(
    features: Dict[str, float],
    catchment_id: str = "unknown",
) -> Tuple[bool, List[str]]:
    """
    Check if input features fall outside the model's training
    distribution.

    Returns:
      (is_in_distribution, list_of_ood_features)

    If OOD features are detected, the prediction should be flagged
    with lower confidence.
    """
    ood_features = []

    for feat, (lo, hi) in TRAINING_RANGES.items():
        val = features.get(feat)
        if val is None:
            continue

        # allow 20% margin beyond training range
        margin = (hi - lo) * 0.2
        if val < (lo - margin) or val > (hi + margin):
            ood_features.append(f"{feat}={val:.2f} (training range: {lo}–{hi})")

    if ood_features:
        log.warning(
            f"OUT-OF-DISTRIBUTION: {len(ood_features)} feature(s) outside "
            f"training range — prediction reliability degraded",
            extra={
                "agent": "responsible_ai",
                "catchment_id": catchment_id,
            },
        )
        for oof in ood_features:
            log.warning(f"  ├─ OOD: {oof}", extra={"agent": "responsible_ai"})

    return len(ood_features) == 0, ood_features


# ── 3. Alert Rate Limiting ───────────────────────────────────────

# in-memory alert history (reset on restart; production would use DB)
_alert_history: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(
    catchment_id: str,
    alert_level: str,
) -> Tuple[bool, str]:
    """
    Check if this catchment has exceeded the maximum allowed alerts
    in the past 24 hours.

    Returns:
      (is_allowed, reason_if_blocked)
    """
    now = time.time()
    window_24h = now - 86400

    # clean old entries
    _alert_history[catchment_id] = [
        t for t in _alert_history[catchment_id]
        if t > window_24h
    ]

    count = len(_alert_history[catchment_id])

    if alert_level in ("RED", "EXTREME"):
        max_allowed = CONFIG.max_red_alerts_per_catchment_24h
        if count >= max_allowed:
            reason = (
                f"Rate limited: {count}/{max_allowed} RED/EXTREME alerts "
                f"in 24h for {catchment_id}. Preventing alert fatigue."
            )
            log.warning(reason, extra={
                "agent": "responsible_ai",
                "catchment_id": catchment_id,
                "alert_level": alert_level,
            })
            write_audit_record(
                catchment_id=catchment_id,
                event_type="alert_rate_limited",
                data={"level": alert_level, "count_24h": count, "max": max_allowed},
                agent="responsible_ai",
            )
            return False, reason

    elif alert_level == "ORANGE":
        max_allowed = CONFIG.max_orange_alerts_per_catchment_24h
        if count >= max_allowed:
            reason = (
                f"Rate limited: {count}/{max_allowed} ORANGE alerts "
                f"in 24h for {catchment_id}."
            )
            log.warning(reason, extra={"agent": "responsible_ai"})
            return False, reason

    return True, ""


def record_alert_issued(catchment_id: str) -> None:
    """Record that an alert was issued (for rate limiting)."""
    _alert_history[catchment_id].append(time.time())


# ── 4. Bias Monitoring ───────────────────────────────────────────

# tracks alerts per catchment for bias analysis
_catchment_alert_counts: Dict[str, Dict[str, int]] = defaultdict(
    lambda: {"total_checks": 0, "alerts_issued": 0, "false_alarms": 0}
)


def record_check(catchment_id: str, alert_issued: bool) -> None:
    """Record a monitoring check for bias tracking."""
    _catchment_alert_counts[catchment_id]["total_checks"] += 1
    if alert_issued:
        _catchment_alert_counts[catchment_id]["alerts_issued"] += 1


def record_false_alarm(catchment_id: str) -> None:
    """Record a confirmed false alarm (post-event feedback)."""
    _catchment_alert_counts[catchment_id]["false_alarms"] += 1


def get_bias_report() -> Dict[str, dict]:
    """
    Returns a bias report showing alert rates per catchment.

    If one catchment has a significantly higher false alarm rate than
    others, this could indicate model bias or data quality issues
    for that area.
    """
    report = {}
    for cid, stats in _catchment_alert_counts.items():
        total = stats["total_checks"]
        if total == 0:
            continue
        alert_rate = stats["alerts_issued"] / total
        false_alarm_rate = (
            stats["false_alarms"] / stats["alerts_issued"]
            if stats["alerts_issued"] > 0 else 0
        )
        report[cid] = {
            "total_checks": total,
            "alerts_issued": stats["alerts_issued"],
            "alert_rate": round(alert_rate, 3),
            "false_alarms": stats["false_alarms"],
            "false_alarm_rate": round(false_alarm_rate, 3),
        }
    return report


# ── 5. Human-Readable Explanation Generator ──────────────────────

# driver descriptions (plain language)
DRIVER_DESCRIPTIONS = {
    "rainfall_3d": "cumulative rainfall over the past 3 days",
    "rainfall_7d": "cumulative rainfall over the past 7 days",
    "rainfall_1d": "rainfall in the last 24 hours",
    "rainfall_30d": "total rainfall in the past month",
    "soil_saturation_proxy": "estimated soil moisture saturation level",
    "slope_mean": "average terrain slope angle",
    "flow_accumulation": "upstream drainage area contributing runoff",
    "ndvi": "vegetation density (lower = less ground cover)",
}


def generate_explanation(
    catchment_id: str,
    probability: float,
    confidence: float,
    top_drivers: List[str],
    features: Dict[str, float],
    alert_level_name: str,
    lead_time_hrs: float,
) -> str:
    """
    Generate a human-readable, non-technical explanation of why
    an alert was triggered.
    """
    lines = [
        f"[ALERT] FLASH FLOOD ALERT -- {alert_level_name}",
        f"",
        f"Catchment: {catchment_id}",
        f"Risk Level: {probability*100:.0f}% probability of flash flood",
        f"Confidence: {confidence*100:.0f}%",
        f"Expected within: {lead_time_hrs:.0f} hours",
        f"",
        f"Key Risk Factors:",
    ]

    for i, driver in enumerate(top_drivers[:3], 1):
        desc = DRIVER_DESCRIPTIONS.get(driver, driver)
        val = features.get(driver)
        val_str = f" (current: {val:.1f})" if val is not None else ""
        lines.append(f"  {i}. {desc}{val_str}")

    # add contextual warnings
    r3d = features.get("rainfall_3d", 0)
    if r3d > 100:
        lines.append(f"")
        lines.append(
            f"[Context] {r3d:.0f}mm in 3 days is "
            f"{r3d/50:.1f}x the regional average. "
            f"Soil is likely near saturation."
        )

    slope = features.get("slope_mean", 0)
    if slope > 25:
        lines.append(
            f"[Terrain] Steep terrain ({slope:.0f} deg) accelerates surface runoff "
            f"and increases flash flood velocity."
        )

    return "\n".join(lines)
