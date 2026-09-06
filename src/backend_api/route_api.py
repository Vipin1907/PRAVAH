"""
route_api.py — Safe-route + shelter recommendation service.

Run:
    python route_api.py
    -> listens on http://0.0.0.0:5002
"""

import os
import sys

from flask import Flask, request, jsonify

try:
    from flask_cors import CORS
    HAS_CORS = True
except Exception:
    HAS_CORS = False

routing_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "routing_engine"))
if routing_path not in sys.path:
    sys.path.insert(0, routing_path)

try:
    import routing_pipeline
except ImportError as e:
    routing_pipeline = None
    print(f"[route_api] Could not import routing_pipeline: {e}")

app = Flask(__name__)

if HAS_CORS:
    CORS(app)
else:
    @app.after_request
    def _add_cors_headers(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return resp

# Demo data shaped EXACTLY the way the gateway (SERVER.JS) and frontend
# (setRoutes / setShelters in app.js) expect it.
DEMO_ROUTES = {
    "Assam": {
        "normal": {"name": "Silchar-Guwahati (NH-27)", "dist": "328 km", "time": "7h 20min", "exp": "VERY HIGH", "warn": "NH-27 submerged near Jatinga river crossing."},
        "safe":   {"name": "Silchar-Jiribam-Guwahati (Highland Bypass)", "dist": "412 km", "time": "9h 10min", "exp": "LOW", "warn": "Elevated highland route away from Barak overflow."},
    },
    "Uttarakhand": {
        "normal": {"name": "Chamoli-Rishikesh (NH-58)", "dist": "218 km", "time": "5h 00min", "exp": "HIGH", "warn": "NH-58 blocked near Devprayag riverbank."},
        "safe":   {"name": "Chamoli-Gwaldam-Haridwar (Alt Route)", "dist": "250 km", "time": "6h 30min", "exp": "MODERATE", "warn": "Upper Garhwal alternate - no stream crossing."},
    },
}

DEMO_SHELTERS = {
    "Assam": [
        {"name": "Udharbond Central Relief Shelter", "capacity": "1,200", "dist": "5.4 km", "isHospital": False},
        {"name": "Lakhipur Govt High School Camp", "capacity": "800", "dist": "12.1 km", "isHospital": False},
        {"name": "Cachar District Hospital, Silchar", "capacity": "Civil Hospital", "dist": "18.3 km", "isHospital": True},
    ],
    "Uttarakhand": [
        {"name": "Joshimath Relief Camp", "capacity": "900", "dist": "8.3 km", "isHospital": False},
        {"name": "Chamoli Block Office Shelter", "capacity": "600", "dist": "15.6 km", "isHospital": False},
        {"name": "Base Hospital Srinagar (Garhwal)", "capacity": "Hospital", "dist": "40.0 km", "isHospital": True},
    ],
}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "routing_pipeline_loaded": routing_pipeline is not None}), 200


@app.route("/route", methods=["POST"])
def get_safe_route():
    body = request.get_json(silent=True) or {}
    state = body.get("state", "Assam")

    # NOTE FOR THE TEAM: Ayush's real routing_pipeline.build_routing_for_place()
    # needs (place_name, place_tag, shelter_points) — the simple
    # {state, district, basin} payload from the frontend doesn't provide
    # those yet. Until that's wired up properly, this returns realistic
    # data in the CORRECT shape so the dashboard isn't stuck on null/fake data.
    try:
        routes = DEMO_ROUTES.get(state, DEMO_ROUTES["Assam"])
        shelters = DEMO_SHELTERS.get(state, DEMO_SHELTERS["Assam"])
        return jsonify({
            "status": "success",
            "routes_and_safety": routes,
            "safe_shelters": shelters,
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "routes_and_safety": None,
            "safe_shelters": None,
            "error": str(e),
        }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    print(f"[route_api] Starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)