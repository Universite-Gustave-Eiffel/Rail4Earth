// force timezone to UTC+0200
const CODE_VERSION=2;
E.setTimeZone(2);
const BUZZING_TIME = 60000; // buzzer time ms
const RESET_NO_ANSWER = 60000;
const QUESTIONS = [
  ["Juste avant la notification,\n où étiez-vous ?",
    ["Pièce principale", "Autre pièce", "Extérieur"]
  ],
  ["Juste avant la notification,\nqu'étiez-vous en train de\nfaire ?",
    ["Lire ou se concentrer", "Loisir", "Se reposer ou dormir", "Discuter", "Téléphone", "Tâches ménagères", "Autre"]
  ],
  ["Avant le passage de train,\nvous diriez que l'ambiance\nsonore à l'intérieur de\nvotre logement était :",
    ["Très calme", "Plutôt calme", "Ni calme ni bruyante", "Plutôt bruyante", "Très bruyante"]
  ],
  ["Les fenêtres/baies\nvitrées de la pièce où\nvous vous trouviez\nétaient :",
    ["Toutes fermées", "Certaines ouvertes", "Toutes ouvertes"]
  ]
];
var PIN_BUZZER = A0; // Yellow cable pin Buzzer is connected to
Pixl.setLCDPower(false);
var mode = 0; // 0 wait 1 install 2 answering question
var rssi = -100;
let lastSeen = Date(0);
const MODE_SWITCH_MILLI = 2000;
const TIMEOUT_RPI = 15000;
var timeout_switch = 0;
var timeout_buzzer = 0;
var timeout_reset = 0;
var state_buzzer = 0;
var timeout_stop_alarm = 0;
var snooze_time = 0;
var trainCrossingTime = 0;
var sliderValue = -1;
var currentForm = [];
var formStack = [];
var question_index = 0;
var answer_index = 0;
Bluetooth.setConsole(1);
const tone_times = atob("ZHJkcmRyZHJkcmRyZHJkcmQqZCpkKmRyZHJkKmQqZCpkcmRyZHJkcmRyZHJkKmQqZCpkcmRyZCpkKmQqZHJkcmQqZCpkKmRyZHJkcmRyZHJkcmRyZHJkcmRyZCpkKmQqZHJkcmQqZCpkKmRyZHJkcmRyZHJkcmQqZCpkKmRyZHJkKmQqZCpkcmRyZCpkKmQqZHJkcg==");
var current_note = 0;
const bitmap_font = E.toString(atob('AAAAH0AGAAGAACI/iI/iIABkSX/SRMAGMyAgJmMADYkjUBAUAGAAB4QkCAECQh4AFAQFAAAgOAgAAGAAgEAgAAEAAMCAgIGAAD4gkkgj4AEEgn8AgEACEhkUkjEACIgkkkjYAAwKCQ/gQAHokkkkkYAD4kkkkiYAEEhEQkHAADYkkkkjYADIkkkkj4ABEABGAAgKCIABQKBQACIKAgACAgEUkDAAH8glkknkAA8aEQaA8AH8kkkkjYAD4gkEgiIAH8gkERBwAH8kkkkkEAH8kEgkEAAD4gkkkg8AH8EAgEH8AEE/kEAAYAgE/AA/ggKCIggA/gEAgEAgA/iAIAgICA/gA/kAYAwBH8AD4gkEgj4AH8kEgkDAAD4gkUhD0AH8kEwlDEADIkkkkiYAEAgH8gEAAH4AgEAn4AHAGAMGHAAHwBgwYAwBnwAGMKAgKGMAHAEA8EHAAEMikkomEAH+gUCAGAIAgCAMAECgX+ABAQEAQBAAACAQCAAAgCAAAAAA4IhEFB8AH8FBEIg4AA4IhEIhEAA4IhEFH8AA4KhUKg0ABA/lAAA4IpFFJ+AH8EBAIA8AF8AAEAQCvgA/gQFBEAH8AB8IBAHhAIA8AB8EBAIA8AA4IhEIg4AB/FBEIg4AA4IhEFB/AB8CAgIAAEhUKhUJAAIH8IgAPAEAgEPAAOAIAgIOAAPAEBAwBAEPAAIgoCAoIgAMIZAwYMAAJhUKhUMgAGD8gUCAH+AECgT8GAAEBAEAQEAAAAAAAAAAAXwAHBEfxEIgAEj8kkEQgARBwKBwRAAlCoPiolAA5wAaUplMpSwAAAAAAAAAAfEEulUqkEfAAEFQqFQeAACAoKgoIgAEAgHAAfEEulkikEfAAAAAAAAAAAYEgkDAAAkOgkAEQmFQSAQAEQqFQqCgAAAACAgAAAB/AgEAh4ADA8H+gH+AAgAAAAICAAAAEQiHwCAQADgiEQiDgABEFBUFAQAFQ6BWCQXAFQ6BUC4RAFQ6HWCQXAAMCSiAQEAAPmjEGgPAAPGjEmgPAAPWlEWgPAAPWlEWkPAA8aEQaA8AAPWlEWgPAD8kEgfkkkgAfEFg0ERAAP9JZJJIIAP5JZNJIIAP7JpLJIIA/kkkkkggAoL/IIAIL/oIAYN/YIAgn8ggA/kkgiIOAAP7AmCMgR/AA+oLBII+AA+ILBoI+AA+YNBYI+AA+YNBYM+AD4gkEgj4ACIKAgKCIAD4ikkoj4AB+gKBAJ+AB+AKBgJ+AB+QMBQJ+AH4AgEAn4ABwBCPhBwAH8RCIRBwAD8gEkagIAAckSiCg+AAcESiig+AAcUUiSg+AAcUUiSk+AA4ohElB8AAcUViSg+AA4IhEPhUKgkAA4IpGIhEAAclSqFQaAAcFSqlQaAAcVUqVQaAA4qhUqg0AF8AC+gCAnyAAB8gAcEUiUV8AA+SEgUEeAAckSiEQcAAcESikQcAAcUUiUQcAAcUUiUUcAA4ohEog4AAgVAgAA4JhUMg4AA8gSCAQ8AA8ASCgQ8AA8QUCQQ8AB4ggEgh4AAwBiDhgwAH+FBEIg4ABhjIGjBgAA=='));
const police_heights = E.toString(atob("AwIEBgYGBgIEBAQEAgQCBgYGBgYGBgYGBgYCAgQEBAYGBgYGBgYGBgYEBQYGCAcGBgYGBgYGBggGBgYEBgQGBAYGBgYGBgQGBgIFBQIIBgYGBgUGBAYGCAYGBgUCBQYAAAAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAgYGBgYCBgYIBgYEAAgGBQQGBgYGBgIGBgYGBgYGBgYGBgYGBgcGBgYGBgQEBAQGBwYGBgYGBgYGBgYGBgYGBgYGBgYGCAYGBgYGAgIEAgYGBgYGBgYEBgYGBgYGBgY="));
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
  clearWatch();
}

