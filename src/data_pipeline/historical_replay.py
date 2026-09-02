import pandas as pd
from flood_alert_agent import app


def estimate_risk_from_rainfall(row) -> dict:
    """
    Simple rule-based stand-in for Vipin's model, using real data we
    already have. NOT the final model -- swap for model.predict() once
    Vipin's model is ready.
    """
    r3d = row.get("rainfall_3d", 0)
    r7d = row.get("rainfall_7d", 0)
    soil = row.get("soil_saturation_proxy", 0)

    raw_score = (r3d / 150) * 0.5 + (r7d / 300) * 0.3 + soil * 0.2
    probability = min(round(raw_score, 2), 0.99)
    confidence = 0.75

    return {
        "probability": probability,
        "confidence": confidence,
        "lead_time_hrs": 4.0,
        "top_drivers": ["rainfall_3d", "rainfall_7d", "soil_saturation_proxy"],
    }


def replay_day(row, catchment_id_override=None):
    risk = estimate_risk_from_rainfall(row)
    config = {"configurable": {"thread_id": f"replay-{row['date']}-{row['grid_cell_id']}"}}
    state = {
        "catchment_id": catchment_id_override or row["grid_cell_id"],
        "threshold": 0.6,
        "min_conf": 0.6,
        "_real_data": True,
        **risk,
    }
    result = app.invoke(state, config=config)
    return result


if __name__ == "__main__":
    df = pd.read_csv("data/processed/uttarakhand_rainfall_with_proxies.csv")
    df["date"] = pd.to_datetime(df["date"])

    top_events = df.sort_values("rainfall_3d", ascending=False).head(5)

    print("=== Top 5 highest-rainfall days in the dataset (replay candidates) ===\n")
    for _, row in top_events.iterrows():
        state = replay_day(row)
        print(f"Date: {row['date'].date()}  Cell: {row['grid_cell_id']}")
        print(f"  rainfall_3d={row['rainfall_3d']:.1f}mm, rainfall_7d={row['rainfall_7d']:.1f}mm, "
              f"soil_proxy={row['soil_saturation_proxy']:.2f}")
        print(f"  -> estimated probability={state['probability']}, "
              f"confidence={state['confidence']}, status={state.get('final_status', 'PENDING_APPROVAL (paused)')}")
        print()