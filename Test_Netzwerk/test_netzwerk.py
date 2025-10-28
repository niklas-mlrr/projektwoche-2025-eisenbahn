from bleak import BleakServer
from bleak.backends.characteristic import BleakGATTCharacteristic

import asyncio

SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
CHAR_UUID =    "abcdef01-1234-5678-1234-56789abcdef0"

class MyBLEServer(BleakServer):
    async def read_char(self, characteristic: BleakGATTCharacteristic):
        return b"READY\n"

    async def write_char(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        print("Received from Processing:", data.decode().strip())

async def main():
    server = MyBLEServer(
        service_uuid=SERVICE_UUID,
        characteristic_uuid=CHAR_UUID
    )
    async with server:
        print("BLE server running... press CTRL+C to stop")
        await asyncio.Future()

asyncio.run(main())
