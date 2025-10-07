# Color Sensor Debugging Guide

## Changes Made

Based on the GitHub discussion (https://github.com/orgs/pybricks/discussions/1372), I've updated the color sensor parsing logic with the following improvements:

### Key Fixes:
1. **Correct byte position**: Color value is now checked at byte 6 first (confirmed working in Mario example), then falls back to bytes 4 and 5
2. **Enhanced logging**: All PORT_VALUE messages (0x43, 0x45, 0x47) are now logged with full hex data
3. **Better diagnostics**: Shows exactly what command is sent when enabling the sensor
4. **Improved error handling**: Better validation of message lengths before parsing

### Message Format (from Mario example):
```
Subscribe command: 0x0a 0x00 0x41 0x01 0x00 0x01 0x00 0x00 0x00 0x01
  - 0x0a: Length (10 bytes)
  - 0x00: Hub ID
  - 0x41: PORT_INPUT_FORMAT_SETUP_SINGLE
  - 0x01: Port (Mario uses port 1, Train Base uses port 0x12)
  - 0x00: Mode (0 = Color Index)
  - 0x01 0x00 0x00 0x00: Delta (little-endian int32 = 1)
  - 0x01: Notify enabled

Response format: PORT_VALUE_SINGLE (0x45)
  - Byte 0: Length
  - Byte 1: Hub ID (0x00)
  - Byte 2: Message Type (0x45)
  - Byte 3: Port ID
  - Byte 4-5: Mode info (possibly)
  - Byte 6: Color value (0-10) ← KEY POSITION
```

## How to Test

1. **Connect to Train Base**
   - Click "Connect to Train Base" button
   - Wait for connection success message

2. **Enable Debug Logging**
   - Go to "Debug & Diagnostics" tab
   - Ensure "Log RX" and "Log TX" are checked

3. **Test Color Sensor**
   - Go to "Color Sensor" tab
   - Ensure port is set to "Built-in (0x12)" (port 18 decimal)
   - Mode should be "Color Index (0-10)"
   - Click "Enable Color Sensor"

4. **Check Debug Console**
   - Switch to "Debug & Diagnostics" tab
   - Look for these messages:
     ```
     Sending PORT_INPUT_FORMAT_SETUP command: 0a0041120001000000001
     PORT_VALUE msg_type=0x45: port=0x12 (18), len=X, data=...
     ```

5. **Place colored objects** in front of the sensor and watch for:
   - Color value updates in the Color Sensor tab
   - Debug messages showing parsed color values

## Expected Color Values

| Value | Color       |
|-------|-------------|
| 0     | Black       |
| 1     | Pink        |
| 2     | Purple      |
| 3     | Blue        |
| 4     | Light Blue  |
| 5     | Cyan        |
| 6     | Green       |
| 7     | Yellow      |
| 8     | Orange      |
| 9     | Red         |
| 10    | White       |

## Troubleshooting

### No messages received at all (YOUR CURRENT ISSUE)
This is the most common problem - the hub is not responding to the PORT_INPUT_FORMAT_SETUP command.

**Possible causes:**
1. **Wrong port number** - Port 0x12 might not be correct for your Train Base variant
2. **Hub doesn't auto-send notifications** - Some hubs need different setup
3. **Color sensor not attached/detected** - Check physical connection

**Solutions to try:**

#### Option 1: Scan All Ports (RECOMMENDED)
1. Go to Color Sensor tab
2. Click **"Scan All Ports for Sensor"** button
3. This will try ports: 0x00, 0x01, 0x02, 0x03, 0x12, 0x13, 0x32, 0x3B, 0x3C
4. Watch the debug console for PORT_VALUE messages
5. Note which port responds (if any)
6. Update the port selection to that port

#### Option 2: Check Connection
- Try clicking "Check RX Handler" in Debug tab
- Verify the hub is sending data by testing motor control first
- Ensure hub is properly connected and powered on

#### Option 3: Check for HUB_ATTACHED_IO messages
- When you first connect, the hub should send HUB_ATTACHED_IO (0x04) messages
- These tell you which ports have devices attached
- Look in the debug console for messages like: `HUB_ATTACHED_IO Port=0xXX Event=ATTACHED IOType=0xXXXX`
- The color sensor typically has IOType 0x0025 (37 decimal)

### Messages received but wrong port
- The built-in color sensor should be on port 0x12 (18 decimal)
- If you see PORT_VALUE messages for other ports, note which port has the color sensor
- Update the port selection accordingly

### Messages received but can't parse color
- Check the debug console for the full hex data
- Look for the pattern: `PORT_VALUE msg_type=0x45: port=0x12 (18), len=X, data=...`
- The color value should be a number between 0-10
- If you see the data but it's not parsing, note which byte position contains the color value (0-10)
- Report the full hex string so we can adjust the parsing logic

### Color sensor not responding
- Try the "Test Color Sensor" button which sends port info requests first
- Some hubs may need a different mode (try switching between "Color Index" and "RGB Values")
- The auto-fallback will try switching modes after 2 seconds if no data is received

## Common Issues

1. **Port 0x12 doesn't exist**: Some Train Base variants may use a different port number
2. **Different message format**: Some hubs send data in PORT_VALUE (0x43) instead of PORT_VALUE_SINGLE (0x45)
3. **Mode not supported**: Try both mode 0 (Color Index) and mode 3 (RGB)

## Next Steps if Still Not Working

If the color sensor still doesn't work after these changes:
1. Share the debug console output (especially the hex data of PORT_VALUE messages)
2. Note which port the color sensor is actually on (check HUB_ATTACHED_IO messages on connection)
3. Try the "Scan All Ports" button to see all available ports
4. Check if any PORT_VALUE messages appear when you move colored objects in front of the sensor
