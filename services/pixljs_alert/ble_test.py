import asyncio
from bleak import BleakClient, BleakError
from bleak import BleakScanner
import logging
import argparse
import time

logger = logging.getLogger(__name__)
UUID_NORDIC_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UUID_NORDIC_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
SERVICE_MODE = "0000183b-0000-1000-8000-00805f9b34fb"

def uart_data_received(sender, data):
    decoded = data.decode('UTF-8')
    print(decoded)


class ScanResult:
    device = None
    advertising_data = None

    def __init__(self, stop_event):
        self.stop_event = stop_event

    def callback(self, d, advertising_data):
        if d.name and "Pixl.js" in d.name and SERVICE_MODE in advertising_data.service_data:
            self.device = d
            self.advertising_data = advertising_data
            self.stop_event.set()


async def sendCommand(client, c):
    #print("Send command: %s" % c.decode("utf8"))
    while len(c) > 0:
        await client.write_gatt_char(UUID_NORDIC_TX, bytearray(c[0:20]), True)
        c = c[20:]
    await asyncio.sleep(0.125)  # wait for a response≈


async def main():
    while True:
        stop_event = asyncio.Event()
        # TODO: add something that calls stop_event.set()
        scan_result = ScanResult(stop_event)
        async with BleakScanner(scan_result.callback) as scanner:
            await stop_event.wait()
        mode = scan_result.advertising_data.service_data[SERVICE_MODE].decode("ascii")
        if mode == "install":
            try:
                async with BleakClient(scan_result.device) as client:
                    await client.start_notify(UUID_NORDIC_RX, uart_data_received)
                    now = time.time()
                    c = (b"\x03\x10if(Math.abs(getTime()-%f) > 300) { setTime(%f);E.setTimeZone(%d);}lastSeen=Date("
                         b");rssi=%f;\n") % ( now, now, -time.altzone // 3600, scan_result.advertising_data.rssi)
                    await sendCommand(client, c)
            except (BleakError,asyncio.TimeoutError) as e:
                logger.error("Abort communication with pixl.js", e)


logging.basicConfig(level=logging.INFO)
asyncio.run(main())
