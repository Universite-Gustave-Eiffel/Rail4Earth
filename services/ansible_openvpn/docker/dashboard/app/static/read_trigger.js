import WaveSurfer from '/static/wavesurfer.esm.js'
import Spectrogram from '/static/spectrogram.esm.js'

function loadDateTimePlayer() {
    $('input[name="datetimes"]').daterangepicker({
        "showISOWeekNumbers": true,
        "timePicker": true,
        "timePicker24Hour": true,
        "timePickerSeconds": true,
        "autoApply": true,
        ranges: {
            'Today': [moment().startOf('day'), moment().endOf('day')],
            'Yesterday': [moment().subtract(1, 'days').startOf('day'), moment().subtract(1, 'days').endOf('day')],
            'Last 7 Days': [moment().subtract(6, 'days'), moment().endOf('day')],
            'Last 30 Days': [moment().subtract(29, 'days'), moment().endOf('day')],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        "locale": {
            "format": "MM/DD/YYYY HH:mm:ss",
            "separator": " - ",
            "applyLabel": "Apply",
            "cancelLabel": "Cancel",
            "fromLabel": "From",
            "toLabel": "To",
            "customRangeLabel": "Custom",
            "weekLabel": "W",
            "daysOfWeek": [
                "Su",
                "Mo",
                "Tu",
                "We",
                "Th",
                "Fr",
                "Sa"
            ],
            "monthNames": [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December"
            ],
            "firstDay": 1
        },
        "startDate": moment().subtract(6, 'days').startOf('day'),
        "endDate": moment().endOf('day')
    });
}




var downloadedData = [];
var privateKey = null;
loadDateTimePlayer();
var stationTable = document.getElementById('stations');

var stations = new Handsontable(stationTable, {
  data:downloadedData,
  stretchH: 'all',
  height: 320,
  colHeaders: ['Hardware Address', 'Date', 'Selection'],
  columns: [
    {
      data: 'hwa',
      readOnly: true,
      editor: false
    },
    {
      data: 'timestamp',
      readOnly: true,
      editor: false
    },
    {
      data: 'id',
      renderer: 'html',
      type: 'text',
      readOnly: true,
      editor: false
    },
  ]
});



function StrToArrayBuffer(byteStr) {
  var bytes = new Uint8Array(byteStr.length)
  for (var i = 0; i < byteStr.length; i++) {
    bytes[i] = byteStr.charCodeAt(i)
  }
  return bytes.buffer
}

function base64StringToArrayBuffer(b64str) {
  return StrToArrayBuffer(atob(b64str));
}

function convertPemToBinary(pem) {
  var lines = pem.split('\n')
  var encoded = ''
  for(var i = 0;i < lines.length;i++){
    if (lines[i].trim().length > 0 &&
        lines[i].indexOf('-BEGIN') < 0 &&
        lines[i].indexOf('-END') < 0) {
      encoded += lines[i].trim()
    }
  }
  return base64StringToArrayBuffer(encoded);
}

/*
Import a PEM encoded RSA private key, to use for RSA-PSS signing.
Takes a string containing the PEM encoded key, and returns a Promise
that will resolve to a CryptoKey representing the private key.
*/
function importPrivateKey(pem) {
      // convert from a binary string to an ArrayBuffer
      const binaryDer = convertPemToBinary(pem);

      return window.crypto.subtle.importKey(
        "pkcs8",
        binaryDer,
        {
          name: "RSA-OAEP",
          hash: {name: "SHA-256"},
        },
        true,
        ["decrypt"]
      );
}
function stringToArrayBuffer(str){
    var buf = new ArrayBuffer(str.length);
    var bufView = new Uint8Array(buf);
    for (var i=0, strLen=str.length; i<strLen; i++) {
        bufView[i] = str.charCodeAt(i);
    }
    return buf;
}

function arrayBufferToString(str){
    var byteArray = new Uint8Array(str);
    var byteString = '';
    for(var i=0; i < byteArray.byteLength; i++) {
        byteString += String.fromCodePoint(byteArray[i]);
    }
    return byteString;
}

function encryptDataWithPublicKey(data, key) {
    data = stringToArrayBuffer(data);
    return window.crypto.subtle.encrypt(
    {
        name: "RSA-OAEP",
        //label: Uint8Array([...]) //optional
    },
    key, //from generateKey or importKey above
    data //ArrayBuffer of data you want to encrypt
);
}


function decryptDataWithPrivateKey(data, key) {
    data = stringToArrayBuffer(data);
    return window.crypto.subtle.decrypt(
        {
            name: "RSA-OAEP",
            //label: Uint8Array([...]) //optional
        },
        key, //from generateKey or importKey above
        data //ArrayBuffer of data you want to encrypt
    );
}


async function do_decrypt(jsonContent) {
    const el = document.getElementById("error_panel");
    try {
      const encrypted = atob(jsonContent.encrypted_audio);
      if(privateKey == null) {
        // convert a Forge certificate from PEM
        const pem = await $('input[name="privkey"]')[0].files[0].text();
        const pki = forge.pki;
        privateKey = pki.decryptRsaPrivateKey(pem, $('input[name="pwd"]')[0].value);
      }
      if(privateKey == null) {
          el.style.visibility = "visible";
          el.innerHTML = "Invalid decryption key or password";
          return;
      } else {
          el.style.visibility = "hidden";
          const keyLength = privateKey.n.bitLength() / 8;
          const decrypted = privateKey.decrypt(encrypted.substring(0, keyLength ), 'RSA-OAEP');
          const aes_key = decrypted.substring(0, 16);
          const iv = decrypted.substring(16, 32);
          const decipher = forge.cipher.createDecipher('AES-CBC', aes_key);
          decipher.start({iv: iv});
          decipher.update(forge.util.createBuffer(encrypted.substring(keyLength)));
          const result = decipher.finish(); // check 'result' for true/false
          // outputs decrypted hex
          // Create regex patterns for replacing unwanted characters in file name
          let format = "raw";
          // look for magic word in file header
          if(decipher.output.data.substring(0,4) == "fLaC") {
            format = "flac";
          } else if(decipher.output.data.substring(0,3) == "Ogg") {
            format = "ogg";
          }
          return {"data": decipher.output.data, "jsonContent": jsonContent, "format" : format}
      }
    } catch (e) {
        el.style.visibility = "visible";
        el.innerHTML = "No private key file submitted "+e;
        return;
    }
}

async function do_decrypt_and_download(jsonContent) {
      const decrypted_data = await do_decrypt(jsonContent);
      let formattedDate = decrypted_data.jsonContent.date.replace(new RegExp(`[-:]`, 'g'), "_");
      let file_name = decrypted_data.jsonContent.hwa+"_"+formattedDate+"."+decrypted_data.format;
      download(decrypted_data.data, file_name, "audio/"+decrypted_data.format);
}

async function do_decrypt_and_play(jsonContent) {
      const decrypted_data = await do_decrypt(jsonContent);
      var len = decrypted_data.data.length;
      var buf = new ArrayBuffer(len);
      var view = new Uint8Array(buf);
      for (var i = 0; i < len; i++) {
        view[i] = decrypted_data.data.charCodeAt(i) & 0xff;
      }
      let b = new Blob([view], { type : "audio/"+decrypted_data.format });
      ws.loadBlob(b);
}

function decrypt_and_download() {
    let sample_id = document.querySelector('input[name="trigger_row"]:checked').value;
    $.ajax({
      type: "GET",
      url: "get-samples/"+btoa(sample_id),
      success: function(jsonContent) {
          do_decrypt_and_download(jsonContent);
      },
      contentType : 'application/json',
    });
}

function decrypt_and_play() {
    let sample_id = document.querySelector('input[name="trigger_row"]:checked').value;
    $.ajax({
      type: "GET",
      url: "get-samples/"+btoa(sample_id),
      success: function(jsonContent) {
            do_decrypt_and_play(jsonContent);
      },
      contentType : 'application/json',
    });
}

function fetch() {
    let dateStart = $('input[name="datetimes"]').data('daterangepicker').startDate.valueOf();
    let dateEnd = $('input[name="datetimes"]').data('daterangepicker').endDate.valueOf();
    let hwa = $('input[name="hwa"]')[0].value;
    let qhwa = hwa ? "?hwa="+hwa : "";
    $.ajax({
      type: "GET",
      url: "/api/list-samples/"+dateStart+"/"+dateEnd+"/"+qhwa,
      success: function(jsonContent) {
        downloadedData.length = 0;
        jsonContent.forEach(function(element) {
            let entry = {};
            entry["id"]="<input type=\"radio\" name=\"trigger_row\" id=\"trigger_row_"+element["_id"]+"\" value="+element["_id"]+" /><label for=\"trigger_row_"+element["_id"]+"\">Select</label>";
            entry["elementid"] = element["_id"];
            var date = new Date(parseInt(element["timestamp"][0]));
            entry["timestamp"]=date.toLocaleDateString()+" "+date.toLocaleTimeString();
            entry["hwa"]=element["hwa"];
            downloadedData.push(entry);
        });
        stations.render();
      },
      contentType : 'application/json',
    });
}
function add_template() {
    var col = results.countRows();
    results.alter('insert_row', col, 2);
    resultsTable[resultsTable.length - 1] = new Array(fields.length).fill(1.0);
    results.render();
}

function remove_template() {
    var col = results.countRows();
    if(col > 2) {
        results.alter('remove_row', results.countRows() - 1);
        results.alter('remove_row', results.countRows() - 1);
    }
}

function configure() {
    var dateStart = $('input[name="datetimes"]').data('daterangepicker').startDate.valueOf();
    var dateEnd = $('input[name="datetimes"]').data('daterangepicker').endDate.valueOf();

    var startHour = $('input[name="startHour"]')[0].value;
    var endHour = $('input[name="endHour"]')[0].value;
    // Extract spectrums and weigth arrays
    spectrum_arrays = [];
    weight_arrays = [];
    for(var i=0; i < resultsTable.length; i+=2) {
        spectrum_arrays.push(resultsTable[i]);
    }
    for(var i=1; i < resultsTable.length; i+=2) {
        weight_arrays.push(resultsTable[i]);
    }

    // generate json to post
    var jsonQuery = {
        date_start : dateStart,
        date_end : dateEnd,
        spectrum : spectrum_arrays,
        weight : weight_arrays,
        cosine : parseFloat($('input[name="cos_threshold"]')[0].value),
        min_leq : parseFloat($('input[name="minleq"]')[0].value),
        cached_length : parseInt($('input[name="minlength"]')[0].value),
        total_length : parseInt($('input[name="maxlength"]')[0].value),
        trigger_count : parseInt($('input[name="triggerday"]')[0].value)
         };

    if(startHour != "") {
        jsonQuery["start_hour"] = startHour;
    }

    if(endHour != "") {
        jsonQuery["end_hour"] = endHour;
    }
    var el = document.getElementById("error_panel");
    var el2 = document.getElementById("info_panel");
    if($('input[name="pubkey"]')[0].files.length==0) {
        el.style.visibility = "visible";
        el.innerHTML = "Please select the public encryption key";
        $('html, body').animate({ scrollTop: 0 }, 'fast');
    } else{
        el.style.visibility = "hidden";
        el2.style.visibility = "hidden";
    }
    $('input[name="pubkey"]')[0].files[0].text().then(function(value) {
        jsonQuery["file"] = value;

        $.ajax({
          type: "POST",
          url: "set-trigger",
          data: JSON.stringify(jsonQuery),
          success: function(val) {
            if(val["result"] != 'success') {
                el.style.visibility = "visible";
                el.innerHTML = "Invalid public encryption key. Reason :" + val["result"];
                el2.style.visibility = "hidden";
            } else{
                el.style.visibility = "hidden";
                el2.style.visibility = "visible";
                el2.innerHTML = "Trigger set";
            }
          },
          contentType : 'application/json',
        });


        $('html, body').animate({ scrollTop: 0 }, 'fast');
    });

}

// Create an instance of WaveSurfer
const ws = WaveSurfer.create({
  container: '#waveform',
  waveColor: 'rgb(200, 0, 200)',
  progressColor: 'rgb(100, 0, 100)',
  normalize: true,
  mediaControls:true,
  height: 100,
})

// Initialize the Spectrogram plugin
ws.registerPlugin(
  Spectrogram.create({
    labels: true,
    labelsColor: "#7c9cb6",
    height: 100,
    splitChannels: true,
    maxFrequency: 8000
  }),
)

// Play on click
ws.once('interaction', () => {
  ws.play()
})

// Create Web Audio context
const audioContext = new AudioContext()

var gainNode = null

// Connect the audio to the equalizer
ws.media.addEventListener(
  'canplay',
  () => {
    // Create a MediaElementSourceNode from the audio element
    const mediaNode = audioContext.createMediaElementSource(ws.media)

	gainNode = audioContext.createGain();
	gainNode.gain.value = 100 * ws.media.volume;
    mediaNode.connect(gainNode);
    // Connect the filters to the audio output
    gainNode.connect(audioContext.destination)
  },
  { once: true },
)

ws.media.onvolumechange = function() {
    if(gainNode != null) {
        gainNode.gain.value = 100 * ws.media.volume;
    }
}

document.getElementById('fetch_button').addEventListener('click', fetch)
document.getElementById('download_button').addEventListener('click', decrypt_and_download)
document.getElementById('play_button').addEventListener('click', decrypt_and_play)
