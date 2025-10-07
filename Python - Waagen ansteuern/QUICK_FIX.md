# Quick Fix for "Waiting for data..." Issue

## Your Problem
The color sensor shows "Waiting for data..." and no PORT_VALUE messages are received.

## Quick Solution

### Step 1: Click "Scan All Ports for Sensor"
1. Open the Train Hub GUI
2. Connect to Train Base
3. Go to **Color Sensor** tab
4. Click the **"Scan All Ports for Sensor"** button (new purple button)
5. Watch the Debug console

### Step 2: Look for PORT_VALUE Messages
The scan will try these ports in order:
- 0x00, 0x01, 0x02, 0x03 (external ports)
- 0x12, 0x13 (common internal ports)
- 0x32, 0x3B, 0x3C (hub LED and other internal)

**What to look for:**
```
>>> Trying port 0xXX...
TX: 0a0041XX000100000001
RX: XXXXXX | PORT_VALUE_SINGLE Port=0xXX Value=X  ← THIS IS WHAT YOU WANT!
```

### Step 3: Update Port Selection
If you see PORT_VALUE messages for a specific port:
1. Note the port number (e.g., 0x01, 0x03, etc.)
2. Select that port in the "Color Sensor Port" radio buttons
3. Click "Enable Color Sensor"
4. Place colored objects in front of the sensor

## Alternative: Check What's Connected

### Look at connection messages
When you first connect, scroll up in the debug console to see HUB_ATTACHED_IO messages:
```
RX: ... | HUB_ATTACHED_IO Port=0xXX Event=ATTACHED IOType=0x0025
```

- IOType 0x0025 (37) = Color & Distance Sensor
- IOType 0x0026 (38) = Color Sensor (simple)
- IOType 0x0029 (41) = Vision Sensor

The port number in that message is your color sensor port!

## Still Not Working?

### Check if ANY messages are received
1. Go to Debug tab
2. Click "Check RX Handler"
3. If it says "No messages received from hub", the connection might not be working properly
4. Try:
   - Testing motor control first (Basic Motor Control tab)
   - Reconnecting to the hub
   - Restarting the hub (turn off/on)

### Try manual port entry
If you know your color sensor is on a different port:
1. The port selection only has presets (0x12, 0, 1, 2)
2. You may need to add your port to the code
3. Or use the "Scan All Ports" which covers more options

## Expected Behavior When Working

When the color sensor is working, you should see:
```
[11:48:22.327] TX: 0a004112000100000001 (Enable color sensor port=0x12 mode=0)
[11:48:22.328] RX: 0700450012XX | PORT_VALUE_SINGLE Port=0x12 Value=6
[11:48:22.329] PORT_VALUE msg_type=0x45: port=0x12 (18), len=7, data=0700450012XX
[11:48:22.329] ✓ Color sensor data received! Mode=0, Length=7, Full data: 07 00 45 00 12 XX
[11:48:22.330] Parsed color index from byte 6 (Mario format): 6
[11:48:22.330] ✓ Color Index: 6
```

And the Color Sensor tab will show the detected color (e.g., "Green" for value 6).
