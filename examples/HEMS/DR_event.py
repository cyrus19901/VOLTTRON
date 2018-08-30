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

para_AC_dn = {}
values = {'a', 'b', 'c', 'd', 'e', 'f'}
tf = 24  # simulation time = 24hr;
ddt = 1.0 / 3600.0 * 30  # device simulation step = 0.5min;
Dtimestamps = (tf - ddt) / ddt + 1
Dtimes = int(Dtimestamps)
mdt = 1.0 / 3600.0 * 300.0  # market simulation step = 5min;
Mtimes = int(Dtimes / (mdt / ddt))
# HEMS interface inputs
hr_start = 12  # DR start time
hr_stop = 18  # DR end time
uncontrolled = 0
# homeowner's preference of saving versus comfort for each appliance

# AC Simulation
para_AC_dn['Tmin'] = 66
para_AC_dn['Tmax'] = 78
para_AC_dn['Tdesired'] = 70
para_AC_dn['ratio'] = 5
Q_lim = 4000

T_out_extract = np.genfromtxt('T_out.csv', delimiter=",")
T_out = T_out_extract[2880 * 1:2880 * 2]

mat_contents = sio.loadmat('AC_data_real.mat')
Q_s_extract = mat_contents['Q_s']
Q_s = Q_s_extract[:, 2880 * 1: 2880 * 2]

P_h_extract = np.genfromtxt('P_R.csv', delimiter=",")
P_h = P_h_extract[288 * 0:288 * 1]

Q_i = np.genfromtxt('Q_i.csv', delimiter=",")
Q_h = np.genfromtxt('Q_h.csv', delimiter=",")

# T_out is used as the outdoor air temperature history and prediction
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
P_R_extract = np.genfromtxt('P_R.csv', delimiter=",")
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


# Initialize uncontrollable loads;
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
#
# need to work on this part

for i in range(1, 288):
    Q_uc_avg[i] = np.mean(Q_uc[(i - 1) * 10 :i * 10])
    # print(len(Q_uc_avg))
# Simulation initialization specific to MATLAB
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
#
#
#
#
# This is only for MATLAB dynamic simulation;

ih = 0;
Q_h[ih] = [(-para_AC_dn['COP']) * para_AC_dn['power']][0]

ETP_a_AC_dn = (-U_A) / C_a
Q_s_range = (0.5 * (Q_s[ih, :]))
ETP_b_on_AC_dn = ((U_A * T_out) + (0.5 * np.tile((Q_i[ih]), (1, Dtimes))[0]) + Q_s_range +
                  (np.tile((Q_h[ih]), (1, Dtimes)))[0]) / C_a
ETP_b_off_AC_dn = ((U_A * T_out) + (0.5 * np.tile((Q_i[ih]), (1, Dtimes))[0]) + Q_s_range) / C_a


