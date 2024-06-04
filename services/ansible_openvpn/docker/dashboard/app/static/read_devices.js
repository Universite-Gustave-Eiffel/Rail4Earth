
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

Handsontable.renderers.registerRenderer('bytes', sizeRenderer);

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
      data: 'Connected Since',
      readOnly: true,
      editor: false
    },
    {
      data: 'Last Ref',
      readOnly: true,
      editor: false
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

function fetch() {
    $.ajax({
      type: "GET",
      url: "/api/list-devices",
      success: function(jsonContent) {
        downloadedData.length = 0;
        jsonContent.forEach(function(element) {
          downloadedData.push(element);
        });
        devices.render();
      },
      contentType : 'application/json',
    });
}

fetch();