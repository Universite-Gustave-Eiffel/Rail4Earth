import sys

from gpsdclient import GPSDClient
import argparse
import serial
import time
import zmq
import subprocess  # For executing a shell command
import datetime

TTYUSB_PATH = "/dev/serial/by-id/usb-Android_LE910C4-EU_0123456789ABCDEF-if05-port0"
PIN_CODE = "0000"

def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    """
    # Option for the number of packets as a function of
    param = '-c'
    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', param, '1', host]
    return subprocess.call(command) == 0


def send_command(ser, cmd, comment=""):
    if len(comment) == 0:
        print("SEND: " + cmd)
    else:
        print("%s: %s" % (comment, cmd))
    ser.write(bytes(cmd + "\r", encoding='ascii'))
    return ser.read(64).decode("ascii").strip()


def epoch_to_elasticsearch_date(epoch):
    """
    strict_date_optional_time in elastic search format is
    yyyy-MM-dd'T'HH:mm:ss.SSSZ
    @rtype: string
    """
    return datetime.datetime.utcfromtimestamp(epoch).strftime(
        "%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"



def lte_config(args):
    ####################
    # LTE Configuration and initialisation
    # Module active mode
    # AT+CFUN=1
    # Module in sleep mode
    # AT+CFUN=4
    #
    while True:
        try:
            with serial.Serial(TTYUSB_PATH, 115200, timeout=5) as ser:
                print("Waiting for response")
                while "OK" not in send_command(ser, "AT"):
                    print("Not ready..")
                    time.sleep(1)
                print("Should return READY")
                resp = send_command(ser, "AT+CPIN?")
                if "SIM PIN" in resp: #require pin code
                    resp = send_command(ser, "AT+CPIN=\"%s\"" % PIN_CODE)
                    if not "READY" in send_command(ser, "AT+CPIN?"):
                        # we should not try to send a new pin code as it could lock the sim card
                        while True:
                            print("Sim code rejected by the sim card, "
                                  "this service is in standby mode")
                            print(send_command(ser, "AT+CPIN?"))
                            time.sleep(5)
                print("Should return 3 or 4")
                resp = send_command(ser, "AT#USBCFG?")
                print(resp)
                while "USBCFG: 4" not in resp:
                    send_command(ser, "AT#USBCFG=4")
                    time.sleep(5)
                    send_command(ser, "AT#REBOOT")
                    time.sleep(35)
                    resp = send_command(ser, "AT#USBCFG?")
                    print(resp)
                print("Should return the APN details and IP address")
                resp = send_command(ser, "AT+CGDCONT?")
                print(resp)
                if args.apn not in resp:
                    print(send_command(ser, 'AT+CGDCONT=1,"%s","%s"' % (
                     'IPV4V6' if args.ipv6 else "IP", args.apn)))
                    print(send_command(ser, "AT#REBOOT"))
                    time.sleep(35)
                    continue
                print("Should return 0,1")
                resp = send_command(ser, "AT#ECM?")
                print(resp)
                while "0,1" not in resp:
                    print("Start connection")
                    print(send_command(ser, "AT#ECM=1,0"))
                    while "OK" not in send_command(ser, "AT"):
                        print("Not ready..")
                        time.sleep(1)
                    print("Should return 0,1")
                    resp = send_command(ser, "AT#ECM?")
                    print(resp)
                print("Should return 0,1 or 0,5")
                print(send_command(ser, "AT+CREG?"))
                return
        except serial.serialutil.SerialException as e:
            print("Got disconnected from serial reason:\n%s" % e,
                  file=sys.stderr)
            wait(35)


def wait(wait_time):
    cpt = wait_time
    while cpt > 0:
        cpt -= 1
        print("Waiting %d" % cpt)
        time.sleep(1)


def gps_config(args):
    while True:
        try:
            with serial.Serial(TTYUSB_PATH, 115200, timeout=5) as ser:
                print("Waiting for response")
                while "OK" not in send_command(ser, "AT"):
                    print("Not ready..")
                    time.sleep(1)
                print("READY")
                print(send_command(ser, "AT$GPSNMUN=2,1,1,1,1,1,1",
                             "Enabling unsolicited messages of GNSS data"))
                resp = send_command(ser, "AT$GPSP?")
                print(resp)
                while "GPSP: 1" not in resp:
                    resp = send_command(ser, "AT$GPSP=1", "Enable GPS")
                    print(resp)
                    if "ERROR" in resp:
                        print(send_command(ser, "AT$GPSRST", "Restore factory configuration"))
                        print(send_command(ser, "AT$GPSNVRAM=15,0", "Delete the GPS information stored in NVM"))
                        wait(10)
                        print(send_command(ser, "AT$GPSACP", "Check that after history buffer cleaning no GPS information is available"))
                        print(send_command(ser, "AT$GPSNMUN=2,1,1,1,1,1,1", "Enabling unsolicited messages of GNSS data"))
                        print(send_command(ser, "AT$GPSP=1", "Enable GPS"))
                        print(send_command(ser, "AT$GPSSAV", "save settings"))
                        wait(300)
                        resp = send_command(ser, "AT$GPSP?")
            return
        except serial.serialutil.SerialException as e:
            print("Got disconnected from serial reason:\n%s" % e,
                  file=sys.stderr)
            wait(35)


def clean_response(resp):
    rows = resp.split("\n")
    if len(rows) > 1:
        return rows[1].replace("\r", "")
    else:
        return resp.replace("\r", "").replace("\n", " ")


def main():
    parser = argparse.ArgumentParser(
        description='This program read json documents on zeromq channels'
                    ' and write in the specified folder', formatter_class=
        argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--apn", help="APN name", default="mmsbouygtel.com", type=str)
    parser.add_argument("--output_address",
                        help="Address for publishing JSON of GPS data",
                        default="tcp://*:10006")
    parser.add_argument("--ipv6",
                        help="Activate IPV6", default=False,
                        action="store_true")
    parser.add_argument("--wait_check",
                        help="Time to wait for next lte and GPS check",
                        default=300, type=int)
    parser.add_argument("--push_interval",
                        help="JSON GPS push interval in second",
                        default=1, type=int)
    parser.add_argument("-v", "--verbose",
                        help="Verbose mode", default=False,
                        action="store_true")
    parser.add_argument("--check_ip",
                        help="Check internet ip address",
                        default="8.8.8.8")

    args = parser.parse_args()
    args.running = True
    context = zmq.Context()
    socket_out = context.socket(zmq.PUB)
    socket_out.bind(args.output_address)
    last_push = 0
    try:
        while True:
            last_config_check = time.time()
            # configuration
            if not ping(args.check_ip):
                lte_config(args)
            gps_config(args)
            next_tpv = None
            with GPSDClient(host="127.0.0.1") as gpsd_client:
                while args.running:
                    try:
                        if time.time() >= last_push + args.push_interval:
                            # Get gps position
                            document = {"date": epoch_to_elasticsearch_date(
                                time.time())}
                            if next_tpv:
                                document["TPV"] = next_tpv
                                next_tpv = None
                            for result in gpsd_client.dict_stream(
                                    convert_datetime=False,
                                    filter=["TPV", "Sky", "GST", "Att", "Imu",
                                            "Toff", "PPS", "Osc"]):
                                if result["class"] == "TPV" and "TPV" in \
                                        document.keys():
                                    next_tpv = result
                                    break
                                document[result["class"]] = result
                            # Read stuff from telit
                            if "TPV" in document.keys() and "lat" in document["TPV"].keys():
                                # create special entry specifically for elastic search
                                document["location"] = {"lat": document["TPV"]["lat"],
                                                        "lon": document["TPV"]["lon"],
                                                        "z": document["TPV"]["alt"]}
                            try:
                                with serial.Serial(TTYUSB_PATH, 115200,
                                                   timeout=5) as ser:
                                    resp = send_command(ser, "AT#TEMPMON=1")
                                    if "TEMPMEAS" in resp and "," in resp:
                                        document[
                                            "temperature_module"] = clean_response(
                                            resp)
                                    resp = send_command(ser, "AT+CSQ")
                                    if "CSQ:" in resp:
                                        document["lte_strength"] = clean_response(resp)
                            except serial.serialutil.SerialException as e:
                                print("Got disconnected from serial reason:\n%s" % e,
                                      file=sys.stderr)
                            if args.verbose:
                                print(repr(document))
                            socket_out.send_json(document)
                            last_push = time.time()
                        while time.time() < min(last_push + args.push_interval,
                                                last_config_check+args.wait_check):
                            time.sleep(0.1)
                        if time.time() >= last_config_check+args.wait_check:
                            break  # go check GPS and LTE status
                    except Exception as e:
                        print(repr(e), file=sys.stderr)
                        time.sleep(5)
    finally:
        args.running = False


if __name__ == "__main__":
    main()
