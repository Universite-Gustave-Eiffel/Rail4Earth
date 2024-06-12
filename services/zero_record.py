#!/usr/bin/env python3
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

import sys
import zmq
import argparse
import time
import datetime
import io
import os
import collections
import threading
import struct

ALERT_STACK_BYTES = 960000
ALERT_DELAY = 5.0
SECONDS_DELAY_RESET_USB = 5.0


class ZeroMQThread(threading.Thread):
    def __init__(self, args):
        threading.Thread.__init__(self)
        self.samples_queue = collections.deque()
        self.args = args
        self.last_warning = 0

    def push_bytes(self, samples_bytes):
        self.samples_queue.append([time.time(), samples_bytes])
        sum_bytes = sum([len(element) for element in self.samples_queue])
        if sum_bytes > ALERT_STACK_BYTES and \
                time.time() - self.last_warning > ALERT_DELAY:
            print("Warning buffer overflowing with %d bytes" % sum_bytes)
            self.last_warning = time.time()

    def run(self):
        interface = self.args.interface
        port = self.args.port

        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        if self.args.zmq_audio_buffer_size > 0:
            socket.setsockopt(zmq.SNDBUF, self.args.zmq_audio_buffer_size)
        address = "tcp://%s:%d" % (interface, port)
        socket.bind(address)
        print("Publishing samples on interface:")
        print(address)
        while self.args.running or len(self.samples_queue) > 0:
            while len(self.samples_queue) > 0:
                capture_time, audio_data_bytes = self.samples_queue.popleft()
                socket.send_multipart([struct.pack("d", capture_time),
                                       audio_data_bytes])
            time.sleep(0.05)


class AudioFolderPlayListBuffer(io.BytesIO):
    def __init__(self, folder_or_file, sample_rate, resample_method):
        super().__init__(b"")
        self.sample_rate = sample_rate
        self.playlist = []
        if os.path.isdir(folder_or_file):
            self.playlist = [folder_or_file+os.sep+filepath for filepath in os.listdir(folder_or_file) if filepath.lower().endswith(".wav")]
        else:
            self.playlist.append(folder_or_file)
        self.resample_method = resample_method

    def get_bytes_rate(self):
        return self.sample_rate * 4

    def read(self, __size: int = ...) -> bytes:
        if len(self.getbuffer()) == self.tell():
            import soundfile as sf
            import random
            import numpy as np
            # push new data
            file_name = self.playlist[random.randrange(0, len(self.playlist))]
            wav_data, sr = sf.read(file_name, dtype=np.int16)
            print("Playing " + file_name + " sample rate %d Hz-> %d Hz" % (sr, self.sample_rate))
            assert wav_data.dtype == np.int16, 'Bad sample type: %r' % wav_data.dtype
            waveform = wav_data / 32768.0  # Convert to [-1.0, +1.0]
            waveform = waveform.astype('float32')
            # Convert to mono and the sample rate expected by YAMNet.
            if len(waveform.shape) > 1:
              waveform = np.mean(waveform, axis=1)
            if sr != self.sample_rate:
                import resampy
                waveform = resampy.resample(waveform, sr, self.sample_rate,
                                            filter=self.resample_method)
            super().__init__(b"")
            self.write(waveform.tobytes())
            self.seek(0)
        return super().read(__size)


class AudioFolderPlayOnce(io.BytesIO):
    def __init__(self, folder_or_file, sample_rate, resample_method, speed=1.0):
        super().__init__(b"")
        self.speed = speed
        self.sample_rate = sample_rate
        self.playlist = []
        if os.path.isdir(folder_or_file):
            self.playlist = [folder_or_file+os.sep+filepath for filepath in os.listdir(folder_or_file) if filepath.lower().endswith(".wav")]
        else:
            self.playlist.append(folder_or_file)
        self.resample_method = resample_method

    def get_bytes_rate(self):
        return int(self.sample_rate * 4 * self.speed)

    def read(self, __size: int = ...) -> bytes:
        if len(self.playlist) > 0 and len(self.getbuffer()) == self.tell():
            import soundfile as sf
            import random
            import numpy as np
            # push new data
            file_name = self.playlist[random.randrange(0, len(self.playlist))]
            self.playlist.remove(file_name)
            wav_data, sr = sf.read(file_name, dtype=np.int16)
            print("Playing " + file_name + " sample rate %d Hz-> %d Hz" % (sr, self.sample_rate))
            assert wav_data.dtype == np.int16, 'Bad sample type: %r' % wav_data.dtype
            waveform = wav_data / 32768.0  # Convert to [-1.0, +1.0]
            waveform = waveform.astype('float32')
            # Convert to mono and the sample rate expected by YAMNet.
            if len(waveform.shape) > 1:
              waveform = np.mean(waveform, axis=1)
            if sr != self.sample_rate:
                import resampy
                waveform = resampy.resample(waveform, sr, self.sample_rate,
                                            filter=self.resample_method)
            super().__init__(b"")
            self.write(waveform.tobytes())
            self.seek(0)
        return super().read(__size)

