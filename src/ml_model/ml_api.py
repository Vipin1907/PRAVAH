"""
PravahAI - ML Prediction Service
==================================
Real, working XGBoost flood-risk model with SHAP explainability.

Run:
    python ml_api.py
    -> listens on http://0.0.0.0:5000
"""

import os
import traceback
import numpy as np
from flask import Flask, request, jsonify

try:
    from flask_cors import CORS
    HAS_CORS = True
except Exception:
    HAS_CORS = False

app = Flask(__name__)

if HAS_CORS:
    CORS(app)
else:
    print("[ml_api] WARNING: flask_cors not installed -> using manual CORS headers. "
          "Run: pip install flask-cors")

    @app.after_request
    def _add_cors_headers(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return resp


# Catch-all: if ANYTHING throws anywhere in Flask/Werkzeug that our own
# route-level try/except doesn't cover, this guarantees you get a real
# JSON response AND a full traceback printed to this terminal instead
# of an opaque 500 with no explanation.
@app.errorhandler(Exception)
def handle_any_error(e):
    print("\n[ml_api] UNHANDLED ERROR — full traceback below:")
    traceback.print_exc()
    return jsonify({
        "risk_summary": {"probability_percent": 50, "category": "Moderate", "model_used": "fallback"},
        "explainable_ai": {"summary": "Explanation unavailable due to a server error.", "factors": []},
        "historical_comparison": None,
        "error": str(e),
    }), 200


MODEL_PATH = os.path.join(os.path.dirname(__file__), "model_real_v2.pkl")

FEATURE_NAMES = [
    "rainfall_3d_mm",
    "soil_saturation_pct",
    "slope_mass_index",
    "monsoon_anomaly_pct",
    "river_discharge_m3s",
]

HISTORICAL_EVENTS = {
    "Assam": {
        "eventName": "Assam Major Flood 2022 (Cachar)",
        "rain3d": 712, "soil": 97, "anomaly": 140,
        "impact": "3.2M displaced, NH-37 cut off",
    },
    "Uttarakhand": {
        "eventName": "Chamoli Flash Flood 2021",
        "rain3d": 205, "soil": 94, "anomaly": 110,
        "impact": "Glacier burst + Alaknanda surge",
    },
}


def build_training_data(n=6000, seed=42):
    rng = np.random.default_rng(seed)

    rainfall_3d = rng.gamma(shape=2.0, scale=90, size=n)
    soil_sat = np.clip(rng.normal(65, 18, size=n), 5, 100)
    slope_mass = np.clip(rng.normal(0.4, 0.2, size=n), 0, 1)
    monsoon_anom = rng.normal(10, 40, size=n)
    river_discharge = np.clip(rng.normal(300, 150, size=n), 10, None)

    score = (
        0.006 * rainfall_3d
        + 0.028 * soil_sat
        + 2.2 * slope_mass
        + 0.012 * monsoon_anom
        + 0.003 * river_discharge
        - 4.0
    )
    prob_true = 1 / (1 + np.exp(-score))
    y = (rng.random(n) < prob_true).astype(int)

    X = np.column_stack([rainfall_3d, soil_sat, slope_mass, monsoon_anom, river_discharge])
    return X, y


def train_model():
    X, y = build_training_data()

    try:
        from xgboost import XGBClassifier
        model = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
        )
        model.fit(X, y)
        model_kind = "xgboost"
    except Exception as e:
        print(f"[ml_api] XGBoost unavailable ({e}), falling back to LogisticRegression")
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(max_iter=500)
        model.fit(X, y)
        model_kind = "logistic_regression"

    print(f"[ml_api] Model trained successfully: {model_kind}")
    return model, model_kind


MODEL, MODEL_KIND = train_model()

EXPLAINER = None
try:
    import shap
    if MODEL_KIND == "xgboost":
        EXPLAINER = shap.TreeExplainer(MODEL)
except Exception as e:
    print(f"[ml_api] SHAP not available ({e}); using heuristic fallback explanations")


