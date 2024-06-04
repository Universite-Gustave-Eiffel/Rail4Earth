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

import socket
import time
import logging


def parse_csv(lines, start_index, end_index):
    # Extract the lines containing client information
    client_lines = lines[start_index:end_index]
    # Create a dictionary to store the hosts and their attributes
    hosts = []
    fields = lines[start_index - 1].split(",")
    for line in client_lines:
        # Split the line by commas
        parts = line.split(',')
        data = {}
        for index, field_name in enumerate(fields):
            data[field_name] = parts[index]
        hosts.append(data)
    return hosts


def parse_openvpn_status(log_text):
    # Split the log text into lines
    lines = [line.strip() for line in log_text.strip().split('\n')]
    # Find the start and end indexes for the client list section
    start_index = lines.index('ROUTING TABLE') + 2
    end_index = lines.index('GLOBAL STATS', start_index)
    # Create a dictionary to store the hosts and their attributes
    hosts = parse_csv(lines, start_index, end_index)
    # will add additional fields
    start_index = lines.index('OpenVPN CLIENT LIST') + 3
    end_index = lines.index('ROUTING TABLE', start_index)
    clients = parse_csv(lines, start_index, end_index)
    clients_map = {}
    for client in clients:
        if "Connected Since" in client and "Real Address" in client:
            clients_map[client["Real Address"]] = client
    return [host | clients_map[host["Real Address"]] for host in hosts]


class OpenVPNManagement:
    def __init__(self):
        self.s = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(5)
        self.logger = logging.getLogger(__name__)

    def receive(self, wait_time=0.1):
        time.sleep(wait_time)
        return self.s.recv(4096).decode("utf-8")

    def send(self, command):
        self.s.send(bytes(command, "utf-8"))

    def status(self):
        self.send("status\n")
        log_text = self.receive()
        return parse_openvpn_status(log_text)

    def connect(self, host: str, port: int, password: str):
        self.s.connect((host, port))
        sout = self.receive()
        if sout == 'ENTER PASSWORD:':
            self.send("%s\n" % password)
            sout = self.receive()
        if ">INFO:" not in sout:
            self.logger.error("INFO not found exiting")
            return False
        return True


if __name__ == "__main__":
    m = OpenVPNManagement()
    m.connect(input("OpenVPN host name: "), int(input("OpenVPN port: ")),
              input("OpenVPN password: "))
    print(m.status())
