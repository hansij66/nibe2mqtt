#!/usr/bin/python3

"""
 DESCRIPTION
   Read NIBE S2125/SMO S40 via TCP modbus

2 Worker threads:
  - MODBUS TCP reader & parser
  - MQTT client

        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with this program.  If not, see <http://www.gnu.org/licenses/>.

Inspired by:
  https://github.com/yozik04/nibe-mqtt

Modified to use pyModbusTCP, so it works also under Windows
Supports (only) S series with TCP Modbus

"""

__version__ = "1.0.4"
__author__ = "Hans IJntema"
__license__ = "GPLv3"

import signal
import socket
import time
import sys
import threading

# Local imports
import config as cfg
import nibe_parser as nibe
import mqtt as mqtt

from log import logger
logger.setLevel(cfg.loglevel)


# ------------------------------------------------------------------------------------
# Instance running?
# ------------------------------------------------------------------------------------
import os
script = os.path.basename(__file__)
script = os.path.splitext(script)[0]

# Ensure that only one instance is started
if sys.platform == "linux":
  lockfile = "\0" + script + "_lockfile"
  try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # Create an abstract socket, by prefixing it with null.
    s.bind(lockfile)
    logger.info(f"Starting {__file__}; version = {__version__}")
  except IOError as err:
    logger.info(f"{lockfile} already running. Exiting; {err}")
    sys.exit(1)

# ------------------------------------------------------------------------------------
# LATE GLOBALS
# ------------------------------------------------------------------------------------

# To flag that all threads (except MQTT) have to stop
t_threads_stopper = threading.Event()

# Assumption is that exit is with error unless called via exit_gracefully()
exit_code = 1


def close(exitcode):
  """
  Args:
    :param int exitcode: 0 success; 1 error

  Returns:
    None
  """

  # Wait a while to have all threads properly terminated
  time.sleep(1)

  logger.info(f"Exitcode = {exitcode} >>")
  sys.exit(exitcode)


def exit_gracefully(sig, stackframe):
  """
  Exit_gracefully by stopping all threads

  Keyword arguments:
    :param int sig: the associated signalnumber
    :param str stackframe: current stack frame
    :return: None
  """
  global exit_code

  logger.debug(f"Signal {sig} {stackframe}: >>")

  # indicate that this is a clean shutdown
  exit_code = 0
  t_threads_stopper.set()
  logger.info("<<")
  return


def main():
  logger.debug(">>")

  # To flag that MQTT thread has to stop
  t_mqtt_stopper = threading.Event()

  # MQTT thread
  t_mqtt = mqtt.mqttclient(cfg.MQTT_BROKER,
                           cfg.MQTT_PORT,
                           cfg.MQTT_CLIENT_UNIQ,
                           cfg.MQTT_RATE,
                           cfg.MQTT_QOS,
                           cfg.MQTT_USERNAME,
                           cfg.MQTT_PASSWORD,
                           t_mqtt_stopper,
                           t_threads_stopper)

  t_nibe = nibe.TaskReadNibe(cfg.MODBUS_ADDRESS, t_mqtt, t_threads_stopper)

  # Set MQTT last will/testament
  t_mqtt.will_set(cfg.MQTT_TOPIC_PREFIX + "/status", payload="offline", qos=cfg.MQTT_QOS, retain=True)

  # Start MQTT and nibe threads
  t_mqtt.start()
  t_nibe.start()

  # Set MQTT status to online and publish SW version of MQTT parser
  t_mqtt.set_status(cfg.MQTT_TOPIC_PREFIX + "/status", "online", retain=True)
  t_mqtt.do_publish(cfg.MQTT_TOPIC_PREFIX + "/sw-version", f"main={__version__};mqtt={mqtt.__version__}", retain=True)

  t_nibe.join()

  # Not really required...
  t_threads_stopper.set()

  # Set status to offline
  t_mqtt.set_status(cfg.MQTT_TOPIC_PREFIX + "/status", "offline", retain=True)

  # Use a simple delay of 1 sec before closing MQTT, to allow last MQTT messages to be send
  time.sleep(1)
  t_mqtt_stopper.set()

  logger.debug("<<")
  return


# ------------------------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------------------------
if __name__ == '__main__':
  logger.debug("__main__: >>")
  signal.signal(signal.SIGINT, exit_gracefully)
  signal.signal(signal.SIGTERM, exit_gracefully)

  # start main program
  main()

  logger.debug("__main__: <<")

  logger.error(f"EXIT_CODE = {exit_code}")

  close(exit_code)
