"""
Direct Bleak implementation for LEGO Train Base Color Sensor
This bypasses pybricksdev to ensure BLE notifications work properly
"""

import asyncio
from bleak import BleakScanner, BleakClient

LWP3_SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"
LWP3_CHAR_UUID = "00001624-1212-efde-1623-785feabcd123"
TARGET_NAME = "Train Base"

# Color stabilization settings
COLOR_HISTORY = []
COLOR_HISTORY_MAX = 5  # Number of readings to keep
COLOR_STABILITY_THRESHOLD = 3  # Minimum occurrences to confirm color
LAST_STABLE_COLOR = -1

def make_port_input_format_setup(port_id: int, mode: int, delta: int = 1, notify: bool = True) -> bytes:
    """Setup port input format [0x41]"""
    payload = bytes([
        0x00, 0x41, port_id & 0xFF, mode & 0xFF,
        delta & 0xFF, 0x00, 0x00, 0x00,  # delta as int32 little-endian
        1 if notify else 0
    ])
    return bytes([len(payload) + 1]) + payload

def stabilize_color(color_value: int):
    """
    Stabilize color readings by requiring multiple consistent readings.
    Returns the stable color value, or None if not yet stable.
    """
    global COLOR_HISTORY, LAST_STABLE_COLOR
    
    # Add to history
    COLOR_HISTORY.append(color_value)
    
    # Keep only recent readings
    if len(COLOR_HISTORY) > COLOR_HISTORY_MAX:
        COLOR_HISTORY.pop(0)
    
    # Need enough samples
    if len(COLOR_HISTORY) < COLOR_STABILITY_THRESHOLD:
        return None
    
    # Count occurrences of each color in recent history
    from collections import Counter
    color_counts = Counter(COLOR_HISTORY)
    
    # Get most common color and its count
    most_common_color, count = color_counts.most_common(1)[0]
    
    # Only update if we have enough consistent readings
    if count >= COLOR_STABILITY_THRESHOLD:
        # Only return if it's different from last stable color
        if most_common_color != LAST_STABLE_COLOR:
            LAST_STABLE_COLOR = most_common_color
            return most_common_color
    
    return None

async def main():
    print("=" * 60)
    print("LEGO Train Base Color Sensor - Direct Bleak Implementation")
    print("=" * 60)
    print(f"\nScanning for '{TARGET_NAME}'...")
    
    devices = await BleakScanner.discover(timeout=10.0)
    
    device = None
    for d in devices:
        if d.name == TARGET_NAME:
            device = d
            print(f"✓ Found: {d.name} (Address: {d.address})")
            break
    
    if not device:
        print(f"✗ '{TARGET_NAME}' not found!")
        print("\nAvailable devices:")
        for d in devices:
            print(f"  - {d.name} ({d.address})")
        return
    
    print(f"\nConnecting to {device.name}...")
    
    async with BleakClient(device.address) as client:
        print(f"✓ Connected: {client.is_connected}")
        
        # Callback for notifications
        def notification_handler(sender, data: bytes):
            print(f"\nRX: {data.hex()}")
            
            # Decode message type
            if len(data) < 3:
                return
            
            msg_type = data[2]
            
            # HUB_ATTACHED_IO (0x04) - shows what's connected
            if msg_type == 0x04 and len(data) >= 5:
                port = data[3]
                event = data[4]
                if event == 1 and len(data) >= 7:  # ATTACHED
                    io_type = (data[6] << 8) | data[5]
                    print(f"  → HUB_ATTACHED_IO: Port 0x{port:02X} ({port}) has device type 0x{io_type:04X}")
                    if io_type == 0x0025:
                        print(f"     ✓ This is a Color & Distance Sensor!")
            
            # PORT_VALUE_SINGLE (0x45) - color sensor data
            elif msg_type == 0x45 and len(data) >= 5:
                port = data[3]
                # For Train Base color sensor: 5-byte message, color at byte 4 (last byte)
                # Format: [05, 00, 45, port, color_value]
                color_value = data[4]
                
                # Apply stabilization filter (only for valid colors)
                if 0 <= color_value <= 10:
                    stable_color = stabilize_color(color_value)
                    if stable_color is not None:
                        colors = ["Black", "Pink", "Purple", "Blue", "Light Blue", 
                                 "Cyan", "Green", "Yellow", "Orange", "Red", "White"]
                        print(f"\n  → PORT_VALUE_SINGLE: Port 0x{port:02X} ({port})")
                        print(f"     🎨 STABLE Color: {colors[stable_color]} (value={stable_color})")
                elif color_value == 0xFF:
                    # Don't show "no color" messages (too noisy)
                    pass
                else:
                    print(f"  → PORT_VALUE_SINGLE: Port 0x{port:02X} ({port}), unknown value={color_value}")
            
            # PORT_VALUE (0x43) - alternative format
            elif msg_type == 0x43 and len(data) >= 5:
                port = data[3]
                print(f"  → PORT_VALUE: Port 0x{port:02X} ({port}), data={data[4:].hex()}")
            
            # Other messages
            else:
                msg_names = {
                    0x01: "HUB_PROPERTIES",
                    0x02: "HUB_ACTIONS",
                    0x82: "PORT_OUTPUT_CMD_FEEDBACK",
                }
                msg_name = msg_names.get(msg_type, f"UNKNOWN(0x{msg_type:02X})")
                print(f"  → {msg_name}")
        
        # Enable notifications
        print("\nEnabling BLE notifications...")
        await client.start_notify(LWP3_CHAR_UUID, notification_handler)
        print("✓ Notifications enabled")
        
        # Wait a moment for any initial messages
        await asyncio.sleep(0.5)
        
        # Try multiple common ports for color sensor
        print("\n" + "=" * 60)
        print("Attempting to enable color sensor on common ports...")
        print("=" * 60)
        
        test_ports = [0x12, 0x00, 0x01, 0x02, 0x03, 0x13]
        
        for port in test_ports:
            print(f"\nTrying port 0x{port:02X} ({port})...")
            cmd = make_port_input_format_setup(port, mode=0, delta=1, notify=True)
            print(f"  TX: {cmd.hex()}")
            await client.write_gatt_char(LWP3_CHAR_UUID, cmd, response=False)
            await asyncio.sleep(0.3)  # Wait for response
        
        print("\n" + "=" * 60)
        print("Setup complete! Monitoring for color sensor data...")
        print("Place colored objects in front of the sensor.")
        print("Press Ctrl+C to stop")
        print("=" * 60 + "\n")
        
        # Keep running and monitoring
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopping...")
        
        # Clean up
        await client.stop_notify(LWP3_CHAR_UUID)
        print("✓ Disconnected")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
