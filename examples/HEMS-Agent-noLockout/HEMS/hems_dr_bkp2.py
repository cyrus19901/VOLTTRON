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

from datetime import datetime
import errno
import inspect
import logging
import numpy as np
import pandas as pd
import os, os.path
from pprint import pprint
import re
import math
import sys
import uuid
import scipy.io
import scipy.io as sio
import gevent
from volttron.platform.agent import json as jsonapi
from scipy.interpolate import interp1d
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod




utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'



def hems_dr(config_path, **kwargs):

    config = utils.load_config(config_path)
    tf = config.get('tf', None)
    ddt = config.get('ddt', None)
    Dtimestamps = (tf - ddt) / ddt + 1
    Dtimes = int(Dtimestamps)
    mdt = config.get('mdt', None)
    Mtimes = int(Dtimes / (mdt / ddt))
    uncontrolled = config.get('uncontrolled', None)
    para_AC_dn = {}
    values = {'a', 'b', 'c', 'd', 'e', 'f'}
    para_AC_dn['ratio'] = config.get('para-ratio')
    para_AC_dn['Tdesired'] = config.get('para-Tdesired')
    para_AC_dn['Tmin'] = config.get('para-Tmin')
    para_AC_dn['Tmax'] = config.get('para-Tmax')
    # para_AC_dn['power'] = config.get('para-power', None)
    para_AC_dn['COP'] = config.get('para-COP')
    hr_start = config.get('hr_start')
    hr_stop = config.get('hr_stop')
    Q_lim = config.get('Q_lim')
    percentage = config.get('percentage')
    P_cap = config.get('P_cap')
    U_A = config.get('U_A')
    C_a = config.get('C_a')
    halfband_AC_dn_above =  config.get('halfband_AC_dn_above')
    halfband_AC_dn_below =  config.get('halfband_AC_dn_below')
    Q_i = config.get('Q_i') 
    Delta = config.get('delta')
    Dtimestamps = np.arange(0, tf - ddt, ddt)
    Dtimestamps = np.insert(Dtimestamps, len(Dtimestamps), 23.9917)
    Q_uc =0 
    Q_uc_avg =0
    ## Initialize
    P_avg = 0.15
    P_sigma =  0.01 

    class HemsDR(Agent):
        '''This is a simple example of a historian agent that writes stuff
        to a SQLite database. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        '''

        def __init__(self, **kwargs):
            super(HemsDR, self).__init__(**kwargs)

        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            # Demonstrate accessing a value from the config file
            self._agent_id = config['agentid']


        @PubSub.subscribe('pubsub', '')
        def subscribeHouseValues(self, peer, sender, bus,  topic, headers, message):
            if (topic == 'analysis/controls/ecobeeCurrent/currentTemp/currentTemp'):
                self.T_a = message[0]
            if (topic == 'devices/LabHomes/controlsHome/campbell-TC-B/Solar Outside Modbus'):
                self.Q_s = message[0]
            if (topic == 'devices/LabHomes/controlsHome/campbell-TC-B/Outside Air Temperature RH'): 
                self.T_out = message[0]
            if (topic == 'devices/LabHomes/controlsHome/campbell-PW-B/Heat Pump Total Power'): 
                self.HP_power = message[0]
            if (topic == 'ControlsHouse/AC/participate'):
                self.DR = message[0]

            self.HP_power = 1500
            self.DR = True
            self.power = (0.1865 * pow(self.T_out,2)) - (10.49*self.T_out) + 1439.1
            Q_h = -para_AC_dn['COP'] * self.power
            self.ETP_a_AC_dn = (-U_A) / C_a
            self.Q_s_range = 0.5 * self.Q_s
            self.Q_limvalue = (self.HP_power * percentage) /100
            self.ETP_b_on_AC_dn = (U_A * self.T_out + np.tile(0.5 * Q_i, (1, Dtimes))[0] + self.Q_s_range +
                              np.tile(Q_h, (1, Dtimes))[0]) / C_a
            self.ETP_b_off_AC_dn = (U_A * self.T_out + np.tile(0.5 * Q_i, (1, Dtimes))[0] + self.Q_s_range) / C_a

        @Core.periodic(5)
        def DRStartController(self):
            if (self.DR == True):

                A_ETP_AC_dn = self.ETP_a_AC_dn
                B_ETP_ON_AC_dn = self.ETP_b_on_AC_dn
                B_ETP_OFF_AC_dn = self.ETP_b_off_AC_dn
                A = 1.0012
                B = -1.5378e-03
                C = -2.7438e-06
                D = 8.840e-05
                Q_i = 3.5813e-03 #this is will Qunknown

                if (self.HP_power < 50):
                    Dstatus_AC_dn = 1
                else:
                    Dstatus_AC_dn = 0

                AC_flexibility = self.AC_flexibility_prediction(P_avg, P_sigma, P_cap, para_AC_dn,
                                                                self.T_a,
                                                                halfband_AC_dn_above,halfband_AC_dn_below, Dstatus_AC_dn, mdt, A, B,
                                                                C,D, self.T_out, Q_i, self.Q_s,-8616.29,ddt)
                P_bid_AC_dn = AC_flexibility[0]
                P_min_AC_dn = AC_flexibility[1]
                P_max_AC_dn = AC_flexibility[2]
                Q_min_AC_dn = AC_flexibility[3]
                Q_max_AC_dn = AC_flexibility[4]

                P_min = P_min_AC_dn
                P_max = P_max_AC_dn
                Q_min = Q_min_AC_dn
                Q_max = Q_max_AC_dn
                market_clear = self.market_clear_ideal_accurate_1AC(P_min, P_max, Q_max, Q_min,
                                                                   P_avg, P_cap, Q_uc_avg, self.Q_limvalue)

                P_clear = market_clear[0]
                Q_clear = market_clear[1]
                T_set_AC_dn = self.AC_Tset_control_ideal(P_clear, P_avg, P_sigma, para_AC_dn)
                self.publishValue(T_set_AC_dn)
            else :
                self.NoDR()
                
        
        def publishValue(self,value):
            now = datetime.utcnow().isoformat(' ') + 'Z'
            headers = {
                headers_mod.DATE: now
            }
            T_set_AC_dn_message = [float(value),{'units': 'F','tz':'UTC','type':'float'}]
            pub_topic = 'analysis/controls/ecobeeSet/TSetACdn'
            self.vip.pubsub.publish('pubsub',pub_topic,headers,T_set_AC_dn_message).get(timeout=2)


        def NoDR(self):

            T_set_AC_dn = para_AC_dn['Tdesired']

            # if uncontrolled:

        def AC_compute_temp(self,A, B, C, D , T_out, Q_i, Q_s, Q_h, T_a, mdt, ddt):

            temp = T_a;
            for i in  np.arange(0, int(mdt / ddt)):
                temp = A * temp + B * T_out + C * Q_h + D * Q_s + Q_i 
            return temp

        def AC_compute_time(self, A, B, C, D, T_out, Q_i, Q_s, Q_h, T_0, T_1, mdt, ddt):
            temp = T_0
            for i in np.arange(0, int(mdt / ddt)):
                temp = A * temp + B * T_out + C * Q_h + D * Q_s + Q_i 
                if Q_h == 0:
                    if (temp > T_1):
                        break
                else:
                    if (temp < T_1):
                        break
            time = i * ddt
            return time

        def AC_Status_update(self,Dtemp_current, halfband, T_set, Dstatus_current):
            if Dtemp_current <= (T_set - halfband):
                Dstatus_update = 0

            elif Dtemp_current >= (T_set + halfband):
                Dstatus_update = 1

            elif Dtemp_current > T_set - halfband and Dtemp_current < T_set + halfband:
                Dstatus_update = Dstatus_current
            return Dstatus_update

        def AC_Temp2Price_ideal_accurate(self,P_avg, P_sigma, P_cap, para, Temp):
            if Temp <= para["Tdesired"]:
                Price = P_avg + (Temp - para["Tdesired"]) * para["ratio"] * P_sigma / (para["Tdesired"] - para["Tmin"])
            if Temp >= para["Tdesired"]:
                Price = P_avg + (Temp - para["Tdesired"]) * para["ratio"] * P_sigma / (para["Tmax"] - para["Tdesired"])
            if Price < max(P_avg - para["ratio"] * P_sigma, 0):
                Price = 0
            if Price > min(P_cap, P_avg + para["ratio"] * P_sigma):
                Price = P_cap

            return Price

        def AC_Tset_control_ideal(self,P_clear, P_avg, P_sigma, para):
            T_set = 0
            if (P_clear <= P_avg):
                T_set = para['Tdesired'] + (P_clear - P_avg) / (para['ratio'] * P_sigma) * (para['Tdesired'] - para['Tmin'])
            if (T_set < para['Tmin']):
                T_set = para['Tmin']
            if (P_clear > P_avg):
                T_set = para['Tdesired'] + (P_clear - P_avg) / (para['ratio'] * P_sigma) * (para['Tmax'] - para['Tdesired'])
            if (T_set > para['Tmax']):
                T_set = para['Tmax']
            return T_set

        def power_response(self,P_min, P_max, Q_max, Q_min, P):
            if (Q_max == Q_min):
                Q = Q_min
            elif (P_max == P_min):
                if (P > P_max):
                    Q = Q_min
                else:
                    Q = Q_max
            else:
                if (P >= P_max):
                    Q = Q_min
                elif (P <= P_min):
                    Q = Q_max
                else:
                    Q = Q_min + (Q_max - Q_min) * (P - P_max) / (P_min - P_max)

            return Q

        def market_clear_ideal_accurate_1AC(self,P_min, P_max, Q_max, Q_min, P_avg, P_cap, Q_uc_avg, Q_lim):
            Q_clear_AC_dn = self.power_response(P_min, P_max, Q_max, Q_min, P_avg)
            Q_clear = Q_clear_AC_dn
            # print(Q_clear)
            range = 0
            if (Q_clear <= (Q_lim - Q_uc)):
                P_clear = P_avg
            else:
                P = np.arange(P_cap, 0, -0.001)
                Q_clear = np.zeros((1, len(P)))[0]
                Q_error = np.zeros((1, len(P)))[0]
                for i in np.arange(0, len(P)):
                    Q_clear_AC_dn = self.power_response(P_min, P_max, Q_max, Q_min, P[i])
                    Q_clear[i] = Q_clear_AC_dn
                    Q_error[i] = Q_clear[i] - (Q_lim - Q_uc)
                    if (Q_error[i] >= 0):
                        range = i
                        break
                if (Q_error[range] == 0):

                    P_clear = P[range]
                    Q_clear = Q_clear[range]
                else:
                    if range == 1:
                        P_clear = P[range]
                        Q_clear = Q_clear[range]
                    else:
                        P_clear = P[range - 1]
                        Q_clear = Q_clear[range - 1]

            return P_clear, Q_clear



        def AC_flexibility_prediction(self,P_avg, P_sigma, P_cap, para, T_a, halfband_above,halfband_below, status, mdt, A, B, C, D, T_out, Q_i, Q_s, Q_h,ddt):
            
            power = (0.1865 * pow(T_out,2)) - (10.49*T_out) + 1439.1
            tmpON = self.AC_compute_temp(A, B, C, D, T_out, Q_i, Q_s, Q_h, T_a, mdt, ddt)
            tmpOFF = self.AC_compute_temp(A, B, C, D, T_out, Q_i, Q_s, 0, T_a, mdt, ddt)

            if status == 0:
                if T_a <= para["Tmin"] + halfband_above and tmpOFF <= para["Tmin"] + halfband_above:
                    Q_max = 0
                    T_min = para["Tmin"]
                    Q_min = 0
                    T_max = para["Tmin"]

                if T_a < para["Tmin"] + halfband_above and tmpOFF > para["Tmin"] + halfband_above:
                    tOFF = self.AC_compute_time(A, B, C, D, T_out, Q_i, Q_s, 0, para["Tmin"] + halfband_above, mdt, ddt)
                    Q_max = (mdt - tOFF) / mdt * power
                    T_min = para["Tmin"]
                    Q_min = 0
                    T_max = tmpOFF - halfband_above

                if T_a == para["Tmin"] + halfband_above and tmpOFF > para["Tmin"] + halfband_above:
                    if tmpON >= para["Tmin"] - halfband_below:
                        Q_max = power
                    else:
                        tON = self.AC_compute_time(A, B, C,D, T_out, Q_i, Q_s, Q_h, T_a, para["Tmin"] - halfband_below, mdt, ddt)
                        Q_max = tON / mdt * power
                    T_min = para["Tmin"]
                    Q_min = 0
                    T_max = tmpOFF - halfband_above

                if T_a > para["Tmin"] + halfband_above:
                    if tmpON >= para["Tmin"] - halfband_below:
                        Q_max = power
                        T_min = min(T_a - halfband_above, tmpON + halfband_below)
                    else:
                        tON = self.AC_compute_time(A, B, C, D ,T_out, Q_i, Q_s, Q_h, T_a, para["Tmin"] - halfband_below, mdt, ddt)
                        Q_max = tON / mdt * power
                        T_min = T_a - halfband_above

                    if tmpOFF <= para["Tmax"] + halfband_above:
                        Q_min = 0
                        T_max = max(T_a - halfband_above, tmpOFF - halfband_above)
                    else:
                        tOFF = self.AC_compute_time(A, B, C, D, T_out, Q_i, Q_s, 0, T_a, para["Tmax"] + halfband_above, mdt, ddt)
                        Q_min = (mdt - tOFF) / mdt * power
                        T_max = para["Tmax"]

            if status == 1:
                if T_a >= para["Tmax"] - halfband_below and tmpON >= para["Tmax"] - halfband_below:
                    Q_max = power
                    T_min = para["Tmax"]
                    Q_min = power
                    T_max = para["Tmax"]

                if T_a > para["Tmax"] - halfband_below and tmpON < para["Tmax"] - halfband_below:
                    Q_max = power
                    T_min = tmpON + halfband_below
                    tON = self.AC_compute_time(A, B, C, D, T_out, Q_i, Q_s, Q_h, T_a, para["Tmax"] - halfband_below, mdt, ddt)
                    Q_min = tON / mdt * power
                    T_max = para["Tmax"]

                if T_a == para["Tmax"] - halfband_below and tmpON < para["Tmax"] - halfband_below:
                    Q_max = power
                    T_min = tmpON + halfband_below
                    if (tmpOFF <= para["Tmax"] + halfband_above):
                        Q_min = 0
                    else:
                        tOFF = self.AC_compute_time(A, B, C,D, T_out, Q_i, Q_s, 0,T_a, para["Tmax"] + halfband_above, mdt, ddt)
                        Q_min = (mdt - tOFF) / mdt * power
                    T_max = para["Tmax"]

                if (T_a < para["Tmax"] - halfband_below):
                    if (tmpOFF <= para["Tmax"] + halfband_above):
                        Q_min = 0
                        T_max = max(T_a + halfband_below, tmpOFF - halfband_above)
                    else:
                        tOFF = self.AC_compute_time(A, B, C, D, T_out, Q_i, Q_s, 0,T_a, para["Tmax"] + halfband_above, mdt, ddt)
                        Q_min = (mdt - tOFF) / mdt * power
                        T_max = T_a + halfband_below

                    if (tmpON >= para["Tmin"] - halfband_below):
                        Q_max = power
                        T_min = min(T_a + halfband_below, tmpON + halfband_below)
                    else:
                        tON = self.AC_compute_time(A, B, C,D, T_out, Q_i, Q_s, T_a, (para["Tmin"] - halfband_below), mdt, ddt)
                        Q_max = tON / mdt * power
                        T_min = para["Tmin"]
            if (Q_min == Q_max and Q_min == 0):
                P_min = 0
                P_max = 0
                P_bid = 0
            elif (Q_min == Q_max and Q_min > 0):
                P_min = P_cap
                P_max = P_cap
                P_bid = P_cap
                Q_min = 0
            else:
                P_min = self.AC_Temp2Price_ideal_accurate(P_avg, P_sigma, P_cap, para, T_min)
                P_max = self.AC_Temp2Price_ideal_accurate(P_avg, P_sigma, P_cap, para, T_max)
                P_bid = (P_min + P_max) / 2

            return P_bid, P_min, P_max, Q_min, Q_max

        def AC_Temp_control(self,Dtemp_current, A_etp, B_etp_on, B_etp_off, halfband, T_set, Dstatus_current, ddt):

            eAt = 0.994989265677227
            factor = 0
            if (Dstatus_current == 1):
                Dtemp_next = eAt * Dtemp_current + 0.008312437794098 * B_etp_on  # A_etp\(eAt-eye(1)) = 0.0083 np.eye()
                Dstatus_next = Dstatus_current

                # find index of Ta compoments outside range

                if (Dtemp_next <= T_set - halfband):  # need to turn off, since temperature goes below the deadband
                    Dtemp_next = Dtemp_current
                    sub_ddt = 1.0 / 3600.0
                    for t in np.arange(sub_ddt, ddt + sub_ddt, sub_ddt):
                        if Dstatus_next == 1:
                            factor = factor + sub_ddt / ddt
                            Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_on) * sub_ddt
                            if (Dtemp_next <= T_set - halfband):
                                Dstatus_next = 0
                        else:
                            Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_off) * sub_ddt
                    factor = factor - 1

            else:

                Dtemp_next = eAt * Dtemp_current + 0.008312437794098 * B_etp_off
                Dstatus_next = Dstatus_current

                # find index of Ta compoments outside range

                if (Dtemp_next >= T_set + halfband):
                    # need to turn on, since temperature goes beyond the deadband
                    Dtemp_next = Dtemp_current

                    sub_ddt = 1.0 / 3600.0
                    for t in np.arange(sub_ddt, ddt + sub_ddt, sub_ddt):
                        if Dstatus_next == 0:
                            Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_off) * sub_ddt
                            if (Dtemp_next >= T_set + halfband):
                                Dstatus_next = 1
                        else:
                            factor = factor + sub_ddt / ddt
                            Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_on) * sub_ddt
                #print(Dtemp_next, Dstatus_next, factor)
            return Dtemp_next, Dstatus_next, factor


        def P_actualCalculate(self,Mtimes,Q_actual_AC_dn_avg,Q_actual_AC_dn,P_actual,Q_actual,Q_actual_avg,P_actual_avg,mdt):
            for i in range (0,Mtimes):
                Q_actual_AC_dn_avg[i] = np.average(Q_actual_AC_dn[ i*10 : (i*10)+10])
                Q_actual_avg[i] = np.average(Q_actual[i * 10 : (i*10)+10])
                P_actual_avg[i] = np.average(P_actual[i*10 : (i*10)+10])
                print(T_set_AC_dn)
                print("=============================================")
                # print(P_actual_avg[i])

            avg_period = 0.25/mdt
            Q_actual_AC_dn_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]
            Q_actual_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]
            P_actual_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]

            for i in np.arange (1,int(Mtimes/avg_period)):
                Q_actual_AC_dn_quarter[i] = np.mean(Q_actual_AC_dn_avg[int((i-1)*avg_period+1):int(i*avg_period)])
                Q_actual_quarter[i] = np.mean(Q_actual_avg[int((i-1)*avg_period): int(i*avg_period)])
                P_actual_quarter[i] = np.mean(P_actual_avg[int((i-1)*avg_period) : int(i*avg_period)])
                


    HemsDR.__name__ = 'HemsDR'
    return HemsDR(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(hems_dr, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
