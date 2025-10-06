#include <Arduino.h>
#include <Servo.h>

Servo myServo;
Servo myServo2; // second servo on pin 8
int currentAngle = 90;
int targetAngle = 90;
unsigned long lastStepMs = 0;
const unsigned long stepIntervalMs = 15; // ms between steps
const int stepSize = 2;                  // degrees per step

// LED blink (pin 6) while motors are moving
const int ledPin = 6;
bool ledState = false;
unsigned long lastLedToggleMs = 0;
const unsigned long ledBlinkIntervalMs = 150;

// Timed move state (fixed-duration interpolation on Arduino)
bool moveActive = false;
int moveStartAngle = 90;
int moveEndAngle = 90;
unsigned long moveStartMs = 0;
unsigned long moveDurationMs = 0;

// Servo2 state
int currentAngle2 = 90;
// Timed move state for servo2
bool move2Active = false;
int move2StartAngle = 90;
int move2EndAngle = 90;
unsigned long move2StartMs = 0;
unsigned long move2DurationMs = 0;

void setup() {
  myServo.attach(9);
  myServo2.attach(8);
  myServo.write(currentAngle);
  myServo2.write(currentAngle2);
  Serial.begin(9600);
  Serial.setTimeout(20); // allow full line to arrive for readStringUntil
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      // Check for second motor command: "M2 <angle>"
      if (line.startsWith("M2")) {
        // Accept either: "M2 <angle>" or "M2 <angle> <durationMs>"
        int a2 = -1, d2 = -1;
        int firstSpace = line.indexOf(' ');
        if (firstSpace > 0) {
          String rest = line.substring(firstSpace + 1);
          rest.trim();
          int secondSpace = rest.indexOf(' ');
          if (secondSpace >= 0) {
            String aStr = rest.substring(0, secondSpace);
            String dStr = rest.substring(secondSpace + 1);
            a2 = constrain(aStr.toInt(), 0, 180);
            d2 = dStr.toInt();
          } else {
            a2 = constrain(rest.toInt(), 0, 180);
          }
        }
        if (a2 >= 0 && a2 <= 180) {
          if (d2 > 0) {
            // Timed move for servo2
            move2StartAngle = currentAngle2;
            move2EndAngle = a2;
            move2StartMs = millis();
            move2DurationMs = (unsigned long)d2;
            move2Active = true;
          } else {
            // Immediate move for servo2
            currentAngle2 = a2;
            myServo2.write(currentAngle2);
            move2Active = false;
          }
          // No Serial.println() for servo2 to avoid confusing Processing UI
        }
      } else {
        // Default: interpret as commands for servo on pin 9
        int a = -1, d = -1;
        int parsed = sscanf(line.c_str(), "%d %d", &a, &d);
        if (parsed >= 1 && a >= 0 && a <= 180) {
          if (parsed == 2 && d > 0) {
            // Start timed move from currentAngle to 'a' in 'd' ms
            moveStartAngle = currentAngle;
            moveEndAngle = a;
            moveStartMs = millis();
            moveDurationMs = (unsigned long)d;
            moveActive = true;
          } else {
            // Fallback: keep smooth step mode to targetAngle
            targetAngle = a;
            moveActive = false; // cancel any timed move
          }
        }
      }
    }
  }

  unsigned long now = millis();

  if (moveActive) {
    // Timed interpolation to ensure fixed duration regardless of distance
    unsigned long elapsed = now - moveStartMs;
    float t = moveDurationMs == 0 ? 1.0f : min(1.0f, (float)elapsed / (float)moveDurationMs);
    int newAngle = (int)round(moveStartAngle + (moveEndAngle - moveStartAngle) * t);
    if (newAngle != currentAngle) {
      currentAngle = newAngle;
      myServo.write(currentAngle);
      Serial.println(currentAngle);
    }
    if (t >= 1.0f) {
      moveActive = false;
      targetAngle = currentAngle; // keep step mode in sync
    }
  } else {
    // Smoothly move toward targetAngle without blocking (legacy step mode for slider)
    if (now - lastStepMs >= stepIntervalMs) {
      bool moved = false;
      if (currentAngle < targetAngle) {
        currentAngle = min(currentAngle + stepSize, targetAngle);
        myServo.write(currentAngle);
        moved = true;
      } else if (currentAngle > targetAngle) {
        currentAngle = max(currentAngle - stepSize, targetAngle);
        myServo.write(currentAngle);
        moved = true;
      }
      if (moved) {
        Serial.println(currentAngle);
      }
      lastStepMs = now;
    }
  }

  // Timed interpolation for servo2
  if (move2Active) {
    unsigned long elapsed2 = now - move2StartMs;
    float t2 = move2DurationMs == 0 ? 1.0f : min(1.0f, (float)elapsed2 / (float)move2DurationMs);
    int newAngle2 = (int)round(move2StartAngle + (move2EndAngle - move2StartAngle) * t2);
    if (newAngle2 != currentAngle2) {
      currentAngle2 = newAngle2;
      myServo2.write(currentAngle2);
      // No Serial feedback for servo2
    }
    if (t2 >= 1.0f) {
      move2Active = false;
    }
  }

  // LED blinking logic: blink while any motor is moving
  // Consider movement if: servo1 timed move active, servo2 timed move active,
  // or servo1 in step mode has not yet reached targetAngle
  bool movingNow = moveActive || move2Active || (currentAngle != targetAngle);
  if (movingNow) {
    if (now - lastLedToggleMs >= ledBlinkIntervalMs) {
      ledState = !ledState;
      digitalWrite(ledPin, ledState ? HIGH : LOW);
      lastLedToggleMs = now;
    }
  } else {
    if (ledState) {
      ledState = false;
      digitalWrite(ledPin, LOW);
    }
  }
}
