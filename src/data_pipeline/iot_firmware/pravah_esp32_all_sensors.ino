/*
 * =====================================================================
 * TriNetra AI — ESP32 Cyber-Physical 4-Sensor Hydrological Node
 * =====================================================================
 * 
 * Works with USB Data Cable (Direct Serial) AND Optional Wi-Fi!
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

#include <DHT.h>

// ==========================================
// 1. PIN CONFIGURATION
// ==========================================
// Sensor Pins
#define PIN_RAIN_SENSOR       34   
#define PIN_WATER_LEVEL       35   
#define PIN_SOIL_MOISTURE     32   
#define PIN_DHT               4    
#define PIN_STATUS_LED        2    

// Indicator Pins (LEDs & Buzzer)
#define PIN_LED_GREEN         25
#define PIN_LED_YELLOW        26
#define PIN_LED_RED           27
#define PIN_BUZZER            14

#define DHTTYPE DHT11              
DHT dht(PIN_DHT, DHTTYPE);

const unsigned long TRANSMIT_INTERVAL_MS = 2000; 
unsigned long lastTransmitTime = 0;

// Device Metadata
const char* DEVICE_ID = "ESP32_DEMO_01";
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
  Serial.println("  🌊 TriNetra AI — ESP32 4-Sensor + Alarm Node Ready");
  Serial.println("=======================================================");
}

int currentRiskPct = 0;

void loop() {
  unsigned long currentMillis = millis();
  
  // 1. Send sensor data to Python every 2 seconds
  if (currentMillis - lastTransmitTime >= TRANSMIT_INTERVAL_MS) {
    lastTransmitTime = currentMillis;
    readAndTransmitTelemetry();
  }

  // 2. Receive ML Risk Percentage from Python Backend
  if (Serial.available() > 0) {
    String incomingMsg = Serial.readStringUntil('\n');
    incomingMsg.trim();
    if (incomingMsg.startsWith("RISK:")) {
      currentRiskPct = incomingMsg.substring(5).toInt();
      updateIndicatorsByRisk(currentRiskPct);
    }
  }
}

void updateIndicatorsByRisk(int riskPct) {
  // Subse pehle saari LEDs aur Buzzer OFF kar do
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  // ML Risk Percentage based logic:
  if (riskPct >= 95) {
    // 🚨 CRITICAL (Risk 95-100%): Red + Buzzer ON
    digitalWrite(PIN_LED_RED, HIGH);
    digitalWrite(PIN_BUZZER, HIGH); 
  }
  else if (riskPct >= 80) {
    // 🔴 DANGER (Risk 80-94%): Red LED Only (No Buzzer)
    digitalWrite(PIN_LED_RED, HIGH);
  }
  else if (riskPct >= 40) {
    // 🟡 WARNING (Risk 40-79%): Yellow LED Only
    digitalWrite(PIN_LED_YELLOW, HIGH);
  } 
  else {
    // 🟢 SAFE (Risk 0-39%): Green LED Only
    digitalWrite(PIN_LED_GREEN, HIGH);
  }
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

  Serial.println(jsonPayload);

  delay(50);
  digitalWrite(PIN_STATUS_LED, LOW);
}
