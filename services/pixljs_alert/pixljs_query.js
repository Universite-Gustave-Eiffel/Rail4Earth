Bluetooth.setConsole(1);
Pixl.setLCDPower(false);
var mode=0;
var button_watch = [0,0,0,0];

function update_advertisement() {
  NRF.setAdvertising({
    0x1801 : [mode]
  });
}

update_advertisement();

