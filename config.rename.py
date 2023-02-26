"""
  Rename to config.py

  Configure:
  - MQTT client
  - NIBE S2125
  - Debug level

"""

# [ LOGLEVELS ]
# DEBUG, INFO, WARNING, ERROR, CRITICAL
loglevel = "INFO"

# NROF parameter reads from NIBE per hour (60 equals every minute)
# No safety checks build in for too high read_rate
READ_RATE = 60


# [ MQTT Parameters ]
# Using local dns names was not always reliable with PAHO
MQTT_BROKER = "192.168.1.1"
MQTT_PORT = 1883
MQTT_CLIENT_UNIQ = 'mqtt-nibe'
MQTT_QOS = 1
MQTT_USERNAME = "username"
MQTT_PASSWORD = "password"

# Max nrof MQTT messages per second
# Set to 0 for unlimited rate
MQTT_RATE = 100
MQTT_TOPIC_PREFIX = "nibe-smos40"

# [ INFLUXDB v1 ]
# Not required, but is used to maintain & update defrost counter
# Comment if not used
INFLUXDB1_HOST = "192.168.1.1"
INFLUXDB1_PORT = 8084
# no authentication implemented yet...
INFLUXDB1_DB = "nibe"

# See telegraf-nibe-s2125.conf
INFLUXDB1_SERIES = "nibe_s2125_mqtt"

# [ TCP ModBus ]
# DNS names do not always work....
#MODBUS_ADDRESS = 'NIBE.fritz.box'
MODBUS_ADDRESS = '192.168.1.16'

# File with register info
JSON = "data/smos40.json"

# [ Registers you want to MQTT; use JSON file as reference ]
NIBE_REGISTER = [
"30001",
"40011",
"40018",
"30037",
"30039",
"30088",
"30301",
"30401",
"30404",
"30406",
"30407",
"30408",
"30409",
"30410",
"30412",
"30550",
"30551",
"30552",
"40857",
"31017",
"31029",
"31066",
"31475",
"31478",
"31479",
"31480",
"31481",
"31489",
"31491",
"31621",
"31622",
"31636",
"31802",
"31803",
"31804",
"31805",
"31854",
"31967",
"31975",
"32283",
"32305",
]
