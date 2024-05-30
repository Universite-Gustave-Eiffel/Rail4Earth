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
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os
from elasticsearch import Elasticsearch
import base64

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.mount("/fonts", StaticFiles(directory="app/fonts"), name="fonts")

templates = Jinja2Templates(directory="app/templates")

if not os.path.exists("certs/api.json"):
    raise Exception("Configuration file not found " +
                    os.path.abspath("certs/api.json"))
configuration = json.load(open("certs/api.json", "r"))

client = Elasticsearch(
    configuration.get("url", "https://es01:9200"),
    api_key=(configuration["id"], configuration["api_key"]),
    ca_certs="certs/ca/ca.crt",
    verify_certs=configuration.get("verify_certs", True), request_timeout=60
)


@app.get("/api/list-samples/{start_epoch_millis}/{end_epoch_millis}")
async def get_list_samples(request: Request, start_epoch_millis: int,
                           end_epoch_millis: int):
    post_data = json.loads(
        templates.get_template("trigger_list.json").render(
            start_time=start_epoch_millis, end_time=end_epoch_millis))
    resp = client.search(**post_data)
    print(json.dumps(post_data))
    hits = resp["hits"]["hits"]
    # reformat elastic search result
    return [{"hwa": hit["fields"]["hwa.keyword"],
             "timestamp": hit["fields"]["date"],
             "_id": hit["_id"]} | hit["fields"]
            for hit in hits]


@app.get("/api/get-uptime/{sensor_id}/{start_epoch_millis}/{end_epoch_millis}")
async def get_sensor_uptime(request: Request, sensor_id: str,
                            start_epoch_millis: int, end_epoch_millis: int):
    post_data = json.loads(
        templates.get_template("query_sensor_uptime.json").render(
            sensor_id=sensor_id, start_time=start_epoch_millis,
            end_time=end_epoch_millis))
    print(json.dumps(post_data))
    resp = client.search(**post_data)
    # reformat elastic search result
    return resp


@app.get("/api/sensor_record_count/{start_epoch_millis}/{end_epoch_millis}")
async def get_sensor_record_count(request: Request, start_epoch_millis: int,
                                  end_epoch_millis: int):
    post_data = json.loads(
        templates.get_template("query_sensor_record_count.json").render(
            start_time=start_epoch_millis, end_time=end_epoch_millis))
    resp = client.search(**post_data)
    # reformat elastic search result
    return [{"hwa": bucket["key"], "count": bucket["doc_count"]}
            for bucket in resp["aggregations"]["group"]["buckets"]]


@app.get("/api/get-last-record/{sensor_id}")
async def get_sensor_last_record(request: Request, sensor_id: str):
    post_data = json.loads(
        templates.get_template("query_last_record.json").render(
            sensor_id=sensor_id))
    resp = client.search(**post_data)
    # reformat elastic search result
    result = resp["hits"]["hits"][0]
    return {"date": result["_source"]["date_start"],
            "timestamp": int(result["fields"]["date_start"][0])}


@app.get("/api/sensor_position")
async def get_sensor_position(request: Request):
    post_data = json.loads(
        templates.get_template("query_sensor_list.json").render())
    resp = client.search(**post_data)
    # reformat elastic search result
    return [
        {"hwa": sub_hit["fields"]["hwa"][0],
         "lat": sub_hit["fields"]["TPV.lat"][0],
         "lon": sub_hit["fields"]["TPV.lon"][0],
         "date": sub_hit["fields"]["date"][0]}
        for hit in resp["hits"]["hits"] for
        sub_hit in hit["inner_hits"]["most_recent"]["hits"]["hits"]]


@app.get('/recordings', response_class=HTMLResponse)
async def recordings(request: Request):
    return templates.TemplateResponse("recordings.html",
                                      context={"request": request})


@app.get('/agenda', response_class=HTMLResponse)
async def recordings(request: Request):
    return templates.TemplateResponse("alert_agenda.html",
                                      context={"request": request})


@app.get('/get-samples/{document_id}')
async def get_samples(request: Request, document_id: str):
    post_data = json.loads(
        templates.get_template("trigger_audio.json").render(id=base64.b64decode(document_id).decode("utf-8")))
    resp = client.search(**post_data)
    # reformat elastic search result
    try:
        return resp["hits"]["hits"][0]["_source"]
    except IndexError as e:
        raise Exception(e, "Error parsing document required by " + json.dumps(post_data))


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("status.html",
                                      context={"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
