#include <Arduino.h>
#include <Servo.h>

Servo servo;

const int servoPin = 9;     // Servo signal pin
const int inputPin = A0;    // Hand crank (analog input)

// Smoothing variables
const int numReadings = 20;  // Increased averaging for more stability
int readings[numReadings];   // Array to store readings
int readIndex = 0;           // Current reading index
long total = 0;              // Running total (long to prevent overflow)
int average = 0;             // Averaged value

int lastAngle = 90;          // Last servo position (start at center)
const int threshold = 5;     // Increased deadband to prevent jitter

void setup() {
  Serial.begin(115200);
  
  // Set analog reference to default (5V) for stability
  analogReference(DEFAULT);
  
  // Take initial reading to stabilize ADC
  for (int i = 0; i < 10; i++) {
    analogRead(inputPin);
    delay(10);
  }
  
  // Initialize readings array with current sensor value
  int initialValue = analogRead(inputPin);
  for (int i = 0; i < numReadings; i++) {
    readings[i] = initialValue;
  }
  total = initialValue * numReadings;
  average = initialValue;
  
  // Calculate initial angle - start at 90° (center) for testing
  lastAngle = 90;  // Force center position for power test
  
  servo.attach(servoPin);
  servo.write(lastAngle);
  
  Serial.println("=== Servo Control with Hand Crank ===");
  Serial.print("Initial reading: ");
  Serial.print(initialValue);
  Serial.print(" | Starting angle: ");
  Serial.print(lastAngle);
  Serial.println("°");
  Serial.println("Ready!");
  
  delay(500);
}

void loop() {
  // Take multiple readings to filter out glitches
  int rawValue = 0;
  int validReadings = 0;
  
  // Take 3 readings and average them
  for (int i = 0; i < 3; i++) {
    int reading = analogRead(inputPin);
    // Only reject obvious bad readings (0 or very low values that indicate disconnection)
    if (reading > 5) {
      rawValue += reading;
      validReadings++;
    }
    delayMicroseconds(500);
  }
  
  // If we got no valid readings, skip this loop iteration
  if (validReadings == 0) {
    Serial.println("WARNING: No valid readings - check connection!");
    delay(100);
    return;
  }
  
  // Average the valid readings
  rawValue = rawValue / validReadings;
  
  // Subtract the oldest reading
  total = total - readings[readIndex];
  
  // Store new reading
  readings[readIndex] = rawValue;
  
  // Add the new reading to the total
  total = total + readings[readIndex];
  
  // Advance to the next position in the array
  readIndex = (readIndex + 1) % numReadings;
  
  // Calculate the average
  average = total / numReadings;
  
  // Map averaged value to servo angle (0–180)
  int angle = map(average, 0, 1023, 0, 180);
  
  // Constrain to valid servo range
  angle = constrain(angle, 0, 180);
  
  // Only move servo if change is significant (deadband)
  if (abs(angle - lastAngle) >= threshold) {
    // Smooth transition - move gradually instead of jumping
    int steps = abs(angle - lastAngle);
    int direction = (angle > lastAngle) ? 1 : -1;
    
    for (int i = 0; i < steps; i++) {
      lastAngle += direction;
      servo.write(lastAngle);
      delay(15); // Slower movement = less current draw
    }
    
    // Print debug info
    Serial.print("Raw: ");
    Serial.print(rawValue);
    Serial.print(" (");
    Serial.print(validReadings);
    Serial.print("/3) | Avg: ");
    Serial.print(average);
    Serial.print(" | Angle: ");
    Serial.print(lastAngle);
    Serial.println("°");
  }
  
  // Delay for ADC stability
  delay(20);
}
