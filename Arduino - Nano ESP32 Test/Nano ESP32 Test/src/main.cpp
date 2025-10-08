#include <Arduino.h>

// Forward declaration
void setColor(int r, int g, int b);

const int buttonPin = 2;

const int redPin = 46;
const int greenPin = 0;
const int bluePin = 45;

int colorIndex = 0;
bool lastButtonState = HIGH;

void setup() {
  pinMode(buttonPin, INPUT_PULLUP);
  pinMode(redPin, OUTPUT);
  pinMode(greenPin, OUTPUT);
  pinMode(bluePin, OUTPUT);

  setColor(255, 0, 0); // start with red
}

void loop() {
  bool buttonState = digitalRead(buttonPin);

  if (buttonState == LOW && lastButtonState == HIGH) {
    colorIndex = (colorIndex + 1) % 4;
    switch (colorIndex) {
      case 0: setColor(255, 0, 0); break;   // Red
      case 1: setColor(0, 255, 0); break;   // Green
      case 2: setColor(0, 0, 255); break;   // Blue
      case 3: setColor(255, 255, 0); break; // Yellow
    }
    delay(200); // debounce
  }

  lastButtonState = buttonState;
}

void setColor(int r, int g, int b) {
  analogWrite(redPin, r);
  analogWrite(greenPin, g);
  analogWrite(bluePin, b);
}
