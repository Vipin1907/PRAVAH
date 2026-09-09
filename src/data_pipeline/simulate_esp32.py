#!/usr/bin/env python3
"""
PravahAI — ESP32 Virtual Node Hardware Simulator
Simulates real ESP32 micro-controller hydro-physical telemetry over HTTP POST.
Allows instant testing of dry baseline, rain spray, and flash flood scenarios.
"""

import time
import json
import random
import argparse
import sys
import urllib.request
import urllib.error

# Fix Windows console UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_BACKEND_URL = "http://localhost:5000/api/iot-telemetry"
DEFAULT_GATEWAY_URL = "http://localhost:3000/api/iot/readings"

SCENARIOS = {
    "1": {
        "name": "Dry Baseline (Safe/Low Risk)",
        "description": "Rain sensor completely dry, river gauge at safe baseline, dry soil",
        "raw_rain": (3800, 4095),      # Dry ADC
        "raw_water_level": (200, 450), # Out of water
        "raw_soil": (3600, 4000),      # Dry soil
        "temp": (28.0, 31.0),
        "humidity": (50.0, 65.0)
    },
    "2": {
        "name": "Rain Spray / Moderate Surge (Medium Risk)",
        "description": "Mist/Water spray on raindrop sensor, steady river flow, moist soil",
        "raw_rain": (1200, 1800),      # Partially wet
        "raw_water_level": (1500, 2200),# Moderate depth
        "raw_soil": (1800, 2400),      # Moist soil
        "temp": (25.0, 27.0),
        "humidity": (80.0, 88.0)
    },
    "3": {
        "name": "Extreme Flash Flood (Very High / Danger Alert)",
        "description": "Rain sensor submerged/soaked, river probe submerged (+0.45m above danger), 95% saturated soil",
        "raw_rain": (350, 600),        # Heavily soaked ADC
        "raw_water_level": (3300, 3800),# High water submersion
        "raw_soil": (400, 800),        # Liquid saturated soil
        "temp": (23.5, 25.5),
        "humidity": (92.0, 98.0)
    }
}

def generate_telemetry_payload(scenario_key="1"):
    sc = SCENARIOS.get(str(scenario_key), SCENARIOS["1"])
    raw_rain = random.randint(sc["raw_rain"][0], sc["raw_rain"][1])
    raw_water = random.randint(sc["raw_water_level"][0], sc["raw_water_level"][1])
    raw_soil = random.randint(sc["raw_soil"][0], sc["raw_soil"][1])
    temp = round(random.uniform(sc["temp"][0], sc["temp"][1]), 1)
    humidity = round(random.uniform(sc["humidity"][0], sc["humidity"][1]), 1)

    payload = {
        "device_id": "ESP32_DEMO_01",
        "location": "Subansiri River Gauge Node",
        "state": "Assam",
        "district": "Dhemaji",
        "basin": "A011",
        "raw_rain": raw_rain,
        "raw_water_level": raw_water,
        "raw_soil": raw_soil,
        "temperature": temp,
        "humidity": humidity,
        "demo_mode": True,
        "scenario_name": sc["name"]
    }
    return payload

def send_payload(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            return status, body
    except urllib.error.URLError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)

def main():
    parser = argparse.ArgumentParser(description="PravahAI ESP32 Hardware Simulator")
    parser.add_argument("--url", default=DEFAULT_BACKEND_URL, help="Backend or Gateway URL")
    parser.add_argument("--scenario", default=None, choices=["1", "2", "3"], help="Scenario 1=Dry, 2=Spray, 3=Flash Flood")
    parser.add_argument("--continuous", action="store_true", help="Send stream every 2.5 seconds")
    parser.add_argument("--interval", type=float, default=2.5, help="Interval in seconds for continuous stream")
    args = parser.parse_args()

    print("=" * 60)
    print("  🌊 PravahAI — Virtual ESP32 Hardware Telemetry Node")
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
