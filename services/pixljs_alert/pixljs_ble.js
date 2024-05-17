// force timezone to UTC+0200
E.setTimeZone(2);
var BUZZING_TIME = 300000; // buzzer time ms
var SNOOZE_TOTAL_TIME_MS = 24 * 3600 * 1000;
var PIN_BUZZER = A0; // Yellow cable pin Buzzer is connected to
Pixl.setLCDPower(false);
var mode = 0;
var rssi = -100;
let lastSeen = Date(0);
const MODE_SWITCH_MILLI = 4000;
const TIMEOUT_RPI = 15000;
var button_watch = [0, 0, 0, 0];
var timeout_switch = 0;
var timeout_buzzer = 0;
var state_buzzer = 0;
var timeout_stop_alarm = 0;
var snooze_time = 0;
var trainCrossingTime = 0;
var sliderValue = -1;
Bluetooth.setConsole(1);
var zzImage = {
  width: 20,
  height: 20,
  bpp: 1,
  buffer: atob("AAHwAB8GAGDADBwB88AffHwHh8B8GA/DAPx8D+fA/gAH8AB/wMf//D//gf/wD/4AP8A=")
};
var checkImage = {
  width: 20,
  height: 20,
  bpp: 1,
  buffer: atob("AAAAAAAAAAAAAAABAAA4AAfAAPgQHwOD4Hx8A++AH/AA/gAHwAA4AAEAAAAAAAAAAAA=")
};
const tone_times = atob("ZHJkcmRyZHJkcmRyZHJkcmQqZCpkKmRyZHJkKmQqZCpkcmRyZHJkcmRyZHJkKmQqZCpkcmRyZCpkKmQqZHJkcmQqZCpkKmRyZHJkcmRyZHJkcmRyZHJkcmRyZCpkKmQqZHJkcmQqZCpkKmRyZHJkcmRyZHJkcmQqZCpkKmRyZHJkKmQqZCpkcmRyZCpkKmQqZHJkcg==");
var current_note = 0;
const bitmap_font = E.toString(require('heatshrink').decompress(atob('AAUfoEGgEBwEAkU/xGP8UggFkpN/6VE4EGmcgkEmscAhuJkdQiEUgFggEHwkkhEBgVCj0AikEgoxBkE4hAEBCgOAoAuBgIIB4GAwGBHwM+kGSpEj8EBgmCv4XCgUSjMUyUxgEIxEkCgPYgEMhUJh/goEB9GSpMkyOAgfiAoOSk0AiFIolCoPAgE2BYNJkZJB5AaCx+AgMQgFGGYMKhAIBoGgqCPBhUCgECgUBimQmChB5ElEAPkgEPjURg2A+EB/gsCxpHChJrBkQaCkkRiFwgF/I4UkiAaByFIAoMADQQOBh4aB4KJBoP8gFBn+QoCsBhEEBIM/wUCGIK5B/yzBXIUD/GAkEIAAKYBgf5DoMMgMf4BQEnw1B5IFBoCYBZwORpFD6BQCpklhlAgciWYsIg/yd4V+HwUndIPAjEDg0cgEHAwMwHwWfgEGmGgkEoscAjggB+DXCociyVKkyPB/2BoGAjDGBNIMMgDSBr4zBAAIHBT4MAkBJBAgIUBAYIAB8GIokUj6qCoMQxE4gEOhGEoUhD4M4kURgqPBDQOoqkqhsAgkP8olBCIORopyBg/woC3Ba4MXDQMQgkC3zOBwMBGoKhBHgLbBgPhJwM8BAMECwJ9BHwcIweADANQokih0AgeCKANQv4aBgQABIwNIKAMVhMAgRHBxEAniJBwFDMYUIC4IkC4EQiEwIgJaBgUgYgUigEMkOQagIcBk0VhWFoalBsH8YoUf8EEhUE/kYRwImBYQNAXIYACgN8d4MRj/EoQjBpH8ySLBwEEfIOguFEgElhWD8WiqEA88AjVSzNM0ssFg/xgm6qsqyFHK4NBqDZBjwQBwGg1BrCWQMB4AaDrMiDQYAFg0EwVABYMJhwFBglCsNQpEEgERRANC0GgDIUIhAECv4yBgGHwEDgfB/2Av+AawS2BAgb0Bw/AkEQfo0AokUisFEoMFoegq0JgvAisOwNQl0RgFUnUdsGQrjdBhMowDCCn1o4kafAMA+OjiVofAMD62UougnkAh9aqMWyHwCYOhiATCgH10sRAwU/kkSg/kyVIgF8oNg6FEGwP/pNkBgMggf5kuTpMgwEP9mapckwUA/1JkgTCgWC/4RBhEv/UIgODv9gwEgz/IEoQcBkUOLgP7gVgxmBj/AgfqhbYBnxkBxEsjUI/B/BJwNYkfggH5wZXB55IBxBlBCYUihTKBwUggH4xVJlGPwEB/UCwMAz+Ag/ghUGgV+gEfyEwikJ/EB/D7CCYMB4EQx+EjgTB4lCkMQuChBkESo2gGoMcyMowWDKANwomixUPEIPFimJlBrBg8UqUk0hXBnGiiMlg7rBuNFsVKDQMDwQ0B/FUlUJS4OClMYxFEEYMlpWhqFoHwMVlWloOgEYNVlVVgwjBxWhqWomkAr8AhfoSIN8wBpBkEB4JQBot8XgOSiUFgl4NYeEoJQBNYWRg8ANYdERoJrCksURoJrClGDGIOBqCRBh0JwtDkCRBnmBkGAoYsB+D8BwMPOgPEYwMEnkAjwSBpEhDQMwg0g8ODHIP4qFEkUOgEGjHIjUwsEAA=')));
const police_heights = E.toString(require('heatshrink').decompress(atob("gcCgkGAAQFBAAQEBgQLDAA0CCYYOJgkFAYMIg4NHhARDAIgcFFwUFgsCCocGE4INCBIYPBBQJkGP7ZrEGIkEgAEBgpRFRBYACO4qjDBQwAOPAixDG464IA==")));
Graphics.prototype.setFontPixeloidSans = function(scale) {
  // Actual height 9 (8 - 0)
  // Generated with https://www.espruino.com/Font+Converter
  return this.setFontCustom(
    bitmap_font,
    32,
    police_heights,
    9 | 65536 | scale << 8
  );
};
g.setFontPixeloidSans(1);

