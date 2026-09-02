"""
historical_replay.py — Replays historical flood events through the
multi-agent pipeline to validate the system against known events.

Updated for the new multi-agent architecture with:
  - Structured logging
  - Data quality tracking
  - Multi-level alerts
  - Responsible AI checks
"""

import pandas as pd
import time
from typing import Optional

from flood_alert_agent import app, FloodState
from logger_config import get_agent_logger

log = get_agent_logger("system")


def estimate_risk_from_rainfall(row) -> dict:
    """
    Improved rule-based estimator using real features.

    This serves as the risk estimation when replaying historical
    data through the agent pipeline. The agent's own forecast_agent
    will use this data (with _real_data=True) and apply calibration
    and OOD checks on top.
    """
    r1d = row.get("rainfall_mm", row.get("rainfall_1d", 0))
    r3d = row.get("rainfall_3d", 0)
    r7d = row.get("rainfall_7d", 0)
    r30d = row.get("rainfall_30d", 0)
    soil = row.get("soil_saturation_proxy", 0)
    slope = row.get("slope_mean", 20)
    flow = row.get("flow_accumulation", 1000)
    ndvi = row.get("ndvi", 0.65)

    # weighted score
    score = (
        (min(r3d / 200, 1.0) * 0.30) +
        (min(r7d / 500, 1.0) * 0.15) +
        (soil * 0.25) +
        (min(slope / 45, 1.0) * 0.15) +
        (min(flow / 10000, 1.0) * 0.08) +
        (max(1.0 - ndvi, 0) * 0.07)
    )

    probability = min(round(score, 3), 0.99)

    # lead time inversely related to intensity
    if r3d > 100:
        lead_time = round(2.0 + (200 - min(r3d, 200)) / 100 * 2, 1)
    else:
        lead_time = round(4.0 + (100 - r3d) / 50, 1)

    return {
        "probability": probability,
        "confidence": 0.75,
        "lead_time_hrs": lead_time,
        "top_drivers": ["rainfall_3d", "rainfall_7d", "soil_saturation_proxy",
                        "slope_mean", "flow_accumulation", "ndvi"],
        "driver_importances": {
            "rainfall_3d": min(r3d / 200, 1.0) * 0.30,
            "rainfall_7d": min(r7d / 500, 1.0) * 0.15,
            "soil_saturation_proxy": soil * 0.25,
            "slope_mean": min(slope / 45, 1.0) * 0.15,
            "flow_accumulation": min(flow / 10000, 1.0) * 0.08,
            "ndvi": max(1.0 - ndvi, 0) * 0.07,
        },
    }


def replay_day(
    row,
    catchment_id_override: Optional[str] = None,
    auto_approve: bool = True,
) -> dict:
    """
    Replay a single historical day through the multi-agent pipeline.

    Args:
        row: pandas Series with rainfall/feature data
        catchment_id_override: optional catchment ID override
        auto_approve: if True, auto-approve alerts for batch replay

    Returns:
        Final agent state dict
    """
    risk = estimate_risk_from_rainfall(row)
    cid = catchment_id_override or row.get("grid_cell_id", "unknown")
    thread_id = f"replay-{row.get('date', 'unknown')}-{cid}"

    config = {"configurable": {"thread_id": thread_id}}
    state: FloodState = {
        "catchment_id": cid,
        "_real_data": True,
        "_replay_mode": True,
        "data_source": "historical_replay",
        "rainfall_mm": float(row.get("rainfall_mm", row.get("rainfall_1d", 0))),
        "rainfall_1d": float(row.get("rainfall_1d", row.get("rainfall_mm", 0))),
        "rainfall_3d": float(row.get("rainfall_3d", 0)),
        "rainfall_7d": float(row.get("rainfall_7d", 0)),
        "rainfall_30d": float(row.get("rainfall_30d", 0)),
        "soil_saturation_proxy": float(row.get("soil_saturation_proxy", 0)),
        "ndvi": float(row.get("ndvi", 0.65)),
        "slope_mean": float(row.get("slope_mean", 20)),
        "flow_accumulation": float(row.get("flow_accumulation", 1000)),
        **risk,
    }

    result = app.invoke(state, config=config)

    # if paused for human approval and auto_approve is on
    if auto_approve and result.get("final_status") is None:
        from langgraph.types import Command
        result = app.invoke(Command(resume="approve"), config=config)

    return result


