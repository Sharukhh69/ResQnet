#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>

// Ra-02 Pin Configuration for ESP32
#define LORA_SS    5   // Orange wire
#define LORA_RST   14  // White wire
#define LORA_DIO0  2   // Purple wire

const String NODE_ID = "ALPHA-01";
float latitude = 26.2006;
float longitude = 92.9376;
int batteryLevel = 98;
int sequenceNumber = 1;
bool emergencyActive = false;

unsigned long lastTelemetryTime = 0;
const unsigned long TELEMETRY_INTERVAL = 3000;

void sendTelemetry() {
  String status = emergencyActive ? "SOS_CRITICAL" : "NORMAL";
  
  // Clean packet format: TEL|ALPHA-01|26.2006,92.9376|98%|NORMAL|SEQ:1
  String packet = "TEL|" + NODE_ID + "|" + 
                  String(latitude, 4) + "," + String(longitude, 4) + "|" + 
                  String(batteryLevel) + "%|" + 
                  status + "|SEQ:" + String(sequenceNumber++);

  Serial.print("📡 [LORA TX] Broadcasting: ");
  Serial.println(packet);

  LoRa.beginPacket();
  LoRa.print(packet);
  LoRa.endPacket();

  if (sequenceNumber % 10 == 0 && batteryLevel > 15) {
    batteryLevel--;
  }
}

void checkIncomingCommands() {
  int packetSize = LoRa.parsePacket();
  if (packetSize > 0) {
    String command = "";
    while (LoRa.available()) {
      command += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();
    
    Serial.println("\n🎯 >>> [HQ DOWNLINK COMMAND RECEIVED] <<<");
    Serial.print("Payload : ");
    Serial.println(command);
    Serial.print("Signal  : ");
    Serial.print(rssi);
    Serial.println(" dBm\n");

    if (command.indexOf("ACK_SOS") >= 0) {
      emergencyActive = false;
      Serial.println("✅ HQ Acknowledged Emergency. Reset to NORMAL.");
    }
  }
}

void checkSerialInput() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.equalsIgnoreCase("SOS") || input.equalsIgnoreCase("HELP")) {
      emergencyActive = !emergencyActive;
      Serial.println("\n🚨 [EMERGENCY TOGGLED] Mode: " + String(emergencyActive ? "CRITICAL SOS!" : "NORMAL"));
      sendTelemetry();
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n========================================");
  Serial.println("  ResQ-Mesh Tactical Field Node (" + NODE_ID + ")");
  Serial.println("========================================");

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(433E6)) {
    Serial.println("❌ ERROR: LoRa init failed!");
    while (1) { delay(1000); }
  }

  LoRa.setSyncWord(0x12);
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.enableCrc(); // Enable hardware CRC matching Pi
  LoRa.setTxPower(14, PA_OUTPUT_PA_BOOST_PIN); // 14 dBm prevents receiver saturation in the same room

  Serial.println("✅ LoRa Ready at 433.0 MHz.");
  Serial.println("----------------------------------------\n");

  sendTelemetry();
}

void loop() {
  checkIncomingCommands();
  checkSerialInput();

  if (millis() - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    lastTelemetryTime = millis();
    sendTelemetry();
  }
}
