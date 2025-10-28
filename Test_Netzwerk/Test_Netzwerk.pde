import processing.ble.*;

BLE ble;
Characteristic ch;

String SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0";
String CHAR_UUID    = "abcdef01-1234-5678-1234-56789abcdef0";

void setup() {
  size(400, 200);
  ble = new BLE(this, true);
  println("Scanning...");
  ble.startScan();
}

void draw() {
}

void onScan(BLEDevice device) {
  println("Found:", device.getName(), device.getAddress());
  // Connect automatically to the first matching device
  device.connect();
  ble.stopScan();
}

void onConnect(BLEDevice device) {
  println("Connected!");
  ch = device.getService(SERVICE_UUID).getCharacteristic(CHAR_UUID);
}

void mousePressed() {
  if (ch != null) {
    ch.write("BUTTON\n");
    println("Sent BUTTON");
  }
}
