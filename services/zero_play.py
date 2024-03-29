#!/usr/bin/env python3

import sys
import zmq
import argparse

def main():
    parser = argparse.ArgumentParser(description='This program read audio stream from zeromq and push to stdout',
                                     epilog='''example:  python zero_play | aplay -D default -r 16000 -f FLOAT_LE''',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-p", "--port", help="Port to publish samples", default=10001, type=int)
    parser.add_argument("-i", "--interface", help="Interface to publish", default="127.0.0.1", type=str)
    parser.add_argument("-o", "--output_file",
                        help="Instead of output audio into stdout, write into the specified file", default="", type=str)

    args = parser.parse_args()

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    address = "tcp://%s:%d" % (args.interface, args.port)
    socket.connect(address)
    socket.subscribe('')

    out_buffer = sys.stdout.buffer

    if len(args.output_file) > 0:
        out_buffer = open(args.output_file, "wb")

    try:
        while True:
            time_bytes, audio_data_bytes = socket.recv_multipart()
            out_buffer.write(audio_data_bytes)
    finally:
        if len(args.output_file) > 0:
            out_buffer.close()


if __name__ == "__main__":
    main()
