
function onMarkerClick(e) {
    selectedSensor = e.target.options.data["hwa"];
    // Fetch the last sensor record
    $.getJSON( "/api/get-last-record/" + selectedSensor, function( data ) {
       if ( $("#uptimectrl").length == 0 ) {
        upTimeControl.addTo(lmap);
        loadDateTime();
        buildUpTime();
       }
       var pickerCtrl = $('input[name="datetimes"]').data('daterangepicker');
       var start = pickerCtrl.startDate.clone();
       var end = pickerCtrl.endDate.clone();
       start = start.add(start.utcOffset(), 'm').valueOf();
       end = end.add(end.utcOffset(), 'm').valueOf();
       var sensorEpoch = data["timestamp"];
       // Always display the last month of selected sensor data
       start = moment(sensorEpoch).utc().startOf('month').valueOf();
       end = moment(sensorEpoch).utc().endOf('month').valueOf();
       pickerCtrl.setStartDate(moment(start));
       pickerCtrl.setEndDate(moment(end));
       uptimeChart(selectedSensor, start, end);
   });
}


function getStations(lmap, sensorsLayer) {
    $.getJSON( "/api/sensor_position", function( data ) {
      var minLat = 90;
      var maxLat = -90;
      var minLong = 180;
      var maxLong = -180;
      $.each( data, function( key, val ) {
        var lat = val.lat;
        var lon = val.lon;
        var style = {data: val, title:"id: "+val.hwa, icon: greyIcon};
        var marker = L.marker([lat, lon], style);
        marker.on('click', onMarkerClick);
        sensorsLayer.addLayer(marker);
        minLat = Math.min(minLat, lat);
        minLong = Math.min(minLong, lon);
        maxLat = Math.max(maxLat, lat);
        maxLong = Math.max(maxLong, lon);
      });
      // Set extent to sensors
      if(minLat < 90 && minLong < 180) {
        lmap.fitBounds([ [minLat, minLong], [maxLat, maxLong] ]);
      }
      // Update sensors status from database
      getStationsRecordCount(lmap, sensorsLayer);
    });
  }

function getStationsRecordCount(lmap, sensorsLayer) {
    var start_time = moment().subtract(60, 'minutes').valueOf();
    var end_time = moment().subtract(30, 'minutes').valueOf();
    var expected_records = Math.trunc((end_time - start_time) / 1000 / 10);
    var sensors = new Map();
    $.getJSON( "/api/sensor_record_count/" + start_time + "/" + end_time, function( data ) {
      $.each( data, function( key, val ) {
            // Set sensor status
            sensors.set(val.hwa, val.count);
      });
     // Loop over leaflet markers
     sensorsLayer.eachLayer(function(val) {
            var icon = val.options.icon;
            if(!sensors.has(val.options.data.hwa)) {
                val.setIcon(redIcon);
            } else if(sensors.get(val.options.data.hwa) < expected_records - 1) {
                val.setIcon(yellowIcon);
            } else {
                val.setIcon(greenIcon);
            }
      });
    });
  }


var lmap = L.map('mapid').setView([47.7456, -3.3687], 16);

L.control.scale().addTo(lmap);

var sensors = L.layerGroup();

var osm = L.tileLayer('https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png', {
  maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attribution">CARTO</a>'});

osm.addTo(lmap);

sensors.addTo(lmap);

getStations(lmap, sensors);

var legend = L.control({position: 'bottomright'});

legend.onAdd = function (lmap) {
    var div = L.DomUtil.create('div', 'info legend'),
    labels = ['Online', 'Missing values', 'Offline'],
    icons = [greenIcon, yellowIcon, redIcon];


    // loop through our density intervals and generate a label with a colored square for each interval
    div.innerHTML += "30 minutes delayed status map<br/>";
    for (var i = 0; i < icons.length; i++) {
        div.innerHTML += '<i ><img style="max-height:100%;" src="'+icons[i].options.iconUrl+'"/></i>'+labels[i];
        if(i < icons.length - 1) {
            div.innerHTML += '<br/>';
        }
    }

    return div;
};

legend.addTo(lmap);

var toplinkbar = L.control({position: 'topcenter'});


toplinkbar.onAdd = function (lmap) {
    var div = L.DomUtil.create('div', 'info');
    const links = [
      { text: "Map", url: "/", target : "_self"},
      { text: "Audio records", url: "/recordings", target : "_self" },
      { text: "Alert agenda", url: "/agenda", target : "_self" },
      { text: "Backup data", url: "https://nsraw.noise-planet.org" , target : "_blank"}
    ];
    var divhtml = "<ul class=\"ul_top_menu\">";
    links.forEach((link) => {
      divhtml += `<li class="li_top_menu"><a href="${link.url}" target="${link.target}">${link.text}</a></li>`;
    });
    divhtml += "</ul>";
    div.innerHTML += divhtml;

    return div;
};

toplinkbar.addTo(lmap);

var upTimeControl = L.control({position: 'bottomcenter', });


upTimeControl.onAdd = function (lmap) {
    var div = L.DomUtil.create('div', 'info uptime');
    div.id = "uptimectrl";
    div.innerHTML += "<div class=\"form-style-7\"> <input type=\"text\" name=\"datetimes\"/> </div> <div id=\"chart\"></div>";
    return div;
};
