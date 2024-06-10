#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
BSD 3-Clause License

Copyright (c) 2022, Université Gustave-Eiffel
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import datetime
import os.path
import struct
import time
from noisesensor.spectrumchannel import SpectrumChannel, compute_leq
import sys
import argparse
import zmq
import numpy as np
import json

# do not accept auto calibration if std is superior to this value
AC_STANDARD_DEVIATION = 0.2
# Wait for at least this time before accepting the calibration value
AC_STABILISATION_TIME = 5.0
# Ratio in power between 1000 Hz level and global LZeq
AC_1000HZ_MINIMUM_RATIO = 0.9


def epoch_to_elasticsearch_date(epoch):
    """
    strict_date_optional_time in elastic search format is
    yyyy-MM-dd'T'HH:mm:ss.SSSZ
    @rtype: string
    """
    return datetime.datetime.utcfromtimestamp(epoch).strftime(
        "%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def generate_stack_dict(filter_config, config):
    stack_dict = {"LZeq": []}
    fields = []
    if "bandpass" in filter_config:
        fields = ["%gHZ" % bp["nominal_frequency"] for bp in
                  filter_config["bandpass"]]
    if "a_weighting" in filter_config:
        stack_dict["LAeq"] = []
    if "c_weighting" in filter_config:
        stack_dict["LCeq"] = []
    for field in fields:
        stack_dict[field] = []
    stack_dict["timestamps"] = []
    stack_dict["sensitivity"] = config.sensitivity
    return fields, stack_dict


class AcousticIndicatorsProcessor:
    def __init__(self, config):
        self.config = config
        self.epoch = datetime.datetime.utcfromtimestamp(0)
        self.total_read = 0
        self.filter_config = json.load(open(self.config.configuration_file,
                                            "r"))
        # for old configuration, or to fetch a default calibration value
        if (not os.path.exists(self.config.data_file)
                and "sensitivity" in self.filter_config["configuration"]):
            self.config.sensitivity = self.filter_config["configuration"]["sensitivity"]
            self.save_data()  # write on application data file
        self.channel = SpectrumChannel(self.filter_config, use_scipy=False,
                                       use_cascade=True)
        # load application data
        self.load_data()
        fields, stack_dict = generate_stack_dict(self.filter_config, self.config)
        self.fields = fields
        self.current_stack_dict = stack_dict
        self.stack_count = 0
        self.socket = None
        self.socket_out = None
        self.auto_calibration_stack = []
        self.auto_calibration_time = []
        self.auto_calibration_field_index = self.fields.index("1000HZ")

    def init_socket(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.SUB)
        self.socket.connect(self.config.input_address)
        self.socket.subscribe("")
        self.socket_out = context.socket(zmq.PUB)
        self.socket_out.bind(self.config.output_address)

    def auto_calibration_check(self, l1000_hz, l_db_fs, window_time):
        # 1000 hz with a stabilisation of 5 seconds
        power_ratio = (10 ** (l1000_hz / 10.0)) / (10 ** (l_db_fs / 10.0))
        has_1000hz_signal = power_ratio >= AC_1000HZ_MINIMUM_RATIO
        if len(self.auto_calibration_stack) > 0 and not has_1000hz_signal:
            self.auto_calibration_stack = []
            self.auto_calibration_time = []
        if has_1000hz_signal:
            if len(self.auto_calibration_time) == 0:
                print("Got calibration signal %.2f dBFS" % l1000_hz)
            self.auto_calibration_stack.append(l1000_hz)
            self.auto_calibration_time.append(window_time)
            if (len(self.auto_calibration_time) > 0 and
                    window_time - self.auto_calibration_time[0] >= AC_STABILISATION_TIME):
                print("stddev %.2f" % np.std(np.array(self.auto_calibration_stack)))
                if np.std(np.array(self.auto_calibration_stack)) < AC_STANDARD_DEVIATION:
                    # keep this calibration value
                    self.config.sensitivity = round(np.average(
                        np.array(self.auto_calibration_stack)), 2)
                    print("Save new sensitivity value %.2f dB" % self.config.sensitivity)
                    self.save_data()
                    self.auto_calibration_stack = []
                    self.auto_calibration_time = []
                else:
                    self.auto_calibration_stack.pop(0)
                    self.auto_calibration_time.pop(0)

    def save_data(self):
        # save configuration file
        with open(self.config.data_file, "w") as f:
            json.dump({"sensitivity": self.config.sensitivity}, f, sort_keys=False, indent=4)

    def load_data(self):
        if os.path.exists(self.config.data_file):
            data_file_config = json.load(open(self.config.data_file, "r"))
            if not self.config.sensitivity < 0:
                self.config.sensitivity = data_file_config["sensitivity"]

    def run(self):
        self.init_socket()
        sample_rate = self.filter_config["configuration"]["sample_rate"]
        # sensitivity of my Umik-1 is -28.34 dBFS @ 94 dB/1khz
        db_delta = 94 - self.config.sensitivity
        window_samples = int(
            self.config.window * self.filter_config["configuration"][
                "sample_rate"])
        if sample_rate % (
                1 / self.config.window) != 0:
            print("Warning ! window does not fit with sample rate")
        current_window = np.zeros(shape=window_samples, dtype=np.single)
        cursor = 0
        while True:
            time_bytes, audio_data_bytes = self.socket.recv_multipart()
            audio_data_samples = np.frombuffer(audio_data_bytes,
                                             dtype=np.single)
            frame_time = struct.unpack("d", time_bytes)[0]
            buffer_cursor = 0
            while buffer_cursor < len(audio_data_samples):
                # Process part of samples to fit configured windows
                to_read = min(window_samples-cursor, len(audio_data_samples)
                              - buffer_cursor)
                current_window[cursor:cursor+to_read] = \
                    audio_data_samples[buffer_cursor:buffer_cursor+to_read]
                cursor += to_read
                buffer_cursor += to_read
                self.total_read += to_read
                if cursor == window_samples:
                    window_time = frame_time + buffer_cursor / \
                                  self.filter_config["configuration"][
                                      "sample_rate"]
                    # analysis window filled
                    cursor = 0
                    ldbfs = compute_leq(current_window)
                    lzeq = round(ldbfs + db_delta, 2)
                    if self.config.verbose:
                        print("LZeq: %.2f" % lzeq)
                    self.current_stack_dict["LZeq"].append(lzeq)
                    if "a_weighting" in self.filter_config:
                        laeq = round(self.channel.process_samples_weight_a(
                            current_window) + db_delta, 2)
                        self.current_stack_dict["LAeq"].append(laeq)
                    if "c_weighting" in self.filter_config:
                        lceq = round(self.channel.process_samples_weight_c(
                            current_window) + db_delta, 2)
                        self.current_stack_dict["LCeq"].append(lceq)
                    if "bandpass" in self.filter_config:
                        spectrum = self.channel.process_samples(current_window)
                        # auto-detection of noise calibrator
                        self.auto_calibration_check(spectrum[self.auto_calibration_field_index],
                                                    ldbfs, window_time)
                        for column, lzeq in zip(self.fields, spectrum):
                            self.current_stack_dict[column].append(
                                round(lzeq + db_delta, 2))
                    self.current_stack_dict["timestamps"].append(window_time)
                    self.stack_count += 1
                    if self.stack_count == self.config.output_stack:
                        # stack of noise indicator complete
                        # send the full document
                        self.stack_count = 0
                        self.current_stack_dict[
                            "date_start"] = epoch_to_elasticsearch_date(
                            self.current_stack_dict["timestamps"][0])
                        self.current_stack_dict[
                            "date_end"] = epoch_to_elasticsearch_date(
                            self.current_stack_dict["timestamps"][-1])
                        if not self.config.output_time:
                            del self.current_stack_dict["timestamps"]
                        self.socket_out.send_json(self.current_stack_dict)
                        fields, stack_dict = generate_stack_dict(
                            self.filter_config, self.config)
                        db_delta = 94 - self.config.sensitivity
                        self.current_stack_dict = stack_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='This program read audio stream from zeromq and publish'
                    ' noise events', formatter_class=
        argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-c", "--configuration_file",
                        help="Configuration file generated by filterdesign.py", required=True,
                        type=str)
    parser.add_argument("--data_file",
                        help="Where to store data generated by this script,"
                             " must have write access rights", required=True, type=str)
    parser.add_argument("--sensitivity",
                        help="Override Microphone sensitivity in dBFS at 94 dB 1 kHz",
                        default=0, type=float)
    parser.add_argument("-w", "--window",
                        help="Will produce one indicator per provided time frame in seconds",
                        default=0.125, type=float)
    parser.add_argument("-s", "--output_stack",
                        help="Each output document will provide this number of indicators "
                             "(related to window)", default=80, type=int)
    parser.add_argument("-t", "--output_time",
                        help="Output time for each time frame", default=False,
                        action="store_true")
    parser.add_argument("--input_address", help="Address for zero_record samples",
                        default="tcp://127.0.0.1:10001")
    parser.add_argument("--output_address", help="Address for publishing JSON of"
                                                 " noise indicators",
                        default="tcp://127.0.0.1:10005")
    parser.add_argument("-v", "--verbose", help="Print LZeq", default=False,
                        action="store_true")
    args = parser.parse_args()
    print("Configuration: " + repr(args))
    if not os.path.exists(args.configuration_file):
        parser.print_help()
        print("File not found "+args.configuration_file)
    ai = AcousticIndicatorsProcessor(args)
    ai.run()

