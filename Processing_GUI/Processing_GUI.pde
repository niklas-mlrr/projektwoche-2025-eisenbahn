import processing.serial.*;
import controlP5.*;

Serial myPort;
ControlP5 cp5;
int angle = 90;
int lastSentAngle = -1; // Initialize to -1 to force first send
int motorAngle = 90;     // Last known actual motor angle from Arduino

// Duration for Arduino-side timed moves (ms)
int animDurationMs = 2000; // 2 seconds

// Suppress slider transmissions while a timed move is active
int suppressSliderUntilMs = 0;

void setup() {
  size(400, 240);
  printArray(Serial.list());
  
  // -> z.B. Serial.list()[0] oder [1], je nach Ausgabe
  // Prefer COM10 (matches platformio.ini upload_port); fallback to first available
  String target = null;
  for (String p : Serial.list()) {
    if (p != null && p.contains("COM10")) { target = p; break; }
  }
  if (target == null && Serial.list().length > 0) {
    target = Serial.list()[0];
  }
  println("Using serial port: " + target);
  myPort = new Serial(this, target, 9600);
  myPort.bufferUntil('\n'); // accumulate until newline for serialEvent
  
  cp5 = new ControlP5(this);
  
  cp5.addSlider("angle")
     .setPosition(50, 80)
     .setSize(300, 40)
     .setRange(0, 180)
     .setDecimalPrecision(0)
     .setValue(angle)
     .setSliderMode(Slider.FLEXIBLE); // FLEXIBLE mode for better responsiveness
  
  // Buttons for 20° -> 75° and reverse over 5 seconds
  cp5.addButton("to75")
     .setPosition(50, 140)
     .setSize(120, 30)
     .setLabel("Weiche Links");
  
  cp5.addButton("to20")
     .setPosition(230, 140)
     .setSize(120, 30)
     .setLabel("Weiche Rechts");

  // Second row: Motor 2 (pin 8) direct positions
  cp5.addButton("m2_90")
     .setPosition(50, 185)
     .setSize(120, 30)
     .setLabel("Motor2 90°");

  cp5.addButton("m2_0")
     .setPosition(230, 185)
     .setSize(120, 30)
     .setLabel("Motor2 0°");
     
  textAlign(CENTER, CENTER);
}

void draw() {
  background(240);
  fill(0);
  textSize(16);
  // Show the actual motor angle reported by Arduino for accurate UI feedback
  text("Servo Winkel: " + motorAngle + "°", width/2, 40);
  
  // Always read the current slider value directly
  float sliderVal = cp5.getController("angle").getValue();
  
  // Only process valid values
  if (!Float.isNaN(sliderVal)) {
    int currentSliderValue = constrain((int)sliderVal, 0, 180);
    
    // Send to Arduino if value changed
    if (currentSliderValue != lastSentAngle && millis() >= suppressSliderUntilMs) {
      myPort.write(currentSliderValue + "\n");
      lastSentAngle = currentSliderValue;
      angle = currentSliderValue;
    }
  }
}

// Receive current motor angle from Arduino
void serialEvent(Serial p) {
  String line = p.readStringUntil('\n');
  if (line == null) return;
  line = trim(line);
  if (line.length() == 0) return;
  try {
    int val = constrain(Integer.parseInt(line), 0, 180);
    motorAngle = val;
    // Always sync UI slider/state to actual motor angle; avoid echo by updating lastSentAngle
    angle = val;
    lastSentAngle = val;
    // Prevent emitting a slider event while updating from hardware feedback
    cp5.getController("angle").setBroadcast(false);
    cp5.getController("angle").setValue(val);
    cp5.getController("angle").setBroadcast(true);
  } catch (Exception e) {
    // ignore non-numeric lines
  }
}

// Callback when slider changes - update angle variable
void angle(float val) {
  if (!Float.isNaN(val)) {
    angle = constrain(int(val), 0, 180);
  }
}

  // Button callbacks: send timed move commands to Arduino
  void to75() {
  myPort.write("75 " + animDurationMs + "\n");
  suppressSliderUntilMs = millis() + animDurationMs + 50; // ignore slider echo during move
  lastSentAngle = (int)cp5.getController("angle").getValue();
  }
  
  void to20() {
  myPort.write("20 " + animDurationMs + "\n");
  suppressSliderUntilMs = millis() + animDurationMs + 50;
  lastSentAngle = (int)cp5.getController("angle").getValue();
  }

// Second-row button callbacks for Motor 2
void m2_90() {
  myPort.write("M2 90 " + animDurationMs + "\n");
}

void m2_0() {
  myPort.write("M2 0 " + animDurationMs + "\n");
}

