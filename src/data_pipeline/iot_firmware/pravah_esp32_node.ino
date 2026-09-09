/*
 * PravahAI — ESP32 Cyber-Physical Hydrological Sensing Node
 * 
 * Hardware Bill of Materials & Pin Configuration:
 * - Raindrop Sensor AO   -> GPIO 34 (ADC1_CH6)
 * - Water Level Probe S  -> GPIO 35 (ADC1_CH7)
 * - Soil Moisture AO     -> GPIO 32 (ADC1_CH4)
 * - DHT11 Data Pin       -> GPIO 4  (Digital I/O)
 * - Status LED           -> GPIO 2  (Built-in LED)
 * 
 * Function:
 * Reads physical analog/digital sensors every 2-3 seconds, builds JSON payload,
 * and transmits via HTTP POST to the PravahAI Gateway / Master Backend.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// ==========================================
// 1. Wi-Fi & Backend Server Configuration
// ==========================================
const char* ssid = "YOUR_WIFI_SSID";           // Replace with your Wi-Fi SSID / Mobile Hotspot
const char* password = "YOUR_WIFI_PASSWORD";   // Replace with your Wi-Fi Password

// URL to PravahAI Express Gateway or Python Master Backend
// Example: "http://192.168.1.100:3000/api/iot/readings" or "http://192.168.1.100:5000/api/iot-telemetry"
const char* serverUrl = "http://192.168.1.100:5000/api/iot-telemetry";

// ==========================================
// 2. Pin Assignments
// ==========================================
#define PIN_RAIN_SENSOR       34  // ADC1
#define PIN_WATER_LEVEL       35  // ADC1
#define PIN_SOIL_MOISTURE     32  // ADC1
#define PIN_DHT               4   // Digital
#define PIN_STATUS_LED        2   // Builtin LED

#define DHTTYPE DHT11             // Set to DHT22 if using white sensor
DHT dht(PIN_DHT, DHTTYPE);

// Sampling Configuration
const unsigned long TRANSMIT_INTERVAL_MS = 2500; // 2.5 seconds
unsigned long lastTransmitTime = 0;

// Device Metadata
const char* DEVICE_ID = "ESP32_DEMO_01";
const char* LOCATION_NAME = "Subansiri River Basin";
const char* STATE_NAME = "Assam";
const char* DISTRICT_NAME = "Dhemaji";
const char* BASIN_CODE = "A011";

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  // Configure ADC attenuation (0 - 3.3V range)
  analogReadResolution(12); // 12-bit resolution: 0 - 4095
  analogSetAttenuation(ADC_11db);

  dht.begin();

  Serial.println("\n==========================================");
  Serial.println("  🌊 PravahAI ESP32 IoT Node Initializing  ");
  Serial.println("==========================================");

  // Connect to Wi-Fi
  connectWiFi();
}

void loop() {
  // Ensure Wi-Fi stays connected
  if (WiFi.status() != WL_CONNECTED) {
    digitalWrite(PIN_STATUS_LED, LOW);
    connectWiFi();
  }

  unsigned long currentMillis = millis();
  if (currentMillis - lastTransmitTime >= TRANSMIT_INTERVAL_MS) {
    lastTransmitTime = currentMillis;
    readAndTransmitTelemetry();
  }
}

void connectWiFi() {
  Serial.printf("[WiFi] Connecting to %s...", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.printf("[WiFi] ESP32 IP Address: %s\n", WiFi.localIP().toString().c_str());
    digitalWrite(PIN_STATUS_LED, HIGH);
  } else {
    Serial.println("\n[WiFi] Connection failed. Will retry in main loop.");
  }
}

void readAndTransmitTelemetry() {
  // Read Raw Analog Sensors (0 - 4095)
  // Raindrop sensor: Dry ≈ 4095, Wet/Submerged ≈ 400-800
  int rawRain = analogRead(PIN_RAIN_SENSOR);

  // Water level probe: Dry/Air ≈ 0-300, Submerged in water ≈ 2500-3600
  int rawWater = analogRead(PIN_WATER_LEVEL);

  // Soil moisture sensor: Dry soil ≈ 3500-4095, Saturated soil ≈ 800-1500
  int rawSoil = analogRead(PIN_SOIL_MOISTURE);

  // Read DHT11 Temperature & Humidity
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  // Fallback defaults if DHT reading fails
  if (isnan(temperature)) temperature = 27.5;
  if (isnan(humidity)) humidity = 78.0;

  // Build JSON Payload
  char jsonPayload[512];
  snprintf(jsonPayload, sizeof(jsonPayload),
    "{"
      "\"device_id\":\"%s\","
      "\"location\":\"%s\","
      "\"state\":\"%s\","
      "\"district\":\"%s\","
      "\"basin\":\"%s\","
      "\"raw_rain\":%d,"
      "\"raw_water_level\":%d,"
      "\"raw_soil\":%d,"
      "\"temperature\":%.2f,"
      "\"humidity\":%.2f,"
      "\"demo_mode\":false"
    "}",
    DEVICE_ID, LOCATION_NAME, STATE_NAME, DISTRICT_NAME, BASIN_CODE,
    rawRain, rawWater, rawSoil, temperature, humidity
  );

  Serial.println("\n[IoT Telemetry] Transmitting Sensor Packet:");
  Serial.println(jsonPayload);

  // Blink LED to indicate transmission
  digitalWrite(PIN_STATUS_LED, LOW);
  
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    int httpResponseCode = http.POST(jsonPayload);

    if (httpResponseCode > 0) {
      Serial.printf("[HTTP] POST Success! Response Code: %d\n", httpResponseCode);
      String response = http.getString();
      Serial.printf("[HTTP] Server Response: %s\n", response.c_str());
    } else {
      Serial.printf("[HTTP] POST Error! Code: %d, Error: %s\n", httpResponseCode, http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  } else {
    Serial.println("[HTTP] Cannot POST: Wi-Fi disconnected");
  }

  digitalWrite(PIN_STATUS_LED, HIGH);
}
