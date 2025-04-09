This folder contain scripts that will use noisesensor to convert
a linux os into an advanced noise measurement device:

- Computation of noise indicators LZeq LAeq LCeq with iec_61672_1_2013 spectrum analysis.
- Sound classification using tensorflow light and Yamnet with 521 tags
- Optional recording of short audio sequence triggered by sound classification tags
- Storage of analysis into bulked compressed json files, compatible with big-data analysis such as Elastic-Search

On raspberry-pi, using symbolic link, customize and install all systemd services defined in [rpi_systemd](rpi_systemd) folder.

# Launch unit test

```shell
tox run
```

# Install on Raspberry Pi

Clone or copy this repository on the rpi.

Install noisesensor library (from repository folder)

```shell
pip install .
```

Install services dependencies

```shell
cd services
pip -r requirements.txt
```

Edit recording service with the characteristics of your microphone (device name/sampling rate)

Select plughw:XXX in order to be able to output audio samples in FLOAT format.

```shell
arecord -L
nano rpi_systemd/zerorecord.service
```


Install systemd services

```shell
cd /etc/systemd/system
sudo ln -s /home/pi/noisesensor/services/rpi_systemd/*.service ./
sudo systemctl daemon-reload
sudo systemctl enable zero*
```

