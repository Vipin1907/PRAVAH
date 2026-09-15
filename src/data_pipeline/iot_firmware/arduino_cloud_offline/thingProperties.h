// thingProperties.h
#include <ArduinoIoTCloud.h>
#include <Arduino_ConnectionHandler.h>

const char DEVICE_LOGIN_NAME[]  = "d587a110-9a08-4df1-907f-da9cb87f1828";

const char SSID[]               = "Future with me";    // Network SSID (name)
const char PASS[]               = "Future with me";    // Network password
const char DEVICE_KEY[]         = "WnAIsyvIhywBUTiBs120q2Qbz";    // Secret device password

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
