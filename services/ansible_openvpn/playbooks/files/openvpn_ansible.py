#!/usr/bin/env python

#  BSD 3-Clause License
#
#  Copyright (c) 2023, University Gustave Eiffel
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#   Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#   Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#  BSD 3-Clause License
#
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#
#
#
import os
import argparse
import json
import socket
import sys
import time

# This script convert OpenVPN status into a dynamic Ansible inventory
# It can use local /var/log/openvpn/openvpn-status.log file
# or OpenVPN telnet management console


def receive(s, wait_time=0.1):
    time.sleep(wait_time)
    return s.recv(4096).decode("utf-8")


def send(s, command):
    s.send(bytes(command, "utf-8"))


def parse_openvpn_status(log_text):
    # Split the log text into lines
    lines = [line.strip() for line in log_text.strip().split('\n')]
    # Find the start and end indexes for the client list section
    start_index = lines.index('ROUTING TABLE') + 2
    end_index = lines.index('GLOBAL STATS', start_index)
    # Extract the lines containing client information
    client_lines = lines[start_index:end_index]
    # Create a dictionary to store the hosts and their attributes
    hosts = []
    fields = lines[start_index-1].split(",")
    for line in client_lines:
        # Split the line by commas
        parts = line.split(',')
        data = {}
        for index, field_name in enumerate(fields):
            data[field_name] = parts[index]
        hosts.append(data)
    return hosts


def main():
    arg_parser = argparse.ArgumentParser(
        description=__doc__,
        prog=__file__
    )
    arg_parser.add_argument(
        '--pretty',
        action='store_true',
        default=False,
        help="Pretty print JSON"
    )
    mandatory_options = arg_parser.add_mutually_exclusive_group()
    mandatory_options.add_argument(
        '--list',
        action='store',
        nargs="*",
        default="dummy",
        help="Show JSON of all managed hosts"
    )
    mandatory_options.add_argument(
        '--host',
        action='store',
        help="Display vars related to the host"
    )
    args = arg_parser.parse_args()
    # Replace this with the path to your openvpn-status.log file
    log_text = ""

    if "OPENVPN_STATUS_PATH" in os.environ and \
            os.environ["OPENVPN_STATUS_PATH"]:
        if not os.path.exists(os.environ["OPENVPN_STATUS_PATH"]):
            print("Could not find "+os.environ["OPENVPN_STATUS_PATH"] +
                  " file, abort..", file=sys.stderr)
            exit(-1)
        with open(os.environ["OPENVPN_STATUS_PATH"], 'r') as file:
            log_text = file.read()
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((os.environ.get("MANAGEMENT_OPENVPN_HOST", "localhost"),
                   int(os.environ.get("MANAGEMENT_OPENVPN_PORT", "5555"))))
        sout = receive(s)
        if sout == 'ENTER PASSWORD:':
            send(s, os.environ["MANAGEMENT_OPENVPN_PASSWORD"] + "\n")
            sout = receive(s)
        if ">INFO:" not in sout:
            print(sout, file=sys.stderr)
            print("INFO not found exiting", file=sys.stderr)
            exit(-1)
        send(s, "status\n")
        log_text = receive(s)

    hosts = parse_openvpn_status(log_text)

    data = {
        common_name: {
            'hosts': {host["Virtual Address"]: None for host in hosts
                      if common_name in host["Common Name"]}
        }
        for common_name in set([host["Common Name"].replace("-", "_")
                                for host in hosts])
    }
    if args.host:
        print(json.dumps({}))
    elif len(args.list) >= 0:
        print(json.dumps(data, indent=args.pretty))
    else:
        raise ValueError("Expecting either --host $HOSTNAME or --list")


if __name__ == "__main__":
    main()
