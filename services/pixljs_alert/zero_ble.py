import asyncio
from bleak import BleakClient, BleakError
from bleak import BleakScanner
import logging
import zmq
import argparse
import time
from colorama import Fore

UUID_NORDIC_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UUID_NORDIC_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
logger = logging.getLogger(__name__)


def uart_data_received(sender, data):
    decoded = data.decode('UTF-8')
    print(Fore.GREEN + decoded + Fore.RESET, end="")


def get_refresh_time_command():
    now = time.time()
    return b"\x03\x10if(Math.abs(getTime()-%f) > 300) { setTime(%f);E.setTimeZone(%d);load_parameters();installTimeouts(false);disabledScreen();}\n" % (
     now, now, -time.altzone // 3600)


def process_message(socket, config):
    logger.info("Waiting for next zmq message")
    event = socket.poll(timeout=config.reconnect_ble)
    if event == 0:
        return ""
    data = socket.recv_json()
    scores = data["scores"]
    if len(scores) > 0:
        print(repr(scores))
        return get_refresh_time_command()+b"\x03\x10onTrainCrossing(false);\n"
    return ""


"""
How to overwrite Flash:

command:
"\u0010reset();\n\u0010print()\n\u0010setTime(1681798003.809);E.setTimeZone(2)\n\u0010\u001b[1drequire(\"Storage\").write(\".bootcde\",\"// Disable logging events to screen\\nBluetooth.setConsole(1);\\n\",0,939);\n\u0010\u001b[2dload()\n\n"
"""



async def main(config):
    address = None
    while address is None:
        logger.info("Discover BLE devices..")
        devices = await BleakScanner.discover()
        for d in devices:
            if d.name and "Pixl.js" in d.name:
                address = d.address
                logger.info("Found Pixl.js " + repr(d))
                break
        if address is None:
            logger.info("Could not find Pixl.js device.")
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(config.input_address)
    socket.subscribe("")
    last_push = time.time()
    tries = 0
    # sync time of pixl.js
    c = get_refresh_time_command()
    while True:
        if not c:
            c = process_message(socket, config)
        if not c:
            c = get_refresh_time_command()
        logger.info("Reconnect to " + repr(address))
        try:
            async with BleakClient(address) as client:
                await client.start_notify(UUID_NORDIC_RX, uart_data_received)
                while True:
                    if len(c) > 0:
                        last_push = time.time()
                    while len(c) > 0:
                        await client.write_gatt_char(UUID_NORDIC_TX, bytearray(c[0:20]), True)
                        c = c[20:]
                    await asyncio.sleep(0.125)  # wait for a response
                    tries = 0
                    event = socket.poll(timeout=config.disconnect_ble_timeout)
                    if event == 0:
                        # Timeout, disconnect
                        break
                    else:
                        c = process_message(socket, config)
                        if len(c) == 0 and time.time() - last_push > config.disconnect_ble_timeout:
                            # Timeout, disconnect
                            print("Disconnect bluetooth..")
                            break
        except BleakError as e:
            tries += 1
            # try to reconnect if Bleak throw an error
            if tries < 10:
                await asyncio.sleep(0.125)  # wait for a response
            else:
                print(repr(e))
                break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This program read trigger tags from zeromq and display summary on '
                                                 ' pixl.js device',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input_address", help="Address for zero_trigger tags", default="tcp://127.0.0.1:10002")
    parser.add_argument("--disconnect_ble_timeout", help="Disconnect ble if no new message in this delay in"
                                                         " milliseconds", default=10000, type=int)
    parser.add_argument("--reconnect_ble", help="Reconnect to pixl.js at "
                                                "least each milliseconds",
                        default=300000, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(args))
