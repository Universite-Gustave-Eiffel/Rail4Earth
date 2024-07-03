import asyncio
import os.path
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
from urllib.error import HTTPError
from urllib.request import urlopen
import fcntl
import socket
import struct
import re
import base64
from pijuice import PiJuice
import subprocess
from gpsdclient import GPSDClient

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
SERVICE_MODE = "0000183b-0000-1000-8000-00805f9b34fb"
SERVICE_ANSWER_SIZE = "0000180a-0000-1000-8000-00805f9b34fb"
SERVICE_VERSION = "0000180b-0000-1000-8000-00805f9b34fb"
FILE_URI = "file://"
logger = logging.getLogger(__name__)


def get_hw_address(interface_name):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack(
            '256s', bytes(interface_name, 'utf-8')[:15]))
        return ''.join('%02x' % b for b in info[18:24])
    except OSError:
        return ""


def slice_bytes(data: bytes, n: int):
    return (data[i:i + n] for i in range(0, len(data), n))


def time_to_iso(seconds_since_epoch):
    dt = datetime.datetime.utcfromtimestamp(seconds_since_epoch)
    # Convert the datetime object to an ISO-formatted string
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


class AgendaUpdateDaemon:
    def __init__(self, agenda_query_url: str, t: Event, agenda):
        self.agenda_query_url = agenda_query_url
        self.t = t
        self.agenda = agenda

    def run(self):
        while not self.t.is_set():
            if self.agenda_query_url.startswith(FILE_URI):
                filepath = self.agenda_query_url[len(FILE_URI):]
                if os.path.exists(filepath):
                    with open(filepath, "r") as fp:
                        self.agenda["days"] = json.load(fp)
                        self.agenda["last_fetch"] = time.time()
            else:
                try:
                    with urlopen(self.agenda_query_url) as response:
                        if response.status == 200:
                            try:
                                self.agenda["days"] = json.loads(response.read().decode())
                                self.agenda["last_fetch"] = time.time()
                            except json.JSONDecodeError as e:
                                logger.error("Error while decoding api response", e)
                except HTTPError as e:
                    logger.error("Error while fetching agenda", e)
            self.t.wait(1300)

def get_rpi_status():
    pi_juice = PiJuice(1, 0x14)
    battery = pi_juice.status.GetStatus()["data"]["battery"]
    vpn_out = subprocess.check_output(("ifconfig", "tun0"), timeout=1)
    vpn = "disconnected"
    for line in vpn_out.decode("utf8").splitlines():
        if "inet " in line:
            vpn = line.split()[1]
            break
    mic_out = subprocess.check_output(("arecord","-L"), timeout=1)
    mic = "no mic"
    for line in mic_out.decode("utf8").splitlines():
        if "plughw" in line:
            mic = line
            break
    with GPSDClient() as client:
        for result in client.dict_stream(convert_datetime=True, filter=["TPV"]):
            gpdsdout = "%.5s %.5s" % (result.get("lat", "n/a"), result.get("lon", "n/a"))
            break
    rpi_status = "Mic: %.25s\\nVpn: %.25s\\nBat: %.25s\\nGps: %.25s" % (mic, vpn, battery, gpdsdout)
    return rpi_status.encode("iso-8859-1")


class BleTrackingDaemon:
    known_devices = {}
    known_devices_last_report = {}
    reports = {}
    running = True

    def __init__(self, socket_out_lost, t: Event):
        self.socket_out_lost = socket_out_lost
        self.t = t

    def on_found_device(self, device):
        self.known_devices[device.address] = time.time()

    def stop(self, sig, frame):
        # stop main process
        self.t.set()
        logger.warning("Interrupted by %d, shutting down" % sig)
        self.running = False
        for k, v in self.known_devices.items():
            self.reports[k]["lastSeen"] = time_to_iso(v)
            self.socket_out_lost.send_json(self.reports[k])

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

    def __init__(self, stop_event, ble_tracking: BleTrackingDaemon):
        self.stop_event = stop_event
        self.ble_tracking = ble_tracking

    def callback(self, d, advertising_data):
        if d.name and "Pixl." in d.name and SERVICE_MODE in advertising_data.service_data:
            self.device = d
            self.ble_tracking.on_found_device(d)
            self.advertising_data = advertising_data
            self.stop_event.set()

    def uart_data_received(self, _: BleakGATTCharacteristic, data: bytearray):
        self.received_data.write(data)
        self.received_data_time = time.time()


