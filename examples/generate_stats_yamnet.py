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
import time
import elasticsearch
import json
import argparse
import datetime


def main():
    parser = argparse.ArgumentParser(
        description='This program compute statistics around Yamnet triggers',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--elastic_host",
                        help="Elastic search  host",
                        default="https://es01:9200", type=str)
    parser.add_argument("--api_path",
                        help="Elastic search json api file path "
                             "https://www.elastic.co/guide/en/elasticsearch/reference/current"
                             "/security-api-create-api-key.html",
                        type=str, required=True)
    parser.add_argument("--connection_timeout",
                        help="Elastic search server connection timeout in seconds",
                        default=60, type=int)
    parser.add_argument("--ca_certs",
                        help="Elastic certificate",
                        default=None, type=str)
    parser.add_argument("--yamnet_index",
                        help="Yamnet index to search for events",
                        default="sensor_yamnet_*", type=str)
    parser.add_argument("--ignore_certs",
                        help="Do not verify certificate", default=False, action="store_true")
    args = parser.parse_args()
    configuration = json.load(open(args.api_path, "r"))
    client = elasticsearch.Elasticsearch(
        configuration.get("url", args.elastic_host),
        api_key=(configuration["id"], configuration["api_key"]),
        ca_certs=args.ca_certs,
        verify_certs=not args.ignore_certs,
        request_timeout=args.connection_timeout
    )
    search_after = None
    print("hwa,date,l10")
    while True:
        result = client.search(index=args.yamnet_index, _source=False,
                               fields=[{"field": "date", "format": "epoch_millis"}, "hwa"],
                               sort=[{"date": {"order": "desc"}}], search_after=search_after)
        hits = result["hits"]["hits"]
        if len(hits) == 0:
            break
        for doc in hits:
            train_crossing = datetime.datetime.fromtimestamp(
                int(doc["fields"]["date"][0]) / 1000, tz=datetime.timezone.utc)
            hwa = doc["fields"]["hwa"][0]
            query_indicators = {
                "bool": {
                    "must": [
                        {
                            "range": {
                                "date_start": {
                                    "gte": int((train_crossing.timestamp() - 30) * 1000)
                                }
                            }
                        },
                        {
                            "range": {
                                "date_end": {
                                    "lte": int((train_crossing.timestamp() + 30) * 1000)
                                }
                            }
                        },
                        {
                          "match": {
                            "hwa": hwa
                          }
                        }
                    ]
                }
            }
            query_aggregate = {"l10": {"percentiles": {"field": "LZeq", "percents": [90]}}}
            result_indicators = client.search(index="sensor_indicators_*", size=0,
                                              query=query_indicators,
                                              aggs=query_aggregate)
            percentile = result_indicators["aggregations"]["l10"]["values"]["90.0"]
            if percentile:
                print("%s,%s,%.2f" % (hwa, train_crossing.astimezone().isoformat(timespec="seconds"), percentile))
                search_after = doc["sort"]


if __name__ == "__main__":
    main()
