# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import datetime
import logging
import sys
import json
import requests
import json
import time
import csv
import gevent
import grequests
from volttron.platform import jsonrpc
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM, CONTROL, CONFIGURATION_STORE)
from . import settings
from volttron.platform.messaging import topics, headers as headers_mod
from datetime import timedelta
from calendar import timegm
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS)
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM, CONTROL, CONFIGURATION_STORE)

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'
record_topic = 'record/'
new_state ='on'
class TransactiveAgent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 
        super(TransactiveAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.url = self.config['url']
        self.password = self.config['password']
        self.new_state = self.config['state']
        self.path = '/home/pi/volttron'
        self.deviceDictionary={}
        self.energyPoint={}
        self.powerPoint={}
        self.devicePowerStausesDict ={}
        self.deviceEnergyStausesDict ={}
        self.startTime= datetime.datetime.utcnow()
        self.future = self.startTime + timedelta(seconds=30,minutes=0)
        self.energyDevicesStatusesDict={'series':{},'times':[],'time-format': 'h:mm a','step': 30}
        self.powerDevicesStatusesDict={'series':{},'times':[],'time-format': 'h:mm a','step':30}
        self.entityId_transactive_component = 'transactive_home.transactive_home'
        self.entityId_connectedDevices_component = 'connected_devices.connected_devices'
        self.entityId_utilitySetting_component = 'advanced_settings.utility_settings'
        self.entityId_deviceStatus_component = 'device_statuses.device_statuses'
        self.entityId_user_settings_component = 'user_settings.device_settings'
        self.entityId_wholeHouseEnergy_component = 'whole_house_energy.whole_house_energy'
        self.entityId_extras_component = 'extras.extras'
        self.entityId_datPrivacy_component ='data_privacy.data_privacy'
        self.count=0
        self.energyDict = {'series':[],'times':[]}
        self.privacy_settings_default = 'no_external'
        cumulative_historical = 0
        cumulative_transactive = 0
        energySeries = {'actual':[],'historical':[],'transactive':[]}
        energySeries['actual'] = { 'color':'#FF7F50','label':'actual','line-style':'','points':[]}
        energySeries['historical'] = { 'color':'#696969','label':'historical','line-style':'dot','points':[]}
        energySeries['transactive'] = { 'color':'ForestGreen','label':'transactive','line-style':'dash','points':[]}
        self.energyDict['series']= energySeries
        self.initializeInitialState()
        self.base_url ="http://52.87.227.27:8080/vc/jsonrpc"
        self.totalEnergy  = 0
        self.totalPower = 0
        

    def executeForwardHistorian(self,uuidForwardHistorian,token,uuidPlatform, method):

        headers = {
            'Content-Type': 'application/json',
        }

        payload = {
             "jsonrpc": "2.0",
             "method": "platforms.uuid."+uuidPlatform+"."+ method,
             "params":[uuidForwardHistorian],
             "authorization": token,
             "id": '72581-4'
        }
        response = requests.post(self.base_url, headers=headers,
                                 data=json.dumps(payload),verify=False).json()
        if response:
            return response
        else:
            return "Agent not found"

    def getuuidPlatform(self,token):

        headers = {
            'Content-Type': 'application/json',
        }

        payload = {
             "jsonrpc": "2.0",
             "method": "list_platforms",
             "authorization": token,
             "id": '72581-4'
        }
        response = requests.post(self.base_url, headers=headers,
                                 data=json.dumps(payload),verify=False).json()
        if response:
            return response
        else:
            return "No Platforms found"

    def getAgentList(self,uuid_platform,method,agent_name,token):

        headers = {
            'Content-Type': 'application/json',
        }

        payload = {
             "jsonrpc": "2.0",
             "method": "platforms.uuid."+ uuid_platform + "." + method,
             "authorization": token,
             "id": '72581-4'
        }
        response = requests.post(self.base_url, headers=headers,
                                 data=json.dumps(payload),verify=False).json()
        if response:
            # return response
            for agent in response['result']:
                if (agent['identity'] == agent_name):
                    return(agent['uuid'])
        else:
            return agent_name + 'not found'


    def authenticationVC(self,username, password):
        """ Makes use of Send API:
            https://developers.facebook.com/docs/messenger-platform/send-api-reference
        """
        headers = {
            'Content-Type': 'application/json',
        }
        payload = {
             "jsonrpc": "2.0",
             "method": "get_authorization",
             "params": {
                "username": username,
                "password": password
             },
             "id": '72581-4'
        }
        response = requests.post(self.base_url, headers=headers,
                                 data=json.dumps(payload),verify=False).json()
        if response:
            return response
        else:
            return "The authentication was a failure "

    def initializeInitialState(self):
        now = datetime.datetime.now()
        future=now
        response = self.apiResponse()
        dataObject_all = json.loads(response[7].text)
        try:
            if (dataObject_all == []):
                msg = "No data was received from HASS API, Please check the connection to the API and the Agent configuration file"
                _log.error(msg)
            else:
                msg = []
                self.deviceList = ["A.O.Smith.WH","PoolPump","HVACOutdoor","HVACIndoor"]
                # for entry in dataObject_all:
                #     entityId = entry['entity_id']
                #     if(entityId.startswith("climate.")):
                #         self.deviceList.append(entityId.split(".")[1])
        except requests.exceptions.RequestException as e:
            print(e)   

        for d in self.deviceList:
            self.deviceDictionary[d] = []
            self.devicePowerStausesDict[d] = []
            self.deviceEnergyStausesDict[d] = []
            self.energyPoint[d]=[]
            self.powerPoint[d]=[]
            # Initiate the json in the beginning of the code
            for device_list in self.deviceList:
                device_json = {
                        "name": device_list, 
                        "flexibility": 0,
                        "participate": True,
                        "reset":False
                        }
                self.deviceDictionary[device_list]= device_json
            self.reset_default = False
            jsonMsg = json.dumps({
                            "attributes": {
                                "devices": self.deviceDictionary,
                                "friendly_name":"Connected Devices",
                            },
                            "state": self.new_state
                        })
            header = {'Content-Type': 'application/json' ,'x-ha-access':self.password}
            requests.post(self.url+'states/'+ self.entityId_connectedDevices_component, data = jsonMsg, headers = header)  

        with open(self.path+'/examples/TransactiveAgent/config_devices') as device_file: 
            device_dictionary = json.load(device_file)

        for i in range(1,50):
            minute = timedelta(days=6,seconds=0,microseconds=0)
            future = future + minute
            self.energyDict['times'].append(future.isoformat())

        for i in range(1,50):
            self.energyDict['series']['actual']['points'].append(None)

        with open(self.path +'/examples/TransactiveAgent/transactiveagent/greendata-transactive.json') as data_file: 
            data_historical = json.load(data_file)
            for i in data_historical:
                try:
                    cumulative_historical =  float(i['Value - Real energy (Watt-hours)'])/1000
                    self.energyDict['series']['historical']['points'].append(cumulative_historical)
                except IndexError:
                     pass
                continue

        with open(self.path + '/examples/TransactiveAgent/transactiveagent/greenButtonHistoricalData.json') as data_file:   
            data_transactive = json.load(data_file)
            for i in data_transactive:
                try:
                    cumulative_transactive =  float(i['Value - Real energy (Watt-hours)'])/1000
                    self.energyDict['series']['transactive']['points'].append(cumulative_transactive)
                except IndexError:
                    pass
                continue

        self.changeUsereSettings(device_dictionary)
        # self.dataForward()

    def dataForward(self,dataObject_dataPrivacy):
        #dataPrivacy -> forward historian 
        privacy_settings = dataObject_dataPrivacy['attributes']['privacy_setting'] 
        # print("=====================================")
        # print(privacy_settings)
        # print(self.privacy_settings_default)
        if (privacy_settings != self.privacy_settings_default):
            authentication_response = self.authenticationVC("admin","admin")
            token = authentication_response['result']
            uuid_response = self.getuuidPlatform(token)
            uuidPlatform = uuid_response['result'][0]['uuid']
            uuidForwardHistorian = self.getAgentList(uuidPlatform,'list_agents','ForwardHistorian',token)
            
            if (privacy_settings == 'allow_control'):
                self.executeForwardHistorian(uuidForwardHistorian,token,uuidPlatform,"start_agent")
                self.privacy_settings_default = 'allow_control'
            if (privacy_settings == 'no_external'):
                self.executeForwardHistorian(uuidForwardHistorian,token,uuidPlatform,"stop_agent")
                self.privacy_settings_default = 'no_external'



    def apiResponse(self):

        urls = [
            self.url+'states/'+ self.entityId_transactive_component,
            self.url+'states/'+ self.entityId_connectedDevices_component,
            self.url+'states/'+ self.entityId_utilitySetting_component,
            self.url+'states/'+ self.entityId_wholeHouseEnergy_component,
            self.url+'states/'+ self.entityId_user_settings_component,
            self.url+'states/'+ self.entityId_extras_component,
            self.url+'states/'+ self.entityId_datPrivacy_component,
            self.url+'states'
        ]

        request_data = (grequests.get(u,headers= {'Content-Type': 'application/json' ,'x-ha-access':self.password}) for u in urls)
        response = grequests.map(request_data)
        return response

    @PubSub.subscribe('pubsub', 'devices/Yarnell')
    def on_match_all(self, peer, sender, bus,  topic, headers, message):
        ''' This method subscibes to all topics. It simply prints out the 
        topic seen.
        # '''
	print("--------------------inside subscribe---------------------")
        # request_data = (grequests.get(u,headers= {'Content-Type': 'application/json' ,'x-ha-access':self.password}) for u in self.urls)
        response = self.apiResponse()
        dataObject_transactive = json.loads(response[0].text) 
        self.dataObject_connected = json.loads(response[1].text)
        self.dataObject_utility_settings = json.loads(response[2].text)
        self.dataObject_wholeHouse = json.loads(response[3].text)
        self.dataObject_user_sett = json.loads(response[4].text)
        self.dataObject_extras = json.loads(response[5].text)
        self.dataObject_dataPrivacy = json.loads(response[6].text)
        self.dataForward(self.dataObject_dataPrivacy)
        

        load_value =0
        energy_value =0
        device_name =topic.split("/")[3]
	print(device_name)

        # device_name = topic.partition('/')[-1].rpartition('/')[0].rpartition('/')[0].rpartition('/')[2]
        if (topic == "devices/Yarnell/Energy/WholeHouse/all"):
	    print("================inside second ====================")
            self.totalEnergy =  float(message[0]['value'])
            self.totalPower = float(self.totalEnergy)/60
            # print(self.totalEnergy)
            # print(self.totalPower)
            # print("========================")

        if (device_name in self.deviceList):

            if (topic.startswith("devices/Yarnell")):
                print(topic)
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                for device in  self.deviceList:
                    if (device_name == device):
                        load_value =0
                        energy_value =0
                        if (topic == "devices/Yarnell/Energy/"+device_name + '/all'):
			    print("=============HERE")
			    print(message)
                            energy_value = float(message[0]['value'])
                        else :
                            energy_value = 0 
                        if (topic == "devices/Yarnell/Power/" +device_name + "/all"):
                            load_value = float(message[0]['value'])
                        else :
                            load_value = 0 
                        # self.populateDict(device_name,energy_value,load_value)
                        self.energyPoint[str(device)].append(energy_value)
                        self.powerPoint[str(device)].append(load_value)
                    else :
                        load_value =0 
                        energy_value = 0
                        # load_value = float(self.dataObject_connected['attributes']['devices'][str(device)]['power'])
                        # energy_value = float(self.dataObject_connected['attributes']['devices'][str(device)]['energy'])



                    flexibility = self.dataObject_connected['attributes']['devices'][str(device)]['flexibility']
                    participation = self.dataObject_connected['attributes']['devices'][str(device)]['participate']
                    reset = self.dataObject_connected['attributes']['devices'][str(device)]['reset']
                    device_json = {
                        "name":str(device),
                        "flexibility":flexibility,
                        "participate": participation,
                        "reset":reset
                        }
                    devicesEnergyStatus_json = {
                        "name": device_name,
                        "points": self.energyPoint[str(device_name)]
                    }
                    devicesPowerStatus_json = {
                        "name" : device_name,
                        "points": self.powerPoint[str(device_name)]
                    }


                    self.devicePowerStausesDict[device_name] = devicesPowerStatus_json
                    self.deviceEnergyStausesDict[device_name] = devicesEnergyStatus_json
                    if (len(self.deviceEnergyStausesDict[device_name]) == 11):     
                        del (self.deviceEnergyStausesDict[device_name][0])      
                    if (len(self.devicePowerStausesDict[device_name]) == 11):       
                        del (self.devicePowerStausesDict[device_name][0])       
                    self.energyDevicesStatusesDict['series']= self.deviceEnergyStausesDict      
                    self.powerDevicesStatusesDict['series']= self.devicePowerStausesDict
                    self.deviceDictionary[device]= device_json
                    # totalEnergy += energy_value
                    # totalPower += load_value
		print(self.deviceDictionary)
                self.energyDict['series']['actual']['line-style'] = ""
                if (self.energyDict['series']['actual']['points'][self.count] == None):
                    self.energyDict['series']['actual']['points'][self.count] =round(self.totalEnergy,2)
                    self.energyDict['series']['transactive']['points'][self.count] =round(self.totalEnergy,2)
                    print("the first entry deleted")
                energyDataPlot = {
                    "series":self.energyDict['series'],
                    "time-format": "MM/DD",
                    "times":self.energyDict['times']
                }
#		print(self.energyDict)
                if (self.count == 50):
                    self.count=0
                self.count = self.count + 1
                gevent.sleep(1)
                self.changeConnectedDevicesState(self.deviceDictionary)
                self.changePrivacyState(self.dataObject_dataPrivacy)
                self.changeUtilitySettings(self.dataObject_utility_settings)
                self.changeExtrasState(self.dataObject_extras) 

#                self.ChangeTransactiveState(round(self.totalEnergy,2),round(self.totalPower,2),energyDataPlot,flexibility)
                
                self.startTime =datetime.datetime.utcnow()
                if (datetime.datetime.utcnow() >= self.future):
                    self.setTime(self.energyDevicesStatusesDict,self.powerDevicesStatusesDict,timestamp)

    def setTime(self,energyDevicesStatusesDict,powerDevicesStatusesDict,timestamp):
        energyDevicesStatusesDict['times'].append(timestamp)
        powerDevicesStatusesDict['times'].append(timestamp)
        if (len(energyDevicesStatusesDict['times']) == 11):
            del (energyDevicesStatusesDict['times'][0])
        if (len(powerDevicesStatusesDict['times']) == 11):
            del (powerDevicesStatusesDict['times'][0])
        self.future = datetime.datetime.utcnow() + timedelta(seconds=30,minutes=0)
        self.ChangeDeviceStatuses(energyDevicesStatusesDict,powerDevicesStatusesDict)

    def changePrivacyState(self,privacyValues):

        if self.entityId_datPrivacy_component is None:
            return
        
        urlServices = self.url+'states/'+ self.entityId_datPrivacy_component
        try:
            jsonMsg = json.dumps(privacyValues)
            header = {'Content-Type': 'application/json' ,'x-ha-access':self.password}
            requests.post(urlServices, data = jsonMsg, headers = header)
            # print("Privacy State has been changed")
        except ValueError:
                pass

    def changeExtrasState(self,objectExtras):

        if self.entityId_extras_component is None:
            return
        
        urlServices = self.url+'states/'+ self.entityId_extras_component
        try:
            jsonMsg = json.dumps(objectExtras)
            header = {'Content-Type': 'application/json' ,'x-ha-access':self.password}
            requests.post(urlServices, data = jsonMsg, headers = header)
            # print("Extras State has been changed")
        except ValueError:
                pass
    def ChangeTransactiveState(self,overall_energy,overall_power,energyDataPlot,flexibility):

        if self.entityId_transactive_component is None:
            return
        
        urlServices = self.url+'states/'+ self.entityId_transactive_component
        try:
            jsonMsg = json.dumps({
                    "attributes": {
                        "chartSeries":[{
                            "data": energyDataPlot,
                            "type": "line",
                            "label": "Energy (kWh)",
                            "id": "transactive-home",
                            "xAxisLabel": "Date",
                            "yAxisLabel": "kWh"
                        }
                        ],
                        "friendly_name": "Transactive Home",
                        "measures":[
                        {
                            "label":"Overall Energy",
                            "unit":"kWh",
                            "value":overall_energy
                        },
                        {
                            "label":"Overall Power",
                            "unit":"kW",
                            "value":overall_power                           
                        }],
                        "friendly_name": "Transactive Home",  
                        "overallflexibility":[
                        {
                            "flexibility" : flexibility,
                            "zone_max" : 100,
                            "zone_min" : 0
                        }],
                        "progress_bar":{
                            "comparisonLabel": "savings compared to last year",
                            "end_point":250,
                            "lastYearLabel": "Last year's total energy cost",
                            "last_year": 1680,
                            "message": "You are off to a good start",
                            "starting_point": 0,
                            "value": 55
                        },     

                    },
                    "state": self.new_state
                })
            header = {'Content-Type': 'application/json' ,'x-ha-access':self.password}
            requests.post(urlServices, data = jsonMsg, headers = header)
            # print("Transactive State has been changed")
        except ValueError:
                pass

    def changeConnectedDevicesState(self,device_json):

            if self.entityId_connectedDevices_component is None:
                return
            urlServices = self.url+'states/'+ self.entityId_connectedDevices_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                            "devices": device_json,
                            "friendly_name":"Connected Devices",
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json' ,'x-ha-access':self.password}
                requests.post(urlServices, data = jsonMsg, headers = header)
                # print("Connected Devices State has been changed")
            except ValueError:
                    pass

    def ChangeDeviceStatuses(self,energyDevicesStatusesDict,powerDevicesStatusesDict):
            
            if self.entityId_deviceStatus_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_deviceStatus_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                            "chartSeries":[{
                                "data":energyDevicesStatusesDict,
                                "id":"device-energy",
                                "label":"Energy (kWh)",
                                "type":"bar",
                                "updateMethod":"update_chart_type",
                                "xAxisLabel": "Time",
                                "yAxisLabel": "kWh"
                                },
                                {
                                "data":powerDevicesStatusesDict,
                                "id":"device-power",
                                "label":"Power (kW)",
                                "type":"bar",
                                "updateMethod":"update_chart_type",
                                "xAxisLabel": "Time",
                                "yAxisLabel": "kW"
                            }],
                            "friendly_name":"Device Statuses",
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json','x-ha-access':self.password}
                requests.post(urlServices, data = jsonMsg, headers = header)
                # print(" Devices Statuses State has been changed")
            except ValueError:
                    pass

    def changeUtilitySettings(self,utilitySettings):

            if self.entityId_utilitySetting_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_utilitySetting_component
            try:
                jsonMsg = json.dumps(utilitySettings)
                header = {'Content-Type': 'application/json','x-ha-access':self.password}
                requests.post(urlServices, data = jsonMsg, headers = header)
                # print("Advanced Setting State has been changed")
            except ValueError:
                    pass

    def changeUsereSettings(self,device_dictionary):

            if self.entityId_user_settings_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_user_settings_component
            try:

                jsonMsg = json.dumps({
                        "attributes":device_dictionary,
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json','x-ha-access':self.password}
                requests.post(urlServices, data = jsonMsg, headers = header)
                # print("Advanced Setting State has been changed")
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





   

