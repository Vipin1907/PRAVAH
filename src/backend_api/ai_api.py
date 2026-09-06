"""
ai_api.py — Agentic AI Explainability & Alert-Decision Service
================================================================
Wraps flood_alert_agent's LangGraph multi-agent pipeline behind an
HTTP endpoint that the Node.js gateway (SERVER.JS) calls.

Run:
    python ai_api.py
    -> listens on http://0.0.0.0:5001
"""

import os
import sys
import traceback

from flask import Flask, request, jsonify

try:
    from flask_cors import CORS
    HAS_CORS = True
except Exception:
    HAS_CORS = False

pipeline_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data_pipeline"))
if pipeline_path not in sys.path:
    sys.path.insert(0, pipeline_path)

from langgraph.types import Command
from flood_alert_agent import app as agent_app

app = Flask(__name__)

if HAS_CORS:
    CORS(app)
else:
    # flask_cors missing on this machine -> add CORS headers manually
    # so the service still works instead of silently breaking.
    @app.after_request
    def _add_cors_headers(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return resp


def resolve_catchment_id(body: dict) -> str:
    """
    IMPORTANT: The frontend/gateway sends {state, district, basin, ...}
    — it never sends a raw 'catchment_id'. The agent graph REQUIRES
    catchment_id, so we build one ourselves here. This is the fix for
    the KeyError('catchment_id') crash that was causing the 500.
    """
    if body.get("catchment_id"):
        return str(body["catchment_id"])
    if body.get("basin"):
        return str(body["basin"])
    state = body.get("state", "unknown")
    district = body.get("district", "unknown")
    return f"{state}_{district}".replace(" ", "_")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/explain", methods=["POST"])
def get_ai_explanation():
    body = request.get_json(silent=True) or {}
    catchment_id = resolve_catchment_id(body)

    try:
        initial_state = {"catchment_id": catchment_id}
        thread_id = f"api-run-{catchment_id}"
        config = {"configurable": {"thread_id": thread_id}}

        result = agent_app.invoke(initial_state, config=config)

        # Non-EXTREME alerts pause for human approval (LangGraph
        # "interrupt") -> final_status stays None. For the API demo
        # we auto-approve so the caller always gets a final result.
        if result.get("final_status") is None:
            result = agent_app.invoke(Command(resume="approve"), config=config)

        factors = [
            {"feature": k, "score": round(float(v), 4)}
            for k, v in (result.get("driver_importances") or {}).items()
        ]

        return jsonify({
            "status": "success",
            "catchment_id": catchment_id,
            "alert_level": result.get("alert_level"),
            # <-- THIS is the key SERVER.JS actually reads (explain.explainable_ai)
            "explainable_ai": {
                "summary": result.get("explanation") or "No explanation generated for this risk level.",
                "factors": factors,
            },
            "probability": result.get("probability"),
            "confidence": result.get("confidence"),
        }), 200

    except Exception as e:
        print(f"\n[ai_api] /explain crashed for catchment_id={catchment_id}:")
        traceback.print_exc()
        # Never hard-fail the caller — return a safe fallback instead.
        return jsonify({
            "status": "error",
            "catchment_id": catchment_id,
            "alert_level": None,
            "explainable_ai": {
                "summary": "Explanation unavailable due to a server error.",
                "factors": [],
            },
            "probability": None,
            "confidence": None,
            "error": str(e),
        }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"[ai_api] Starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)