def AC_model_calibration(T_a, T_out, Power, COP, h, k):
    internal_value_file = scipy.io.loadmat('internal.mat')
    A = 1 - (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
    B = (internal_value_file['U_A'][0][0]) / (internal_value_file['C_a'][0][0]) * h
    C = h / (internal_value_file['C_a'][0][0])
    Q_i_val = (internal_value_file['Q_i'][0][0])
    Q_s_val = internal_value_file['Q_s'][0][k]
    return A, B, C, Q_s_val, Q_i_val



for number in np.arange(1, 2880, 1):
    A_ETP_AC_dn = ETP_a_AC_dn;
    # print(ETP_b_on_AC_dn[number-1])
    B_ETP_ON_AC_dn = ETP_b_on_AC_dn[number-1]
    B_ETP_OFF_AC_dn = ETP_b_off_AC_dn[number-1]

    if (((number-1) % (mdt / ddt)) == 0):

        im = math.floor((number-1) / mdt * ddt)
        # print(im)
        P_avg[im] = 0.15
        P_sigma[im] = 0.05
        # print(number)
        if ((number  >= hr_start / ddt + 1) and (number  <= hr_stop / ddt)):
            values = AC_model_calibration(T_a, T_out, Power, para_AC_dn['COP'], ddt, number-1)
            # print(number)
            A = values[0]
            B = values[1]
            C = values[2]
            Q_s = values[3]
            Q_i = values[4]
            AC_flexibility = AC_flexibility_prediction(P_avg[im], P_sigma[im], P_cap, para_AC_dn, Dtemp_AC_dn[number-1],
                                                       halfband_AC_dn, Dstatus_AC_dn[number-1], mdt, A, B,
                                                       C, T_out[number-1], Q_i, Q_s, ddt)
            # print(im)
            # print(AC_flexibility)

            # print(number)
            # print(AC_flexibility)
            P_bid = AC_flexibility[0]
            P_min = AC_flexibility[1]
            P_max = AC_flexibility[2]
            Q_min = AC_flexibility[3]
            Q_max = AC_flexibility[4]

            # print(Q_min)

            # print(P_min,P_max,Q_max,Q_min,P_avg[im],P_cap,Q_uc_avg[im],Q_lim)
            market_clear = market_clear_ideal_accurate_1AC(P_min,P_max,Q_max,Q_min,P_avg[im],P_cap,Q_uc_avg[im],Q_lim)
            # print(market_clear)
            P_clear[im] = market_clear[0]
            Q_clear[im] = market_clear[1]
            T_set_AC_dn[im] = AC_Tset_control_ideal(P_clear[im],P_avg[im],P_sigma[im],para_AC_dn)
        else:
            T_set_AC_dn[im] = para_AC_dn['Tdesired']
        P_h = np.insert(P_h[1:],len(P_h)-1,P_clear[im])

        if uncontrolled:
            T_set_AC_dn[im] = para_AC_dn['Tdesired']
        Dstatus_AC_dn[number] = AC_Status_update(Dtemp_AC_dn[number],halfband_AC_dn,T_set_AC_dn[im],Dstatus_AC_dn[number])

        Q_actual_AC_dn[number] = para_AC_dn['power'] * Dstatus_AC_dn[number]
        Q_actual[number] = Q_actual_AC_dn[number]

    P_actual[number] = Q_actual[number] + Q_uc[number]
    AC_attributes = AC_Temp_control(Dtemp_AC_dn[number], A_ETP_AC_dn, B_ETP_ON_AC_dn, B_ETP_OFF_AC_dn, halfband_AC_dn,
                                    T_set_AC_dn[im], Dstatus_AC_dn[number], ddt)
    # print(AC_attributes)
    # print(number)
    if (number < 2879):
        Dtemp_AC_dn[number+1] = AC_attributes[0]
        Dstatus_AC_dn[number+1] = AC_attributes[1]
        factor_AC_dn[number] = AC_attributes[2]

        Q_actual_AC_dn[number] = Q_actual_AC_dn[number] + para_AC_dn['power'] * factor_AC_dn[number]
        Q_actual[number] = Q_actual_AC_dn[number]
        P_actual[number] = Q_actual[number] + Q_uc[number]

        Q_actual_AC_dn[number+1] = para_AC_dn['power'] * Dstatus_AC_dn[number+1]
        Q_actual[number+1]= Q_actual_AC_dn[number+1]
        P_actual[number+1]= Q_actual[number+1] + Q_uc[number+1]
        # print(number,Dstatus_AC_dn[number])

for i in np.arange(1,288):
    Q_actual_AC_dn_avg[i] = np.mean(Q_actual_AC_dn[(i-1)*10+1 : (i*10)])
    Q_actual_avg[i] = np.mean(Q_actual[(i-1)*10+1 : (i*10)])
    P_actual_avg[i] = np.mean(P_actual[(i-1)*10+1 : (i*10)])
    print(P_actual_avg[i])

avg_period = 0.25/mdt
Q_actual_AC_dn_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]
Q_actual_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]
P_actual_quarter = np.zeros((1,int(Mtimes/avg_period)))[0]


for i in np.arange (1,int(Mtimes/avg_period)):
    Q_actual_AC_dn_quarter[i] = np.mean(Q_actual_AC_dn_avg[int((i-1)*avg_period+1):int(i*avg_period)])
    Q_actual_quarter[i] = np.mean(Q_actual_avg[int((i-1)*avg_period): int(i*avg_period)])
    P_actual_quarter[i] = np.mean(P_actual_avg[int((i-1)*avg_period) : int(i*avg_period)])

