import asyncio
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak import BleakClient, BleakError
from bleak import BleakScanner
import logging
import zmq
import argparse
import time
import io
import json

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
SERVICE_MODE = "0000183b-0000-1000-8000-00805f9b34fb"
SERVICE_ANSWER_SIZE = "0000180a-0000-1000-8000-00805f9b34fb"
logger = logging.getLogger(__name__)

def uart_data_received(_: BleakGATTCharacteristic, data: bytearray):
    decoded = data.decode('UTF-8')
    logger.info(decoded)


def slice_bytes(data: bytes, n: int):
    return (data[i:i+n] for i in range(0, len(data), n))

class ScanResult:
    device = None
    advertising_data = None
    received_data = io.BytesIO()

    def __init__(self, stop_event):
        self.stop_event = stop_event

    def callback(self, d, advertising_data):
        if d.name and "Pixl.js" in d.name and SERVICE_MODE in advertising_data.service_data:
            self.device = d
            self.advertising_data = advertising_data
            self.stop_event.set()

    def uart_data_received(self, _: BleakGATTCharacteristic, data: bytearray):
        self.received_data.write(data)

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
    socket_out = context.socket(zmq.PUB)
    socket_out.bind(config.output_address)
    while True:
        stop_event = asyncio.Event()
        scan_result = ScanResult(stop_event)
        async with BleakScanner(scan_result.callback) as scanner:
            await stop_event.wait()
        mode = scan_result.advertising_data.service_data[SERVICE_MODE].decode("ascii")
        answer_stack = int.from_bytes(scan_result.advertising_data.service_data[SERVICE_ANSWER_SIZE]
                                      , byteorder="big")
        if mode == "install":
            try:
                async with BleakClient(scan_result.device) as client:
                    await client.start_notify(UART_TX_CHAR_UUID, uart_data_received)
                    nus = client.services.get_service(UART_SERVICE_UUID)
                    rx_char = nus.get_characteristic(UART_RX_CHAR_UUID)
                    now = time.time()
                    c = (b"\x03\x10if(Math.abs(getTime()-%f) > 300) { setTime(%f);E.setTimeZone(%d);}lastSeen=Date();rssi=%f;\n") % ( now, now, -time.altzone // 3600, scan_result.advertising_data.rssi)
                    for buffer in slice_bytes(c, rx_char.max_write_without_response_size):
                        await client.write_gatt_char(rx_char, buffer, False)
            except (BleakError, asyncio.TimeoutError) as e:
                logger.error("Abort communication with pixl.js", e)
        elif answer_stack > 0:
            # fetch answer json
            try:
                async with BleakClient(scan_result.device) as client:
                    await client.start_notify(UART_TX_CHAR_UUID, scan_result.uart_data_received)
                    nus = client.services.get_service(UART_SERVICE_UUID)
                    rx_char = nus.get_characteristic(UART_RX_CHAR_UUID)
                    c = b"\x03\x10E.pipe(formStack[0], Bluetooth);\n"
                    scan_result.received_data = io.BytesIO()
                    for buffer in slice_bytes(c, rx_char.max_write_without_response_size):
                        await client.write_gatt_char(rx_char, buffer, False)
                    await asyncio.sleep(0.5)
                    try:
                        json_data = json.loads(scan_result.received_data.getvalue().decode("utf8"))
                        # remove item from pixl.js device
                        for buffer in slice_bytes("\x03\x10formStack.pop(0)\n", rx_char.max_write_without_response_size):
                            await client.write_gatt_char(rx_char, buffer, False)
                        socket_out.send_json(json_data)
                    except json.JSONDecodeError as e:
                        logger.error("Error while fetching user response", e)
            except (BleakError, asyncio.TimeoutError) as e:
                logger.error("Send data error", e)
        else:
            c = process_message(socket, config)
            tries = 0
            while c:
                try:
                    async with BleakClient(scan_result.device) as client:
                        await client.start_notify(UART_TX_CHAR_UUID, uart_data_received)
                        nus = client.services.get_service(UART_SERVICE_UUID)
                        rx_char = nus.get_characteristic(UART_RX_CHAR_UUID)
                        for buffer in slice_bytes(c, rx_char.max_write_without_response_size):
                            await client.write_gatt_char(rx_char, buffer, False)
                        c = ""
                except (BleakError, asyncio.TimeoutError) as e:
                    tries += 1
                    logger.error("Send data error", e)
                    if tries > config.max_try:
                        break
                    else:
                        await asyncio.sleep(0.5)
                # E.pipe(\"mode=\"+mode, Bluetooth);

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This program read trigger tags from zeromq and display summary on '
                                                 ' pixl.js device',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input_address", help="Address for zero_trigger tags", default="tcp://127.0.0.1:10002")
    parser.add_argument("--zmq_timeout", help="Wait for zmq message for x milliseconds",
                        default=1000, type=int)
    parser.add_argument("--max_try", help="Maximum sending data try",
                        default=10, type=int)
    parser.add_argument("--output_address", help="Address for publishing JSON of pixl.js answers",
                        default="tcp://*:10010")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(args))
