# OnoSensor

OnoSensor, a system developed by UMRAE, is an environmental acoustic sensor that costs less than €500 and consists solely of readily available off-the-shelf hardware and a fully featured, 100% open-source software solution. As part of the “Rail4Earth” research project, 50 of these sensors were deployed across France and collected no less than 1 TB of data (acoustic and audio indicators).

This platform aim to define an open source hardware and software stack for the deployment of a large set of advanced noise sensors.

Installed on a Raspberry Pi (3+, 4, 5) device.

- Computation of noise indicators LZeq LAeq LCeq with iec_61672_1_2013 spectrum analysis.
- Recognition of 1Khz 94dB calibration device and storage of microphone sensitivity
- Embedded sound source classification using tensorflow light and Yamnet with 521 tags
- Optional recording and encryption (public/private key) of short audio sequence triggered by sound classification tags
- Storage and transfer of all data into bulked compressed json files, processed by big-data analysis open source platform Elastic-Search/Kibana.
- Visualization through Kibana
- All services on server(s) through a straightforward Docker compose configuration.
- Custom html public dashboard with Python FastApi

![rpi.jpg](docs%2Fimages%2Frpi.jpg)
*Stack with Raspberry Pi 3B+ with PiJuice and 4G/GPS Header Telit*


![sensor_case.jpg](docs%2Fimages%2Fsensor_case.jpg)
*Microphone on  Tripod with RPI in a case*

![dashboard_map.png](docs%2Fimages%2Fdashboard_map.png)
*Web dashboard that display sensors connection status*

![dashboard_audiorecord.png](docs%2Fimages%2Fdashboard_audiorecord.png)
*Web dashboard with integrated audio player for encrypted audio recordings*

![kibana_dashboard.png](docs%2Fimages%2Fkibana_dashboard.png)
*Kibana dashboard with various analysis*

![kibana_map.png](docs%2Fimages%2Fkibana_map.png)
*Kibana map with location of sensors*

