"""
data_validator.py — Validates all incoming data before it reaches
the ML model or alert decision agent.

Prevents garbage-in-garbage-out by checking:
  - Physical bounds (rainfall can't be -50mm or 2000mm/day)
  - Completeness (NaN ratio)
  - Staleness (data age)
  - Consistency (sudden impossible jumps)

Every validation result gets a quality score (0.0–1.0) that travels
with the prediction through the entire pipeline.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from logger_config import get_agent_logger, write_audit_record

log = get_agent_logger("data_validator")


# ── Physical bounds for each feature ─────────────────────────────
FEATURE_BOUNDS = {
    "rainfall_mm":          (0.0, 500.0),    # mm/day; world record ~1825mm
    "rainfall_1d":          (0.0, 500.0),
    "rainfall_3d":          (0.0, 1200.0),
    "rainfall_7d":          (0.0, 2500.0),
    "rainfall_30d":         (0.0, 8000.0),
    "soil_saturation_proxy":(0.0, 1.0),
    "ndvi":                 (-1.0, 1.0),
    "slope_mean":           (0.0, 90.0),     # degrees
    "flow_accumulation":    (0.0, 1e9),      # cells
    "probability":          (0.0, 1.0),
    "confidence":           (0.0, 1.0),
}


@dataclass
class ValidationResult:
    """Result of validating a data payload."""
    is_valid: bool
    quality_score: float            # 0.0 (garbage) → 1.0 (perfect)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    corrections_applied: Dict[str, str] = field(default_factory=dict)
    data_age_seconds: Optional[float] = None

    @property
    def is_degraded(self) -> bool:
        """True if data is usable but below ideal quality."""
        return self.is_valid and self.quality_score < 0.9


def validate_feature_bounds(
    features: Dict[str, float],
    catchment_id: str = "unknown",
) -> ValidationResult:
    """
    Check every feature value against known physical bounds.
    Returns a ValidationResult with quality score.
    """
    warnings = []
    errors = []
    corrections = {}
    total_features = 0
    valid_features = 0

    for key, value in features.items():
        if key not in FEATURE_BOUNDS:
            continue

        total_features += 1
        lo, hi = FEATURE_BOUNDS[key]

        if value is None:
            warnings.append(f"{key} is None (missing)")
            continue

        try:
            fval = float(value)
        except (ValueError, TypeError):
            errors.append(f"{key}={value!r} is not numeric")
            continue

        if fval != fval:  # NaN check
            warnings.append(f"{key} is NaN")
            continue

        if fval < lo:
            corrections[key] = f"clamped from {fval:.4f} to {lo:.4f}"
            features[key] = lo
            warnings.append(f"{key}={fval:.4f} below min {lo}, clamped")
            valid_features += 0.5  # partial credit
        elif fval > hi:
            corrections[key] = f"clamped from {fval:.4f} to {hi:.4f}"
            features[key] = hi
            warnings.append(f"{key}={fval:.4f} above max {hi}, clamped")
            valid_features += 0.5
        else:
            valid_features += 1

    quality = valid_features / max(total_features, 1)
    is_valid = len(errors) == 0 and quality >= 0.5

    result = ValidationResult(
        is_valid=is_valid,
        quality_score=round(quality, 3),
        warnings=warnings,
        errors=errors,
        corrections_applied=corrections,
    )

    # log validation
    if errors:
        log.error(
            f"Validation FAILED: {len(errors)} errors",
            extra={
                "agent": "data_validator",
                "catchment_id": catchment_id,
                "data_quality": quality,
            },
        )
    elif warnings:
        log.warning(
            f"Validation passed with {len(warnings)} warnings, "
            f"quality={quality:.1%}",
            extra={
                "agent": "data_validator",
                "catchment_id": catchment_id,
                "data_quality": quality,
            },
        )
    else:
        log.info(
            f"Validation passed: quality={quality:.1%}",
            extra={
                "agent": "data_validator",
                "catchment_id": catchment_id,
                "data_quality": quality,
            },
        )

    return result


def check_data_staleness(
    data_timestamp: float,
    max_age_hours: float = 6.0,
    catchment_id: str = "unknown",
) -> Tuple[bool, float]:
    """
    Check if data is too old to be reliable.
    Returns (is_fresh, age_in_hours).
    """
    age_seconds = time.time() - data_timestamp
    age_hours = age_seconds / 3600

    if age_hours > max_age_hours:
        log.warning(
            f"Data is {age_hours:.1f}h old (max={max_age_hours}h) — STALE",
            extra={
                "agent": "data_validator",
                "catchment_id": catchment_id,
                "latency_ms": int(age_seconds * 1000),
            },
        )
        write_audit_record(
            catchment_id=catchment_id,
            event_type="data_quality_warning",
            data={"age_hours": round(age_hours, 2), "max_allowed": max_age_hours},
            agent="data_validator",
        )
        return False, age_hours

    return True, age_hours


def check_sudden_jump(
    current_value: float,
    previous_value: float,
    feature_name: str,
    max_ratio: float = 5.0,
    catchment_id: str = "unknown",
) -> bool:
    """
    Detects suspicious sudden jumps in feature values between
    consecutive time steps.

    For example, if rainfall_3d goes from 10mm to 500mm in one step,
    that's likely a data error, not a real event.
    """
    if previous_value == 0:
        return True  # can't compute ratio

    ratio = current_value / previous_value

    if ratio > max_ratio:
        log.warning(
            f"{feature_name} jumped {ratio:.1f}x "
            f"({previous_value:.1f} → {current_value:.1f}) — "
            f"possible data error",
            extra={
                "agent": "data_validator",
                "catchment_id": catchment_id,
            },
        )
        return False

    return True
