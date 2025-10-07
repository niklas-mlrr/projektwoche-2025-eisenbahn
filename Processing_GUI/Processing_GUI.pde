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
  size(500, 320);
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
  
  // Weiche (switch) buttons - centered at top
  cp5.addButton("to20")
     .setPosition(50, 30)
     .setSize(180, 45)
     .setLabel("Weiche Links")
     .setColorBackground(color(70, 130, 180))
     .setColorForeground(color(100, 160, 210))
     .setColorActive(color(50, 110, 160));

  cp5.addButton("to75")
     .setPosition(270, 30)
     .setSize(180, 45)
     .setLabel("Weiche Rechts")
     .setColorBackground(color(70, 130, 180))
     .setColorForeground(color(100, 160, 210))
     .setColorActive(color(50, 110, 160));
  
  // Slider for manual control - centered
  cp5.addSlider("angle")
     .setPosition(50, 110)
     .setSize(400, 40)
     .setRange(0, 180)
     .setDecimalPrecision(0)
     .setValue(angle)
     .setSliderMode(Slider.FLEXIBLE)
     .setColorBackground(color(100, 100, 100))
     .setColorForeground(color(150, 150, 150))
     .setColorActive(color(70, 130, 180));

  // Level crossing buttons - centered at bottom
  cp5.addButton("bueZu")
     .setPosition(50, 230)
     .setSize(180, 50)
     .setLabel("BÜ Zu")
     .setColorBackground(color(220, 50, 50))
     .setColorForeground(color(250, 80, 80))
     .setColorActive(color(180, 30, 30));
  
  cp5.addButton("bueAuf")
     .setPosition(270, 230)
     .setSize(180, 50)
     .setLabel("BÜ Auf")
     .setColorBackground(color(50, 180, 50))
     .setColorForeground(color(80, 210, 80))
     .setColorActive(color(30, 150, 30));
     
  textAlign(CENTER, CENTER);
}

void draw() {
  // Modern gradient background
  for (int i = 0; i < height; i++) {
    float inter = map(i, 0, height, 0, 1);
    int c = lerpColor(color(230, 240, 250), color(200, 210, 220), inter);
    stroke(c);
    line(0, i, width, i);
  }
  
  // Title section
  fill(40, 60, 80);
  textSize(14);
  textAlign(LEFT);
  text("⚡ Eisenbahn Steuerung", 20, 20);
  
  // Servo angle display
  fill(40, 60, 80);
  textSize(16);
  textAlign(CENTER, CENTER);
  text("Weiche: " + motorAngle + "°", width/2, 90);
  
  // Section labels
  textSize(12);
  fill(70, 90, 110);
  textAlign(CENTER);
  text("Bahnübergang", width/2, 210);
  
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

// BÜ Zu button callback
void bueZu() {
  // Start indefinite blinking and close gates
  myPort.write("BZU\n");
}

// BÜ Auf button callback
void bueAuf() {
  // Stop blinking and open gates slowly
  myPort.write("BAUF\n");
}
