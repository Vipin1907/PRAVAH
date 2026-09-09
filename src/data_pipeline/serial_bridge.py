#!/usr/bin/env python3
"""
PravahAI — USB Data Cable (Serial) to Dashboard Bridge
Reads live JSON telemetry packets from ESP32 via USB COM Port
and forwards them to the PravahAI Master Backend (:5000) & Gateway (:3000).
"""

import sys
import time
import json
import urllib.request
import urllib.error

# Fix Windows UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] 'pyserial' package is not installed. Run: pip install pyserial")
    sys.exit(1)

TARGET_API_URL = "http://localhost:5000/api/iot-telemetry"
BAUD_RATE = 115200

def find_esp32_port():
    """Auto-detects active COM port connected to ESP32 / USB-Serial chip."""
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    
    print("\n🔍 Available COM Ports on System:")
    for p in ports:
        print(f"   • {p.device}: {p.description} ({p.hwid})")
        # Common ESP32 USB-UART Chips: CP210x, CH340, FTDI, USB Serial
        desc = p.description.lower()
        if any(k in desc for k in ["cp210", "ch340", "ch341", "usb-serial", "uart", "esp32", "silicon labs"]):
            return p.device
            
    # Default to first available port if specific signature not matched
    return ports[0].device

def forward_to_backend(json_str):
    try:
        data = json_str.strip().encode("utf-8")
        req = urllib.request.Request(
            TARGET_API_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            return resp.status, resp.read().decode("utf-8")
    except Exception as ex:
        return None, str(ex)

def main():
    print("=" * 65)
    print("  🔌 PravahAI — USB Data Cable (Serial) Bridge")
    print("=================================================")
    
    port = find_esp32_port()
    if not port:
        print("\n❌ No USB COM Port detected! Please check:")
        print("   1. Is the ESP32 USB cable firmly plugged into your laptop?")
        print("   2. Is the USB Data Cable (not charge-only cable)?")
        sys.exit(1)
        
    print(f"\n✅ Auto-Selected ESP32 Port: {port} at {BAUD_RATE} Baud")
    print(f"📡 Forwarding Target: {TARGET_API_URL}")
    print("-------------------------------------------------")
    print("Streaming live hardware sensor telemetry. Press Ctrl+C to stop.\n")

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
        time.sleep(1.5) # Wait for serial port stabilization
    except Exception as e:
        print(f"❌ Could not open {port}: {e}")
        print("💡 Make sure Arduino IDE Serial Monitor is CLOSED so this script can access the port!")
        sys.exit(1)

    while True:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            # Check if line is valid JSON telemetry
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    status, res = forward_to_backend(line)
                    if status == 200:
                        print(f"[🟢 LIVE HW HTTP {status}] RainADC={payload.get('raw_rain')} | WaterADC={payload.get('raw_water_level')} | SoilADC={payload.get('raw_soil')} | Temp={payload.get('temperature')}°C -> Ingested OK")
                    else:
                        print(f"[⚠️ WARNING] Data read from USB, but server returned: {res}")
                except json.JSONDecodeError:
                    pass
            else:
                # Debug message from ESP32 setup
                if "PravahAI" in line or "Reading" in line:
                    print(f"[ESP32 BOOT] {line}")
        except KeyboardInterrupt:
            print("\n🛑 Stopped Serial Bridge.")
            break
        except Exception as ex:
            print(f"[ERROR] Serial read error: {ex}")
            time.sleep(1)

if __name__ == "__main__":
    main()
