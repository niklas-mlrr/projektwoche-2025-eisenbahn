# LEGO Train Base Color Sensor - Complete Solution

## Quick Start

Run the working color sensor script:
```bash
python color_sensor_direct.py
```

Place colored LEGO bricks or objects in front of the sensor and watch the colors appear in real-time!

## What You'll See

```
🎨 Color: Red (value=9)
🎨 Color: Yellow (value=7)
🎨 Color: Green (value=6)
⚪ No color detected (value=0xFF)
```

## Your Train Base Setup

Based on the scan, your Train Base has:
- **Port 0x00:** Train Motor (device 0x0029)
- **Port 0x01:** Train Motor (device 0x002A)
- **Port 0x12:** **Color Sensor** ← This is what we're using! (device 0x002B)
- **Port 0x13:** Speedometer (device 0x002C)
- **Port 0x14:** Voltage Sensor (device 0x0014)

## Files

### Working Files ✓
1. **color_sensor_direct.py** - Standalone color sensor reader (RECOMMENDED)
2. **train_hub_gui.py** - Full GUI with motor control and color sensor
3. **COLOR_SENSOR_WORKING.md** - Detailed explanation of the solution

### Documentation
4. **CRITICAL_ISSUE.md** - Explains the BLE notification issue
5. **QUICK_FIX.md** - Troubleshooting guide
6. **COLOR_SENSOR_DEBUG.md** - Original debugging guide

## The Problem & Solution

### Problem 1: No RX Messages
- **Issue:** `pybricksdev.ble.BLEConnection` didn't enable BLE notifications
- **Solution:** Used `bleak` library directly in `color_sensor_direct.py`

### Problem 2: Wrong Byte Position
- **Issue:** Code looked for color at byte 6 (Mario format)
- **Your format:** 5-byte message with color at byte 4
- **Solution:** Updated parsing to check byte 4 first

## Message Format

Your Train Base sends:
```
[05, 00, 45, 12, color_value]
 │   │   │   │   └─ Color (0-10 or 0xFF)
 │   │   │   └───── Port 0x12
 │   │   └───────── Message type (PORT_VALUE_SINGLE)
 │   └───────────── Hub ID
 └───────────────── Length (5 bytes)
```

## Color Values

| Value | Color      |
|-------|------------|
| 0     | Black      |
| 1     | Pink       |
| 2     | Purple     |
| 3     | Blue       |
| 4     | Light Blue |
| 5     | Cyan       |
| 6     | Green      |
| 7     | Yellow     |
| 8     | Orange     |
| 9     | Red        |
| 10    | White      |
| 255   | No color   |

## Using in Your Project

### Example: Train Automation
```python
# Stop at red, go at green
if color_value == 9:  # Red
    stop_train()
elif color_value == 6:  # Green  
    start_train()
```

### Example: Track Detection
```python
# Use colored markers on track
if color_value == 7:  # Yellow = Station
    slow_down_and_stop()
elif color_value == 8:  # Orange = Speed zone
    increase_speed()
```

## Next Steps

1. ✓ Color sensor working
2. ✓ Can detect colors reliably
3. → Integrate into your train control logic
4. → Add automation based on colors

Enjoy your working color sensor! 🎉
