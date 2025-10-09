#include <Arduino.h>

const int stopButtonPin = 2;   // STOP button (active LOW with pull-up)
const int dirButtonPin = 4;    // DIRECTION button (active LOW with pull-up)
const int flexPin = A0;        // pin A0 to read analog input

//Variables:

int value;                // save analog value
int prevStopState = HIGH; // previous state for STOP button
int prevDirState = HIGH;  // previous state for DIR button

void setup(){
  pinMode(stopButtonPin, INPUT_PULLUP); // internal pull-up, pressed = LOW
  pinMode(dirButtonPin, INPUT_PULLUP);  // internal pull-up, pressed = LOW
  Serial.begin(9600); //Begin serial communication
}

void loop(){
  value = analogRead(flexPin); //Read and save analog value from flex sensor
  Serial.println(value); //Print raw flex value for Python mapping
 
  // Button handling with press edge detection (HIGH->LOW)
  int stopState = digitalRead(stopButtonPin);
  if (prevStopState == HIGH && stopState == LOW) {
    Serial.println("STOP");
  }
  prevStopState = stopState;
 
  int dirState = digitalRead(dirButtonPin);
  if (prevDirState == HIGH && dirState == LOW) {
    Serial.println("DIR");
  }
  prevDirState = dirState;
  delay(50); //Small delay & basic debounce
}