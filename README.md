# NIBE SMO S40 and S2125 heatpump to MQTT
MQTT client/parser for NIBE SMO S40 and S2125 heatpump.
(I guess other Nibe S-series will work)

Inspired and reuse from https://github.com/yozik04/nibe-mqtt

You can download supported register list from SMO S40
This list can converted to json (see data directory, csv file is hard coded in convert_csv.py)
Or use the one provided

Note, register map can change after SMO firmware upgrade

## Usage:
* Copy `systemd/nibe-s2125-mqtt.service` to `/etc/systemd/system`
* Adapt path in `nibe-s2125-mqtt.service` to your install location (default: `/opt/iot/nibe`)
* Copy `config.rename.py` to `config.py` and adapt for your configuration (minimal: mqtt ip, username, password, RS485)
* `sudo systemctl enable nibe-s2125-mqtt.service`
* `sudo systemctl start nibe-s2125-mqtt.service`

Use
http://mqtt-explorer.com/
to test & inspect MQTT messages

## Requirements
* paho-mqtt
* pyModbusTCP
* influxdb
* python 3.x
* pandas, nibe, uni-slugify (for convert_csv)

Tested under Linux & Windows; 

## InfluxDB
* Use `telegraf-nibe-s2125.conf` as Telegraf configuration file to get Nibe MQTT data into InfluxDB

## Licence
GPL v3

## Versions
1.0.0
* Initial version

## Limitations
* Nibe does not maintain a count on defrosts.
* A counter is implemented, reading back last value from InfluxDB v1 when parser is started
* Reading back last value from InfluxDB v2 is not supported yet
* If InfluxDB is not used, then counter is added to MQTT message
