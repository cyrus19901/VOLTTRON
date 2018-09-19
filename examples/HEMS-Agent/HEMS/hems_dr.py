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
from __future__ import absolute_import, print_function
from scipy.interpolate import interp1d
from volttron.platform.vip.agent import Core, Agent
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
# from market_clear_ideal_accurate_1AC import market_clear_ideal_accurate_1AC
# from AC_Temp_control import AC_Temp_control
# from AC_Tset_control_ideal import AC_Tset_control_ideal
# from AC_Status_update import AC_Status_update
# from AC_flexibility_prediction import AC_flexibility_prediction




utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'



def hems_dr(config_path, **kwargs):

    config = utils.load_config(config_path)

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
            tf = config.get('tf', None)
            ddt = config.get('ddt', None)
            Dtimestamps = (tf - ddt) / ddt + 1
            Dtimes = int(Dtimestamps)
            mdt = config.get('mdt', None)
            Mtimes = int(Dtimes / (mdt / ddt))
            uncontrolled = config.get('uncontrolled', None)
            para_AC_dn = {}
            values = {'a', 'b', 'c', 'd', 'e', 'f'}
            para_AC_dn['ratio'] = config.get('para-ratio', None)
            para_AC_dn['Tdesired'] = config.get('para-Tdesired', None)
            para_AC_dn['Tmin'] = config.get('para-Tmin', None)
            para_AC_dn['Tmax'] = config.get('para-Tmax', None)
            para_AC_dn['power'] = config.get('para-power', None)
            para_AC_dn['COP'] = config.get('para-COP', None)
            hr_start = config.get('hr_start', None)
            hr_stop = config.get('hr_stop', None)
            Q_lim = config.get('Q_lim', None)
            P_cap = config.get('P_cap', None)
            U_A = config.get('U_A', None)
            C_a = config.get('C_a', None)
            Power = np.zeros((1, Dtimes))[0]
            mat_contents = sio.loadmat('AC_data_real.mat')
            T_out_extract = mat_contents['T_out'][0]
            T_out = T_out_extract[2880 * 1:2880 * 2]
            T_a = np.zeros((1, Dtimes))[0]
            Q_s_extract = mat_contents['Q_s']
            Q_s = Q_s_extract[:, 2880 * 1: 2880 * 2]
            P_h_extract = mat_contents['P_R'][0]
            P_h = P_h_extract[288 * 0:288 * 1]
            Q_i = mat_contents['Q_i'][0]
            Q_h = mat_contents['Q_h'][0]
            T_a_extract = np.zeros((1, Dtimes))
            T_a = T_a_extract[0]
            Power_extract = np.zeros((1, Dtimes))
            Power = Power_extract[0]
            P_avg_extract = np.zeros((1, Mtimes))
            P_avg = P_avg_extract[0]
            P_sigma_extract = np.zeros((1,Mtimes))
            P_sigma = P_sigma_extract[0]
            P_R_extract = mat_contents['P_R'][0]
            P_R = P_R_extract[288 * 1:288 * 2]
            halfband_AC_dn = config.get('halfband_AC_dn', None)
            Delta = config.get('delta', None)
            Dstatus_AC_dn_extract = np.zeros((1, Dtimes))
            Dstatus_AC_dn = Dstatus_AC_dn_extract[0]
            Dtemp_AC_dn_extract = np.zeros((1, Dtimes))
            Dtemp_AC_dn = Dtemp_AC_dn_extract[0]

            ###########################################
            ## Initialize UNCONTROLLABLE LOAD

            xl_workbook = pd.ExcelFile("base_load_profile.xlsx")
            df = xl_workbook.parse("Sheet1")
            rep_load_hourly = np.multiply((df['Responsive load base profile'].tolist()), 1000)
            unrep_load_hourly = np.multiply((df['Unresponsive load base profile'].tolist()), 1000)
            scalar_value = scipy.io.loadmat('uc_load_scalar.mat')
            scalar1 = scalar_value['scalar'][0][0]
            scalar2 = scalar_value['scalar'][0][1]
            scalar3 = scalar_value['scalar'][0][2]
            range1 = np.arange(0, 25, 1)
            range2 = np.arange(0, tf - mdt, mdt)
            rep_load_5min = interp1d(range1, np.insert(rep_load_hourly, len(rep_load_hourly), rep_load_hourly[0]),
                                     axis=0,
                                     fill_value="extrapolate")(range2)
            unrep_load_5min = interp1d(range1,
                                       np.insert(unrep_load_hourly, len(unrep_load_hourly), unrep_load_hourly[0]),
                                       axis=0,
                                       fill_value="extrapolate")(range2)
            rep_load = scalar1 * scalar2 * np.array(rep_load_5min)
            unrep_load = scalar1 * scalar3 * np.array(unrep_load_5min)
            Q_uc_avg = rep_load + unrep_load
            range3 = np.arange(0, tf, mdt)
            range3 = np.insert(range3, len(range3), 24)
            Dtimestamps = np.arange(0, tf - ddt, ddt)
            Dtimestamps = np.insert(Dtimestamps, len(Dtimestamps), 23.9917)
            Q_uc = interp1d(range3, np.insert(Q_uc_avg, len(Q_uc_avg), Q_uc_avg[0]), axis=0, fill_value="extrapolate")(
                Dtimestamps)

            for i in range(0, Mtimes):
                Q_uc_avg[i] = np.average(Q_uc[i * 10:(i * 10) + 10])

            ## Initialize

            P_clear = np.zeros((1, Mtimes))[0]
            Q_clear = np.zeros((1, Mtimes))[0]

            Q_actual = np.zeros((1, Dtimes))[0]
            Q_actual_avg = np.zeros((1, Mtimes))[0]
            P_actual = np.zeros((1, Dtimes))[0]
            P_actual_avg = np.zeros((1, Mtimes))[0]

            factor_AC_dn = np.zeros((1, Dtimes))[0]
            Q_actual_AC_dn = np.zeros((1, Dtimes))[0]
            Q_actual_AC_dn_avg = np.zeros((1, Mtimes))[0]

            P_bid_AC_dn = np.zeros((1, Mtimes))[0]
            P_min_AC_dn = np.zeros((1, Mtimes))[0]
            P_max_AC_dn = np.zeros((1, Mtimes))[0]
            Q_min_AC_dn = np.zeros((1, Mtimes))[0]
            Q_max_AC_dn = np.zeros((1, Mtimes))[0]
            Q_clear_AC_dn = np.zeros((1, Mtimes))[0]

            T_set_AC_dn = np.zeros((1, Mtimes))[0]

            P_max = np.zeros((1, Mtimes))[0]
            P_min = np.zeros((1, Mtimes))[0]
            Q_min = np.zeros((1, Mtimes))[0]
            Q_max = np.zeros((1, Mtimes))[0]
            ###############################################
            ## Matlab dynamic simulation

            ih = 0
            Q_h[ih] = [(-para_AC_dn['COP']) * para_AC_dn['power']][0]

            ETP_a_AC_dn = (-U_A) / C_a
            Q_s_range = (0.5 * (Q_s[ih, :]))
            ETP_b_on_AC_dn = (U_A * T_out + np.tile(0.5 * Q_i[ih], (1, Dtimes))[0] + Q_s_range +
                              np.tile(Q_h[ih], (1, Dtimes))[0]) / C_a
            ETP_b_off_AC_dn = (U_A * T_out + np.tile(0.5 * Q_i[ih], (1, Dtimes))[0] + Q_s_range) / C_a
            self.DRStart(self,Dtimes,ETP_a_AC_dn,ETP_b_on_AC_dn,ETP_b_off_AC_dn,mdt,ddt,P_avg,P_sigma,hr_start,hr_stop,T_a,T_out,Power,para_AC_dn,P_cap,Dtemp_AC_dn,halfband_AC_dn,Dstatus_AC_dn,P_bid_AC_dn,P_min_AC_dn,P_max_AC_dn,Q_min_AC_dn,Q_max_AC_dn,P_min,P_max,Q_min,Q_max,P_clear,Q_clear,Q_uc_avg,Q_lim,T_set_AC_dn,uncontrolled,Q_actual_AC_dn,Q_actual,P_actual,Q_uc,factor_AC_dn)

        @Core.receiver("onstart")
        def DRStart(self,Dtimes,ETP_a_AC_dn,ETP_b_on_AC_dn,ETP_b_off_AC_dn,mdt,ddt,P_avg,P_sigma,hr_start,hr_stop,T_a,T_out,Power,para_AC_dn,P_cap,Dtemp_AC_dn,halfband_AC_dn,Dstatus_AC_dn,P_bid_AC_dn,P_min_AC_dn,P_max_AC_dn,Q_min_AC_dn,Q_max_AC_dn,P_min,P_max,Q_min,Q_max,P_clear,Q_clear,Q_uc_avg,Q_lim,T_set_AC_dn,uncontrolled,Q_actual_AC_dn,Q_actual,P_actual,Q_uc,factor_AC_dn):

            for k in range(0, Dtimes - 1):
                # print(k)
                A_ETP_AC_dn = ETP_a_AC_dn
                B_ETP_ON_AC_dn = ETP_b_on_AC_dn[k]
                B_ETP_OFF_AC_dn = ETP_b_off_AC_dn[k]
                val = 0
                if ((k % (mdt / ddt)) == 0):
                    im = int((math.floor(k / mdt * ddt - 1)))
                    P_avg[im] = 0.15
                    P_sigma[im] = 0.05
                    if ((k >= (hr_start / ddt)) and (k <= (hr_stop / ddt))):
                        im = im
                        values = self.AC_model_calibration(self,T_a, T_out, Power, para_AC_dn['COP'], ddt, k)
                        A = values[0]
                        B = values[1]
                        C = values[2]
                        Q_s = values[3]
                        Q_i = values[4]
                        AC_flexibility = AC_flexibility_prediction(P_avg[im], P_sigma[im], P_cap, para_AC_dn,
                                                                        Dtemp_AC_dn[k],
                                                                        halfband_AC_dn, Dstatus_AC_dn[k], mdt, A, B,
                                                                   C, T_out[k], Q_i, Q_s, ddt)
                        P_bid_AC_dn[im] = AC_flexibility[0]
                        P_min_AC_dn[im] = AC_flexibility[1]
                        P_max_AC_dn[im] = AC_flexibility[2]
                        Q_min_AC_dn[im] = AC_flexibility[3]
                        Q_max_AC_dn[im] = AC_flexibility[4]

                        P_min[im] = P_min_AC_dn[im]
                        P_max[im] = P_max_AC_dn[im]
                        Q_min[im] = Q_min_AC_dn[im]
                        Q_max[im] = Q_max_AC_dn[im]

                        market_clear = self.market_clear_ideal_accurate_1AC(self,P_min[im], P_max[im], Q_max[im], Q_min[im],
                                                                       P_avg[im], P_cap, Q_uc_avg[im], Q_lim)

                        P_clear[im] = market_clear[0]
                        Q_clear[im] = market_clear[1]
                        T_set_AC_dn[im] = self.AC_Tset_control_ideal(self,P_clear[im], P_avg[im], P_sigma[im], para_AC_dn)

                    else:
                        T_set_AC_dn[im] = para_AC_dn['Tdesired']

                    P_h = np.insert(P_h[1:], len(P_h) - 1, P_clear[im])

                    if uncontrolled:
                        T_set_AC_dn[im] = para_AC_dn['Tdesired']

                    Dstatus_AC_dn[k] = self.AC_Status_update(self,Dtemp_AC_dn[k], halfband_AC_dn, T_set_AC_dn[im],
                                                        Dstatus_AC_dn[k])
                    Q_actual_AC_dn[k] = para_AC_dn['power'] * Dstatus_AC_dn[k]
                    Q_actual[k] = Q_actual_AC_dn[k]

                P_actual[k] = Q_actual[k] + Q_uc[k]
                AC_attributes = self.AC_Temp_control(self,Dtemp_AC_dn[k], A_ETP_AC_dn, B_ETP_ON_AC_dn, B_ETP_OFF_AC_dn,
                                                halfband_AC_dn,
                                                T_set_AC_dn[im], Dstatus_AC_dn[k], ddt)

                Dtemp_AC_dn[k + 1] = AC_attributes[0]
                Dstatus_AC_dn[k + 1] = AC_attributes[1]
                factor_AC_dn[k] = AC_attributes[2]
                Q_actual_AC_dn[k] = Q_actual_AC_dn[k] + para_AC_dn['power'] * factor_AC_dn[k]
                Q_actual[k] = Q_actual_AC_dn[k]
                P_actual[k] = Q_actual[k] + Q_uc[k]

                Q_actual_AC_dn[k + 1] = para_AC_dn['power'] * Dstatus_AC_dn[k + 1]
                Q_actual[k + 1] = Q_actual_AC_dn[k + 1]
                P_actual[k + 1] = Q_actual[k + 1] + Q_uc[k + 1]


        def AC_model_calibration(self,T_a, T_out, Power, COP, h, k):
            internal_value_file = scipy.io.loadmat('internal.mat')
            A = 1 - (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
            B = (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
            C = h / (internal_value_file['C_a'][0][0])
            Q_i_val = (internal_value_file['Q_i'][0][0])
            Q_s_val = internal_value_file['Q_s'][0][k]
            return A, B, C, Q_s_val, Q_i_val

        def AC_compute_temp(self,A, B, C, T_out, Q_i, Q_s, Q_h, T_a, mdt, ddt):

            temp = T_a;
            for i in np.arange(0, int(mdt / ddt)):
                temp = A * temp + B * T_out + C * Q_h + C * (0.5 * Q_i + 0.5 * Q_s)
            return temp

        def AC_compute_time(A, B, C, T_out, Q_i, Q_s, Q_h, T_0, T_1, mdt, ddt):
            temp = T_0
            for i in range(1, mdt / ddt):
                temp = A * temp + B * T_out + C * Q_h + C * (0.5 * Q_i + 0.5 * Q_s)
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

        def market_clear_ideal_accurate_1AC(self,P_min, P_max, Q_max, Q_min, P_R, P_cap, Q_uc, Q_lim):
            Q_clear_AC_dn = self.power_response(P_min, P_max, Q_max, Q_min, P_R)
            Q_clear = Q_clear_AC_dn
            # print(Q_clear)
            range = 0
            if (Q_clear <= (Q_lim - Q_uc)):
                P_clear = P_R
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


        def AC_Temp_control(self,Dtemp_current, A_etp, B_etp_on, B_etp_off, halfband, T_set, Dstatus_current, ddt):

            eAt = 0.994989265677227
            # eAt = expm(A_etp*ddt)
            factor = 0
            if (Dstatus_current == 1):
                Dtemp_next = eAt * Dtemp_current + 0.008312437794098 * B_etp_on  # A_etp\(eAt-eye(1)) = 0.0083 np.eye()
                Dstatus_next = Dstatus_current

                # find index of Ta compoments outside range

                if (Dtemp_next <= T_set - halfband):  # need to turn off, since temperature goes below the deadband
                    Dtemp_next = Dtemp_current
                    sub_ddt = 1 / 3600
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

                    sub_ddt = 1 / 3600
                    for t in np.arange(sub_ddt, ddt + sub_ddt, sub_ddt):
                        if Dstatus_next == 0:
                            Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_off) * sub_ddt
                            if (Dtemp_next >= T_set + halfband):
                                Dstatus_next = 1
                        else:
                            factor = factor + sub_ddt / ddt
                            Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_on) * sub_ddt

            return Dtemp_next, Dstatus_next, factor

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