function disableButtons() {
  for (id = 0; id < 4; id++) {
    if (button_watch[id] > 0) {
      clearWatch(button_watch[id]);
    }
    button_watch[id] = 0;
  }
}

function watchIdleButtons() {
  disableButtons();
  button_watch[0] = setWatch(onPressButtonInstallMode, BTN1, {
    repeat: true,
    edge: 'both',
    debounce: 10
  });
  button_watch[3] = setWatch(onPressButtonTrainDemo, BTN4, {
    repeat: true,
    edge: 'both',
    debounce: 10
  });
}

function updateAdvertisement() {
  NRF.setAdvertising({
    0x183B: mode == 1 ? 'install' : 'normal'
  }, {
    whenConnected: true
  }); //, interval: 1000
}

function switchStateInstall(newMode) {
  mode = newMode;
  updateAdvertisement();
  installScreen();
  if (mode) {
    setTimeout(switchStateInstall, 15 * 60000, false);
  }
}

function rssiPowerHint() {
  if (rssi > -55)
    return "Très bon";
  else if (rssi > -67)
    return "Bon";
  else if (rssi > -80)
    return "Faible";
  else return "Très faible";
}

// Function to draw the slider
function drawSlider() {
  Pixl.setLCDPower(true);
  let sliderWidth = 100;
  let sliderHeight = 10;
  let knobHeight = 15;
  let sliderYPosition = 40;
  // Clear the display
  g.clear();
  // Draw the slider track
  var sliderXPosition = (g.getWidth() - sliderWidth) / 2;
  g.drawRect(sliderXPosition, sliderYPosition, sliderXPosition + sliderWidth,
    sliderYPosition + sliderHeight);
  // Calculate the position of the slider knob vertically
  var knobY = sliderYPosition;
  // Draw the slider knob as a triple vertical line
  var knobYPosition = knobY - (knobHeight - sliderHeight) / 2;
  if(sliderValue >= 0) {
    // Calculate the position of the slider knob
    var knobX = Math.round(sliderValue / 10 * sliderWidth) + sliderXPosition;
    g.fillRect(knobX - 2, knobYPosition, knobX + 2, knobYPosition + knobHeight);
  }
  g.setFontAlign(-1, -1);
  g.drawString("-", 0, 0);
  g.setFontAlign(1, -1);
  g.drawString("+", g.getWidth(), 0);
  g.setFontAlign(0.5, 0.5);
  var x = g.getWidth() / 2; // Calculate the center x-coordinate
  var y = 13 + 15 / 2; // Calculate the center y-coordinate
  g.drawString(sliderValue==-1?"?":sliderValue, x, y);
  g.setFontAlign(0.5, 1);
  if (sliderValue == 0) {
    g.drawString("Pas du tout", g.getWidth() / 2, knobYPosition);
  } else if (sliderValue == 10) {
    g.drawString("Extrêmement", g.getWidth() / 2, knobYPosition);
  }
  g.setFontAlign(0.0, -1);
  x = g.getWidth() / 2; // Calculate the center x-coordinate
  g.drawString("Gêne au passage", x, 0);
  g.setFontAlign(1, 0.0);
  g.drawString("Suivant > ", g.getWidth(), 60);
  // Update the display
  g.flip();
}

