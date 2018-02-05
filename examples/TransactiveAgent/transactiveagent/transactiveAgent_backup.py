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
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from . import settings
from volttron.platform.messaging import topics, headers as headers_mod
from datetime import timedelta
from calendar import timegm

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
        self.deviceList = self.config['device_list']
        self.deviceDictionary={}
        self.energyPoint={}
        self.powerPoint={}
        self.devicePowerStausesDict ={}
        self.deviceEnergyStausesDict ={}
        for d in self.deviceList:
            self.deviceDictionary[d] = []
            self.devicePowerStausesDict[d] = []
            self.deviceEnergyStausesDict[d] = []
            self.energyPoint[d]=[]
            self.powerPoint[d]=[]
        self.startTime= datetime.datetime.utcnow()

        self.future = self.startTime + timedelta(seconds=30,minutes=0)
        self.energyDevicesStatusesDict={'series':[],'times':[],'time-format': 'h:mm a'}
        self.powerDevicesStatusesDict={'series':[],'times':[],'time-format': 'h:mm a'}
        self.entityId_transactive_component = 'transactive_home.transactive_home'
        self.entityId_connectedDevices_component = 'connected_devices.connected_devices'
        self.entityId_energyEfficiencyPeakPeriod_component = 'energy_efficiency.peak_period_energy_and_compensation'
        self.entityId_advancedSetting_component = 'advanced_settings.advanced_settings'
        self.entityId_deviceStatus_component = 'device_statuses.device_statuses'
        self.entityId_user_settings_component = 'user_settings.user_settings'
        self.entityId_timeOfEnergyUseSaving = 'time_of_use.time_of_use_energy_and_savings'
        self.new_state = self.config['state']
        self.count=0
        self.energyDict = {'series':[],'times':[]}
        cumulative_historical = 0
        cumulative_transactive = 0
        energySeries = {'actual':[],'historical':[],'transactive':[]}
        energySeries['actual'] = { 'color':'#FF7F50','label':'actual','line-style':'','points':[]}
        energySeries['historical'] = { 'color':'#696969','label':'historical','line-style':'dash','points':[]}
        energySeries['transactive'] = { 'color':'ForestGreen','label':'transactive','line-style':'dash','points':[]}
        self.energyDict['series']= energySeries
        now = datetime.datetime.now()
        future=now
        urlServices = self.url+'states/'+ self.entityId_connectedDevices_component
        for i in range(1,50):
            minute = timedelta(days=6,seconds=0,microseconds=0)
            future = future + minute
            self.energyDict['times'].append(future.isoformat())

        for i in range(1,50):
            self.energyDict['series']['actual']['points'].append(None)

        with open('/home/yingying/Desktop/5.0RC/volttron/examples/TransactiveAgent/transactiveagent/greendata-transactive.json') as data_file: 
            data_historical = json.load(data_file)
            for i in data_historical:
                try:
                    cumulative_historical = cumulative_historical + float(i['Value - Real energy (Watt-hours)'])/1000
                    self.energyDict['series']['historical']['points'].append(cumulative_historical)
                except IndexError:
                     pass
                continue

        with open('/home/yingying/Desktop/5.0RC/volttron/examples/TransactiveAgent/transactiveagent/greenButtonHistoricalData.json') as data_file:   
            data_transactive = json.load(data_file)
            for i in data_transactive:
                try:
                    cumulative_transactive = cumulative_transactive + float(i['Value - Real energy (Watt-hours)'])/1000
                    self.energyDict['series']['transactive']['points'].append(cumulative_transactive)
                except IndexError:
                    pass
                continue


