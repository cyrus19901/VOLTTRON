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
from urlparse import urlparse

import gevent
from volttron.platform.agent import json as jsonapi
import paho.mqtt.client as mqtt
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.vip.agent import Agent, Core, compat
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
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 
        super(MqttSubscribe, self).__init__(**kwargs)


	def on_connect(self,client, userdata, flags, rc):
	    print("Connected with result code "+str(rc))

	    # Subscribing in on_connect() means that if we lose the connection and
	    # reconnect then subscriptions will be renewed.
	    client.subscribe("Yarnell/#")

	def on_message(self,client, userdata, msg):
	    #a = MqttSubscribe(MqttSubscribe)
            #print(a)	
	    print(msg.topic+" "+str(msg.payload))
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
	    #self.vip.pubsub.publish('pubsub',msg.topic,headers,msg.payload) 


	client = mqtt.Client()
	client.on_connect = self.on_connect
	client.on_message = self.on_message

	client.connect("10.1.10.31", 1883, 60)

	# Blocking call that processes network traffic, dispatches callbacks and
	# handles reconnecting.
	# Other loop*() functions are available that give a threaded interface and a
	# manual interface.
	client.loop_forever()


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(MqttSubscribe, version=__version__)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