def replay_dataset(
    csv_path: str,
    n_events: int = 10,
    sort_by: str = "rainfall_3d",
    region_name: str = "unknown",
) -> pd.DataFrame:
    """
    Replay top-N highest-risk events from a dataset.

    Returns a DataFrame with results for analysis.
    """
    log.info(
        f"{'═' * 60}",
        extra={"agent": "system"},
    )
    log.info(
        f"Historical Replay: {region_name} — Top {n_events} events",
        extra={"agent": "system"},
    )
    log.info(
        f"{'═' * 60}",
        extra={"agent": "system"},
    )

    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])

    top_events = df.sort_values(sort_by, ascending=False).head(n_events)

    results = []
    for idx, (_, row) in enumerate(top_events.iterrows(), 1):
        log.info(
            f"\n{'─' * 50}",
            extra={"agent": "system"},
        )
        log.info(
            f"Event {idx}/{n_events}: {row['date'].date()} | "
            f"Cell: {row.get('grid_cell_id', 'N/A')} | "
            f"Rain_3d: {row.get('rainfall_3d', 0):.1f}mm",
            extra={"agent": "system"},
        )

        state = replay_day(row)

        results.append({
            "date": row["date"].date(),
            "grid_cell_id": row.get("grid_cell_id", "N/A"),
            "rainfall_3d": row.get("rainfall_3d", 0),
            "rainfall_7d": row.get("rainfall_7d", 0),
            "soil_proxy": row.get("soil_saturation_proxy", 0),
            "probability": state.get("probability", 0),
            "confidence": state.get("confidence", 0),
            "alert_level": state.get("alert_level", "N/A"),
            "final_status": state.get("final_status", "N/A"),
            "data_quality": state.get("data_quality", 0),
        })

    result_df = pd.DataFrame(results)

    # summary
    log.info(
        f"\n{'═' * 60}",
        extra={"agent": "system"},
    )
    log.info(
        f"REPLAY SUMMARY: {region_name}",
        extra={"agent": "system"},
    )
    log.info(
        f"  Total events replayed: {len(results)}",
        extra={"agent": "system"},
    )

    for level_name in ["EXTREME", "RED", "ORANGE", "YELLOW", "GREEN"]:
        count = len(result_df[result_df["alert_level"] == level_name])
        if count > 0:
            log.info(
                f"  {level_name}: {count} events",
                extra={"agent": "system"},
            )

    return result_df


if __name__ == "__main__":
    import os

    print("═" * 60)
    print("  🌊 Historical Replay — Flash Flood Agentic AI")
    print("═" * 60)
    print()

    # check which datasets are available
    uk_path = "data/processed/uttarakhand_full_features_REAL.csv"
    assam_path = "data/processed/assam_full_features_REAL.csv"
    uk_simple = "data/processed/uttarakhand_rainfall_with_proxies.csv"
    assam_simple = "data/processed/assam_rainfall_with_proxies.csv"

    if os.path.exists(uk_path):
        print(f"Found: {uk_path}")
        df_result = replay_dataset(uk_path, n_events=5, region_name="Uttarakhand")
        print("\n" + df_result.to_string(index=False))
    elif os.path.exists(uk_simple):
        print(f"Found: {uk_simple}")
        df_result = replay_dataset(uk_simple, n_events=5, region_name="Uttarakhand")
        print("\n" + df_result.to_string(index=False))
    else:
        print("No Uttarakhand data found. Running with simulated data...")
        # demo mode with mock data
        from flood_alert_agent import app
        from langgraph.types import Command

        config = {"configurable": {"thread_id": "demo-replay-1"}}
        state = {"catchment_id": "catch_demo_001"}
        result = app.invoke(state, config=config)
        print(f"\nResult: {result.get('final_status')}")
        print(f"Alert Level: {result.get('alert_level')}")

        if result.get("final_status") is None:
            print("\nAuto-approving...")
            final = app.invoke(Command(resume="approve"), config=config)
            print(f"Final: {final.get('final_status')}")