# Initiate the json in the beginning of the code
        for device_list in self.deviceList:
            device_json = {
                    "energy":0,
                    "flexibility":"high",
                    "participate": True,
                    "power":0,
                    "reset":False,
                    "zone_max":1,
                    "zone_min":0
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
        header = {'Content-Type': 'application/json'}
        requests.post(urlServices, data = jsonMsg, headers = header)  

    @PubSub.subscribe('pubsub', 'devices/all/')
    def on_match_all(self, peer, sender, bus,  topic, headers, message):
        ''' This method subscibes to all topics. It simply prints out the 
        topic seen.
        # '''
        urls = [
        self.url+'states/'+ self.entityId_transactive_component,
        self.url+'states/'+ self.entityId_connectedDevices_component,
        self.url+'states/'+ self.entityId_advancedSetting_component,
        self.url+'states/'+ self.entityId_energyEfficiencyPeakPeriod_component,
        self.url+'states/'+ self.entityId_timeOfEnergyUseSaving,
        self.url+'states/'+ self.entityId_user_settings_component
        ]

        counter =1

        request_data = (grequests.get(u) for u in urls)
        response = grequests.map(request_data)
        dataObject_transactive = json.loads(response[0].text) 
        dataObject_connected = json.loads(response[1].text)
        dataObject_advanced_settings = json.loads(response[2].text)
        dataObject_energyEfficiency_peakPeriod = json.loads(response[3].text)
        dataObject_timeOfUse_saving = json.loads(response[4].text)
        dataObject_user_sett = json.loads(response[5].text)

        totalEnergy = 0
        totalPower = 0
        zone_max=100
        zone_min =0
        device_name = topic.partition('/')[-1].rpartition('/')[0].rpartition('/')[0].rpartition('/')[2]

        with open('/home/yingying/Desktop/5.0RC/volttron/examples/TransactiveAgent/config_devices') as device_file: 
            device_dictionary = json.load(device_file)
        self.ChangeUserSettings(device_dictionary)
        if (device_name in self.deviceList):
            if (topic == 'devices/all/'+ device_name +'/office/skycentrics'):
                print(device_name)
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                for device in  self.deviceList:
                    if (device == device_name):
                        if (message[0]['InstantaneousElectricityConsumption']):
                            load_value = round(message[0]['InstantaneousElectricityConsumption'],2)
                        else :
                            load_value = 0 
                        if (message[0]['TotalEnergyStorageCapacity']):
                            energy_value = round(message[0]['TotalEnergyStorageCapacity'],2)
                        else :
                            energy_value = 0 
                        self.energyPoint[str(device)].append(energy_value)
                        self.powerPoint[str(device)].append(load_value)
                    else :
                        load_value = float(dataObject_connected['attributes']['devices'][str(device)]['power'])
                        energy_value = float(dataObject_connected['attributes']['devices'][str(device)]['energy'])
                        self.energyPoint[str(device)].append(energy_value)
                        self.powerPoint[str(device)].append(load_value)

                    flexibility = dataObject_connected['attributes']['devices'][str(device)]['flexibility']
                    participation = dataObject_connected['attributes']['devices'][str(device)]['participate']
                    reset = dataObject_connected['attributes']['devices'][str(device)]['reset']

                    device_json = {
                        "energy":energy_value,
                        "flexibility":flexibility,
                        "participate": participation,
                        "power":load_value,
                        "reset":reset,
                        "zone_max":zone_max,
                        "zone_min":zone_min
                        }
                    devicesEnergyStatus_json = {
                        "points": self.energyPoint[str(device_name)]
                        }
                    devicesPowerStatus_json = {
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
                    totalEnergy += energy_value
                    totalPower += load_value
                print("times")
                print(datetime.datetime.utcnow())
                print(self.future)
                self.ChangeConnectedDevicesState(self.deviceDictionary)
                self.energyDict['series']['actual']['line-style'] = ""
                if (self.energyDict['series']['actual']['points'][self.count] == None):
                    self.energyDict['series']['actual']['points'][self.count] =round(totalEnergy,2)
                    self.energyDict['series']['transactive']['points'][self.count] =round(totalEnergy,2)
                    print("the first entry deleted")
                energyDataPlot = {
                    "series":self.energyDict['series'],
                    "time-format": "MM/DD",
                    "times":self.energyDict['times']
                }
                if (self.count == 50):
                    self.count=0
                self.count = self.count + 1
                gevent.sleep(10)
                self.ChangeTransactiveState(round(totalEnergy,2),round(totalPower,2),energyDataPlot,flexibility,zone_max,zone_min)
                self.startTime =datetime.datetime.utcnow()
                if ((datetime.datetime.utcnow()) >= self.future):
                    self.setTime(self.energyDevicesStatusesDict,self.powerDevicesStatusesDict,timestamp)


    def setTime(self,energyDevicesStatusesDict,powerDevicesStatusesDict,timestamp):
        energyDevicesStatusesDict['times'].append(timestamp)
        powerDevicesStatusesDict['times'].append(timestamp)
        if (len(energyDevicesStatusesDict['times']) == 11):
            del (energyDevicesStatusesDict['times'][0])
        if (len(powerDevicesStatusesDict['times']) == 11):
            del (powerDevicesStatusesDict['times'][0])
        self.future = datetime.datetime.utcnow() + timedelta(seconds=0,minutes=1)
        self.ChangeDeviceStatuses(energyDevicesStatusesDict,powerDevicesStatusesDict)

    def ChangeTransactiveState(self,overall_energy,overall_power,energyDataPlot,flexibility,zone_max,zone_min):

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
                            "id": "transactive-home"
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
                            "zone_max" : zone_max,
                            "zone_min" : zone_min
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
            header = {'Content-Type': 'application/json'}
            requests.post(urlServices, data = jsonMsg, headers = header)
            print("Transactive State has been changed")
        except ValueError:
                pass

    def ChangeConnectedDevicesState(self,device_json):

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
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Connected Devices State has been changed")
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
                                "updateMethod":"update_chart_type"
                                },
                                {
                                "data":powerDevicesStatusesDict,
                                "id":"device-power",
                                "label":"Power (kW)",
                                "type":"bar",
                                "updateMethod":"update_chart_type"
                            }],
                            "friendly_name":"Device Statuses",
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print(" Devices Statuses State has been changed")
            except ValueError:
                    pass

    def ChangeAdvancedSettings(self,powerSavingValue,energySavingValue,savingStartTime,savingEndTime,timePeriodStart,timePeriodEnd,incentives):

            if self.entityId_advancedSetting_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_advancedSetting_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                             "powerSavings": {
                                "units": "kW",
                                "value": powerSavingValue,
                                "label":""
                            },
                            "savingsEndTime":{
                                "value": savingEndTime
                            },
                            "incentives": {
                                "units": "$ per peak period",
                                "value": incentives,
                                "label": "Incentives"
                            },
                            "savingsStartTime":{
                                "value": savingStartTime
                            },
                            "timePeriodStart" : {
                                "value": timePeriodStart
                            },
                            "friendly_name":"Advanced Settings",
                            "time_of_use_pricing": {
                                "label":"Time of use pricing",
                                 "list": [
                                    {
                                        "endTime": "2017-10-24T14:00:00-07:00",
                                        "startTime": "2017-10-24T10:00:00-07:00",
                                        "units": "cents per",
                                        "value": 15
                                    },
                                    {
                                        "endTime": "2017-10-24T20:00:00-07:00",
                                        "startTime": "2017-10-24T14:00:00-07:00",
                                        "units": "cents per",
                                        "value": 35
                                    },
                                    {
                                        "endTime": "2017-10-24T09:00:00-07:00",
                                        "startTime": "2017-10-24T20:00:00-07:00",
                                        "units": "cents per",
                                        "value": 10
                                    }
                                ]
                            },
                            "timePeriodEnd":{
                                "value": timePeriodEnd
                            },
                            "energySavings": {
                                "units": "kWh",
                                "value": energySavingValue,
                                "label":""
                            },
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Advanced Setting State has been changed")
            except ValueError:
                    pass
    def ChangeUserSettings(self,device_dictionary):

            if self.entityId_user_settings_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_user_settings_component
            try:

                jsonMsg = json.dumps({
                        "attributes":device_dictionary,
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Advanced Setting State has been changed")
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



   
