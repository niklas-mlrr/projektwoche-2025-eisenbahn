# CRITICAL ISSUE: No RX Messages Received

## The Problem

Your log shows **ZERO RX (receive) messages** - only TX (transmit) messages. This means:
- Commands are being sent to the hub ✓
- The hub is NOT sending any data back ✗

This is **NOT a color sensor parsing issue** - it's a **BLE notification issue**.

## Root Cause

The `pybricksdev.ble.BLEConnection` is not properly enabling BLE notifications on the characteristic. This is a known issue with some versions of pybricksdev when used with the LWP3 protocol.

## Solution Options

### Option 1: Use Direct Bleak (RECOMMENDED)

Instead of using `pybricksdev`, use the `bleak` library directly. This gives you full control over BLE notifications.

Create a new file `color_sensor_direct.py`:

```python
import asyncio
from bleak import BleakScanner, BleakClient

LWP3_SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"
LWP3_CHAR_UUID = "00001624-1212-efde-1623-785feabcd123"
TARGET_NAME = "Train Base"

def make_port_input_format_setup(port_id: int, mode: int, delta: int = 1, notify: bool = True) -> bytes:
    """Setup port input format [0x41]"""
    payload = bytes([
        0x00, 0x41, port_id & 0xFF, mode & 0xFF,
        delta & 0xFF, 0x00, 0x00, 0x00,  # delta as int32
        1 if notify else 0
    ])
    return bytes([len(payload) + 1]) + payload

async def main():
    print("Scanning for Train Base...")
    devices = await BleakScanner.discover(timeout=10.0)
    
    device = None
    for d in devices:
        if d.name == TARGET_NAME:
            device = d
            print(f"Found: {d.name} ({d.address})")
            break
    
    if not device:
        print("Train Base not found!")
        return
    
    async with BleakClient(device.address) as client:
        print(f"Connected: {client.is_connected}")
        
        # Callback for notifications
        def notification_handler(sender, data: bytes):
            print(f"RX: {data.hex()}")
            # Parse color sensor data
            if len(data) >= 7 and data[2] == 0x45:  # PORT_VALUE_SINGLE
                port = data[3]
                color_value = data[6]
                if 0 <= color_value <= 10:
                    colors = ["Black", "Pink", "Purple", "Blue", "Light Blue", 
                             "Cyan", "Green", "Yellow", "Orange", "Red", "White"]
                    print(f"  Color Sensor Port {port}: {colors[color_value]} ({color_value})")
        
        # Enable notifications
        await client.start_notify(LWP3_CHAR_UUID, notification_handler)
        print("✓ Notifications enabled")
        
        # Enable color sensor on port 0x12 (mode 0 = color index)
        cmd = make_port_input_format_setup(0x12, mode=0, delta=1, notify=True)
        print(f"Sending: {cmd.hex()}")
        await client.write_gatt_char(LWP3_CHAR_UUID, cmd)
        
        print("\nWaiting for color sensor data... (place colored objects in front)")
        print("Press Ctrl+C to stop\n")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
        
        await client.stop_notify(LWP3_CHAR_UUID)

if __name__ == "__main__":
    asyncio.run(main())
```

Run this script:
```bash
python color_sensor_direct.py
```

This should work because it uses Bleak directly with explicit notification handling.

### Option 2: Fix pybricksdev Version

The issue might be with your pybricksdev version. Try:

```bash
pip install --upgrade pybricksdev
# or
pip install pybricksdev==1.0.0a48  # Try a specific version
```

### Option 3: Check if Motor Control Works

Try the original `main.py` to see if it receives ANY messages:

```bash
python main.py
```

If `main.py` also doesn't receive messages, then the issue is with your pybricksdev installation or the hub itself.

## What the Fix Does

The new code I added to `train_hub_gui.py` will:
1. Try to manually enable notifications via `client.start_notify()`
2. Test RX by requesting hub name
3. Report if notifications are not working

**Reconnect to the hub** with the updated code and check the debug console for:
- "✓ Manually enabled BLE notifications"
- "✓ RX working! Received X messages"

OR

- "⚠ WARNING: No response to hub name request!"
- "⚠ BLE notifications may not be enabled properly!"

## Why This Happens

The `pybricksdev.ble.BLEConnection` class is designed for Pybricks firmware, not the official LEGO firmware (LWP3 protocol). While it *should* work, there are edge cases where BLE notifications don't get properly enabled.

The direct Bleak approach bypasses this issue entirely.
