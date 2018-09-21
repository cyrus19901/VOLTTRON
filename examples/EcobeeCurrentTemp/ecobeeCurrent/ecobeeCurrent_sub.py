import datetime
import logging
import sys
import json
import requests
import json
import time
import csv
import gevent
#import urllib3
import grequests
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from . import settings
from volttron.platform.messaging import topics, headers as headers_mod
from datetime import datetime
from calendar import timegm

#urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'
class GetEcobeeCurrent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 

        super(GetEcobeeCurrent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.url = self.config['url']
        self.password = self.config['password']
        self.data  = []
        self.data2  = []

#Moving some from the transactive agent 
    @Core.periodic(60)
    def subscribeValues(self):

        url = self.url + 'sensor.my_ecobee_temperature'
        # header = {'Content-Type': 'application/json' , 'Authorization' : 'Basic %s' % base64.b64encode("username":self.password)}
        myresponse  = requests.get(url,auth=('homeassistant',self.password),verify=False)
        ecobeeData = json.loads(myresponse.text)
        value = float(ecobeeData['state'])
       	now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
       	   headers_mod.DATE: now
        }
        message = [{'currentTemp':value},{'currentTemp':{'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        self.vip.pubsub.publish(
            'pubsub', 'analysis/controls/ecobeeCurrent/currentTemp', headers, message)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(GetEcobeeCurrent,version=__version__)
    except Exception as e:
        print e
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass                 



   
            
