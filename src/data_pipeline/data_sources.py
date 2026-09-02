"""
data_sources.py — Multi-source data ingestion with retry and
automatic fallback.

Data source priority:
  1. IMD Gridded Rainfall (primary, most trusted for India)
  2. NASA GPM IMERG (near real-time, 30-min latency, global)
  3. CHIRPS Daily (higher latency but very reliable)
  4. Last-known-good cache (degraded mode)

Each source returns a standardised FeaturePayload dict that the
rest of the pipeline consumes, regardless of which source provided it.
"""

import os
import time
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from logger_config import get_agent_logger, write_audit_record

log = get_agent_logger("data_ingestion")


# ── Cache for last-known-good data ───────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class FeaturePayload:
    """Standardised data payload from any source."""
    catchment_id: str
    timestamp: float  # unix timestamp of observation
    source: str  # which data source provided this
    is_fallback: bool  # True if not from primary source
    quality_score: float  # 0.0–1.0

    # features
    rainfall_mm: float = 0.0
    rainfall_1d: float = 0.0
    rainfall_3d: float = 0.0
    rainfall_7d: float = 0.0
    rainfall_30d: float = 0.0
    soil_saturation_proxy: float = 0.0
    ndvi: float = 0.65
    slope_mean: float = 20.0
    flow_accumulation: float = 1000.0

    def to_dict(self) -> dict:
        return {
            "catchment_id": self.catchment_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "is_fallback": self.is_fallback,
            "quality_score": self.quality_score,
            "rainfall_mm": self.rainfall_mm,
            "rainfall_1d": self.rainfall_1d,
            "rainfall_3d": self.rainfall_3d,
            "rainfall_7d": self.rainfall_7d,
            "rainfall_30d": self.rainfall_30d,
            "soil_saturation_proxy": self.soil_saturation_proxy,
            "ndvi": self.ndvi,
            "slope_mean": self.slope_mean,
            "flow_accumulation": self.flow_accumulation,
        }


# ── Individual Data Source Fetchers ──────────────────────────────

def fetch_imd_rainfall(catchment_id: str) -> Optional[FeaturePayload]:
    """
    Primary source: IMD gridded rainfall.

    In production, this would call imdlib or an HTTP API.
    For demo, we simulate with realistic randomised data that
    reflects actual Uttarakhand / Assam rainfall patterns.
    """
    try:
        # simulate network latency + occasional failure
        latency = random.uniform(0.1, 0.5)
        time.sleep(latency)

        # 10% chance of failure in demo (shows fallback in action)
        if random.random() < 0.10:
            raise ConnectionError("IMD server timeout (simulated)")

        # generate realistic rainfall for demo
        # Uttarakhand monsoon: avg 15-25mm/day, peaks 80-150mm
        is_monsoon = True  # simplification for demo
        base_rain = random.uniform(5, 30) if is_monsoon else random.uniform(0, 10)
        spike = random.uniform(50, 150) if random.random() < 0.15 else 0

        rainfall_mm = round(base_rain + spike, 1)
        rainfall_3d = round(rainfall_mm * random.uniform(2.0, 3.5), 1)
        rainfall_7d = round(rainfall_3d * random.uniform(1.5, 2.5), 1)
        rainfall_30d = round(rainfall_7d * random.uniform(2.0, 4.0), 1)

        soil_proxy = min(round(rainfall_30d / max(rainfall_30d, 300) * 0.9, 2), 1.0)

        payload = FeaturePayload(
            catchment_id=catchment_id,
            timestamp=time.time(),
            source="IMD_GRIDDED_RAINFALL",
            is_fallback=False,
            quality_score=0.95,
            rainfall_mm=rainfall_mm,
            rainfall_1d=rainfall_mm,
            rainfall_3d=rainfall_3d,
            rainfall_7d=rainfall_7d,
            rainfall_30d=rainfall_30d,
            soil_saturation_proxy=soil_proxy,
        )

        log.info(
            f"IMD data fetched: rain={rainfall_mm}mm, "
            f"3d={rainfall_3d}mm, latency={latency*1000:.0f}ms",
            extra={
                "agent": "data_ingestion",
                "catchment_id": catchment_id,
                "source": "IMD",
                "latency_ms": int(latency * 1000),
            },
        )

        # cache as last-known-good
        _save_to_cache(catchment_id, payload)

        return payload

    except Exception as e:
        log.warning(
            f"IMD fetch failed: {e}",
            extra={
                "agent": "data_ingestion",
                "catchment_id": catchment_id,
                "source": "IMD",
            },
        )
        return None


def fetch_gpm_imerg(catchment_id: str) -> Optional[FeaturePayload]:
    """
    Fallback 1: NASA GPM IMERG near-real-time.
    ~30 min latency, 0.1° resolution, global coverage.

    In production: use the NASA GES DISC API.
    For demo: simulated with slightly noisier data.
    """
    try:
        latency = random.uniform(0.2, 0.8)
        time.sleep(latency)

        if random.random() < 0.05:  # 5% failure rate
            raise ConnectionError("GPM IMERG API unavailable (simulated)")

        rainfall_mm = round(random.uniform(5, 120), 1)
        rainfall_3d = round(rainfall_mm * random.uniform(2.0, 3.0), 1)
        rainfall_7d = round(rainfall_3d * random.uniform(1.5, 2.2), 1)

        payload = FeaturePayload(
            catchment_id=catchment_id,
            timestamp=time.time(),
            source="NASA_GPM_IMERG",
            is_fallback=True,
            quality_score=0.82,  # slightly lower than IMD for India
            rainfall_mm=rainfall_mm,
            rainfall_1d=rainfall_mm,
            rainfall_3d=rainfall_3d,
            rainfall_7d=rainfall_7d,
            rainfall_30d=round(rainfall_7d * 2.5, 1),
            soil_saturation_proxy=min(round(rainfall_7d / 400, 2), 1.0),
        )

        log.info(
            f"GPM IMERG fallback: rain={rainfall_mm}mm, "
            f"quality=0.82, latency={latency*1000:.0f}ms",
            extra={
                "agent": "data_ingestion",
                "catchment_id": catchment_id,
                "source": "GPM_IMERG",
                "latency_ms": int(latency * 1000),
            },
        )

        _save_to_cache(catchment_id, payload)
        return payload

    except Exception as e:
        log.warning(
            f"GPM IMERG fetch failed: {e}",
            extra={
                "agent": "data_ingestion",
                "catchment_id": catchment_id,
                "source": "GPM_IMERG",
            },
        )
        return None


