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
# from scipy.interpolate import interp1d
# from cvxopt import matrix, solvers

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'
class GetTransactiveAgent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 

        super(GetTransactiveAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.device_list = self.config['device_list']
        # self.entityId_transactive_component = self.config['entityID_transactive']
        self.entityId_transactive_component = 'transactive_home.transactive_home'
        self.entityId_connectedDevices_component = 'connected_devices.connected_devices'
        self.entityId_utilitySettings_component = 'advanced_settings.utility_settings'
        self.entityId_userSettings_component = 'user_settings.device_settings'
        self.entityId_climate_heatpump = 'climate.heatpump'
        self.entityID_wholeHouseEnergy_component = 'whole_house_energy.whole_house_energy'
        self.url = self.config['url']
        self.password = self.config['password']
        # self.data  = []
        # self.data2  = []
        self.new_state = self.config['state']

#Moving some from the transactive agent 
    @Core.periodic(5)
    def accessService(self):

        urls = [
        self.url+'states/'+ self.entityId_transactive_component,
        self.url+'states/'+ self.entityId_connectedDevices_component,
        self.url+'states/'+ self.entityId_utilitySettings_component,
        self.url+'states/'+ self.entityID_wholeHouseEnergy_component,
        self.url+'states/'+ self.entityId_userSettings_component,
        self.url+'states/'+ self.entityId_climate_heatpump
        ]
        header = {'Content-Type': 'application/json' ,'x-ha-access': self.password}
        request_data = (grequests.get(u, headers= header) for u in urls)
        response = grequests.map(request_data)
        self.dataObject_transactive = json.loads(response[0].text)
        self.dataObject_connected = json.loads(response[1].text)
        self.dataObject_utility_settings = json.loads(response[2].text)
        self.dataObject_whole_house_energy = json.loads(response[3].text)
        self.dataObject_user_sett = json.loads(response[4].text)
        self.dataObject_heat_pump = json.loads(response[5].text)

        self.setWillingness()
        self.setEnergyReduction()
        self.sendDeviceList()
        # self.sendDeviceFromHA()
        try:
            self.vip.pubsub.subscribe(peer='pubsub', prefix='record/', 
                                     callback=self.on_match_all)
        except:
            _log.debug("Topic Not found for enery_reduction or minimum disutility")

    @PubSub.subscribe('pubsub', 'record/skycentrics/')
    def on_match_all(self, peer, sender, bus,  topic, headers, message):


        canToggle = self.dataObject_whole_house_energy['attributes']['canToggle']
        ppBenefitEstimateValue=self.dataObject_whole_house_energy['attributes']['ppBenefitEstimate']['value']
        ppBenefitGoalValue=self.dataObject_whole_house_energy['attributes']['ppBenefitGoal']['value']
        ppReductionEstimateValue=self.dataObject_whole_house_energy['attributes']['ppReductionEstimate']['value']
        # print(self.dataObject_utility_settings['attributes'])
        ppReductionGoalValue=self.dataObject_utility_settings['attributes']['energySavings']['value']

        touBenefitEstimateValue=self.dataObject_whole_house_energy['attributes']['touBenefitEstimate']['value']
        touBenefitGoalValue=self.dataObject_whole_house_energy['attributes']['touBenefitGoal']['value']
        touReductionEstimateValue=self.dataObject_whole_house_energy['attributes']['touReductionEstimate']['value']
        touReductionGoalValue=self.dataObject_whole_house_energy['attributes']['touReductionGoal']['value']
        useAlgorithm = self.dataObject_whole_house_energy['attributes']['useAlgorithm']['value']

        if (topic == 'record/skycentrics/energyReduction'):
            # print(message)
            # print("****************************************")
            # print(str(round(message[0]['EstimatedEnergyReduction'],2)))
            ppReductionEstimateValue=str(round(message[0]['EstimatedEnergyReduction'],2))
            print(ppReductionEstimateValue)
        if (topic == 'record/skycentrics/Compensation'):
            # print("****************************************")
            ppBenefitEstimateValue = "$"+ str(round(message[0]['Compensation'],2))
            # print(ppBenefitEstimateValue)
        self.changeWholeHouseEnergy(canToggle,ppBenefitEstimateValue,ppBenefitGoalValue,ppReductionEstimateValue,ppReductionGoalValue,touBenefitEstimateValue,touBenefitGoalValue,touReductionEstimateValue,touReductionGoalValue,useAlgorithm)

    # def sendDeviceFromHA(self):

    #     devicename =(self.dataObject_heat_pump['attributes']['friendly_name'])
    #     pub_topic = 'devices/all/'+ devicename + '/office/skycentrics'
    #     now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
    #     headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
    #     self.vip.pubsub.publish('pubsub',pub_topic,headers,self.dataObject_heat_pump)         

    def sendDeviceList(self):   

        for value in self.dataObject_user_sett["attributes"]["devices"]:
            settings = self.dataObject_user_sett["attributes"]["devices"][str(value)]["settings"]
            pub_topic = 'house/device/details/'+ value
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,settings)         

    def setWillingness(self):   
        print("in Willingness")
        for value in  self.dataObject_connected["attributes"]["devices"]:
            flexibility = self.dataObject_connected["attributes"]["devices"][str(value)]['flexibility']
            pub_topic = 'house/'+ value+'/'+value+'_beta'
            print(pub_topic)
            print(flexibility)
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,flexibility)        
        
    def setEnergyReduction(self):   
        energyReduction = float(self.dataObject_utility_settings['attributes']['energySavings']['value'])
        energyReductionStartTime = self.dataObject_utility_settings['attributes']['savingsStartTime']['value']
        energyReductionEndTime = self.dataObject_utility_settings['attributes']['savingsEndTime']['value']
        pub_topic_value = 'house/energy_reduction_amount'
        pub_topic_startTime = 'house/energy_reduction_startTime'
        pub_topic_endTime = 'house/energy_reduction_endTime'
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        print(energyReduction)
	print("=============================================")
        self.vip.pubsub.publish('pubsub',pub_topic_value,headers,energyReduction)
        self.vip.pubsub.publish('pubsub',pub_topic_startTime,headers,energyReductionStartTime)
        self.vip.pubsub.publish('pubsub',pub_topic_endTime,headers,energyReductionEndTime)         

    def changeWholeHouseEnergy(self,canToggleValue,ppBenefitEstimateValue,ppBenefitGoalValue,ppReductionEstimateValue,ppReductionGoalValue,touBenefitEstimateValue,touBenefitGoalValue,touReductionEstimateValue,touReductionGoalValue,useAlgorithm):

            if self.entityID_wholeHouseEnergy_component is None:
                return

            urlServices = self.url+'states/'+ self.entityID_wholeHouseEnergy_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                           "canToggle":canToggleValue,
                           "friendly_name": "Whole House Energy",
                           "goalLegendLabel": "goal (from utility",
                           "ppBenefitEstimate":{
                                "value": ppBenefitEstimateValue
                            },
                           "ppBenefitGoal": {
                                "value": ppBenefitGoalValue
                            },
                            "ppReductionEstimate": {
                                "units": "kWh",
                                "value": ppReductionEstimateValue
                            },
                            "ppReductionGoal": {
                                "units": "kWh",
                                "value": ppReductionGoalValue
                            },
                            "touBenefitEstimate": {
                                "value": touBenefitEstimateValue
                            },
                            "touBenefitGoal": {
                                "value": touBenefitGoalValue
                            },
                            "touReductionEstimate": {
                                "units": "kWh",
                                "value": touReductionEstimateValue
                            },
                            "touReductionGoal": {
                                "units": "kWh",
                                "value": touReductionGoalValue
                            },
                            "useAlgorithm": {
                                "value": useAlgorithm
                            }
                        },
                        "state": self.new_state
                    })
                # print(jsonMsg)
                header = {'Content-Type': 'application/json' ,'x-ha-access':self.password}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Energy efficiency for peak period has been changed")
            except ValueError:
                    pass

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(GetTransactiveAgent,version=__version__)
    except Exception as e:
        print e
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass                 



   
            

