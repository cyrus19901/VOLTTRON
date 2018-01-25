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
        self.entityId_advancedSettings_component = 'advanced_settings.utility_settings'
        self.entityId_userSettings_component = 'user_settings.device_settings'
        self.entityId_climate_heatpump = 'climate.heatpump'
        self.entityID_wholeHouseEnergy_component = 'whole_house_energy.whole_house_energy'
        self.url = self.config['url']
        self.password = self.config['password']
        self.data  = []
        self.data2  = []
        self.new_state = self.config['state']

#Moving some from the transactive agent 
    @Core.periodic(1)
    def accessService(self):

        urls = [
        self.url+'states/'+ self.entityId_transactive_component,
        self.url+'states/'+ self.entityId_connectedDevices_component,
        self.url+'states/'+ self.entityId_advancedSettings_component,
        self.url+'states/'+ self.entityID_wholeHouseEnergy_component,
        self.url+'states/'+ self.entityId_userSettings_component,
        self.url+'states/'+ self.entityId_climate_heatpump
        ]
        header = {'Content-Type': 'application/json' ,'x-ha-access': self.password}
        request_data = (grequests.get(u, headers= header) for u in urls)
        response = grequests.map(request_data)
        self.dataObject_transactive = json.loads(response[0].text)
        self.dataObject_connected = json.loads(response[1].text)
        self.dataObject_advanced_settings = json.loads(response[2].text)
        self.dataObject_whole_house_energy = json.loads(response[3].text)
        self.dataObject_user_sett = json.loads(response[4].text)
        self.dataObject_heat_pump = json.loads(response[5].text)


        #Peak Period
        # print(self.dataObject_energyEfficiency_peakPeriod)
        # self.compensationAcutal=dataObject_energyEfficiency_peakPeriod['attributes']['compensationActual']['value']
        self.canToggle = self.dataObject_whole_house_energy['attributes']['canToggle']
        self.ppBenefitEstimateValue=self.dataObject_whole_house_energy['attributes']['ppBenefitEstimate']['value']
        self.ppBenefitGoalValue=self.dataObject_whole_house_energy['attributes']['ppBenefitGoal']['value']
        self.ppReductionEstimateValue=self.dataObject_whole_house_energy['attributes']['ppReductionEstimate']['value']
        self.ppReductionGoalValue=self.dataObject_whole_house_energy['attributes']['ppReductionGoal']['value']
        self.touBenefitEstimateValue=self.dataObject_whole_house_energy['attributes']['touBenefitEstimate']['value']
        self.touBenefitGoalValue=self.dataObject_whole_house_energy['attributes']['touBenefitGoal']['value']
        self.touReductionEstimateValue=self.dataObject_whole_house_energy['attributes']['touReductionEstimate']['value']
        self.touReductionGoalValue=self.dataObject_whole_house_energy['attributes']['touReductionGoal']['value']
        self.useAlgorithm = self.dataObject_whole_house_energy['attributes']['useAlgorithm']['value']
        


        self.setWillingness()
        self.setEnergyReduction()
        self.sendDeviceList()
        # self.sendDeviceFromHA()
        try:
            self.vip.pubsub.subscribe(peer='pubsub', prefix='fncs/input/house/', 
                                     callback=self.on_match_all)
        except:
            _log.debug("Topic Not found for enery_reduction or minimum disutility")

    def on_match_all(self, peer, sender, bus,  topic, headers, message):

        if (topic == 'fncs/input/house/energy_reduction'):
            print("============PEAK PERIOD=============================")
            self.ppReductionEstimateValue=str(float(round(message,2)))
            print(self.ppReductionEstimateValue)

        if (topic == 'fncs/input/house/minimum_disutility'):
            # print("============ENERGY REDUCTION=============================")
            self.ppBenefitEstimateValue = "$"+str(float(round(message,2)))
            # print(self.ppBenefitEstimateValue)

        self.changeWholeHouseEnergy(self.canToggle,self.ppBenefitEstimateValue,self.ppBenefitGoalValue,self.ppReductionEstimateValue,self.ppReductionGoalValue,self.touBenefitEstimateValue,self.touBenefitGoalValue,self.touReductionEstimateValue,self.touReductionGoalValue,self.useAlgorithm)

    def sendDeviceFromHA(self):

        devicename =(self.dataObject_heat_pump['attributes']['friendly_name'])
        pub_topic = 'devices/all/'+ devicename + '/office/skycentrics'
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,self.dataObject_heat_pump)         

    def sendDeviceList(self):   

        for value in self.dataObject_user_sett["attributes"]["devices"]:
            settings = self.dataObject_user_sett["attributes"]["devices"][str(value)]["settings"]
            pub_topic = 'house/device/details/'+ value

            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,settings)         

    def setWillingness(self):   

        for value in  self.dataObject_connected["attributes"]["devices"]:

            flexibility = self.dataObject_connected["attributes"]["devices"][str(value)]["flexibility"]
            if (flexibility == "low"):
                willingness = 8
            if (flexibility == "medium"):
                willingness = 5
            if (flexibility == "high"):
                willingness = 2
            pub_topic = 'house/'+ value+'/'+value+'_beta'
            print("===========================")
            print(pub_topic)
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,willingness)        
        

    def setEnergyReduction(self):   

        energyReduction = float(self.dataObject_advanced_settings['attributes']['energySavings']['value'])
        pub_topic = 'house/energy_reduction'

        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,energyReduction)         

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


    def ChangeTimeOfUseEnergyAndSavings(self,energyReductionActual_timeOfUse,energyReductionEstimate_timeOfUse,energyReductionGoal_timeOfUse,savingsActual,savingsEstimate,savingsGoal,timeOfUseUseAlgorithm):

            if self.entityId_timeOfEnergyUseSaving is None:
                return

            urlServices = self.url+'states/'+ self.entityId_timeOfEnergyUseSaving
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                            "energyReductionActual": {
                                "units": "kwh",
                                "value": energyReductionActual_timeOfUse
                            },
                            "energyReductionEstimate": {
                                "units": "kwh",
                                "value": energyReductionEstimate_timeOfUse
                            },
                            "energyReductionGoal": {
                                "units": "kwh",
                                "value": energyReductionGoal_timeOfUse
                            },
                            "friendly_name": "Time of use energy and savings",
                            "savingsActual": {
                                "value": savingsActual
                            },
                            "savingsEstimate": {
                                "value": savingsEstimate
                            },
                            "savingsGoal": {
                                "value": savingsGoal
                            },
                            "useAlgorithm": {
                                "value": timeOfUseUseAlgorithm
                            }
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json' ,'x-ha-access':self.password}
                # print(jsonMsg)
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



   
            
