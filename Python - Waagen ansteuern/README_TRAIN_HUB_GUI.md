# LEGO Train Hub Control GUI

A comprehensive graphical user interface for controlling LEGO Powered Up Train Hub (DUPLO Train Base) with full access to all LWP3 protocol functions.

## Features

### 🐛 Debug & Diagnostics (NEW!)
- **Debug Console**: Real-time logging of all TX/RX messages with timestamps
- **Message Decoder**: Automatic decoding of LWP3 protocol messages
- **Port Scanner**: Scan all ports to detect attached devices
- **Test Commands**: Automated testing of all ports and command types
- **Raw Command Sender**: Send custom hex commands for advanced debugging
- **Connection Info**: Display detailed connection parameters

### 🎮 Basic Motor Control
- **Port Selection**: Control motors on Port 0, 1, or 2
- **Speed Control**: Regulated speed control with slider (-100 to 100)
- **Quick Speed Buttons**: Instant speed presets (-100, -50, 0, 50, 100)
- **Power Control**: Unregulated power control for direct motor power
- **Stop Motor**: Emergency stop button

### ⚙️ Advanced Motor Control
- **Timed Movement**: Run motor at specific speed for a set duration (ms)
- **Degree-based Movement**: Rotate motor for exact number of degrees
- **Max Power Setting**: Limit maximum power output (0-100%)
- **End State Selection**: Choose motor behavior after movement
  - **Float**: Motor coasts freely
  - **Hold**: Motor holds position
  - **Brake**: Motor actively brakes

### 🎨 Hub Control
- **LED Color Control**: Set hub LED to 11 different colors
  - Off, Pink, Purple, Blue, Light Blue, Cyan, Green, Yellow, Orange, Red, White
- **Hub Actions**: 
  - Shutdown hub
  - Disconnect hub
- **Emergency Stop**: Stop all motors on all ports immediately

### 📊 Profiles & Settings
- **Acceleration Profile**: Set smooth acceleration time (0-10000ms)
- **Deceleration Profile**: Set smooth deceleration time (0-10000ms)
- **Profile Toggle**: Enable/disable profile usage in motor commands

## Installation

### Prerequisites
```bash
pip install pybricksdev bleak
```

### Dependencies
- `pybricksdev` - LEGO Bluetooth communication library
- `bleak` - Bluetooth Low Energy library
- `tkinter` - GUI framework (usually included with Python)

## Usage

### Starting the GUI
```bash
python train_hub_gui.py
```

### Connection Steps
1. **Turn on your LEGO Train Base** - Make sure it's blinking (advertising mode)
2. Click **"Connect to Train Base"** button
3. Wait for connection (may take 10-30 seconds)
4. Once connected, status will show "Connected ✓"

### Basic Operation

#### Controlling a Motor
1. Select the port (Port 0, 1, or 2) using radio buttons
2. Adjust the speed slider
3. Click "Start Speed" to begin motor movement
4. Click "Stop Motor" to stop

#### Timed Movement
1. Go to "Advanced Motor Control" tab
2. Set duration in milliseconds
3. Set speed on the main slider
4. Click "Run for Time"

#### Degree-based Movement
1. Go to "Advanced Motor Control" tab
2. Set degrees (0-3600)
3. Set speed on the main slider
4. Click "Run for Degrees"

#### LED Control
1. Go to "Hub Control" tab
2. Click any color button to change hub LED

#### Setting Profiles
1. Go to "Profiles & Settings" tab
2. Set acceleration time (time to go from 0 to 100%)
3. Set deceleration time (time to go from 100% to 0)
4. Enable "Use Acceleration/Deceleration Profiles" checkbox
5. Click respective "Set" buttons

## LWP3 Protocol Commands Implemented

### Motor Commands (0x81)
- **StartSpeed [0x07]**: Regulated speed control
- **StartSpeedForTime [0x09]**: Timed movement with speed regulation
- **StartSpeedForDegrees [0x0B]**: Degree-based movement
- **StartPower [0x01]**: Unregulated power control
- **SetAccTime [0x05]**: Configure acceleration profile
- **SetDecTime [0x06]**: Configure deceleration profile
- **WriteDirectModeData [0x51]**: Direct mode data writing (LED control)

### Hub Commands
- **Hub LED Color**: Control built-in hub LED (Port 0x32)
- **Hub Actions [0x02]**: Shutdown, disconnect, power control

## Port Information

### Typical Port Assignments
- **Port 0**: Usually the main motor (Motor A)
- **Port 1**: Secondary motor (Motor B)
- **Port 2**: Additional motor (Motor C)

Note: Actual port assignments depend on your LEGO Train Base configuration.

## Troubleshooting

### Connection Issues
- Ensure Train Base is powered on and blinking
- Make sure Bluetooth is enabled on your computer
- Try moving closer to the hub
- Restart the Train Base by turning it off and on
- Check that no other application is connected to the hub

### Motor Not Responding
- Verify correct port is selected
- Check battery level on Train Base
- Try using Power Control instead of Speed Control
- Ensure motor is properly connected to the port

### GUI Not Starting
- Verify all dependencies are installed: `pip install pybricksdev bleak`
- Check Python version (3.7+ recommended)
- On Linux, you may need additional Bluetooth permissions

## Technical Details

### Communication Protocol
- **Protocol**: LEGO Wireless Protocol v3.0 (LWP3)
- **Transport**: Bluetooth Low Energy (BLE)
- **Service UUID**: `00001623-1212-efde-1623-785feabcd123`
- **Characteristic UUID**: `00001624-1212-efde-1623-785feabcd123`

### Command Structure
All commands follow LWP3 format:
```
[Length] [Hub ID] [Message Type] [Port] [Startup/Completion] [Subcommand] [Parameters...]
```

### Threading Model
- Main thread: GUI (tkinter)
- Background thread: Async BLE communication
- Queue-based command system for thread-safe communication

## Safety Notes

⚠️ **Important Safety Information**:
- Always supervise motor operation
- Use Emergency Stop if motors behave unexpectedly
- Be careful with high speeds and power settings
- Ensure motors have clearance to move freely
- Monitor battery level to prevent unexpected shutdowns

## License

This project is for educational purposes as part of Projektwoche 2025.

## References

- [LEGO Wireless Protocol Documentation](https://lego.github.io/lego-ble-wireless-protocol-docs/)
- [Pybricksdev Documentation](https://github.com/pybricks/pybricksdev)
