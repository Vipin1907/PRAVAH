#!/usr/bin/env python3
"""
TriNetra AI — ESP32 Virtual Node Hardware Simulator
Directly sends synthetic sensor ADC readings to backend API (:5000) or Gateway (:3000).
Tests and demonstrates real-time physical calibration into rainfall, river levels & soil moisture.
"""

import sys
import time
import json
import random
import argparse
import urllib.request
import urllib.error

# Fix Windows UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_BACKEND_URL = "http://localhost:5000/api/iot-telemetry"
DEFAULT_GATEWAY_URL = "http://localhost:3000/api/iot/readings"

# -------------------------------------------------------------
# Hardware Scenarios
# -------------------------------------------------------------
SCENARIOS = {
    "1": {
        "name": "Scenario 1: Dry / Normal Baseline",
        "description": "Clear skies, dry soil, low baseline river gauge",
        "rain_range": (3800, 4095),      # High ADC = Dry sensor plate
        "water_range": (150, 450),       # Low ADC = River safely below danger level
        "soil_range": (3400, 3900),      # High ADC = Dry soil
        "temp_range": (26.0, 32.0),
        "hum_range": (45.0, 60.0)
    },
    "2": {
        "name": "Scenario 2: Pre-Monsoon Showers & Soil Saturation",
        "description": "Moderate intermittent rain, wetting soil, rising river channel",
        "rain_range": (1800, 2600),      # Medium ADC = Water droplets on plate
        "water_range": (1200, 1800),     # Moderate river elevation
        "soil_range": (1800, 2400),      # Moist soil
        "temp_range": (24.0, 28.0),
        "hum_range": (70.0, 85.0)
    },
    "3": {
        "name": "Scenario 3: Severe Cloudburst & Imminent Flash Flood",
        "description": "Heavy downpour, fully submerged river probe, 100% saturated soil",
        "rain_range": (400, 1100),       # Low ADC = Heavy sheet flow across sensor
        "water_range": (2600, 3400),     # High ADC = Exceeds danger mark
        "soil_range": (900, 1400),       # High saturation
        "temp_range": (21.0, 24.0),
        "hum_range": (92.0, 99.0)
    }
}

def generate_telemetry(scenario_key):
    sc = SCENARIOS.get(scenario_key, SCENARIOS["3"])
    return {
        "node_id": "ESP32_DEV_K01",
        "raw_rain": random.randint(*sc["rain_range"]),
        "raw_water_level": random.randint(*sc["water_range"]),
        "raw_soil": random.randint(*sc["soil_range"]),
        "temperature": round(random.uniform(*sc["temp_range"]), 1),
        "humidity": round(random.uniform(*sc["hum_range"]), 1),
        "timestamp": int(time.time()),
        "status": "active"
    }

def transmit(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return None, str(e)

def main():
    parser = argparse.ArgumentParser(description="TriNetra AI ESP32 Hardware Simulator")
    parser.add_argument("--url", default=DEFAULT_BACKEND_URL, help="Backend or Gateway URL")
    parser.add_argument("--scenario", default=None, choices=["1", "2", "3"], help="Scenario 1=Dry, 2=Spray, 3=Flash Flood")
    parser.add_argument("--continuous", action="store_true", help="Send stream every 2.5 seconds")
    parser.add_argument("--interval", type=float, default=2.5, help="Interval in seconds for continuous stream")
    args = parser.parse_args()

    print("=" * 60)
    print("  🌊 TriNetra AI — Virtual ESP32 Hardware Telemetry Node")
    print("=" * 60)
    print(f"Target Server Endpoint: {args.url}")

    scenario_choice = args.scenario
    if not scenario_choice:
        print("\nSelect Simulation Scenario:")
        for k, v in SCENARIOS.items():
            print(f"  [{k}] {v['name']} — {v['description']}")
        scenario_choice = input("\nEnter choice (1/2/3) [default 3]: ").strip() or "3"

    print(f"\n🚀 Activated Scenario: {SCENARIOS.get(scenario_choice, SCENARIOS['3'])['name']}")
    
    if args.continuous:
        print(f"Streaming live telemetry every {args.interval}s. Press Ctrl+C to stop.\n")
        while True:
            payload = generate_telemetry_payload(scenario_choice)
            status, res = send_payload(args.url, payload)
            if status:
                print(f"[🟢 SENT {status}] RainADC={payload['raw_rain']} WaterADC={payload['raw_water_level']} SoilADC={payload['raw_soil']} Temp={payload['temperature']}°C -> Response: {res[:80]}")
            else:
                print(f"[🔴 FAILED] Server unreachable at {args.url} ({res})")
            time.sleep(args.interval)
    else:
        payload = generate_telemetry_payload(scenario_choice)
        print("\nPayload to transmit:")
        print(json.dumps(payload, indent=2))
        print("\nTransmitting to server...")
        status, res = send_payload(args.url, payload)
        if status:
            print(f"✅ Success (HTTP {status}): {res}")
        else:
            print(f"⚠️ Note: Server connection failed ({res}). Make sure backend (:5000) or gateway (:3000) is running.")

if __name__ == "__main__":
    main()
