
var downloadedData = [];

var stationTable = document.getElementById('devices');

function bytesToHumanReadable(bytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let index = 0;
  while (bytes >= 1024 && index < units.length - 1) {
    bytes /= 1024;
    index++;
  }
  return `${bytes.toFixed(1)}${units[index]}`;
}

const sizeRenderer = function(instance, td, row, col, prop, value, cellProperties) {
  Handsontable.renderers.BaseRenderer.apply(this, arguments);
  td.innerHTML = bytesToHumanReadable(value);
  return td;
};

const epochRenderer = function(instance, td, row, col, prop, value, cellProperties) {
  Handsontable.renderers.BaseRenderer.apply(this, arguments);
  td.innerHTML = new Date(value).toLocaleString(navigator.language,
   { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute:'numeric',
   second:'numeric', timeZoneName: 'short' })
  return td;
};

Handsontable.renderers.registerRenderer('bytes', sizeRenderer);
Handsontable.renderers.registerRenderer('epoch', epochRenderer);

var devices = new Handsontable(stationTable, {
  data:downloadedData,
  stretchH: 'all',
  colHeaders: ['Virtual Address', 'Common Name', 'Connected Since', 'Last Seen', 'Received', 'Sent'],
  columns: [
    {
      data: 'Virtual Address',
      readOnly: true,
      editor: false
    },
    {
      data: 'Common Name',
      readOnly: true,
      editor: false
    },
    {
      data: 'epoch_connected',
      readOnly: true,
      editor: false,
      renderer: 'epoch'
    },
    {
      data: 'epoch_updated',
      readOnly: true,
      editor: false,
      renderer: 'epoch'
    },
    {
      data: 'Bytes Received',
      readOnly: true,
      editor: false,
      renderer: 'bytes'
    },
    {
      data: 'Bytes Sent',
      readOnly: true,
      editor: false,
      renderer: 'bytes'
    }
  ],
  columnSorting: {
    initialConfig: {
        column: 2,
        sortOrder: 'desc',
    }
  }
});

const columnSorting = devices.getPlugin('columnSorting');

function fetch() {
    $.ajax({
      type: "GET",
      url: "/api/list-devices",
      success: function(jsonContent) {
        downloadedData.length = 0;
        jsonContent.forEach(function(element) {
            element["epoch_connected"]= Date.parse(element["Connected Since"]+'Z');
            element["epoch_updated"] = Date.parse(element["Last Ref"]+'Z');
            downloadedData.push(element);
        });
        devices.loadData(downloadedData);
        columnSorting.sort({
         column: 2,
         sortOrder: 'desc',
         });
      },
      contentType : 'application/json',
    });
}

fetch();