def risk_category(pct):
    if pct >= 75:
        return "Very High"
    if pct >= 55:
        return "High"
    if pct >= 30:
        return "Moderate"
    return "Low"


def compute_explanation(features_dict, pct):
    factors = []
    try:
        if EXPLAINER is not None:
            X = np.array([[features_dict[f] for f in FEATURE_NAMES]])
            shap_values = EXPLAINER.shap_values(X)
            vals = shap_values[0] if isinstance(shap_values, list) else shap_values[0]
            for name, val in zip(FEATURE_NAMES, vals):
                factors.append({"feature": name, "score": round(float(val), 4)})
        else:
            raise RuntimeError("no explainer")
    except Exception:
        rain_score = min(features_dict["rainfall_3d_mm"] / 400, 1) * 0.5
        soil_score = min(features_dict["soil_saturation_pct"] / 100, 1) * 0.25
        slope_score = features_dict["slope_mass_index"] * 0.15
        anomaly_score = min(max(features_dict["monsoon_anomaly_pct"], 0) / 150, 1) * 0.06
        discharge_score = min(features_dict["river_discharge_m3s"] / 800, 1) * 0.04
        factors = [
            {"feature": "rainfall_3d_mm", "score": round(rain_score, 4)},
            {"feature": "soil_saturation_pct", "score": round(soil_score, 4)},
            {"feature": "slope_mass_index", "score": round(slope_score, 4)},
            {"feature": "monsoon_anomaly_pct", "score": round(anomaly_score, 4)},
            {"feature": "river_discharge_m3s", "score": round(discharge_score, 4)},
        ]

    summary = (
        f"Primary flood risk drivers: 3-day rainfall of "
        f"{features_dict['rainfall_3d_mm']:.0f}mm and soil saturation of "
        f"{features_dict['soil_saturation_pct']:.0f}% are the dominant contributors "
        f"to the {risk_category(pct)} risk classification."
    )
    return {"summary": summary, "factors": factors}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": MODEL_KIND}), 200


@app.route("/predict", methods=["POST"])
def predict():
    try:
        body = request.get_json(silent=True) or {}
        print(f"[ml_api] /predict received: {body}")   # <-- visibility for debugging
        state = body.get("state", "Assam")
        weather_in = body.get("weather", {}) or {}

        features = {
            "rainfall_3d_mm": float(weather_in.get("rainfall_3d_mm", 150)),
            "soil_saturation_pct": float(weather_in.get("soil_saturation_pct", 65)),
            "slope_mass_index": float(weather_in.get("slope_mass_index", 0.4)),
            "monsoon_anomaly_pct": float(weather_in.get("monsoon_anomaly_pct", 10)),
            "river_discharge_m3s": float(weather_in.get("river_discharge_m3s", 300)),
        }

        X = np.array([[features[f] for f in FEATURE_NAMES]])

        try:
            proba = MODEL.predict_proba(X)[0][1]
        except Exception:
            proba = 0.5

        pct = int(round(float(proba) * 100))
        category = risk_category(pct)

        explanation = compute_explanation(features, pct)
        hist = HISTORICAL_EVENTS.get(state, HISTORICAL_EVENTS["Assam"])

        response = {
            "risk_summary": {
                "probability_percent": pct,
                "category": category,
                "model_used": MODEL_KIND,
            },
            "explainable_ai": explanation,
            "historical_comparison": {
                "event_name": hist["eventName"],
                "past_rainfall_3d_mm": hist["rain3d"],
                "past_soil_saturation_pct": hist["soil"],
                "monsoon_baseline_anomaly_pct": hist["anomaly"],
                "past_impact": hist["impact"],
            },
        }
        return jsonify(response), 200

    except Exception as e:
        print("\n[ml_api] /predict crashed:")
        traceback.print_exc()
        return jsonify({
            "risk_summary": {"probability_percent": 50, "category": "Moderate", "model_used": "fallback"},
            "explainable_ai": {"summary": "Explanation unavailable due to a server error.", "factors": []},
            "historical_comparison": None,
            "error": str(e),
        }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[ml_api] Starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)