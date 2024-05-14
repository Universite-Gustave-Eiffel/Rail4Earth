Bluetooth.setConsole(1);
Pixl.setLCDPower(false);
var mode=0;
const MODE_SWITCH_MILLI = 4000;
var button_watch = [0,0,0,0];
var timeout_switch = 0;

function disableButtons() {
  for(id=0;id<4;id++) {
    if(button_watch[id] > 0) {
      clearWatch(button_watch[id]);
    }
    button_watch[id] = 0;
  }
}

function update_advertisement() {
  NRF.setAdvertising({
  0x183B : mode == 1 ? 'debug' : 'normal'
}, options={interval:1000});
}

function switchStateInstallation() {
  mode = !mode;
  update_advertisement();
  print("change mode");
}

function onPressButton1(){
  let state = digitalRead(BTN1);
  if(state){
    timeout_switch = setTimeout(switchStateInstallation, MODE_SWITCH_MILLI, true);
  } else {
    clearTimeout(timeout_switch);
  }
}

update_advertisement();

button_watch[0] = setWatch(onPressButton1, BTN1, {  repeat: true,  edge: 'both', debounce : 10});