def fetch_chirps_daily(catchment_id: str) -> Optional[FeaturePayload]:
    """
    Fallback 2: CHIRPS daily rainfall.
    Higher latency (~1 day) but very reliable historical coverage.
    """
    try:
        latency = random.uniform(0.3, 1.0)
        time.sleep(latency)

        rainfall_mm = round(random.uniform(3, 80), 1)

        payload = FeaturePayload(
            catchment_id=catchment_id,
            timestamp=time.time() - 86400,  # 1 day old
            source="CHIRPS_DAILY",
            is_fallback=True,
            quality_score=0.70,  # lower due to latency
            rainfall_mm=rainfall_mm,
            rainfall_1d=rainfall_mm,
            rainfall_3d=round(rainfall_mm * 2.5, 1),
            rainfall_7d=round(rainfall_mm * 5.0, 1),
            rainfall_30d=round(rainfall_mm * 15.0, 1),
            soil_saturation_proxy=min(round(rainfall_mm * 5 / 500, 2), 1.0),
        )

        log.info(
            f"CHIRPS fallback: rain={rainfall_mm}mm, quality=0.70 (1-day lag)",
            extra={
                "agent": "data_ingestion",
                "catchment_id": catchment_id,
                "source": "CHIRPS",
            },
        )

        _save_to_cache(catchment_id, payload)
        return payload

    except Exception as e:
        log.warning(f"CHIRPS fetch failed: {e}")
        return None


def _load_from_cache(catchment_id: str) -> Optional[FeaturePayload]:
    """Last resort: load last-known-good data from local cache."""
    cache_path = os.path.join(CACHE_DIR, f"{catchment_id}.json")
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, "r") as f:
            data = json.load(f)

        payload = FeaturePayload(**data)
        payload.source = f"CACHE({payload.source})"
        payload.is_fallback = True
        payload.quality_score = max(payload.quality_score - 0.3, 0.3)

        log.warning(
            f"Using CACHED data (last-known-good) — degraded mode",
            extra={
                "agent": "data_ingestion",
                "catchment_id": catchment_id,
                "source": "CACHE",
            },
        )

        return payload
    except Exception:
        return None


def _save_to_cache(catchment_id: str, payload: FeaturePayload) -> None:
    """Save successful fetch to cache for future fallback."""
    cache_path = os.path.join(CACHE_DIR, f"{catchment_id}.json")
    with open(cache_path, "w") as f:
        json.dump(payload.to_dict(), f, default=str)


# ── Main Fetch with Automatic Fallback ───────────────────────────

# ordered by priority — try each one until one succeeds
DATA_SOURCES = [
    ("IMD_GRIDDED", fetch_imd_rainfall),
    ("NASA_GPM_IMERG", fetch_gpm_imerg),
    ("CHIRPS_DAILY", fetch_chirps_daily),
]


def fetch_catchment_data(
    catchment_id: str,
    terrain_data: Optional[Dict] = None,
) -> FeaturePayload:
    """
    Fetch data for a catchment with automatic fallback.

    Tries sources in priority order:
      1. IMD → 2. GPM → 3. CHIRPS → 4. Cache

    Always returns a FeaturePayload (never None).
    If all sources fail, returns cached data or a degraded payload.
    """
    for source_name, fetcher in DATA_SOURCES:
        payload = fetcher(catchment_id)
        if payload is not None:
            if payload.is_fallback:
                write_audit_record(
                    catchment_id=catchment_id,
                    event_type="fallback_activated",
                    data={"source": source_name, "quality": payload.quality_score},
                    agent="data_ingestion",
                )
            # inject terrain data if provided
            if terrain_data:
                payload.slope_mean = terrain_data.get("slope_mean", payload.slope_mean)
                payload.flow_accumulation = terrain_data.get(
                    "flow_accumulation", payload.flow_accumulation
                )
                payload.ndvi = terrain_data.get("ndvi", payload.ndvi)
            return payload

    # all sources failed — try cache
    cached = _load_from_cache(catchment_id)
    if cached is not None:
        write_audit_record(
            catchment_id=catchment_id,
            event_type="all_sources_failed_using_cache",
            data={"cache_quality": cached.quality_score},
            agent="data_ingestion",
        )
        return cached

    # absolute last resort — degraded payload with zero rainfall
    log.error(
        "ALL DATA SOURCES FAILED — returning degraded zero payload",
        extra={
            "agent": "data_ingestion",
            "catchment_id": catchment_id,
            "data_quality": 0.1,
        },
    )

    write_audit_record(
        catchment_id=catchment_id,
        event_type="complete_data_failure",
        data={"all_sources": [s[0] for s in DATA_SOURCES]},
        agent="data_ingestion",
    )

    return FeaturePayload(
        catchment_id=catchment_id,
        timestamp=time.time(),
        source="DEGRADED_ZERO",
        is_fallback=True,
        quality_score=0.1,
    )
