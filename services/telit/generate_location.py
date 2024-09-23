#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 This script create an artificial location file when GPS is not working but the position is known and should be stored
"""
import gzip
import json
import argparse
import datetime
import os

def open_file_for_write(filename):
    return gzip.open(filename, 'at')


def main():
    parser = argparse.ArgumentParser(
        description='This program create a json document using specified lat long data', formatter_class=
        argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--latitude",
                        help="latitude value",
                        required=True, type=float)
    parser.add_argument("--longitude",
                        help="longitude value",
                        required=True, type=float)
    parser.add_argument("--altitude",
                        help="altitude value",
                        type=float, default=0.0)
    parser.add_argument("--hwa",
                        help="hardware address field",
                        required=True, type=str)
    parser.add_argument("-t", "--time_format",
                        help="Time format name for the file,"
                             " if the file already exists a counter after "
                             "the file name will be added",
                        default="%Y_%m_%d.%Hh%Mm%S.%f",
                        type=str)
    parser.add_argument("-o", "--output",
                        help="File output folder",
                        default="",
                        type=str)
    args = parser.parse_args()
    time_part = datetime.datetime.now().strftime(args.time_format)
    document = {"date": time_part,"TPV": {"lat": args.latitude,"lon": args.longitude,"alt": args.altitude},"hwa": args.hwa}
    # create special entry specifically for elastic search
    document["location"] = {"lat": document["TPV"]["lat"],
                            "lon": document["TPV"]["lon"],
                            "z": document["TPV"]["alt"]}
    document_path = os.path.join(args.output, "location_"+time_part+".json.gz")
    exists = os.path.exists(document_path)
    with open_file_for_write(document_path) as fp:
        if exists:
            fp.write("\n")
        json.dump(document, fp, allow_nan=True)


if __name__ == "__main__":
    main()
