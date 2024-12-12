import WaveSurfer from '/static/wavesurfer.esm.js'
import Spectrogram from '/static/spectrogram.esm.js'

var privateKey = null;

var updating = false;
var currentAudioAttributes = null;

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
      if (privateKey == null) {
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

function next_and_play() {
  updating = true;
  updateButtons()
  $.ajax({
    type: "GET",
    url: "api/random-sample",
    success: function(jsonContent) {
      updating = false;
      updateButtons();
      currentAudioAttributes = Object.assign({}, jsonContent)
      delete currentAudioAttributes.encrypted_audio
      do_decrypt_and_play(jsonContent);
    },
    error: function(xhr, status, error) {
      console.log("Error: " + error)
      updating = false;
      updateButtons()
    },
    contentType : 'application/json',
  });
}

// Create an instance of WaveSurfer
const ws = WaveSurfer.create({
  container: '#waveform',
  waveColor: 'rgb(200, 0, 200)',
  progressColor: 'rgb(100, 0, 100)',
  normalize: true,
  mediaControls:true,
  height: 0,
})

// Initialize the Spectrogram plugin
ws.registerPlugin(
  Spectrogram.create({
    labels: true,
    labelsColor: "#7c9cb6",
    height: 200,
    splitChannels: true,
    maxFrequency: 8000
  }),
)

// Play on click
ws.once('interaction', () => {
  ws.play()
})

// Create Web Audio context
const audioContext = null

var gainNode = null

// Connect the audio to the equalizer
ws.media.addEventListener(
  'canplay',
  () => {
    if (audioContext == null) {
      audioContext = new AudioContext()
    }
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


function do_update_sample() {
  if(updating) {
    return;
  }
  updating = true;
  updateButtons();

  $.ajax({
    type: "POST",
    url: "api/update-sample",
    data: JSON.stringify(currentAudioAttributes),
    contentType : 'application/json',
    success: next_and_play,
    error: function(xhr, status, error) {
      console.log("Error: " + error)
      updating = false;
      updateButtons()
    },
  });
}

function updateButtons() {
  if (updating) {
    $(".fa-refresh").show();
    $(".a-button").prop("disabled",true);
    // $("#train_button > button").addClass("a-button-disable").prop("disabled",true);;
  } else {
    $(".fa-refresh").hide();
    $(".a-button").prop("disabled",false);
    // $("#train_button > button").removeClass("a-button-disable").prop("disabled",false);;
  }
}

function train_click() {
  console.log("train_click")
  currentAudioAttributes["annotation"] = "train"
  do_update_sample()
}
function not_train_click() {
  console.log("not_train_click")
  currentAudioAttributes["annotation"] = "not_train"
  do_update_sample()
}
function not_sure_click() {
  console.log("not_sure_click")
  currentAudioAttributes["annotation"] = "not_sure"
  do_update_sample()
}

document.getElementById('next_button').addEventListener('click', next_and_play)

document.getElementById('not_train_button').addEventListener('click', not_train_click)
document.getElementById('not_sure_button').addEventListener('click', not_sure_click)
document.getElementById('train_button').addEventListener('click', train_click)
