# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
from __future__ import absolute_import, print_function

import datetime
import logging
import sys
import time
import math
import json
from urlparse import urlparse

import gevent
import six
from volttron.platform.agent import json as jsonapi
import paho.mqtt.client as mqtt
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_GOOD, Status)
from volttron.platform.keystore import KeyStore
from datetime import timedelta

FORWARD_TIMEOUT_KEY = 'FORWARD_TIMEOUT_KEY'
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.5'


class MqttSubscribe(Agent):
    
    def __init__(self, config_path, **kwargs):
        # config = utils.load_config(config_path)

        backup_storage_limit_gb =  None

        # We pass every optional parameter to the MQTT library functions so they
        # default to the same values that paho uses as defaults.
        self.mqtt_qos = 0
        self.mqtt_retain =  False
        self.mqtt_hostname = 'localhost'
        self.mqtt_port =  1883
        self.mqtt_client_id =''
        self.mqtt_keepalive =  60
        self.mqtt_will =  None
        self.mqtt_auth = None
        self.mqtt_tls =  None
        protocol =  'MQTTv311'
        if protocol == "MQTTv311":
            protocol = 'MQTTv311'
        elif protocol == "MQTTv31":
            protocol = 'MQTTv31'

        if protocol not in ('MQTTv311', 'MQTTv31'):
            raise ValueError("Unknown MQTT protocol: {}".format(protocol))

        self.mqtt_protocol = protocol

        # will be available in both threads.
        self._last_error = 0
        #self.publish_to_volttron()

        super(MqttSubscribe, self).__init__(**kwargs)
        #print("here...........................")
        #self.publish_to_volttron()
#    @Core.periodic(1)
    @Core.receiver('onstart')
    def initialize(self, sender, **kwargs):
        self.publish_to_volttron()

        
    def timestamp(self):
        return time.mktime(datetime.datetime.now().timetuple())

    def on_connect(self,client, userdata, flags, rc):
        print("Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("devices/#")


    def on_message(self,client, userdata, msg):
	sensor_dict ={
	"DFF094DA4B58.01":"Sensor1-Temp",
	"DFF094DA4B58.02":"Sensor1-Humid",
	"DFF094DA4B58.03":"Sensor1-Press",
	"E7F68D59810E.01":"Sensor2-Temp",
	"E7F68D59810E.02":"Sensor2-Humid",
	"E7F68D59810E.03":"Sensor2-Press",
	"EE6103830E97.01":"Sensor3-Temp",
	"EE6103830E97.02":"Sensor3-Humid",
	"EE6103830E97.03":"Sensor3-Press",
	"E2DFFB329910.01":"Sensor4-Temp",
	"E2DFFB329910.02":"Sensor4-Humid",
	"E2DFFB329910.03":"Sensor4-Press"
	}
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        data = msg.payload
        data_loads = json.loads(data)
        sensorName = data_loads["m"]
        sensorData = data_loads["d"]
        for key in data_loads['d']['sensors']:
            print(key)
            value_json = [{key['type']: key['data']},{key['type']:{"units" : "F","tz":"UTC","type":"float"}}]
            self.vip.pubsub.publish('pubsub','analysis/controls/' + sensor_dict[key['id']] +  '/' + key['type'] + '/all', headers, value_json)
#       print(sensorName)
#        print("================>>>>")
#        self.vip.pubsub.publish('pubsub','analysis/' + sensorName + '/all',headers,data) 
#        console.log("================")
#       client.loop_stop()
	time.sleep(300)

        

    def publish_to_volttron(self):
       # print("here")
        msgTopic = ''
        msgValue = ''
        client = mqtt.Client()
        client.connect("127.0.0.1", 1883, 60)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.loop_forever()




def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(MqttSubscribe, version=__version__)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass














