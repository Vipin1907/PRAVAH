/*
 * =====================================================================
 * TriNetra AI — ESP32 Cyber-Physical Wi-Fi Node
 * =====================================================================
 * 
 * Works over Wi-Fi (No USB Serial connection needed for data)
 * Uses Custom API to write to SQLite Database
 * 
 * 🔌 SENSOR & OUTPUT WIRING:
 * -------------------------------------------------------------
 * [Inputs]
 * 1. Raindrop Sensor Module: AO -> GPIO 34
 * 2. Water Level Sensor Probe: S -> GPIO 35
 * 3. Soil Moisture Sensor: AO -> GPIO 32
 * 4. DHT11 Temp & Humidity: OUT -> GPIO 4
 * 
 * [Outputs - Warning Indicators]
 * 5. GREEN LED   -> GPIO 25 (Normal State)
 * 6. YELLOW LED  -> GPIO 26 (Warning / Alert)
 * 7. RED LED     -> GPIO 27 (Danger / Flood)
 * 8. BUZZER      -> GPIO 14 (Evacuation Alarm)
 * =====================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h> // Ensure you have ArduinoJson library installed

// ==========================================
// 1. WI-FI CONFIGURATION
// ==========================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Replace with your Laptop's Local IP Address (e.g., 192.168.1.5)
const char* SERVER_IP = "192.168.1.100";
const int SERVER_PORT = 5000;

// ==========================================
// 2. PIN CONFIGURATION
// ==========================================
#define PIN_RAIN_SENSOR       34   
#define PIN_WATER_LEVEL       35   
#define PIN_SOIL_MOISTURE     32   
#define PIN_DHT               4    
#define PIN_STATUS_LED        2    

#define PIN_LED_GREEN         25
#define PIN_LED_YELLOW        26
#define PIN_LED_RED           27
#define PIN_BUZZER            14

#define DHTTYPE DHT11              
DHT dht(PIN_DHT, DHTTYPE);

const unsigned long TRANSMIT_INTERVAL_MS = 5000; // 5 seconds
unsigned long lastTransmitTime = 0;

// Device Metadata
const char* DEVICE_ID = "ESP32_WIFI_NODE_01";
const char* LOCATION_NAME = "Subansiri River Basin Gauge Node";
const char* STATE_NAME = "Assam";
const char* DISTRICT_NAME = "Dhemaji";
const char* BASIN_CODE = "A011";

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Initialize Input/Output Pins
  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Turn off all indicators initially
  digitalWrite(PIN_STATUS_LED, LOW);
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); 
  dht.begin();

  Serial.println("\n=======================================================");
  Serial.println("  🌊 TriNetra AI — ESP32 Wi-Fi Node Starting...");
  Serial.println("=======================================================");

  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ Wi-Fi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  unsigned long currentMillis = millis();
  
  // Transmit Data and Fetch Risk
  if (currentMillis - lastTransmitTime >= TRANSMIT_INTERVAL_MS) {
    lastTransmitTime = currentMillis;
    if(WiFi.status() == WL_CONNECTED){
      readAndTransmitTelemetry();
      fetchRiskAndSetAlarms();
    } else {
      Serial.println("⚠️ Wi-Fi Disconnected. Reconnecting...");
      WiFi.reconnect();
    }
  }
}

void updateIndicatorsByRisk(int riskPct) {
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  if (riskPct >= 95) {
    digitalWrite(PIN_LED_RED, HIGH);
    digitalWrite(PIN_BUZZER, HIGH); 
  }
  else if (riskPct >= 80) {
    digitalWrite(PIN_LED_RED, HIGH);
  }
  else if (riskPct >= 40) {
    digitalWrite(PIN_LED_YELLOW, HIGH);
  } 
  else {
    digitalWrite(PIN_LED_GREEN, HIGH);
  }
}

void fetchRiskAndSetAlarms() {
  HTTPClient http;
  String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + "/predict";
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  
  String payload = "{\"state\":\"" + String(STATE_NAME) + "\", \"district\":\"" + String(DISTRICT_NAME) + "\", \"basin\":\"" + String(BASIN_CODE) + "\"}";
  int httpResponseCode = http.POST(payload);

  if (httpResponseCode > 0) {
    String response = http.getString();
    
    // Parse JSON
    StaticJsonDocument<1024> doc;
    DeserializationError error = deserializeJson(doc, response);
    
    if (!error) {
      int flood_risk = doc["risk_summary"]["probability_percent"] | 0;
      int landslide_risk = doc["landslide_risk"]["probability_percent"] | 0;
      int max_risk = max(flood_risk, landslide_risk);
      
      Serial.print("[🟢 ML Response] Risk: ");
      Serial.print(max_risk);
      Serial.println("%");
      
      updateIndicatorsByRisk(max_risk);
    }
  } else {
    Serial.print("Error on sending POST (Risk): ");
    Serial.println(httpResponseCode);
  }
  http.end();
}

void readAndTransmitTelemetry() {
  int rawRain = analogRead(PIN_RAIN_SENSOR);
  int rawWater = analogRead(PIN_WATER_LEVEL);
  int rawSoil = analogRead(PIN_SOIL_MOISTURE);

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (isnan(temperature) || temperature < -10.0 || temperature > 80.0) temperature = 27.5; 
  if (isnan(humidity) || humidity < 0.0 || humidity > 100.0) humidity = 78.0;    

  digitalWrite(PIN_STATUS_LED, HIGH);

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
      "\"temperature\":%.1f,"
      "\"humidity\":%.1f,"
      "\"demo_mode\":false"
    "}",
    DEVICE_ID, LOCATION_NAME, STATE_NAME, DISTRICT_NAME, BASIN_CODE,
    rawRain, rawWater, rawSoil, temperature, humidity
  );

  HTTPClient http;
  String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + "/api/iot-telemetry";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    Serial.print("[✅ IoT Ingest] DB Stored: ");
    Serial.println(httpResponseCode);
  } else {
    Serial.print("[❌ IoT Error] Code: ");
    Serial.println(httpResponseCode);
  }
  http.end();
  
  delay(50);
  digitalWrite(PIN_STATUS_LED, LOW);
}
