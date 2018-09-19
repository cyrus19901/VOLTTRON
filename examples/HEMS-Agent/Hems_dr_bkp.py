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
from scipy.interpolate import interp1d
from volttron.platform.vip.agent import Core, Agent
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from market_clear_ideal_accurate_1AC import market_clear_ideal_accurate_1AC
from AC_Temp_control import AC_Temp_control
from AC_Tset_control_ideal import AC_Tset_control_ideal
from AC_Status_update import AC_Status_update

from __builtin__ import list



utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'


def hemsdr(config_path, **kwargs):

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
            self.tf = config.get('tf', None)
            self.ddt = config.get('ddt', None)
            self.Dtimestamps = (self.tf - self.ddt) / self.ddt + 1
            self.Dtimes = int(self.Dtimestamps)
            self.mdt = config.get('mdt', None)
            self.Mtimes = int(self.Dtimes / (self.mdt / self.ddt))
            uncontrolled = config.get('uncontrolled', None)
            self.para_AC_dn = {}
            values = {'a', 'b', 'c', 'd', 'e', 'f'}
            self.para_AC_dn['ratio'] = config.get('para-ratio', None)
            self.para_AC_dn['Tdesired'] = config.get('para-Tdesired', None)
            self.para_AC_dn['Tmin'] = config.get('para-Tmin', None)
            self.para_AC_dn['Tmax'] = config.get('para-Tmax', None)
            self.para_AC_dn['power'] = config.get('para-power', None)
            self.para_AC_dn['COP'] = config.get('para-COP', None)
            self.hr_start = config.get('hr_start', None)
            self.hr_stop = config.get('hr_stop', None)
            self.Q_lim = config.get('Q_lim', None)
            self.P_cap = config.get('P_cap', None)
            self.U_A = config.get('U_A', None)
            self.C_a = config.get('C_a', None)
            self.Power = np.zeros((1, self.Dtimes))[0]
            mat_contents = sio.loadmat('AC_data_real.mat')
            self.T_out_extract = mat_contents['T_out'][0]
            self.T_out = self.T_out_extract[2880 * 1:2880 * 2]
            self.T_a = np.zeros((1, self.Dtimes))[0]
            self.Q_s_extract = mat_contents['Q_s']
            self.Q_s = self.Q_s_extract[:, 2880 * 1: 2880 * 2]
            self.P_h_extract = mat_contents['P_R'][0]
            self.P_h = self.mat_contents['Q_i'][0]
            self.Q_h = mat_contents['Q_h'][0]
            self.T_a_extract = np.zeros((1, self.Dtimes))
            self.T_a = self.T_a_extract[0]
            Power_extract = np.zeros((1, self.Dtimes))
            self.Power = Power_extract[0]
            P_avg_extract = np.zeros((1, self.Mtimes))
            self.P_avg = P_avg_extract[0]
            P_sigma_extract = np.zeros((1,self.Mtimes))
            self.P_sigma = P_sigma_extract[0]
            P_R_extract = mat_contents['P_R'][0]
            self.P_R = P_R_extract[288 * 1:288 * 2]
            self.halfband_AC_dn = config.get('halfband_AC_dn', None)
            self.Delta = config.get('delta', None)
            Dstatus_AC_dn_extract = np.zeros((1, self.Dtimes))
            self.Dstatus_AC_dn = Dstatus_AC_dn_extract[0]
            Dtemp_AC_dn_extract = np.zeros((1, self.Dtimes))
            self.Dtemp_AC_dn = Dtemp_AC_dn_extract[0]

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
            range2 = np.arange(0, self.tf - self.mdt, self.mdt)
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
            range3 = np.arange(0, self.tf, self.mdt)
            range3 = np.insert(range3, len(range3), 24)
            Dtimestamps = np.arange(0, self.tf - self.ddt, self.ddt)
            Dtimestamps = np.insert(Dtimestamps, len(Dtimestamps), 23.9917)
            Q_uc = interp1d(range3, np.insert(Q_uc_avg, len(Q_uc_avg), Q_uc_avg[0]), axis=0, fill_value="extrapolate")(
                Dtimestamps)

            for i in range(0, self.Mtimes):
                Q_uc_avg[i] = np.average(Q_uc[i * 10:(i * 10) + 10])

            ## Initialize

            self.P_clear = np.zeros((1, self.Mtimes))[0]
            self.Q_clear = np.zeros((1, self.Mtimes))[0]

            self.Q_actual = np.zeros((1, self.Dtimes))[0]
            self.Q_actual_avg = np.zeros((1, self.Mtimes))[0]
            self.P_actual = np.zeros((1, self.Dtimes))[0]
            self.P_actual_avg = np.zeros((1, self.Mtimes))[0]

            self.factor_AC_dn = np.zeros((1, self.Dtimes))[0]
            self.Q_actual_AC_dn = np.zeros((1, self.Dtimes))[0]
            self.Q_actual_AC_dn_avg = np.zeros((1, self.Mtimes))[0]

            self.P_bid_AC_dn = np.zeros((1, self.Mtimes))[0]
            self.P_min_AC_dn = np.zeros((1, self.Mtimes))[0]
            self.P_max_AC_dn = np.zeros((1, self.Mtimes))[0]
            self.Q_min_AC_dn = np.zeros((1, self.Mtimes))[0]
            self.Q_max_AC_dn = np.zeros((1, self.Mtimes))[0]
            self.Q_clear_AC_dn = np.zeros((1, self.Mtimes))[0]

            self.T_set_AC_dn = np.zeros((1, self.Mtimes))[0]

            self.P_max = np.zeros((1, self.Mtimes))[0]
            self.P_min = np.zeros((1, self.Mtimes))[0]
            self.Q_min = np.zeros((1, self.Mtimes))[0]
            self.Q_max = np.zeros((1, self.Mtimes))[0]
            ###############################################
            ## Matlab dynamic simulation

            ih = 0
            Q_h[ih] = [(-self.para_AC_dn['COP']) * self.para_AC_dn['power']][0]

            self.ETP_a_AC_dn = (-self.U_A) / self.C_a
            Q_s_range = (0.5 * (self.Q_s[ih, :]))
            self.ETP_b_on_AC_dn = (self.U_A * self.T_out + np.tile(0.5 * self.Q_i[ih], (1, self.Dtimes))[0] + Q_s_range +
                              np.tile(self.Q_h[ih], (1, self.Dtimes))[0]) / self.C_a
            self.ETP_b_off_AC_dn = (self.U_A * self.T_out + np.tile(0.5 * self.Q_i[ih], (1, self.Dtimes))[0] + Q_s_range) / self.C_a

        @Core.receiver("onstart")
        def DRStart(self, sender, **kwargs):
            '''
            Subscribes to the platform message bus on the actuator, record,
            datalogger, and device topics to capture data.
            '''

            for k in range(0, self.Dtimes - 1):
                # print(k)
                A_ETP_AC_dn = self.ETP_a_AC_dn
                B_ETP_ON_AC_dn = self.ETP_b_on_AC_dn[k]
                B_ETP_OFF_AC_dn = self.ETP_b_off_AC_dn[k]
                val = 0
                if ((k % (self.mdt / self.ddt)) == 0):
                    im = int((math.floor(k / self.mdt * self.ddt - 1)))
                    self.P_avg[im] = 0.15
                    self.P_sigma[im] = 0.05
                    if ((k >= (self.hr_start / self.ddt)) and (k <= (self.hr_stop / self.ddt))):
                        im = im
                        values = self.AC_model_calibration(self.T_a, self.T_out, self.Power, self.para_AC_dn['COP'], self.ddt, k)
                        A = values[0]
                        B = values[1]
                        C = values[2]
                        Q_s = values[3]
                        Q_i = values[4]
                        AC_flexibility = self.AC_flexibility_prediction(self.P_avg[im], self.P_sigma[im], self.P_cap, self.para_AC_dn,
                                                                        self.Dtemp_AC_dn[k],
                                                                        self.halfband_AC_dn, self.Dstatus_AC_dn[k], self.mdt, A, B,
                                                                   C, self.T_out[k], self.Q_i, Q_s, self.ddt)
                        self.P_bid_AC_dn[im] = AC_flexibility[0]
                        self.P_min_AC_dn[im] = AC_flexibility[1]
                        self.P_max_AC_dn[im] = AC_flexibility[2]
                        self.Q_min_AC_dn[im] = AC_flexibility[3]
                        self.Q_max_AC_dn[im] = AC_flexibility[4]

                        self.P_min[im] = self.P_min_AC_dn[im]
                        self.P_max[im] = self.P_max_AC_dn[im]
                        self.Q_min[im] = self.Q_min_AC_dn[im]
                        self.Q_max[im] = self.Q_max_AC_dn[im]

                        market_clear = market_clear_ideal_accurate_1AC(self.P_min[im], self.P_max[im], self.Q_max[im], self.Q_min[im],
                                                                       self.P_avg[im], self.P_cap, self.Q_uc_avg[im], self.Q_lim)

                        self.P_clear[im] = market_clear[0]
                        self.Q_clear[im] = market_clear[1]
                        self.T_set_AC_dn[im] = AC_Tset_control_ideal(self.P_clear[im], self.P_avg[im], self.P_sigma[im], self.para_AC_dn)

                    else:
                        self.T_set_AC_dn[im] = self.para_AC_dn['Tdesired']

                    P_h = np.insert(P_h[1:], len(P_h) - 1, self.P_clear[im])

                    if self.uncontrolled:
                        self.T_set_AC_dn[im] = self.para_AC_dn['Tdesired']

                    self.Dstatus_AC_dn[k] = AC_Status_update(self.Dtemp_AC_dn[k], self.halfband_AC_dn, self.T_set_AC_dn[im],
                                                             self.Dstatus_AC_dn[k])
                    self.Q_actual_AC_dn[k] = self.para_AC_dn['power'] * self.Dstatus_AC_dn[k]
                    self.Q_actual[k] = self.Q_actual_AC_dn[k]

                self.P_actual[k] = self.Q_actual[k] + self.Q_uc[k]
                AC_attributes = AC_Temp_control(self.Dtemp_AC_dn[k], A_ETP_AC_dn, B_ETP_ON_AC_dn, B_ETP_OFF_AC_dn,
                                                self.halfband_AC_dn,
                                                self.T_set_AC_dn[im], self.Dstatus_AC_dn[k], self.ddt)

                self.Dtemp_AC_dn[k + 1] = AC_attributes[0]
                self.Dstatus_AC_dn[k + 1] = AC_attributes[1]
                self.factor_AC_dn[k] = AC_attributes[2]
                self.Q_actual_AC_dn[k] = self.Q_actual_AC_dn[k] + self.para_AC_dn['power'] * self.factor_AC_dn[k]
                self.Q_actual[k] = self.Q_actual_AC_dn[k]
                self.P_actual[k] = self.Q_actual[k] + self.Q_uc[k]

                self.Q_actual_AC_dn[k + 1] = self.para_AC_dn['power'] * self.Dstatus_AC_dn[k + 1]
                self.Q_actual[k + 1] = self.Q_actual_AC_dn[k + 1]
                self.P_actual[k + 1] = self.Q_actual[k + 1] + self.Q_uc[k + 1]


        def AC_model_calibration(T_a, T_out, Power, COP, h, k):
            internal_value_file = scipy.io.loadmat('internal.mat')
            A = 1 - (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
            B = (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
            C = h / (internal_value_file['C_a'][0][0])
            Q_i_val = (internal_value_file['Q_i'][0][0])
            Q_s_val = internal_value_file['Q_s'][0][k]
            return A, B, C, Q_s_val, Q_i_val


    HemsDR.__name__ = 'HemsDR'
    return HemsDR(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(hemsdr, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