function installScreen() {
  if (mode) {
    var y = 0;
    Pixl.setLCDPower(true);
    LED.write(1);
    g.clear();
    text = "Installation mode";
    text_metrics = g.stringMetrics(text);
    g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, 0);
    y += text_metrics.height;
    let diff = Date().valueOf() - lastSeen.valueOf();
    if (diff > TIMEOUT_RPI) {
      text = "No Rpi Connection";
    } else {
      text = "Vu il y a " + parseInt(diff / 1000) + " secondes";
    }
    text_metrics = g.stringMetrics(text);
    y = g.getHeight() / 2 - text_metrics.height / 2;
    g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, y);
    y += text_metrics.height;
    if (diff < TIMEOUT_RPI) {
      text = "RSSI: " + rssi + " dB (" + rssiPowerHint() + ")";
      text_metrics = g.stringMetrics(text);
      g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, y);
    }
    g.flip();
    setTimeout(installScreen, 125);
  } else {
    Pixl.setLCDPower(false);
    LED.write(0);
  }
}

function onPressButtonInstallMode() {
  let state = digitalRead(BTN1);
  if (state) {
    timeout_switch = setTimeout(switchStateInstall, MODE_SWITCH_MILLI, !mode);
  } else {
    clearTimeout(timeout_switch);
  }
}

function onPressButtonTrainDemo() {
  let state = digitalRead(BTN4);
  if (state) {
    timeout_switch = setTimeout(onTrainCrossing, MODE_SWITCH_MILLI, false);
  } else {
    clearTimeout(timeout_switch);
  }
}

function onTrainCrossing(fromTimer) {
  if (snooze_time > Date()) {
    trainCrossingTime = Date();
    buzzerDelay();
    screen_question0();
  }
}

function playTones() {
  if (current_note % 2 == 1) {
    digitalWrite(PIN_BUZZER, 0);
  } else {
    digitalWrite(PIN_BUZZER, 1);
  }
  current_note += 1;
  if (buzzerEnabled) {
    setTimeout(playTones, tone_times.charCodeAt(current_note % tone_times.length));
  } else {
    digitalWrite(PIN_BUZZER, 0);
  }
}

function stopAlarm() {
  buzzerEnabled = false;
  digitalWrite(PIN_BUZZER, 0);
}

function buzzerDelay() {
  buzzerEnabled = true;
  playTones();
  timeout_stop_alarm = setTimeout(stopAlarm, BUZZING_TIME);
}

function screen_question1() {
  sliderValue = -1;
  disableButtons();
  stopAlarm();
  drawSlider();
  button_watch[0] = setWatch(e => {
    if(sliderValue==-1) sliderValue=0;
    sliderValue = Math.max(0, sliderValue - 1);
    drawSlider();
  }, BTN1, {
    repeat: true,
    edge: 'rising'
  }, BTN1);
  button_watch[1] = setWatch(e => {
    if(sliderValue==-1) sliderValue=10;
    sliderValue = Math.min(10, sliderValue + 1);
    drawSlider();
  }, BTN2, {
    repeat: true,
    edge: 'rising'
  }, BTN2);

}

function screen_question2() {
  disableButtons();
  stopAlarm();
  g.clear();
  g.flip();
}

function onClickSnooze() {
  snooze_time = Date() + SNOOZE_TOTAL_TIME_MS;
  stopAlarm();
  Pixl.setLCDPower(false);
  LED.write(0);
}

function screen_question0() {
  Pixl.setLCDPower(true);
  LED.write(0);
  g.clear();
  g.drawImage(zzImage, 0, 0);
  text = "Avez-vous entendu un \ntrain juste avant la \nnotification ?";
  text_metrics = g.stringMetrics(text);
  g.setFontAlign(-1, -1);
  g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, zzImage.height + 1);
  g.setFontAlign(-1, 1);
  g.drawString("Oui", 0, g.getHeight());
  g.setFontAlign(1, 1);
  g.drawString("Non", g.getWidth(), g.getHeight());
  g.flip();
  disableButtons();
  button_watch[0] = setWatch(onClickSnooze, BTN1, {
    repeat: false,
    edge: 'rising',
    debounce: 10
  });
  button_watch[2] = setWatch(screen_question2, BTN3, {
    repeat: false,
    edge: 'rising',
    debounce: 10
  });
  button_watch[3] = setWatch(screen_question1, BTN4, {
    repeat: true,
    edge: 'both',
    debounce: 10
  });
}
updateAdvertisement();
watchIdleButtons();
screen_question0();