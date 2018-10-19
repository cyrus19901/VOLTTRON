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

from __future__ import absolute_import

from datetime import datetime
import logging
import random
import sys
import math
import json
import requests
from pprint import pprint
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod




utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'

'''
Structuring the agent this way allows us to grab config file settings 
for use in subscriptions instead of hardcoding them.
'''

def ecobeeSetpoint_agent(config_path, **kwargs):
    config = utils.load_config(config_path)
    HEMS_signal= config.get('HEMS_signal',
                          'analysis/controls/ecobeeSet/TSetACdn')
    
    
    class EcobeeSetpoint(Agent):

        def __init__(self, **kwargs):
            super(EcobeeSetpoint, self).__init__(**kwargs)
    
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            # Demonstrate accessing a value from the config file
            self._agent_id = config['agentid']

	
        @PubSub.subscribe('pubsub',HEMS_signal)
        def match_device_all(self, peer, sender, bus,  topic, headers, message):

            file = open('/home/pi/volttron/ecobee.conf','r')
            file_data = file.read()
            #print(json.dumps(file_data))
	    val = json.loads(file_data)
	    file.close()
            access_token = val['ACCESS_TOKEN']
            #print(access_token)
            #pprint(data)
            #print("Whole message", message)
            URL= 'https://api.ecobee.com/1/thermostat?format=json'
            headers = {"content-type": "application/json","Authorization": "Bearer "+ access_token}
            print(headers)
	    #print(message[0]['setpoint'])	
	    setpoint= message[0]['setpoint'] * 10
	    data =json.dumps({
              "selection": {
                "selectionType":"registered",
                "selectionMatch":""
              },
              "functions": [
                { "type" : "setHold",
                  "params":{
                    "holdType":"nextTransition",
                    "heatHoldTemp":500,
                    "coolHoldTemp":int(round(setpoint))
                  }
                }
              ]
            })
	    print(data)
#            print(message[0]['Ecobeesetpoint'])
            r = requests.post(url = URL, data = data, headers=headers)   
            print(r.text)                         

            

        #@Core.periodic(60)
#        def pub_fake_data(self):

            #Create messages for specific points
            #HEMS_point = [65,{'units': 'F', 'tz': 'UTC', 'type': 'float'}]
#            HEMS_point = [{'Ecobeesetpoint': 65},
#                       {'EcobeeSetpoint': {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]            
            #Create timestamp
#            now = datetime.utcnow().isoformat(' ') + 'Z'
#            headers = {
#                headers_mod.DATE: now
#            }
            
            #Publish messages
#            self.vip.pubsub.publish(
#                'pubsub', HEMS_signal, headers, HEMS_point)
            
            


    return EcobeeSetpoint(**kwargs)
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(ecobeeSetpoint_agent, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())

