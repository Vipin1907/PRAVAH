// thingProperties.h
#include <ArduinoIoTCloud.h>
#include <Arduino_ConnectionHandler.h>

const char DEVICE_LOGIN_NAME[]  = "YOUR_DEVICE_ID_HERE";

const char SSID[]               = "YOUR_WIFI_SSID_HERE";    // Network SSID (name)
const char PASS[]               = "YOUR_WIFI_PASSWORD_HERE";    // Network password
const char DEVICE_KEY[]         = "YOUR_SECRET_KEY_HERE";    // Secret device password

float humidity;
float rainfall;
float soilMoisture;
float temperature;
float waterLevel;

void initProperties(){
  ArduinoCloud.setBoardId(DEVICE_LOGIN_NAME);
  ArduinoCloud.setSecretDeviceKey(DEVICE_KEY);
  ArduinoCloud.addProperty(humidity, READ, 5 * SECONDS, NULL);
  ArduinoCloud.addProperty(rainfall, READ, 5 * SECONDS, NULL);
  ArduinoCloud.addProperty(soilMoisture, READ, 5 * SECONDS, NULL);
  ArduinoCloud.addProperty(temperature, READ, 5 * SECONDS, NULL);
  ArduinoCloud.addProperty(waterLevel, READ, 5 * SECONDS, NULL);
}

WiFiConnectionHandler ArduinoIoTPreferredConnection(SSID, PASS);
