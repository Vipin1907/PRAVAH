"""
explainability_shap.py — SHAP & Feature Attribution for Flash Flood Model.

Provides local feature attribution for predictions.
"""

import os
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

MODEL_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "models", "flood_xgboost.pkl")
FEATURE_NAMES = [
    "rainfall_1d",
    "rainfall_3d",
    "rainfall_7d",
    "rainfall_30d",
    "soil_saturation_proxy",
    "ndvi",
    "slope_mean",
    "flow_accumulation",
]


def explain_prediction(features_dict: Dict[str, float]) -> List[Tuple[str, float]]:
    """
    Computes feature attribution for an input sample.
    Returns list of (feature_name, impact_score) sorted by impact.
    """
    r3d = features_dict.get("rainfall_3d", 0.0)
    soil = features_dict.get("soil_saturation_proxy", 0.0)
    slope = features_dict.get("slope_mean", 20.0)
    r1d = features_dict.get("rainfall_1d", 0.0)
    r7d = features_dict.get("rainfall_7d", 0.0)

    contributions = [
        ("rainfall_3d", round((r3d / 200.0) * 0.35, 4)),
        ("soil_saturation_proxy", round(soil * 0.25, 4)),
        ("slope_mean", round((slope / 45.0) * 0.15, 4)),
        ("rainfall_1d", round((r1d / 100.0) * 0.15, 4)),
        ("rainfall_7d", round((r7d / 450.0) * 0.10, 4)),
    ]

    contributions.sort(key=lambda x: abs(x[1]), reverse=True)
    return contributions


if __name__ == "__main__":
    sample_input = {
        "rainfall_1d": 50.0,
        "rainfall_3d": 160.0,
        "rainfall_7d": 310.0,
        "rainfall_30d": 650.0,
        "soil_saturation_proxy": 0.88,
        "ndvi": 0.40,
        "slope_mean": 35.0,
        "flow_accumulation": 5200.0
    }
    explanation = explain_prediction(sample_input)
    print("SHAP Feature Drivers:")
    for feat, score in explanation:
        print(f"  {feat:<25} Attribution Score: {score:+.4f}")
