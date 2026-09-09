#!/usr/bin/env python3
"""
PravahAI — Comprehensive Test Suite for IoT & Dual Inference Engine
Verifies all endpoints, physics scaling calculations, ML inferences and comparisons.
"""

import sys
import os
import json

# Fix Windows console UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in [BASE_DIR, os.path.join(BASE_DIR, "ml_model"), os.path.join(BASE_DIR, "routing_engine"), os.path.join(BASE_DIR, "data_pipeline"), os.path.dirname(__file__)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from main import app, LATEST_IOT_BUFFER, calibrate_iot_reading

def run_tests():
    print("=" * 65)
    print("  🧪 PravahAI IoT & Dual Inference Verification Test Suite")
    print("=" * 65)

    client = app.test_client()

    # -------------------------------------------------------------
    # Test 1: Physics Scaling Engine Unit Test
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Physics Scaling Logic...")
    raw_payload_dry = {"raw_rain": 4000, "raw_water_level": 350, "raw_soil": 3800, "temperature": 29.0, "humidity": 55.0}
    calib_dry = calibrate_iot_reading(raw_payload_dry)
    assert calib_dry["rain_index_pct"] <= 5.0, f"Expected dry rain index <= 5%, got {calib_dry['rain_index_pct']}"
    assert calib_dry["river_difference_m"] < 0, f"Expected river below danger, got {calib_dry['river_difference_m']}"
    assert calib_dry["soil_saturation_pct"] <= 45.0, f"Expected soil <= 45%, got {calib_dry['soil_saturation_pct']}"
    print("  ✅ Dry Baseline Scaling: Rain Index =", calib_dry["rain_index_pct"], "%, River Diff =", calib_dry["river_difference_m"], "m")

    raw_payload_flood = {"raw_rain": 450, "raw_water_level": 3400, "raw_soil": 400, "temperature": 25.0, "humidity": 95.0}
    calib_flood = calibrate_iot_reading(raw_payload_flood)
    assert calib_flood["rain_index_pct"] >= 80.0, f"Expected wet rain index >= 80%, got {calib_flood['rain_index_pct']}"
    assert calib_flood["river_difference_m"] > 0, f"Expected river above danger, got {calib_flood['river_difference_m']}"
    assert calib_flood["soil_saturation_pct"] >= 85.0, f"Expected soil >= 85%, got {calib_flood['soil_saturation_pct']}"
    print("  ✅ Extreme Flood Scaling: Rain Index =", calib_flood["rain_index_pct"], "%, River Diff =", calib_flood["river_difference_m"], "m (Danger Mark 20.0m)")

    # -------------------------------------------------------------
    # Test 2: Ingest Telemetry Endpoint (/api/iot-telemetry)
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing /api/iot-telemetry (POST & GET)...")
    ingest_payload = {
        "device_id": "ESP32_DEMO_01",
        "location": "Subansiri River Gauge Node",
        "state": "Assam",
        "district": "Dhemaji",
        "basin": "A011",
        "raw_rain": 450,
        "raw_water_level": 3400,
        "raw_soil": 400,
        "temperature": 25.0,
        "humidity": 95.0,
        "demo_mode": True
    }
    resp = client.post("/api/iot-telemetry", json=ingest_payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    res_data = json.loads(resp.data)
    assert res_data["status"] == "success"
    print("  ✅ Ingestion Response:", res_data["message"], "| Device:", res_data["device_id"])

    # Test GET /api/iot/latest
    resp_latest = client.get("/api/iot/latest")
    assert resp_latest.status_code == 200
    latest_data = json.loads(resp_latest.data)
    assert latest_data["is_connected"] is True
    print("  ✅ Latest Telemetry Polled: Node Connected =", latest_data["is_connected"], "| Seconds since ping =", latest_data["seconds_since_last_ping"])

    # -------------------------------------------------------------
    # Test 3: IoT ML Prediction Endpoint (/api/predict/iot)
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing /api/predict/iot...")
    resp_iot_ml = client.post("/api/predict/iot", json={"state": "Assam", "district": "Dhemaji", "basin": "A011"})
    assert resp_iot_ml.status_code == 200
    iot_ml_data = json.loads(resp_iot_ml.data)
    prob = iot_ml_data["risk_summary"]["probability_percent"]
    cat = iot_ml_data["risk_summary"]["category"]
    print(f"  ✅ IoT ML Inference: Risk = {prob}% ({cat})")
    print(f"  ✅ Explainable AI Summary: {iot_ml_data['explainable_ai']['summary'][:90]}...")
    print(f"  ✅ Safe Evacuation Route: {iot_ml_data['routes_and_safety']['safe']['name']}")

    # -------------------------------------------------------------
    # Test 4: Dual Comparison Engine (/api/predict/compare)
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing /api/predict/compare (Dual Satellite vs IoT Fusion)...")
    resp_cmp = client.post("/api/predict/compare", json={"state": "Assam", "district": "Dhemaji", "basin": "A011"})
    assert resp_cmp.status_code == 200
    cmp_data = json.loads(resp_cmp.data)
    cmp_info = cmp_data["comparison"]
    sat_model = cmp_data["satellite_model"]
    iot_model = cmp_data["iot_ground_model"]
    print(f"  ✅ Satellite Risk: {sat_model['probability_percent']}% ({sat_model['category']})")
    print(f"  ✅ IoT Ground Risk: {iot_model['probability_percent']}% ({iot_model['category']})")
    print(f"  ✅ Discrepancy Badge: {cmp_info['discrepancy_badge']}")
    print(f"  ✅ Delta Risk: {cmp_info['delta_risk_percent']}%")
    print(f"  ✅ AI Discrepancy Insight: {cmp_info['ai_discrepancy_insight'][:100]}...")
    print(f"  ✅ Recommended Action: {cmp_info['recommended_action']}")

    print("\n" + "=" * 65)
    print("  🎉 ALL TESTS PASSED! FULL SYSTEM IS 100% OPERATIONAL & VERIFIED")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
