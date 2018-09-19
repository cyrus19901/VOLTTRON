import numpy as np
import pandas as pd
from scipy.linalg import expm
import scipy.io
import scipy.io as sio
from scipy.interpolate import interp1d
import pyexcel as pe
import math
from AC_flexibility_prediction import AC_flexibility_prediction
import AC_compute_temp
from scipy.interpolate import interp1d
from market_clear_ideal_accurate_1AC import market_clear_ideal_accurate_1AC
from AC_Temp_control import AC_Temp_control
from AC_Tset_control_ideal import AC_Tset_control_ideal
from AC_Status_update import AC_Status_update
import matplotlib.pyplot as plt
import sys
from numpy import loadtxt
import matplotlib.pyplot as plt

#############################
##Initialize simulation time step

tf = 24  # simulation time = 24hr;
ddt = 1.0 / 3600.0 * 30  # device simulation step = 0.5min;
Dtimestamps = (tf - ddt) / ddt + 1
Dtimes = int(Dtimestamps)
mdt = 1.0 / 3600.0 * 300.0  # market simulation step = 5min;
Mtimes = int(Dtimes / (mdt / ddt))
# HEMS interface inputs


#############################
##HEMS interface
uncontrolled = 0

para_AC_dn = {}
values = {'a', 'b', 'c', 'd', 'e', 'f'}
para_AC_dn['ratio'] = 5
para_AC_dn['Tdesired'] = 70
para_AC_dn['Tmin'] = 66
para_AC_dn['Tmax'] = 78
para_AC_dn['power'] = 4130
para_AC_dn['COP'] = 10
hr_start = 12  # DR start time
hr_stop = 18  # DR end time
Q_lim = 4000
P_cap = 1

Power = np.zeros((1, Dtimes))[0]

mat_contents = sio.loadmat('AC_data_real.mat')
T_out_extract = mat_contents['T_out'][0]
T_out =T_out_extract[2880 * 1:2880 * 2]
T_a = np.zeros((1, Dtimes))[0]

Q_s_extract = mat_contents['Q_s']
Q_s = Q_s_extract[:, 2880 * 1: 2880 * 2]

P_h_extract = mat_contents['P_R'][0]
P_h = P_h_extract[288 * 0:288 * 1]

Q_i =  mat_contents['Q_i'][0]
Q_h =  mat_contents['Q_h'][0]

T_a_extract = np.zeros((1, Dtimes))
T_a = T_a_extract[0]
Power_extract = np.zeros((1, Dtimes))
Power = Power_extract[0]
# Power is used as the AC power history
P_avg_extract = np.zeros((1, Mtimes))
P_avg = P_avg_extract[0]
P_sigma_extract = np.zeros((1, Mtimes))
P_sigma = P_sigma_extract[0]
# P_R simulates the actual base electricity prices
P_R_extract =  mat_contents['P_R'][0]
P_R = P_R_extract[288 * 1:288 * 2]

U_A = 716.4836
C_a = 1.1886e+03
P_cap = 1
# AC halfband value (F)
halfband_AC_dn = 2
# AC rated power (Watt)
para_AC_dn['power'] = 4130
# AC COP (This needs to be estimated offline)
para_AC_dn['COP'] = 10

# Measurement data samping rate
Delta = 1.0 / 3600.0 * 30.0  # 0.5 minute, which should be equal to ddt
#
# AC operating mode: 1=ON; 0=OFF;
Dstatus_AC_dn_extract = np.zeros((1, Dtimes))
Dstatus_AC_dn = Dstatus_AC_dn_extract[0]
# AC current temperature;
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

rep_load_5min = interp1d(range1, np.insert(rep_load_hourly, len(rep_load_hourly), rep_load_hourly[0]), axis=0,
                         fill_value="extrapolate")(range2)
unrep_load_5min = interp1d(range1, np.insert(unrep_load_hourly, len(unrep_load_hourly), unrep_load_hourly[0]), axis=0,
                           fill_value="extrapolate")(range2)
rep_load = scalar1 * scalar2 * np.array(rep_load_5min)
unrep_load = scalar1 * scalar3 * np.array(unrep_load_5min)
Q_uc_avg = rep_load + unrep_load
range3 = np.arange(0, tf, mdt)
range3 = np.insert(range3, len(range3), 24)
Dtimestamps = np.arange(0, tf - ddt, ddt)
Dtimestamps = np.insert(Dtimestamps, len(Dtimestamps), 23.9917)
Q_uc = interp1d(range3, np.insert(Q_uc_avg, len(Q_uc_avg), Q_uc_avg[0]), axis=0, fill_value="extrapolate")(Dtimestamps)

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