def process_message(socket, config, agenda):
    event = socket.poll(timeout=config.zmq_timeout)
    if event == 0:
        return ""
    data = socket.recv_json()
    if data:
        today = datetime.date.today().isoformat()
        today_datetime = datetime.datetime.today()
        if today in agenda["days"]:
            today_agenda = agenda["days"][today]
            now = time.time()
            available = False
            for time_range in today_agenda["time_ranges"]:
                start_time = datetime.datetime.fromisoformat("%sT%s" % (today, time_range["start"]))
                end_time = datetime.datetime.fromisoformat("%sT%s" % (today, time_range["end"]))
                if start_time <= today_datetime <= end_time:
                    available = True
                    break
            if available:
                return (b"\x03\x10if(Math.abs(getTime()-%f) > 300) {"
                        b" setTime(%f);E.setTimeZone(%d);"
                        b"}"
                        b"onTrainCrossing(false);\n") % (now, now, -time.altzone // 3600)
    return ""


def fetch_script_source_and_version():
    uart_commands = []
    chunk_size = 1024
    source_version = None
    with open(os.path.join(os.path.dirname(__file__), "pixljs_ble.js"), "r") as f:
        code = f.read()
        g = re.search(r'CODE_VERSION=(\d+)', code)
        code_bytes = code.encode("iso-8859-1")
        if g:
            source_version = int(g.group(1))
        uart_commands.append("require(\"Storage\").write(\"%s\",atob(\"%s\"),%d,%d);" % (
            ".bootcde", base64.b64encode(code_bytes[:chunk_size]).decode("UTF8"), 0, len(code_bytes)))
        for i in range(chunk_size, len(code_bytes), chunk_size):
            uart_commands.append("require(\"Storage\").write(\"%s\",atob(\"%s\"),%d);" % (
                ".bootcde", base64.b64encode(code_bytes[i:i + chunk_size]).decode("UTF8"), i))
        code = "\n".join(uart_commands)+"\nload();\n"
    return code.encode("iso-8859-1"), source_version


async def main(config):
    # agenda example
    agenda = {
        "days": {},
        "last_fetch": 0}
    t = Event()
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(config.input_address)
    socket.subscribe("")
    socket_out = context.socket(zmq.PUB)
    socket_out.bind(config.output_address)
    socket_out_lost = context.socket(zmq.PUB)
    socket_out_lost.bind(config.output_address_lost)
    ble_tracking = BleTrackingDaemon(socket_out_lost, t)
    # json file can be local file ex: "file:///tmp/agenda.json"
    agenda_url = "https://dashboard.raw.noise-planet.org/api/agenda/" + get_hw_address("eth0")
    agenda_update = AgendaUpdateDaemon(agenda_url, t, agenda)
    # fetch expected pixl.js source code
    code, source_version = fetch_script_source_and_version()
    doing_upgrade = False
    # will kill when program end
    ble_tracking_thread = Thread(target=ble_tracking.run, daemon=True)
    ble_tracking_thread.start()
    agenda_update_thread = Thread(target=agenda_update.run, daemon=True)
    agenda_update_thread.start()
    signal.signal(signal.SIGTERM,
                  lambda sig, frame: ble_tracking.stop(sig, frame))
    signal.signal(signal.SIGINT,
                  lambda sig, frame: ble_tracking.stop(sig, frame))
    while not t.is_set():
        stop_event = asyncio.Event()
        scan_result = ScanResult(stop_event, ble_tracking)
        async with BleakScanner(scan_result.callback) as scanner:
            await asyncio.wait_for(stop_event.wait(), timeout=2.0)
        if SERVICE_MODE in scan_result.advertising_data.service_data:
            mode = scan_result.advertising_data.service_data[SERVICE_MODE].decode("ascii")
        else:
            mode = "normal"
        if SERVICE_ANSWER_SIZE in scan_result.advertising_data.service_data:
            answer_stack = int.from_bytes(scan_result.advertising_data.service_data[SERVICE_ANSWER_SIZE]
                                          , byteorder="big")
        else:
            answer_stack = 0
        if SERVICE_VERSION in scan_result.advertising_data.service_data:
            code_version = int.from_bytes(scan_result.advertising_data.service_data[SERVICE_VERSION]
                                      , byteorder="big")
        else:
            code_version = 0
        if mode == "install":
            print("Install mode connecting to Pixl.js")
            try:
                async with (BleakClient(scan_result.device) as client):
                    await client.start_notify(UART_TX_CHAR_UUID, scan_result.uart_data_received)
                    nus = client.services.get_service(UART_SERVICE_UUID)
                    rx_char = nus.get_characteristic(UART_RX_CHAR_UUID)
                    while client.is_connected and not t.is_set():
                        now = time.time()
                        rpi_status = get_rpi_status()
                        c = (b"\x03\x10if(Math.abs(getTime()-%f) > 300) { setTime("
                             b"%f);E.setTimeZone(%d);};\nrpi_status=\"%s\";lastSeen = Date();print(\"mode=\"+mode);\n"
                             ) % (now, now, -time.altzone // 3600, rpi_status)
                        scan_result.received_data = io.BytesIO()
                        for buffer in slice_bytes(c, rx_char.max_write_without_response_size):
                            await client.write_gatt_char(rx_char, buffer)
                        await asyncio.sleep(0.05)
                        return_messages = scan_result.received_data.getvalue().decode("iso-8859-1")
                        if "mode=1" not in return_messages:
                            print("Exit install mode %s" % return_messages)
                            break
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
                    while time.time() - scan_result.received_data_time < 1.0 and not t.is_set():
                        await asyncio.sleep(0.5)
                    try:
                        json_string = scan_result.received_data.getvalue().decode("utf8")
                        if "{" not in json_string:
                            continue
                        json_string = json_string[json_string.find("{"):json_string.rfind("}") + 1]
                        json_data = json.loads(json_string)
                        json_data["device"] = scan_result.device.address
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
            if source_version == code_version:
                c = process_message(socket, config, agenda)
            else:
                c = code
                doing_upgrade = True
                print("Sending new version of Pixl.js source code to %s" %
                      scan_result.device.address)
            tries = 0
            while c and not t.is_set():
                print("Try sending commands %.10s" % c)
                try:
                    async with BleakClient(scan_result.device) as client:
                        await client.start_notify(UART_TX_CHAR_UUID, scan_result.uart_data_received)
                        nus = client.services.get_service(UART_SERVICE_UUID)
                        rx_char = nus.get_characteristic(UART_RX_CHAR_UUID)
                        for buffer in slice_bytes(c, rx_char.max_write_without_response_size):
                            await client.write_gatt_char(rx_char, buffer)
                            while time.time() - scan_result.received_data_time < 0.1:
                                # wait for end transfer
                                await asyncio.sleep(0.005)
                        c = ""
                        try:
                            output = scan_result.received_data.getvalue().decode("iso-8859-1")
                            scan_result.received_data = io.BytesIO()
                            for line in output.splitlines():
                                print(line)
                        except UnicodeDecodeError as e:
                            pass
                        if doing_upgrade:
                            await asyncio.sleep(10.0)
                            doing_upgrade = False
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