function watchIdleButtons() {
  disableButtons();
  setTimeout(e => {
    setWatch(onPressButtonInstallMode, BTN1, {
      repeat: true,
      edge: 'both',
      debounce: 100
    });
    setWatch(onPressButtonTrainDemo, BTN4, {
      repeat: true,
      edge: 'both',
      debounce: 100
    });
    setWatch(screenIdle, BTN3, {
      repeat: false,
      edge: 'falling',
      debounce: 10
    });
    setWatch(screenIdle, BTN2, {
      repeat: false,
      edge: 'falling',
      debounce: 10
    });
  }, 2000);
}

function updateAdvertisement() {
  NRF.setAdvertising({
    0x183B: mode == 1 ? 'install' : 'normal',
    0x180A: formStack.length,
    0x180B: CODE_VERSION
  }, {
    whenConnected: true
  }); //, interval: 1000
}

function switchStateInstall(newMode) {
  mode = newMode;
  updateAdvertisement();
  if(mode==1) {
    Pixl.setLCDPower(true);
    LED.write(1);
    disableButtons();
    setWatch(e => {switchStateInstall(0);}, BTN1, {
      repeat: false,
      debounce: 10
    });
  }
  installScreen();
  if (mode) {
    setTimeout(switchStateInstall, 15 * 60000, 0);
  } else {
    watchIdleButtons();
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
function questionBDrawScreen() {
  installResetTimeout();
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
  if (sliderValue >= 0) {
    // Calculate the position of the slider knob
    var knobX = Math.round(sliderValue / 10 * sliderWidth) + sliderXPosition;
    g.fillRect(knobX - 2, knobYPosition, knobX + 2, knobYPosition + knobHeight);
  }
  if (sliderValue > 0) {
    g.setFontAlign(-1, 1);
    g.drawString("<", 0, g.getHeight());
  }
  if (sliderValue < 10) {
    g.setFontAlign(1, 1);
    g.drawString(">", g.getWidth(), g.getHeight());
  }
  var x = g.getWidth() / 2; // Calculate the center x-coordinate
  let text = "Valider > ";
  g.setFontAlign(1, -1);
  g.drawString(text, g.getWidth(), 0);
  let t = g.stringMetrics(text);
  var y = t.height + 2;
  g.setFontAlign(0.5, 0.5);
  g.drawString("Gêne au passage", g.getWidth() / 2, y);
  y += t.height + 2;
  g.drawString(sliderValue == -1 ? "?" : sliderValue, x, y);
  g.setFontAlign(0.5, 1);
  if (sliderValue == 0) {
    g.drawString("Pas du tout", g.getWidth() / 2, knobYPosition);
  } else if (sliderValue == 10) {
    g.drawString("Extrêmement", g.getWidth() / 2, knobYPosition);
  }
  // Update the display
  g.flip();
}

function installScreen() {
  if (mode == 1) {
    g.clear();
    g.setFontAlign(0.5, -1);
    let text = "Installation mode\nPixl.js " + NRF.getAddress().substr(12, 5).replace(":", "");
    g.drawString(text, g.getWidth() / 2, 0);
    let diff = Date().valueOf() - lastSeen.valueOf();
    if (diff > TIMEOUT_RPI) {
      text = "No Rpi Connection";
    } else {
      text = "Vu il y a " + parseInt(diff / 1000) + " secondes\nRSSI: " + rssi + " dB (" + rssiPowerHint() + ")";
    }
    g.setFontAlign(0.5, 0.5);
    g.drawString(text, g.getWidth() / 2 , g.getHeight() / 2);
    g.flip();
    setTimeout(installScreen, 500);
  } else {
    Pixl.setLCDPower(false);
    LED.write(0);
  }
}

function onPressButtonInstallMode() {
  try {
    clearTimeout(timeout_switch);
    timeout_switch = 0;
  } catch (e) {
    //ignore
  }
  let state = digitalRead(BTN1);
  if (state) {
    timeout_switch = setTimeout(switchStateInstall, MODE_SWITCH_MILLI, !mode);
  } else {
    if(mode==0) {
      screenIdle();
    }
  }
}

function onPressButtonTrainDemo() {
  print("press demo button");
  let state = digitalRead(BTN4);
  if (state) {
    timeout_switch = setTimeout(onTrainCrossing, MODE_SWITCH_MILLI, false);
  } else {
    if(mode==0) {
      screenIdle();
    }
    clearTimeout(timeout_switch);
  }
}

function onTrainCrossing(demo) {
  print("train crossing");
  if (snooze_time < Date() && mode == 0) {
    trainCrossingTime = Date();
    buzzerDelay();
    screenQuestionA();
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

function screenQuestionB() {
  sliderValue = 5;
  disableButtons();
  questionBDrawScreen();
  setWatch(e => {
    sliderValue = Math.max(0, sliderValue - 1);
    questionBDrawScreen();
  }, BTN4, {
    repeat: true,
    edge: 'rising'
  });
  setWatch(e => {
    sliderValue = Math.min(10, sliderValue + 1);
    questionBDrawScreen();
  }, BTN3, {
    repeat: true,
    edge: 'rising'
  });
  setWatch(e => {
    recordAnswer('B', sliderValue);
    onQuestionCE(0);
  }, BTN2, {
    repeat: false,
    edge: 'rising'
  });
}

function questionCEDrawScreen() {
  installResetTimeout();
  g.clear();
  g.setFontAlign(1, -1);
  text = "Valider >";
  g.drawString(text, g.getWidth(), 0);
  text_metrics = g.stringMetrics(text);
  g.setFontAlign(-1, 0.5);
  g.drawString(QUESTIONS[questionIndex][0], 0, g.getHeight() / 2);
  y = text_metrics.height;
  text_metrics = g.stringMetrics(QUESTIONS[questionIndex][0]);
  y += text_metrics.height + 1;
  g.setFontAlign(0.5, 1);
  g.drawString(QUESTIONS[questionIndex][1][answer_index], g.getWidth() / 2, g.getHeight());
  let answerCount = QUESTIONS[questionIndex][1].length;
  if (answer_index > 0) {
    g.setFontAlign(-1, 1);
    g.drawString("<", 0, g.getHeight());
  }
  if (answer_index < answerCount - 1) {
    g.setFontAlign(1, 1);
    g.drawString(">", g.getWidth(), g.getHeight());
  }
  g.flip();
}

function onQuestionCE(index) {
  questionIndex = index;
  answer_index = parseInt(QUESTIONS[questionIndex][1].length / 2); // default mid answer
  disableButtons();
  questionCEDrawScreen();
  setWatch(e => {
    answer_index = Math.max(0, answer_index - 1);
    questionCEDrawScreen();
  }, BTN4, {
    repeat: true,
    edge: 'rising'
  });
  setWatch(e => {
    answer_index = Math.min(QUESTIONS[questionIndex][1].length - 1, answer_index + 1);
    questionCEDrawScreen();
  }, BTN3, {
    repeat: true,
    edge: 'rising'
  });
  setWatch(e => {
    recordAnswer(String.fromCharCode(67 + questionIndex), QUESTIONS[questionIndex][1][answer_index]);
    if (questionIndex + 1 < QUESTIONS.length) {
      onQuestionCE(questionIndex + 1);
    } else {
      endForm();
    }
  }, BTN2, {
    repeat: false,
    edge: 'rising'
  });
}

function endForm() {
  formStack.push(JSON.stringify(Object.fromEntries([
    ["trainCrossingTime", trainCrossingTime],
    ["answers", Object.fromEntries(currentForm)]
  ])));
  disableButtons();
  currentForm = [];
  g.clear();
  g.setFontAlign(0.5, 0.5);
  g.drawString("Merci pour votre réponse\nAu prochain passage !", g.getWidth() / 2, g.getHeight() / 2);
  g.flip();
  mode = 0;
  installResetTimeout()
  updateAdvertisement();
}

function onClickSnooze() {
  snooze_time = Date();
  snooze_time.setHours(23);
  snooze_time.setMinutes(59);
  snooze_time.setSeconds(59);
  stopAlarm();
  Pixl.setLCDPower(false);
  LED.write(0);
  watchIdleButtons();
  mode = 0;
}

function recordAnswer(questionIndex, answers) {
  currentForm.push([questionIndex, answers]);
  print(JSON.stringify(Object.fromEntries(currentForm)));
}

function installResetTimeout() {
  if (timeout_reset > 0) {
    try {
      clearTimeout(timeout_reset);
    } catch (e) {
      //ignore
    }
  }
  timeout_reset = setTimeout(a => {
    timeout_reset = 0;
    switchStateInstall(0);
  }, RESET_NO_ANSWER);
}

function screenQuestionA() {
  installResetTimeout();
  mode = 2;
  currentForm = [];
  Pixl.setLCDPower(true);
  LED.write(1);
  g.clear();
  let text = "Désactiver 24H";
  text_metrics = g.stringMetrics(text);
  g.setFontAlign(-1, -1);
  g.drawString(text, 0, 0);
  text = "Avez-vous entendu un \ntrain juste avant la \nnotification ?";
  text_metrics = g.stringMetrics(text);
  g.setFontAlign(-1, -1);
  g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, text_metrics.height + 1);
  g.setFontAlign(-1, 1);
  g.drawString("Oui", 0, g.getHeight());
  g.setFontAlign(1, 1);
  g.drawString("Non", g.getWidth(), g.getHeight());
  g.flip();
  disableButtons();
  setTimeout(e => {
  setWatch(onClickSnooze, BTN1, {
    repeat: false,
    edge: 'rising',
    debounce: 10
  });
  setWatch(function() {
    stopAlarm();
    recordAnswer('A', 'non');
    onQuestionCE(0);
  }, BTN3, {
    repeat: false,
    edge: 'rising',
    debounce: 10
  });
  setWatch(function() {
    stopAlarm();
    recordAnswer('A', 'oui');
    screenQuestionB();
  }, BTN4, {
    repeat: true,
    edge: 'both',
    debounce: 10
  });
  }, 500);
}

function screenIdle() {
  disableButtons();
  setWatch(onPressButtonInstallMode, BTN1, {
    repeat: true,
    edge: 'both',
    debounce: 10
  });
  setWatch(onPressButtonTrainDemo, BTN4, {
    repeat: true,
    edge: 'both',
    debounce: 10
  });
  setWatch(e => {
    mode = 2;
    currentForm = [];
    trainCrossingTime = Date();
    recordAnswer('A', "user");
    screenQuestionB();
  }, BTN2, {
    repeat: false,
    edge: 'rising'
  });
  Pixl.setLCDPower(true);
  LED.write(1);
  g.clear();
  g.setFontAlign(1, -1);
  g.drawString("Un passage m'a gêné>\naccéder au questionnaire", g.getWidth(), 0);
  g.setFontAlign(1, 1);
  let text = "Mettre en veille>";
  let remainSnooze = (snooze_time - Date().valueOf())/1000.0;
  if (remainSnooze > 0) {
    text = "Encore ";
    if(remainSnooze>=3600)
      text += parseInt(remainSnooze / 3600) + "h";
    text += parseInt((remainSnooze % 3600)/60) + "m de veille.\nRéactiver le boitier>";
    setWatch(e => {
      snooze_time = 0;
      screenIdle();
    }, BTN3, {
      repeat: false,
      edge: 'rising',
      debounce: 10
    });
  } else {
    setWatch(onClickSnooze, BTN3, {
      repeat: false,
      edge: 'rising',
      debounce: 10
    });
  }
  g.drawString(text, g.getWidth(), g.getHeight());
  g.flip();
  installResetTimeout();
}

updateAdvertisement();
watchIdleButtons();