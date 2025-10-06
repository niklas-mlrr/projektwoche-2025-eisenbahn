import asyncio
from pybricksdev.ble import BLEConnection, find_device

# Build LWP3 Port Output Command: StartSpeedForTime (0x81 / 0x09)
def make_start_speed_for_time(port_id: int, time_ms: int, speed: int,
                              max_power: int = 100, end_state: int = 127, use_profile: int = 0) -> bytes:
    """Creates an LWP3 StartSpeedForTime message for the given port.

    Args:
        port_id: Port number (e.g., 0x00 or 0x01 on DUPLO Train base)
        time_ms: Duration in milliseconds
        speed: -100..100
        max_power: 0..100
        end_state: 0=float, 126=hold, 127=brake
        use_profile: 0 or 1
    """
    if speed < -100 or speed > 100:
        raise ValueError("speed must be in [-100..100]")
    if max_power < 0 or max_power > 100:
        raise ValueError("max_power must be in [0..100]")
    time_l = time_ms & 0xFF
    time_h = (time_ms >> 8) & 0xFF
    # Frame without length byte
    payload = bytes([
        0x00,             # Hub ID (0)
        0x81,             # Message Type: Port Output Command
        port_id & 0xFF,   # Port
        0x11,             # Startup/Completion: execute immediately + feedback
        0x09,             # Subcommand: StartSpeedForTime
        time_l, time_h,   # time (le16)
        (speed + 256) % 256,  # int8
        max_power & 0xFF,
        end_state & 0xFF,
        use_profile & 0xFF,
    ])
    length = len(payload) + 1
    return bytes([length]) + payload

# Build LWP3 Port Output Command: StartSpeed (0x81 / 0x07)
def make_start_speed(port_id: int, speed: int, max_power: int = 100, use_profile: int = 0) -> bytes:
    if speed < -100 or speed > 100:
        raise ValueError("speed must be in [-100..100]")
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x07,
        (speed + 256) % 256,
        max_power & 0xFF,
        use_profile & 0xFF,
    ])
    return bytes([len(payload) + 1]) + payload

# Build LWP3 Port Output Command: WriteDirectModeData (0x81 / 0x51)
def make_write_direct_mode_data(port_id: int, mode: int, *data: int) -> bytes:
    payload = bytes([
        0x00, 0x81, port_id & 0xFF, 0x11, 0x51,
        mode & 0xFF,
    ] + [b & 0xFF for b in data])
    return bytes([len(payload) + 1]) + payload

async def main():
    # Scan for hubs
    print("Scanning for hubs...")
    # LEGO Wireless Protocol v3 service UUID used by Powered Up / DUPLO
    # Use LEGO LWP3 Hub Service UUID (not the Pybricks UART service)
    LWP3_SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"
    # Name filter: discovered advertised name for DUPLO Hub No.5
    TARGET_NAME = "Train Base"
    # Retry scan to reduce transient timeout errors
    max_attempts = 3
    scan_timeout = 30.0
    device = None
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Attempt {attempt}/{max_attempts}: scanning (timeout={scan_timeout}s, service filter=LWP3)...")
            device = await find_device(name=TARGET_NAME, service=LWP3_SERVICE_UUID, timeout=scan_timeout)
            break
        except asyncio.TimeoutError:
            print("Scan timed out. Ensure the hub is ON and advertising (blinking), then retrying...")
            if attempt < max_attempts:
                await asyncio.sleep(1.0)
            else:
                print("Service-filtered scan failed. Falling back to Bleak name match...")

    # Fallback: try BleakScanner by name if service-filtered scan did not find the device
    if device is None:
        try:
            from bleak import BleakScanner
            print("Fallback: scanning with Bleak for name 'Train Base'...")
            devices = await BleakScanner.discover(timeout=8.0)
            for d in devices:
                if getattr(d, 'name', None) == "Train Base":
                    device = d
                    print(f"Selected device from Bleak: name={d.name} address={getattr(d,'address',None)}")
                    break
            if device is None:
                raise asyncio.TimeoutError("Could not find 'Train Base' via Bleak fallback")
        except Exception as e:
            print(f"Bleak fallback failed: {e}")
            raise

    print(f"Found device: {device}")

    # Connect to hub
    # LEGO LWP3 uses a single data characteristic for RX/TX
    LWP3_CHAR_UUID = "00001624-1212-efde-1623-785feabcd123"
    conn = BLEConnection(
        char_rx_UUID=LWP3_CHAR_UUID,
        char_tx_UUID=LWP3_CHAR_UUID,
        max_data_size=20,
    )
    await conn.connect(device)
    print("Connected!")

    # Log any incoming notifications for debugging
    try:
        def _log_data(sender, data: bytes):
            print(f"RX from {sender}: {data.hex()}")
        conn.data_handler = _log_data  # type: ignore[attr-defined]
    except Exception:
        pass

    # Attempt to run motor forward on likely DUPLO motor ports
    for port in (0x00, 0x01, 0x02):
        try:
            print(f"Trying port 0x{port:02X} with WriteDirectModeData speed 50...")
            # Mode 0x00 is commonly the speed mode for simple motors
            await conn.write(make_write_direct_mode_data(port_id=port, mode=0x00, *[(50 + 256) % 256]))
            await asyncio.sleep(2.0)
            # Stop
            await conn.write(make_write_direct_mode_data(port_id=port, mode=0x00, *[0]))

            print("Trying StartSpeed 50 then stop...")
            await conn.write(make_start_speed(port_id=port, speed=50, max_power=100, use_profile=0))
            await asyncio.sleep(2.0)
            await conn.write(make_start_speed(port_id=port, speed=0, max_power=100, use_profile=0))

            print("Trying StartSpeedForTime 2s at 50%...")
            msg = make_start_speed_for_time(port_id=port, time_ms=2000, speed=50, max_power=100, end_state=127, use_profile=0)
            await conn.write(msg)
            await asyncio.sleep(2.2)

            print("Motor command variants sent on this port.")
            break
        except Exception as e:
            print(f"Motor command on port 0x{port:02X} failed: {e}")

    # Disconnect
    await conn.disconnect()
    print("Disconnected!")


if __name__ == "__main__":
    asyncio.run(main())
