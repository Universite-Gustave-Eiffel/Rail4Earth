import asyncio
from threading import Thread
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak import BleakClient, BleakError
from bleak import BleakScanner
import logging
import zmq
import argparse
import time
import io
import json
import datetime
import signal
from threading import Event

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
    return (data[i:i + n] for i in range(0, len(data), n))


def time_to_iso(seconds_since_epoch):
    dt = datetime.datetime.utcfromtimestamp(seconds_since_epoch)
    # Convert the datetime object to an ISO-formatted string
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


class BleTracking:
    known_devices = {}
    known_devices_last_report = {}
    reports = {}
    running = True

    def __init__(self, socket_out_lost, t: Event):
        self.socket_out_lost = socket_out_lost
        self.t = t

    def on_found_device(self, device):
        self.known_devices[device.name] = time.time()

    def stop(self, sig, frame):
        logger.warning("Interrupted by %d, shutting down" % sig)
        self.running = False
        for k, v in self.known_devices.items():
            self.reports[k]["lastSeen"] = time_to_iso(v)
            self.socket_out_lost.send_json(self.reports[k])
        # stop main process
        self.t.set()

    def run(self):
        self.t.wait(2)
        while self.running:
            # look for missing devices
            for k, v in self.known_devices_last_report.items():
                if k not in self.known_devices.keys():
                    self.reports[k]["lastSeen"] = time_to_iso(v)
                    self.socket_out_lost.send_json(self.reports[k])
                    print("Device %s lost since %s" % (k, time_to_iso(v)))
            # look for new devices
            for k, v in self.known_devices.items():
                if k not in self.known_devices_last_report.keys():
                    print("New Device %s since %s" % (k, time_to_iso(v)))
                    self.reports[k] = {"firstSeen": time_to_iso(v), "device": k}
            self.known_devices_last_report = self.known_devices
            self.known_devices = {}
            self.t.wait(300)
        print("Exiting daemon")

class ScanResult:
    device = None
    advertising_data = None
    received_data = io.BytesIO()
    received_data_time = time.time()

    def __init__(self, stop_event, ble_tracking: BleTracking):
        self.stop_event = stop_event
        self.ble_tracking = ble_tracking

    def callback(self, d, advertising_data):
        if d.name and "Pixl.js" in d.name and SERVICE_MODE in advertising_data.service_data:
            self.device = d
            self.ble_tracking.on_found_device(d)
            self.advertising_data = advertising_data
            self.stop_event.set()

    def uart_data_received(self, _: BleakGATTCharacteristic, data: bytearray):
        self.received_data.write(data)
        self.received_data_time = time.time()


def process_message(socket, config):
    event = socket.poll(timeout=config.zmq_timeout)
    if event == 0:
        return ""
    data = socket.recv_json()
    scores = data["scores"]
    if len(scores) > 0:
        now = time.time()
        return (b"\x03\x10if(Math.abs(getTime()-%f) > 300) {"
                b" setTime(%f);E.setTimeZone(%d);"
                b"}"
                b"onTrainCrossing(false);\n") % (now, now, -time.altzone // 3600)
    return ""


async def main(config):
    t = Event()
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(config.input_address)
    socket.subscribe("")
    socket_out = context.socket(zmq.PUB)
    socket_out.bind(config.output_address)
    socket_out_lost = context.socket(zmq.PUB)
    socket_out_lost.bind(config.output_address_lost)
    ble_tracking = BleTracking(socket_out_lost, t)
    # will kill when program end
    ble_tracking_thread = Thread(target=ble_tracking.run, daemon=True)
    ble_tracking_thread.start()
    signal.signal(signal.SIGTERM,
                  lambda sig, frame: ble_tracking.stop(sig, frame))
    signal.signal(signal.SIGINT,
                  lambda sig, frame: ble_tracking.stop(sig, frame))
    while not t.is_set():
        stop_event = asyncio.Event()
        scan_result = ScanResult(stop_event, ble_tracking)
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
                    c = (
                            b"\x03\x10if(Math.abs(getTime()-%f) > 300) { setTime(%f);E.setTimeZone(%d);}lastSeen=Date();rssi=%f;\n") % (
                        now, now, -time.altzone // 3600, scan_result.advertising_data.rssi)
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
                    # wait for end of data arrival
                    await asyncio.sleep(0.5)
                    while time.time() - scan_result.received_data_time < 1.0:
                        await asyncio.sleep(0.5)
                    try:
                        json_string = scan_result.received_data.getvalue().decode("utf8")
                        if "{" not in json_string:
                            continue
                        json_string = json_string[json_string.find("{"):json_string.rfind("}") + 1]
                        json_data = json.loads(json_string)
                        json_data["device"] = scan_result.device.name
                        # remove item from pixl.js device
                        for buffer in slice_bytes(
                                b"\x03\x10formStack.pop(0);updateAdvertisement();\n",
                                rx_char.max_write_without_response_size):
                            await client.write_gatt_char(rx_char, buffer, False)
                        logger.info("Send json to zmq\n%s" % json_data)
                        socket_out.send_json(json_data)
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.error("Error while decoding %s" %
                                     json_string, e)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='This program read trigger tags from zeromq and display summary on '
                    ' pixl.js device',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input_address", help="Address for zero_trigger tags",
                        default="tcp://127.0.0.1:10003")
    parser.add_argument("--zmq_timeout", help="Wait for zmq message for x milliseconds",
                        default=1000, type=int)
    parser.add_argument("--max_try", help="Maximum sending data try",
                        default=10, type=int)
    parser.add_argument("--output_address", help="Address for publishing JSON of pixl.js answers",
                        default="tcp://*:10010")
    parser.add_argument("--output_address_lost", help="Address for publishing pixl.js lost event",
                        default="tcp://*:10011")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(parser.parse_args()))
