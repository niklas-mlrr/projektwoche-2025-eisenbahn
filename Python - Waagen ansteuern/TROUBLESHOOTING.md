# Train Hub Troubleshooting Guide

## Problem: Train Connects But Doesn't Move

Based on your debug log, commands are being sent but there are **NO RX (received) messages** from the hub. This is the key issue.

### Your Debug Log Analysis:
```
[10:03:01.934] ✓ Successfully connected to Train Base
[10:03:03.416] TX: 090081011107176400 (StartSpeed port=1 speed=23)
[10:03:04.813] TX: 090081011107176400 (StartSpeed port=1 speed=23)
[10:03:07.352] TX: 0c0081011109c50917647f00
[10:03:13.767] TX: 0800813211510004
[10:03:14.702] TX: 0800813211510006
```

**Problem**: No `RX:` lines! The hub should respond with feedback messages.

---

## Diagnostic Steps

### Step 1: Check RX Handler
1. Open the GUI and connect
2. Go to **"Debug & Diagnostics"** tab
3. Click **"Check RX Handler"** button
4. This will:
   - Show if any messages were received
   - Send a hub property request that MUST get a response
   - Help identify if the issue is with receiving or sending

### Step 2: Verify Notifications Are Enabled
The issue might be that BLE notifications aren't enabled. The hub won't send data back without this.

**Try this in the Raw Command Sender:**
```
05 00 01 01 05
```
This requests the hub name and should trigger a response.

### Step 3: Test Different Command Types

#### A. Try WriteDirectModeData (Simpler Protocol)
Click **"Test WriteDirectMode"** button, or use Raw Command Sender:
```
08 00 81 00 11 51 00 32
```
This sends speed 50 (0x32) to port 0 using direct mode.

#### B. Try Different Ports
Your commands are going to **port 1** (`port=1`). Try port 0:

**Raw command for Port 0:**
```
09 00 81 00 11 07 32 64 00
```
- `09` = length
- `00` = hub ID
- `81` = port output command
- `00` = **PORT 0** (change this!)
- `11` = startup/completion
- `07` = StartSpeed subcommand
- `32` = speed 50
- `64` = max power 100
- `00` = no profile

**Raw command for Port 2:**
```
09 00 81 02 11 07 32 64 00
```

### Step 4: Check Physical Connection
1. **Turn the train hub off and on** - Sometimes it needs a reset
2. **Check the motor is plugged in firmly**
3. **Try the official LEGO app** - Does the motor work there?
4. **Check battery level** - Low battery can cause issues

---

## Common Issues & Solutions

### Issue 1: No RX Messages (Your Current Issue)
**Symptoms**: Commands sent but no responses
**Causes**:
- BLE notifications not enabled (most likely)
- Hub in wrong mode
- Connection not fully established

**Solutions**:
1. Click "Check RX Handler" button
2. Try disconnecting and reconnecting
3. Restart the hub (turn off/on)
4. Check if `pybricksdev` version is up to date: `pip install --upgrade pybricksdev`

### Issue 2: Wrong Port
**Symptoms**: Commands sent, feedback received, but motor doesn't move
**Solution**: Try all three ports (0, 1, 2) using the test buttons

### Issue 3: Wrong Motor Type
**Symptoms**: Some commands work, others don't
**Solution**: Different motors respond to different commands:
- Train motors: Usually respond to WriteDirectModeData
- Technic motors: Usually respond to StartSpeed

### Issue 4: Hub Firmware
**Symptoms**: Nothing works consistently
**Solution**: Update hub firmware using official LEGO app

---

## Quick Test Commands

### Test Port 0 with Direct Mode:
```
08 00 81 00 11 51 00 32    # Speed 50
08 00 81 00 11 51 00 00    # Stop
```

### Test Port 0 with StartSpeed:
```
09 00 81 00 11 07 32 64 00    # Speed 50
09 00 81 00 11 07 00 64 00    # Stop
```

### Test Port 0 with StartPower (Unregulated):
```
07 00 81 00 11 01 32    # Power 50
07 00 81 00 11 01 00    # Stop
```

### Request Hub Information (Should Always Get Response):
```
05 00 01 01 05    # Request hub name
05 00 01 02 05    # Request button state
05 00 01 06 05    # Request battery level
```

---

## Understanding Command Format

### StartSpeed Command Structure:
```
[Length] [HubID] [MsgType] [Port] [Startup] [SubCmd] [Speed] [MaxPower] [Profile]
   09      00       81       XX     11        07       XX       64         00

Port values:
  00 = Port 0
  01 = Port 1  
  02 = Port 2

Speed values (signed byte):
  32 = 50
  64 = 100
  00 = 0 (stop)
  CE = -50 (reverse)
  9C = -100 (full reverse)
```

---

## Next Steps

1. **Run the updated GUI** with new debug features
2. **Click "Check RX Handler"** immediately after connecting
3. **Try "Test All Ports"** button - this will test ports 0, 1, and 2 sequentially
4. **Watch the debug console** for any RX messages
5. **Report back** what you see in the debug console

If you still see NO RX messages after "Check RX Handler", the issue is with the BLE connection setup, not the motor commands.
