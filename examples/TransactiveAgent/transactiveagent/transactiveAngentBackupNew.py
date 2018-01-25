import datetime
import logging
import sys
import json
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from . import settings
from volttron.platform.messaging import topics, headers as headers_mod

import requests
import json
import time
import csv
from calendar import timegm
from scipy.interpolate import interp1d

from cvxopt import matrix, solvers

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'
record_topic = 'record/'
entityId ='transactive_home.transactive_home'
new_state ='on'
device_list=[]
class TransactiveAgent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 

        super(TransactiveAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.agentId = self.config['agentId']
        self.hassConfig = self.config['hassConfigPath']
        self.url = self.config['url']
        self.urlPass = self.config['urlPass']
        self.entityId = self.config['entityID'] 
        self.friendly_name = self.config['friendly_name']
        self.flexibility = 10
        self.overall_energy =0
        self.overall_power =0
        self.energyDataPlot = ""
        self.powerDataPlot = ""
        self.zone_max =100
        self.participation=""
        self.zone_min =0 
        self.new_state = self.config['state']
        self.request = self.config['request']
        self.data  = []
        self.totalEnergy = 0
        self.totalPower =0
        self.powerDict = {'a':[]}
        self.energyDict = {'b':[]}
        self.deviceDict = {'AC1':[],'AC2':[],'WH1':[]}
        self.deviceDict['AC1'] = {'energy':0,"name":"","participate":"",'power':0,'zone_max':0,'zone_min':0}
        self.deviceDict['AC2'] = {'energy':0,"name":"","participate":"",'power':0,'zone_max':0,'zone_min':0}
        self.deviceDict['WH1'] = {'energy':0,"name":"","participate":"",'power':0,'zone_max':0,'zone_min':0}
    
    # @PubSub.subscribe('pubsub', 'house/')
    # def GetData(self,peer, sender, bus,  topic, headers, message):
    #     '''
    #         Get the current state for loaded components
    #         from Home Assistant API
    #     '''
    #     urlStates = self.url+'states/' + self.entityId
    #     self.data = requests.get(urlStates).json()
    #     data_json =  json.dumps(self.data)
    #     dataObject = json.loads(data_json)
    #     self.flexibility = dataObject['attributes']['overallflexibility'][0]['flexibility']
    #     # dataObject = json.loads(json.dumps(data_json))
    #     print("-------------------->>>>>>>>>>>>>>>>>>")
    #     print(self.flexibility)
    #     print(dataObject)
    #     pub_topic= 'house/AC1/AC1_beta'
    #     now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
    #     headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
    #     self.vip.pubsub.publish('pubsub',pub_topic,headers,0.6)     
    #     time.sleep(10)       

    @PubSub.subscribe('pubsub', 'house/')
    def on_match_all(self, peer, sender, bus,  topic, headers, message):
        ''' This method subscibes to all topics. It simply prints out the 
        topic seen.
        # '''
        urlServices = self.url+'states/'+ self.entityId
        self.data = requests.get(urlServices).json()
        data_json =  json.dumps(self.data)
        dataObject = json.loads(data_json)
        # print(dataObject)
        self.flexibility = dataObject['attributes']['overallflexibility'][0]['flexibility']
        print(self.flexibility)
        # print(dataObject)
        # pub_topic= 'house/AC1/AC1_beta'
        # now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        # headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        # self.vip.pubsub.publish('pubsub',pub_topic,headers,0.6)     
        time.sleep(4) 
        device_name = topic.partition('/')[-1].rpartition('/')[0]
        if (topic == 'house/'+ device_name +'/all'):
            # self.device_name = topic.partition('/')[-1].rpartition('/')[0]
            if (device_name in self.deviceDict):
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                self.load_value = round(message[0]['load(kW)'],2)
                self.energy_value = round(message[0]['Energy(kWH)'],2)
                self.device_json = {
                    "energy":self.energy_value,
                    "name":device_name,
                    "participate":self.participation,
                    "power":self.load_value,
                    "zone_max":self.zone_max,
                    "zone_min":self.zone_min} 
                self.deviceDict[device_name]=self.device_json
                self.powerPoints = [timestamp]
                for key , value in self.deviceDict.items():
                    if (self.deviceDict[key]['energy']) is not None:
                        # print(self.deviceDict[key]['energy'])
                        self.totalEnergy += self.deviceDict[key]['energy']
                    if (self.deviceDict[key]['power']) is not None:
                        # print(self.deviceDict[key]['power'])
                        self.totalPower += self.deviceDict[key]['power']
                        self.powerPoints.append(self.deviceDict[key]['power'])

                # print(self.powerPoints)
                energyPoints = [timestamp,round(self.totalEnergy,2)]
                self.energyDict['b'].append(energyPoints)
                if (len(self.energyDict['b']) == 10):
                    del self.energyDict['b'][0]
                    print("the first entry deleted")
                self.energyDataPlot = {
                                    "data":self.energyDict['b'],
                                    "type":"line",
                                    "label":"energy"
                } 
                # print( self.energyDataPlot)
                self.powerDict['a'].append(self.powerPoints)
                # print(self.powerDict)
                if (len(self.powerDict['a']) == 10):
                    del self.powerDict['a'][0]
                    print("the first entry deleted")

                self.powerDataPlot = {
                                    "data":self.powerDict['a'],
                                    "type":"bar",
                                    "label":"power"
                }
                # print( self.powerDataPlot)
                self.overall_energy =round(self.totalEnergy,2)
                self.overall_power= round(self.totalPower,2)
                # time.sleep(5)
                print("-------------------->>>>>>>>>>>>>>>>>>")
                self.ChangeTransactiveState(self.deviceDict,self.overall_energy,self.overall_power, self.energyDataPlot, self.powerDataPlot,self.flexibility)



    def ChangeTransactiveState(self,device_json,overall_energy,overall_power,energyDataPlot, powerDataPlot,flexibility):
        '''
            Turns on the switch.entityId device
        '''
        init_value = 0
        if entityId is None:
            return
        self.totalEnergy = 0
        self.totalPower =0
        
        urlServices = self.url+'states/'+ self.entityId
        try:
            jsonMsg = json.dumps({
                    "attributes": {
                        "chartSeries":[
                            energyDataPlot,
                            powerDataPlot
                        ],
                        "measures":[
                        {
                            "label":"Overall Energy",
                            "unit":"kw-hr/24 hrs",
                            "value":overall_energy
                        },
                        {
                            "label":"Overall Power",
                            "unit":"kw",
                            "value":overall_power                           
                        }],
                        "friendly_name":self.friendly_name,
                        "device":[
                        device_json['AC1'],
                        device_json['AC2'],
                        device_json['WH1'],
                        ],
                        "friendly_name": "Transactive Home",  
                        "overallflexibility":[
                        {
                            "flexibility" : flexibility,
                            "zone_max" : self.zone_max,
                            "zone_min" : self.zone_min
                        }]              
                    },
                    "state": self.new_state
                })
            header = {'Content-Type': 'application/json'}
            requests.post(urlServices, data = jsonMsg, headers = header)
            print("Transactive State has been changed")
            # print("-------------------------------------")
            # self.data = requests.get(urlServices).json()
            # data_json =  json.dumps(self.data)
            # dataObject = json.loads(data_json)
            # # print(dataObject)
            # self.flexibility = dataObject['attributes']['overallflexibility'][0]['flexibility']
        except ValueError:
                pass

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(TransactiveAgent,version=__version__)
    except Exception as e:
        print e
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass                 



   
            