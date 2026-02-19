#include <Arduino.h>
#include <LiquidCrystal.h>
#include <ArduinoJson.h>
#include "DHT.h"
#include "Servo.h"

// ==========================
// Pin Definitions
// ==========================
LiquidCrystal lcd(12, A1, A2, A3, A4, A5);

// RGB LED (2, 4 are Digital, 3 is PWM)
const int PIN_RED   = 2;
const int PIN_GREEN = 3;
const int PIN_BLUE  = 4;

// Sensors & Actuators
const int PIN_DHT   = 5;
const int PIN_BTN   = 6;
const int PIN_SERVO = 7;
const int PIN_PIEZO = 8;
const int PIN_CDS   = A0; 

// ==========================
// Object Initialization
// ==========================
#define DHTTYPE DHT11
DHT dht(PIN_DHT, DHTTYPE);
Servo myServo;

// ==========================
// Global Variables
// ==========================
const long SERIAL_SPEED = 115200;
const int BUFFER_SIZE = 512;
char inputBuffer[BUFFER_SIZE];
int bufferPos = 0;

unsigned long lastSensorTime = 0;
const unsigned long SENSOR_INTERVAL = 2000;

// ==========================
// Audio Functions (Piezo)
// ==========================
void playTone(const char* mood) {
  if (strcmp(mood, "happy") == 0) {
    tone(PIN_PIEZO, 523, 100); delay(150); // C5
    tone(PIN_PIEZO, 659, 100); delay(150); // E5
    tone(PIN_PIEZO, 784, 150); delay(200); // G5
  } else if (strcmp(mood, "angry") == 0) {
    tone(PIN_PIEZO, 150, 100); delay(100);
    tone(PIN_PIEZO, 100, 100); delay(100);
  } else if (strcmp(mood, "sad") == 0) {
    tone(PIN_PIEZO, 440, 300); delay(350); // A4
    tone(PIN_PIEZO, 349, 400); delay(450); // F4
  } else if (strcmp(mood, "neutral") == 0) {
    tone(PIN_PIEZO, 880, 50); delay(60);
  }
  noTone(PIN_PIEZO);
}

// ==========================
// Hardware Control
// ==========================
void setRGB(int r, int g, int b) {
  digitalWrite(PIN_RED, r > 127 ? HIGH : LOW);
  analogWrite(PIN_GREEN, g);
  digitalWrite(PIN_BLUE, b > 127 ? HIGH : LOW);
}

void setMood(const char* mood) {
  if (strcmp(mood, "happy") == 0) {
    setRGB(0, 255, 0); // Green
  } else if (strcmp(mood, "angry") == 0) {
    setRGB(255, 0, 0); // Red
  } else if (strcmp(mood, "sad") == 0) {
    setRGB(0, 0, 255); // Blue
  } else if (strcmp(mood, "neutral") == 0) {
    setRGB(255, 255, 255); // White
  } else {
    setRGB(0, 0, 0); // Off
  }
}

void performAction(const char* act) {
  if (strcmp(act, "nod") == 0) {
    for(int i=0; i<2; i++) {
      myServo.write(70); delay(150);
      myServo.write(110); delay(150);
    }
    myServo.write(90);
  } else if (strcmp(act, "shake") == 0) {
    for(int i=0; i<3; i++) {
      myServo.write(45); delay(100);
      myServo.write(135); delay(100);
    }
    myServo.write(90);
  } else if (strcmp(act, "scan") == 0) {
    myServo.write(60); delay(500);
    myServo.write(120); delay(500);
    myServo.write(90);
  }
}

// ==========================
// Main Logic
// ==========================
void reportSensors() {
  unsigned long currentMillis = millis();
  if (currentMillis - lastSensorTime >= SENSOR_INTERVAL) {
    lastSensorTime = currentMillis;

    float h = dht.readHumidity();
    float t = dht.readTemperature();
    int light = analogRead(PIN_CDS);
    
    // User Requirement: Button is INPUT (External resistor), Pressed = HIGH
    int btnState = digitalRead(PIN_BTN);
    int btn = (btnState == HIGH) ? 1 : 0; 

    if (isnan(h) || isnan(t)) return;

    JsonDocument doc;
    doc["type"] = "SENSOR";
    doc["temp"] = t;
    doc["humid"] = h;
    doc["light"] = light;
    doc["btn"] = btn;

    serializeJson(doc, Serial);
    Serial.println();
  }
}

void processCommand() {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, inputBuffer);

  if (error) return;

  long seq = doc["seq"] | 0;
  const char* l1 = doc["l1"];
  const char* l2 = doc["l2"];
  const char* mood = doc["mood"] | "neutral";
  const char* act = doc["act"] | "none";

  if (l1 && l2) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(l1);
    lcd.setCursor(0, 1);
    lcd.print(l2);
  }

  setMood(mood);
  playTone(mood);
  performAction(act);

  JsonDocument ackDoc;
  ackDoc["res"] = "ACK";
  ackDoc["seq"] = seq;
  serializeJson(ackDoc, Serial);
  Serial.println();
}

void setup() {
  Serial.begin(SERIAL_SPEED);
  
  lcd.begin(16, 2);
  lcd.clear();
  lcd.print("ARTIE V2.2");

  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BLUE, OUTPUT);
  pinMode(PIN_PIEZO, OUTPUT);
  
  // User Requirement: External Pull-up/down config -> Just INPUT
  pinMode(PIN_BTN, INPUT);
  
  dht.begin();

  myServo.attach(PIN_SERVO);
  myServo.write(90);

  JsonDocument bootDoc;
  bootDoc["status"] = "READY";
  serializeJson(bootDoc, Serial);
  Serial.println();
  
  delay(1000);
  lcd.clear();
  lcd.print("WAITING PC...");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      inputBuffer[bufferPos] = '\0';
      processCommand();
      bufferPos = 0;
    } else if (bufferPos < BUFFER_SIZE - 1) {
      inputBuffer[bufferPos++] = c;
    }
  }
  reportSensors();
}