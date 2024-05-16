import asyncio
from bleak import BleakClient, BleakError
from bleak import BleakScanner
import logging
import zmq
import argparse
import time

UUID_NORDIC_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UUID_NORDIC_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
SERVICE_MODE = "0000183b-0000-1000-8000-00805f9b34fb"
logger = logging.getLogger(__name__)

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


def process_message(socket, config):
    event = socket.poll(timeout=config.zmq_timeout)
    if event == 0:
        return ""
    data = socket.recv_json()
    scores = data["scores"]
    if len(scores) > 0:
        return b"\x03\x10onTrainCrossing(false);\n"
    return ""


async def main(config):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(config.input_address)
    socket.subscribe("")
    while True:
        stop_event = asyncio.Event()
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
                    while len(c) > 0:
                        await client.write_gatt_char(UUID_NORDIC_TX, bytearray(c[0:20]), True)
                        c = c[20:]
            except (BleakError,asyncio.TimeoutError) as e:
                logger.error("Abort communication with pixl.js", e)
        else:
            c = process_message(socket, config)
            tries = 0
            while c:
                try:
                    async with BleakClient(scan_result.device) as client:
                        await client.start_notify(UUID_NORDIC_RX, uart_data_received)
                        while len(c) > 0:
                            await client.write_gatt_char(UUID_NORDIC_TX, bytearray(c[0:20]), True)
                            c = c[20:]
                except (BleakError, asyncio.TimeoutError) as e:
                    tries += 1
                    logger.error("Send data error", e)
                    if tries > config.max_try:
                        break
                    else:
                        await asyncio.sleep(0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This program read trigger tags from zeromq and display summary on '
                                                 ' pixl.js device',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input_address", help="Address for zero_trigger tags", default="tcp://127.0.0.1:10002")
    parser.add_argument("--zmq_timeout", help="Wait for zmq message for x milliseconds",
                        default=1000, type=int)
    parser.add_argument("--max_try", help="Maximum sending data try",
                        default=10, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(args))
