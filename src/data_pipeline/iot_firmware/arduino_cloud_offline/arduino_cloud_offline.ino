/* 
  Offline Arduino Cloud Sketch
  Uses thingProperties.h for configuration
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include "thingProperties.h"
#include <DHT.h>

const char* serverUrl = "http://10.107.107.76:5000/api/iot-telemetry";
const char* DEVICE_ID = "ESP32_DEMO_01";
const char* LOCATION_NAME = "Subansiri River Basin";
const char* STATE_NAME = "Assam";
const char* DISTRICT_NAME = "Dhemaji";
const char* BASIN_CODE = "A011";

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

const unsigned long READ_INTERVAL_MS = 2000; 
unsigned long lastReadTime = 0;

void setup() {
  Serial.begin(115200);
  delay(1500); 

  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  digitalWrite(PIN_STATUS_LED, LOW);
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); 

  dht.begin();

  // Initialize properties from thingProperties.h
  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);
  
  setDebugMessageLevel(2);
  ArduinoCloud.printDebugInfo();
}

void loop() {
  ArduinoCloud.update();
  
  unsigned long currentMillis = millis();
  
  if (currentMillis - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = currentMillis;
    readSensors();
  }
}

void readSensors() {
  int rawRain = analogRead(PIN_RAIN_SENSOR);
  int rawWater = analogRead(PIN_WATER_LEVEL);
  int rawSoil = analogRead(PIN_SOIL_MOISTURE);

  float temp = dht.readTemperature();
  float hum = dht.readHumidity();

  if (isnan(temp) || temp < -10.0 || temp > 80.0) temp = 27.5; 
  if (isnan(hum) || hum < 0.0 || hum > 100.0) hum = 78.0;    

  // Update Arduino Cloud Variables
  rainfall = rawRain;
  waterLevel = rawWater;
  soilMoisture = rawSoil;
  temperature = temp;
  humidity = hum;

  Serial.println("Sensors Updated in Cloud!");

  // Build JSON Payload and send to Local Pravah AI Backend
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
    rawRain, rawWater, rawSoil, temp, hum
  );

  // THIS IS CRITICAL FOR THE USB SERIAL BRIDGE TO WORK!
  Serial.println(jsonPayload);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    int httpResponseCode = http.POST(jsonPayload);

    if (httpResponseCode > 0) {
      Serial.printf("[HTTP] POST Success to Local Dashboard! Response Code: %d\n", httpResponseCode);
    } else {
      Serial.printf("[HTTP] POST Error! Code: %d\n", httpResponseCode);
    }
    http.end();
  } else {
    Serial.print("[WARNING] WiFi not fully connected yet. Status: ");
    Serial.println(WiFi.status());
  }
}
