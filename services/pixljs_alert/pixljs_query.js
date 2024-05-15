
// force timezone to UTC+0200
E.setTimeZone(2);
Pixl.setLCDPower(false);
var mode=0;
var rssi=-100;
let lastSeen = Date(0);
const MODE_SWITCH_MILLI = 4000;
var button_watch = [0,0,0,0];
var timeout_switch = 0;
Bluetooth.setConsole(1);
const bitmap_font = E.toString(require('heatshrink').decompress(atob('AAUfoEGgEBwEAkU/xGP8UggFkpN/6VE4EGmcgkEmscAhuJkdQiEUgFggEHwkkhEBgVCj0AikEgoxBkE4hAEBCgOAoAuBgIIB4GAwGBHwM+kGSpEj8EBgmCv4XCgUSjMUyUxgEIxEkCgPYgEMhUJh/goEB9GSpMkyOAgfiAoOSk0AiFIolCoPAgE2BYNJkZJB5AaCx+AgMQgFGGYMKhAIBoGgqCPBhUCgECgUBimQmChB5ElEAPkgEPjURg2A+EB/gsCxpHChJrBkQaCkkRiFwgF/I4UkiAaByFIAoMADQQOBh4aB4KJBoP8gFBn+QoCsBhEEBIM/wUCGIK5B/yzBXIUD/GAkEIAAKYBgf5DoMMgMf4BQEnw1B5IFBoCYBZwORpFD6BQCpklhlAgciWYsIg/yd4V+HwUndIPAjEDg0cgEHAwMwHwWfgEGmGgkEoscAjggB+DXCociyVKkyPB/2BoGAjDGBNIMMgDSBr4zBAAIHBT4MAkBJBAgIUBAYIAB8GIokUj6qCoMQxE4gEOhGEoUhD4M4kURgqPBDQOoqkqhsAgkP8olBCIORopyBg/woC3Ba4MXDQMQgkC3zOBwMBGoKhBHgLbBgPhJwM8BAMECwJ9BHwcIweADANQokih0AgeCKANQv4aBgQABIwNIKAMVhMAgRHBxEAniJBwFDMYUIC4IkC4EQiEwIgJaBgUgYgUigEMkOQagIcBk0VhWFoalBsH8YoUf8EEhUE/kYRwImBYQNAXIYACgN8d4MRj/EoQjBpH8ySLBwEEfIOguFEgElhWD8WiqEA88AjVSzNM0ssFg/xgm6qsqyFHK4NBqDZBjwQBwGg1BrCWQMB4AaDrMiDQYAFg0EwVABYMJhwFBglCsNQpEEgERRANC0GgDIUIhAECv4yBgGHwEDgfB/2Av+AawS2BAgb0Bw/AkEQfo0AokUisFEoMFoegq0JgvAisOwNQl0RgFUnUdsGQrjdBhMowDCCn1o4kafAMA+OjiVofAMD62UougnkAh9aqMWyHwCYOhiATCgH10sRAwU/kkSg/kyVIgF8oNg6FEGwP/pNkBgMggf5kuTpMgwEP9mapckwUA/1JkgTCgWC/4RBhEv/UIgODv9gwEgz/IEoQcBkUOLgP7gVgxmBj/AgfqhbYBnxkBxEsjUI/B/BJwNYkfggH5wZXB55IBxBlBCYUihTKBwUggH4xVJlGPwEB/UCwMAz+Ag/ghUGgV+gEfyEwikJ/EB/D7CCYMB4EQx+EjgTB4lCkMQuChBkESo2gGoMcyMowWDKANwomixUPEIPFimJlBrBg8UqUk0hXBnGiiMlg7rBuNFsVKDQMDwQ0B/FUlUJS4OClMYxFEEYMlpWhqFoHwMVlWloOgEYNVlVVgwjBxWhqWomkAr8AhfoSIN8wBpBkEB4JQBot8XgOSiUFgl4NYeEoJQBNYWRg8ANYdERoJrCksURoJrClGDGIOBqCRBh0JwtDkCRBnmBkGAoYsB+D8BwMPOgPEYwMEnkAjwSBpEhDQMwg0g8ODHIP4qFEkUOgEGjHIjUwsEAA=')));
const police_heights = atob("AwIEBgYGBgIEBAQEAgQCBgYGBgYGBgYGBgYCAgQEBAYGBgYGBgYGBgYEBQYGCAcGBgYGBgYGBggGBgYEBgQGBAYGBgYGBgQGBgIFBQIIBgYGBgUGBAYGCAYGBgUCBQYAAAAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAgYGBgYCBgYIBgYEAAgGBQQGBgYGBgIGBgYGBgYGBgYGBgYGBgcGBgYGBgQEBAQGBwYGBgYGBgYGBgYGBgYGBgYGBgYGCAYGBgYGAgIEAgYGBgYGBgYEBgYGBgYGBgY=");
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
  for(id=0;id<4;id++) {
    if(button_watch[id] > 0) {
      clearWatch(button_watch[id]);
    }
    button_watch[id] = 0;
  }
}

function update_advertisement() {
  NRF.setAdvertising({
  0x183B : mode == 1 ? 'install' : 'normal'
});
}

function switchStateInstall() {
  mode = !mode;
  update_advertisement();
  installScreen();
}
function leadZero(value) {
  return ("0"+value.toString()).substr(-2);
}
function rssiPowerHint() {
  if(rssi>-55)
    return "Très bon";
  else if(rssi>-67)
    return "Bon";
  else if(rssi>-80)
    return "Faible";
  else return "Très faible";
}
function installScreen() {
  if(mode){
    var y=0;
    Pixl.setLCDPower(true);
    LED.write(1);
    g.clear();
    text = "Installation mode";
    text_metrics = g.stringMetrics(text);
    g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, 0);
    y+=text_metrics.height;
    if(lastSeen.valueOf() < 1){
      text = "No Rpi Connection";
    }else{
      let diff=Date().valueOf()-lastSeen.valueOf();
      text="Vu il y a "+parseInt(diff/1000)+" secondes";
    }
    text_metrics = g.stringMetrics(text);
    y=g.getHeight() / 2 - text_metrics.height / 2;
    g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, y);
    y+=text_metrics.height;
    if(lastSeen.valueOf() > 1){
        text="RSSI: "+rssi+" dB ("+rssiPowerHint()+")";
        text_metrics = g.stringMetrics(text);
        g.drawString(text, g.getWidth() / 2 - text_metrics.width / 2, y);
    }
    g.flip();
    setTimeout(installScreen, 125);
  }else{
    Pixl.setLCDPower(false);
    LED.write(0);
  }
}

function onPressButton1(){
  let state = digitalRead(BTN1);
  if(state){
    timeout_switch = setTimeout(switchStateInstall, MODE_SWITCH_MILLI);
  } else {
    clearTimeout(timeout_switch);
  }
}

update_advertisement();
button_watch[0] = setWatch(onPressButton1, BTN1, {  repeat: true,  edge: 'both', debounce : 10});
installScreen();
