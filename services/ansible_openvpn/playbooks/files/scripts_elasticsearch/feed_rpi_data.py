#!/usr/bin/python
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
import os
import argparse
import sys
from pathlib import Path
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
import elasticsearch.helpers
import gzip
import json
import datetime
import calendar
import zlib

# This python script read json data fetched from RPI and feed it to an
# elastic search node
import hashlib
import base64

def epoch_to_elasticsearch_date(epoch):
    return datetime.datetime.utcfromtimestamp(epoch).strftime(
        "%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def fetch_data(args):
    for root, dirs, files in os.walk(args.json_input_folder):
        for name in files:
            file_path = os.path.join(root, name)
            if name.endswith(".json.gz"):
                if args.verbose:
                    print("Processing " + file_path)
                processed_documents = 0
                try:    
                    with gzip.open(file_path, 'rb') as f:
                        for line in f:
                            try:
                                json_dict = json.loads(line)
                                if "_index" not in json_dict:
                                    if "_source" not in json_dict:
                                        source_doc = json_dict
                                        json_dict = {"_source": source_doc}
                                    # must create index as it is not specified in the
                                    # document
                                    epoch = os.path.getmtime(file_path)
                                    if "timestamp" in json_dict:
                                        epoch = json_dict["timestamp"]
                                    elif "_source" in json_dict and "timestamp" in \
                                            json_dict["_source"]:
                                        epoch = json_dict["_source"]["timestamp"]
                                    elif "date" in json_dict:
                                        epoch = calendar.timegm(datetime.datetime.strptime(
                                            json_dict["date"], "%Y-%m-%dT%H:%M:%S.%fZ")
                                                                .timetuple())
                                    dt = datetime.datetime.utcfromtimestamp(epoch)
                                    stop_position = name.find("_")
                                    if stop_position == -1:
                                        stop_position = name.find(".")
                                    json_dict["_index"] = name[:stop_position] + "_" + dt.strftime(args.time_format)
                                json_dict["_index"] = args.index_prepend + json_dict[
                                    "_index"]
                                if "_id" not in json_dict:
                                    # avoid duplicate by hashing the document
                                    json_dict["_id"] = base64.b64encode(
                                        hashlib.sha256(line).digest()).decode(
                                        sys.getdefaultencoding())
                                if "_op_type" not in json_dict:
                                    json_dict["_op_type"] = "create"
                                yield json_dict
                                processed_documents += 1
                            except json.decoder.JSONDecodeError:
                                print("Cannot parse json: "+line.decode("utf-8"))
                except Exception as e:
                    print("Issue with compressed file named "+file_path, e)
                if not args.keep_file:
                    destination = os.path.join(
                        args.json_archive_folder,
                        os.path.relpath(file_path, args.json_input_folder))
                    parent_dir_destination = Path(
                        destination).parent.absolute()
                    if not os.path.exists(parent_dir_destination):
                        os.makedirs(parent_dir_destination)
                    os.rename(file_path, destination)
                    if args.verbose:
                        print("Processed %d documents, now move %s to %s" %(processed_documents, file_path, destination))


def main():
    parser = argparse.ArgumentParser(
        description='This program parse gziped json (one json per line) in a'
                    ' folder, push it into elastic search then archive the '
                    'source file',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--api_key", help="Elastic Search Api key with "
                                          "search and index rights over "
                                          "sensor_* index name",
                        type=str, required=True)
    parser.add_argument("--api_key_id", help="Elastic Search Api key name",
                        type=str, required=True)
    parser.add_argument("--json_input_folder", help="Folder than contains json"
                                                    " files",
                        type=str, required=True)
    parser.add_argument("--json_archive_folder", help="Folder where processed "
                                                      "json files are moved",
                        type=str, required=True)
    parser.add_argument("--host", help="API url of Elastic Search",
                        default="https://localhost:9200", type=str)
    parser.add_argument("-v", "--verbose", help="Verbose mode",
                        default=False,
                        action="store_true")
    parser.add_argument("-t", "--time_format",
                        help="Time format name for the index name if not"
                             " specified by the json document",
                        default="%Y_%U",
                        type=str)
    parser.add_argument("-k", "--keep_file",
                        help="Do not move file when processed",
                        default=False,
                        action="store_true")
    parser.add_argument("-p", "--index_prepend",
                        help="Index name prepend string",
                        default="sensor_",
                        type=str)
    args = parser.parse_args()
    # arguments check
    if not os.path.exists(args.json_input_folder):
        raise Exception("Folder "+args.json_input_folder+" does not exists")

    if not os.path.exists(args.json_archive_folder):
        os.mkdir(args.json_archive_folder)

    client = Elasticsearch(
        args.host,
        api_key=(args.api_key_id, args.api_key),
        verify_certs=False, request_timeout=60
    )
    # Check if templates are already pushed
    # Templates are optional, but it will help
    # to integrate well with kibana and reduce disk usage/increase performance
    result = client.cat.templates(format="json")
    templates = set([template["name"] for template in result])
    templates_to_push = [filepath for filepath in
                         os.listdir(os.path.dirname(__file__)) if
                         filepath.endswith("template.json")]
    for template in templates_to_push:
        filename = os.path.basename(template)
        if not filename[:filename.rfind(".json")] in templates:
            print("Push index template " + filename)
            client.indices.put_template(**json.load(open(template)))
    successes = 0
    try:
        for ok, action in streaming_bulk(client=client,
                                         actions=fetch_data(args)):
            successes += ok
    except elasticsearch.helpers.BulkIndexError as e:
        print(e, file=sys.stderr)
        print(repr(e.errors), file=sys.stderr)
        exit(-1)


if __name__ == "__main__":
    main()
