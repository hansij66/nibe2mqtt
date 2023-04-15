"""
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

Description
-----------
"""

import threading
import time
import json
from pyModbusTCP.client import ModbusClient
from influxdb import InfluxDBClient


# Local imports
import config as cfg

# Logging
import __main__
import logging
import os

script = os.path.basename(__main__.__file__)
script = os.path.splitext(script)[0]
logger = logging.getLogger(script + "." + __name__)

# TODO
# 01805-defrosting-eb101 convert in defrost counter


class TaskReadNibe(threading.Thread):
  def __init__(self, tcp_address, t_mqtt, t_threads_stopper):
    logger.debug(f">>")
    super().__init__()
    self.__tcp_address = tcp_address

    # MQTT client
    self.__t_mqtt = t_mqtt

    # Signal when to stop
    self.__t_threads_stopper = t_threads_stopper

    # Maintain a dictionary of values to be publised to MQTT
    self.__json_values = dict()

    # modbus registers in json format
    self.__json_modbus = None

    # Keep count of nr of reads since start of parser
    self.__counter = 0

    # Bookkeeping for throttling read rate
    self.__lastreadtime = 0
    self.__interval = 3600/cfg.READ_RATE

    self.__nibe = None

    # previous defrost status
    # Use this to maintain a counter of number of defrosts
    self.__prev_defrost_status = 0
    self.__defrost_counter = 0
    self.__defrost_initialized = False

    self.__init_defrost_counter()

    logger.debug(f"<<")
    return

  def __del__(self):
    logger.debug(f">>")

  def __init_defrost_counter(self):
    """
    defrost_counter maintains a count of number of defrosts
    AFAIK, Nibe does not have a register for this
    Maintain this countee

    In case it is stored in influxdb, at start retrieve last value from influxdb
    Otherwise init with zero

    Supports only influxDB v1
    Todo add influxDB v2

    :return: None
    """

    try:
      client = InfluxDBClient(host=cfg.INFLUXDB1_HOST, port=cfg.INFLUXDB1_PORT, database=cfg.INFLUXDB1_DB, timeout=1)

      # Build influxdb Query
      key = "defrost_counter"

      # select last value of 01805-defrosting-eb101 from influxdb
      query = f'select last("{key}") from {cfg.INFLUXDB1_SERIES}'
      result = client.query(query)

      points = result.get_points()

      if len(result.items()) == 0:
        # InfluxDB is available
        # But "01805-defrosting-eb101" does not exist yet
        # This is a one-off event to initialize influxdb with 01805-defrosting-eb101
        logger.info(f"InfluxDB entry {key} for counting defrost cycles will be created")

        # in principel we start cointing at zero, unless parser is a already up & running for a while
        # and influxdb comes up later
        self.__defrost_counter = self.__defrost_counter
        self.__defrost_initialized = True
      else:
        # retrieve last value from points
        for item in points:
          # If influxDB came online late, then add initial count
          self.__defrost_counter = self.__defrost_counter + item['last']
          self.__defrost_initialized = True
          logger.debug(f"Last {key} from influxdb = {item}; defrost counter set to {self.__defrost_counter}")

    except Exception as e:
      # When influxdb is not (yet) online, just continue
      logger.warning(f"{e}")

    return None

  def __format_json_modbus(self):
    """
    Call once to format __json_modbus a bit
    Ideally, this should be handled in convert_csv.py....no time to fix that

    # As the json is defined by someone else
    # and I am not yet able to generate it in format
    # the way I want it, I do some rework here

    :return: None
    """
    logger.debug(f">>")

    for register_index in self.__json_modbus:
      # MODBUS_COIL: abcd
      # MODBUS_DISCRETE_INPUT: 1abdc
      # MODBUS_INPUT_REGISTER: 3abcd
      # MODBUS_HOLDING_REGISTER: 4abcd
      if int(register_index) < 10000:
        register = int(register_index)
      else:
        register = int(register_index[1:])

      register_description = self.__json_modbus[register_index]

      # Strip register from name
      # "average-temperature-bt1-30001" --> "average-temperature-bt1"
      register_description['name'] = register_description['name'].rstrip("0123456789")
      register_description['name'] = register_description['name'].rstrip("-")
      # Add clean register to name, pad with leading zeros
      # "average-temperature-bt1" --> "00001-average-temperature-bt1"
      register_description['name'] = str(register).zfill(5) + "-" + register_description['name']
    return

  def __publish_telegram(self):
    """
    Publish self.__json_values to MQTT

    :return: None
    """
    logger.debug(f">>")

    # make resilient against double forward slashes in topic
    topic = cfg.MQTT_TOPIC_PREFIX + "/" + "S2125"
    topic = topic.replace('//', '/')

    message = json.dumps(self.__json_values, sort_keys=True, separators=(',', ':'))
    self.__t_mqtt.do_publish(topic, message, retain=False)
    self.__t_mqtt.do_publish(topic + "/counter", str(self.__counter), retain=False)

    logger.debug(f"<<")
    return

  def __read_modbus(self, register_list):
    """

    Read the specified registers via modbus

    :param register_list: list of registers
    :return: None
    """
    logger.debug(f">> {register_list}")

    # Clear the dict where we store all modbus values
    self.__json_values.clear()

    # Loop forever till threads are requested to stop
    while not self.__t_threads_stopper.is_set():
      # Get timestamp and add to dict; 1sec resolution
      ts = int(time.time())
      self.__json_values["timestamp"] = ts

      # Read all registers
      # As MODBUS register type is "encoded" in the register, separate these from each other
      # https://control.com/forums/threads/modbus-register-numbering.49844/
      # Not sure if this was the right way to do this
      # Learning as we go....
      # I assumed that the register space for INPUT and HOLDING is the same
      # But I learned later that these (and COIL, DISCRETE too?) are independent register spaces
      for register_index in register_list:
        # MODBUS_COIL: abcd
        # MODBUS_DISCRETE_INPUT: 1abdc
        # MODBUS_INPUT_REGISTER: 3abcd
        # MODBUS_HOLDING_REGISTER: 4abcd
        if int(register_index) < 10000:
          register_type = "0"
          register = int(register_index)
        else:
          register_type = register_index[:1]
          register = int(register_index[1:])

        try:
          register_description = self.__json_modbus[register_index]
          logger.debug(f"REGISTER = {register}; REGISTERTYPE = {register_type}; JSON = {register_description}")
        except Exception as e:
          logger.warning(f"{e}: Register {register_index} is not specified in JSON file {cfg.JSON}")
          continue

        if register_type == "0":
          # MODBUS_COIL
          # todo specify nrof bits; not used and not tested
          modbus_value = self.__nibe.read_coils(int(register), 1)
        elif register_type == "1":
          # MODBUS_DISCRETE_INPUT
          # todo specify nrof bits; not used and not tested
          modbus_value = self.__nibe.read_discrete_inputs(int(register), 1)
        elif register_type == "3":
          # MODBUS_INPUT_REGISTER
          modbus_value = self.__nibe.read_input_registers(int(register), 1)
        elif register_type == "4":
          # MODBUS_HOLDING_REGISTER
          modbus_value = self.__nibe.read_holding_registers(int(register), 1)
        else:
          logger.error(f"Register_type {register_type} for {register_description} is not supported")
          return

        if modbus_value is None:
          logger.warning(f"Register_type {register_type} for {register_description} returns None")
          return None

        self.__json_values[register_description['name']] = modbus_value[0] / register_description['factor']

      # Done reading all registers

      # Update defrost counter
      # This counter is not available in the Nibe
      try:
        # Detect transition from 0 --> 1
        if self.__prev_defrost_status == 0 and self.__json_values["01805-defrosting-eb101"] == 1:
          self.__defrost_counter += 1

        self.__prev_defrost_status = self.__json_values["01805-defrosting-eb101"]

        # Only publish when InfluxDB is online/defrost counter is initialized
        # To ensure that we do not get wrong defrost_counter data in influxdb
        if self.__defrost_initialized:
          self.__json_values["defrost_counter"] = self.__defrost_counter
        else:
          # Check if influxdb is already online
          self.__init_defrost_counter()

      except KeyError as key:
        logger.warning(f"Key {key} is not in self.__json_values")
      except Exception as e:
        logger.error(f"{e}")

      # We did read values; increment counter
      self.__counter += 1
      self.__publish_telegram()

      # Throttle read pace
      while not self.__t_threads_stopper.is_set():
        t_elapsed = int(time.time()) - self.__lastreadtime
        if t_elapsed > self.__interval:
            self.__lastreadtime = int(time.time())
            break
        else:
          # wait...
          time.sleep(1)

    logger.debug(f"<<")
    return

  def run(self):
    logger.debug(f">>")

    # Where are the files located?
    basepath = os.path.dirname(os.path.realpath(__file__))
    json_filename = basepath + "/" + cfg.JSON

    with open(json_filename, 'r') as f:
      self.__json_modbus = json.load(f)

    # reformat the json file
    # todo, fix json file...so we can remove this
    self.__format_json_modbus()

    try:
      self.__nibe = ModbusClient(host=cfg.MODBUS_ADDRESS, port=502, unit_id=1, timeout=1, auto_open=True, debug=False)
    except Exception as e:
      logger.warning(f"{e}")
      self.__t_threads_stopper.set()

    while not self.__t_threads_stopper.is_set():
      try:
        self.__read_modbus(cfg.NIBE_REGISTER)
      except Exception as e:
        logger.error(f"{e}")

        # Something unexpected happens, stop all threads
        self.__t_threads_stopper.set()

    logger.debug(f"<<")
    return
