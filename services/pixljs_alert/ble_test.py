import asyncio
from bleak import BleakClient, BleakError
from bleak import BleakScanner
import logging
import argparse
import time

logger = logging.getLogger(__name__)
UUID_NORDIC_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UUID_NORDIC_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


class ScanResult:
    device = None
    advertising_data = None

    def __init__(self, stop_event):
        self.stop_event = stop_event

    def callback(self, d, advertising_data):
        if d.name and "Pixl.js" in d.name:
            self.device = d
            self.advertising_data = advertising_data
            self.stop_event.set()


async def main():
    while True:
        stop_event = asyncio.Event()

        # TODO: add something that calls stop_event.set()
        mode = -1
        scan_result = ScanResult(stop_event)

        async with BleakScanner(scan_result.callback) as scanner:
            await stop_event.wait()
        print(scan_result.device)
        mode = scan_result.advertising_data.service_data['0000183b-0000-1000-8000-00805f9b34fb'].decode("ascii")
        print(mode)
        await asyncio.sleep(1.0)


logging.basicConfig(level=logging.INFO)
asyncio.run(main())