def publish_samples(args):
    block_size = args.block_size
    byte_rate = args.debug_byte_rate
    if byte_rate > 0:
        print("Warning zero_record in debug mode, sampling clocked at %d Hz" %
              byte_rate)
    if args.wave != "":
        input_buffer = AudioFolderPlayListBuffer(args.wave, args.sample_rate,
                                                 args.resample_method)
        byte_rate = input_buffer.get_bytes_rate()
    elif args.wave_once != "":
        input_buffer = AudioFolderPlayOnce(args.wave_once, args.sample_rate,
                                                 args.resample_method, args.wave_speed)
        byte_rate = input_buffer.get_bytes_rate()
    else:
        input_buffer = sys.stdin.buffer
    manager = ZeroMQThread(args=args)
    manager.start()
    start = time.time()
    last_time_read = start
    total_bytes=0
    try:
        while args.running:
            audio_data_bytes = input_buffer.read(block_size)
            now = time.time()
            if not audio_data_bytes:
                print("%s End of audio samples, total bytes read %d" %
                      (datetime.datetime.now().isoformat(),
                       total_bytes))
                if total_bytes == 0:
                    reset_usb()
                break
            manager.push_bytes(audio_data_bytes)
            args.total_bytes_read = len(audio_data_bytes)
            total_bytes += args.total_bytes_read
            args.total_bytes_read_since = now - last_time_read
            args.total_bytes_read_last_time = now
            last_time_read = now
            if byte_rate > 0:
                # if byte rate provided by user
                # pause time before reading the next bytes according to expected byte rate
                cur = time.time()
                samples_time = len(audio_data_bytes) / byte_rate
                if cur - start < samples_time:
                    time.sleep(samples_time - (cur - start))
                start = time.time()
    finally:
        args.running = False


def reset_usb():
    found_usb_audio = False
    from usb.core import find as finddev
    for device in finddev(find_all=True):
        usb_label = repr(device.get_active_configuration().
                         interfaces())
        if "Audio" in usb_label:
            print("Reset " + repr(device) + usb_label)
            device.reset()
            found_usb_audio = True
            break
    if not found_usb_audio:
        print("Zero bytes rates but could not find"
              " USB device to reset")


class BandwidthWatchThread(threading.Thread):
    def __init__(self, config):
        threading.Thread.__init__(self)
        self.config = config

    def run(self):
        time.sleep(1)  # wait for some bytes
        watch_delay = 1
        if self.config.delay_print_rate > 0:
            watch_delay = self.config.delay_print_rate
        while self.config.running:
            byte_rate = int(self.config.total_bytes_read /
                            self.config.total_bytes_read_since)
            if time.time() - self.config.total_bytes_read_last_time > \
                    SECONDS_DELAY_RESET_USB:
                # Restart USB
                reset_usb()
            if self.config.delay_print_rate > 0:
                print("received %d B/s" % byte_rate)
            time.sleep(watch_delay)


def main():
    # Get the last modified time in epoch format
    last_modified_time = os.path.getmtime(os.path.realpath(__file__))
    if time.time() < last_modified_time:
        raise OSError("The current file modification time is after the current"
                      " time, so there is an issue with the clock !")
    epilog = "example:\narecord --disable-softvol " \
             "-D plughw:CARD=U18dB,DEV=0 -r 48000 -f FLOAT_LE -c 1 -t raw" \
             " | python3 -u zero_record.py -p 10001 \n\n" \
             "python zero_record.py -w " \
             "../third_parties/yamnet/" \
             "24968__wwwbonsonca__train_tgv_passing_06.wav"

    parser = argparse.ArgumentParser(description=
                                     'This program read audio stream from'
                                     ' std input and publish through zeromq.',
                                     epilog=epilog, formatter_class=
                                     argparse.RawTextHelpFormatter)

    parser.add_argument("-p", "--port", help="Port to publish samples",
                        default=10001, type=int)
    parser.add_argument("-i", "--interface", help="Interface to publish",
                        default="127.0.0.1", type=str)
    parser.add_argument("-b", "--block_size",
                        help="Number of bytes to publish per message",
                        default=16000, type=int)
    parser.add_argument("-r", "--sample_rate",
                        help="Set frequency of debug file", default=16000,
                        type=int)
    parser.add_argument("--resample_method",
                        help="Resampling method when reading wave file",
                        default='kaiser_fast', type=str)
    parser.add_argument("--debug_byte_rate",
                        help="You can use a raw file input and "
                             "provide the expected bytes per second of "
                             "transfer", default=0, type=int)
    parser.add_argument("-w", "--wave", 
                        help="File name or folder containing "
                            "wave file(s), will be used "
                            "instead of stdin, will be played repeatedly",
                        default="", type=str)
    parser.add_argument("-wo", "--wave_once",
                        help="File name or folder containing "
                            "wave file(s), will be used "
                            "instead of stdin, will be only played once\n "
                            "IGNORED IF -w IS SET",
                        default="", type=str)
    parser.add_argument("-ws", "--wave_speed",
                        help="wave file read speed multpiplier",
                        default="1.0", type=float)
    parser.add_argument("--delay_print_rate",
                        help="Delay in second between each print of byte rate",
                        default=0, type=float)
    parser.add_argument("--zmq_audio_buffer_size",
                        help="ZMQ audio buffer size in bytes. 0 (default) means using default OS value",
                        default=0, type=int)
    args = parser.parse_args()
    args.running = True
    args.total_bytes_read = 0
    args.total_bytes_read_since = 1
    args.total_bytes_read_last_time = time.time()
    BandwidthWatchThread(args).start()
    publish_samples(args)


if __name__ == "__main__":
    main()