def AC_model_calibration(T_a, T_out, Power, COP, h, k):
    internal_value_file = scipy.io.loadmat('internal.mat')
    A = 1 - (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
    B = (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
    C = h / (internal_value_file['C_a'][0][0])
    Q_i_val = (internal_value_file['Q_i'][0][0])
    Q_s_val = internal_value_file['Q_s'][0][k]
    return A, B, C, Q_s_val, Q_i_val


for k in range(0,Dtimes-1):
    # print(k)
    A_ETP_AC_dn = ETP_a_AC_dn
    B_ETP_ON_AC_dn = ETP_b_on_AC_dn[k]
    B_ETP_OFF_AC_dn = ETP_b_off_AC_dn[k]
    val = 0
    if ((k % (mdt / ddt)) == 0):
        im = int((math.floor(k/ mdt * ddt-1)))
        P_avg[im] = 0.15
        P_sigma[im] = 0.05
        if ((k  >= (hr_start / ddt)) and (k <= (hr_stop / ddt))):
            im = im
            values = AC_model_calibration(T_a, T_out, Power, para_AC_dn['COP'], ddt, k)
            A = values[0]
            B = values[1]
            C = values[2]
            Q_s = values[3]
            Q_i = values[4]
            AC_flexibility = AC_flexibility_prediction(P_avg[im], P_sigma[im], P_cap, para_AC_dn, Dtemp_AC_dn[k],
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

            market_clear = market_clear_ideal_accurate_1AC(P_min[im],P_max[im],Q_max[im],Q_min[im],P_avg[im],P_cap,Q_uc_avg[im],Q_lim)

            P_clear[im] = market_clear[0]
            Q_clear[im] = market_clear[1]
            T_set_AC_dn[im] = AC_Tset_control_ideal(P_clear[im],P_avg[im],P_sigma[im],para_AC_dn)

        else:
            T_set_AC_dn[im] = para_AC_dn['Tdesired']

        P_h = np.insert(P_h[1:], len(P_h) - 1, P_clear[im])

        if uncontrolled:
            T_set_AC_dn[im] = para_AC_dn['Tdesired']


        Dstatus_AC_dn[k] = AC_Status_update(Dtemp_AC_dn[k],halfband_AC_dn,T_set_AC_dn[im],Dstatus_AC_dn[k])
        Q_actual_AC_dn[k] = para_AC_dn['power'] * Dstatus_AC_dn[k]
        Q_actual[k] = Q_actual_AC_dn[k]


    P_actual[k] = Q_actual[k] + Q_uc[k]
    AC_attributes = AC_Temp_control(Dtemp_AC_dn[k], A_ETP_AC_dn, B_ETP_ON_AC_dn, B_ETP_OFF_AC_dn, halfband_AC_dn,
                                    T_set_AC_dn[im], Dstatus_AC_dn[k], ddt)

    Dtemp_AC_dn[k+1] = AC_attributes[0]
    Dstatus_AC_dn[k+1] = AC_attributes[1]
    factor_AC_dn[k] = AC_attributes[2]
    Q_actual_AC_dn[k] = Q_actual_AC_dn[k] + para_AC_dn['power'] * factor_AC_dn[k]
    Q_actual[k] = Q_actual_AC_dn[k]
    P_actual[k] = Q_actual[k] + Q_uc[k]

    Q_actual_AC_dn[k + 1] = para_AC_dn['power'] * Dstatus_AC_dn[k + 1]
    Q_actual[k + 1] = Q_actual_AC_dn[k + 1]
    P_actual[k+1]= Q_actual[k+1] + Q_uc[k+1]

for y in range(0,Mtimes):
    Q_actual_AC_dn_avg[y] = np.average(Q_actual_AC_dn[ y*10 : (y*10)+10])
    Q_actual_avg[y] = np.average(Q_actual[y * 10 : (y*10)+10])
    P_actual_avg[y] = np.average(P_actual[y*10 : (y*10)+10])
    print(P_actual_avg[y])

avg_period = 0.25/mdt
Q_actual_AC_dn_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]
Q_actual_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]
P_actual_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]

for i in np.arange (1,int(Mtimes/avg_period)):
    Q_actual_AC_dn_quarter[i] = np.mean(Q_actual_AC_dn_avg[int((i-1)*avg_period+1):int(i*avg_period)])
    Q_actual_quarter[i] = np.mean(Q_actual_avg[int((i-1)*avg_period): int(i*avg_period)])
    P_actual_quarter[i] = np.mean(P_actual_avg[int((i-1)*avg_period) : int(i*avg_period)])

