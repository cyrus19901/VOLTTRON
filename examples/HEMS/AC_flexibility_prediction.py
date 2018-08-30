# -*- coding: utf-8 -*-
"""
Created on Wed Aug 15 09:50:55 2018

@author: vlac284
"""
import random
from AC_compute_temp import AC_compute_temp
from AC_Temp2Price_ideal_accurate import AC_Temp2Price_ideal_accurate
def AC_flexibility_prediction(P_avg, P_sigma, P_cap, para, T_a, halfband, status, mdt, A, B, C, T_out, Q_i, Q_s, ddt):

    Q_h = -para["COP"]*para["power"]

    tmpON = AC_compute_temp(A, B, C, T_out, Q_i, Q_s, Q_h, T_a, mdt, ddt)
    tmpOFF = AC_compute_temp(A, B, C, T_out, Q_i, Q_s, 0, T_a, mdt, ddt)

    if status  == 0:
        if T_a <= para["Tmin"]+halfband and tmpOFF <= para["Tmin"]+halfband:
            Q_max = 0
            T_min = para["Tmin"]
            Q_min = 0
            T_max = para["Tmin"]
            
        if T_a < para["Tmin"]+halfband and tmpOFF > para["Tmin"]+halfband:
            # print("here2")
            tOFF = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,0,para["Tmin"]+halfband,mdt,ddt)
            Q_max = (mdt-tOFF)/mdt*para["power"]
            T_min = para["Tmin"]
            Q_min = 0
            T_max = tmpOFF-halfband
            
        if T_a == para["Tmin"]+halfband and tmpOFF > para["Tmin"]+halfband:
            if tmpON >= para["Tmin"]-halfband:
                Q_max = para["power"]
            else:
                tON = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,Q_h,T_a,para["Tmin"]-halfband,mdt,ddt)
                Q_max = tON/mdt*para['power']
            T_min = para["Tmin"]
            Q_min = 0
            T_max = tmpOFF-halfband
            
        if T_a > para["Tmin"]+halfband:
            if tmpON >= para["Tmin"]-halfband:
                Q_max = para["power"]
                T_min = min(T_a-halfband,tmpON+halfband)
            else:
                tON = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,Q_h,T_a,para["Tmin"]-halfband,mdt,ddt)
                Q_max = tON/mdt*para["power"]
                T_min = T_a-halfband

            if tmpOFF <= para["Tmax"]+halfband:
                Q_min = 0
                T_max = max(T_a-halfband,tmpOFF-halfband)
            else:
                tOFF = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,0,para["Tmax"]+halfband,mdt,ddt)
                Q_min = (mdt-tOFF)/mdt*para["power"]
                T_max = para["Tmax"]
                
    if status == 1:
        if T_a >= para["Tmax"]-halfband and tmpON >= para["Tmax"]-halfband:
            Q_max = para["power"]
            T_min = para["Tmax"]
            Q_min = para["power"]
            T_max = para["Tmax"]
            
        if T_a > para["Tmax"]-halfband and tmpON < para["Tmax"]-halfband:
            Q_max = para["power"]
            T_min = tmpON+halfband
            tON = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,Q_h,T_a,para["Tmax"]-halfband,mdt,ddt)
            Q_min = tON/mdt*para["power"]
            T_max = para["Tmax"]
        
        if T_a == para["Tmax"]-halfband and tmpON < para["Tmax"] - halfband:
            Q_max = para["power"]
            T_min = tmpON+halfband
            if (tmpOFF <= para["Tmax"]+halfband):
                Q_min = 0
            else:
                tOFF = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,0,para["Tmax"]+halfband,mdt,ddt)
                Q_min = (mdt-tOFF)/mdt*para["power"]
            T_max = para["Tmax"]
        
        if (T_a < para["Tmax"]-halfband):
            if (tmpOFF <= para["Tmax"]+halfband):
                Q_min = 0
                T_max = max(T_a+halfband,tmpOFF-halfband)
            else:
                tOFF = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,0,para["Tmax"]+halfband,mdt,ddt)
                Q_min = (mdt-tOFF)/mdt*para["power"]
                T_max = T_a+halfband
        
            if (tmpON >= para["Tmin"]-halfband):
                Q_max = para["power"]
                T_min = min(T_a+halfband,tmpON+halfband)
            else:
                tON = AC_compute_temp(A,B,C,T_out,Q_i,Q_s,T_a,(para["Tmin"]-halfband),mdt,ddt)
                Q_max = tON/mdt*para["power"]
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
        P_min = AC_Temp2Price_ideal_accurate(P_avg,P_sigma,P_cap,para,T_min)
        P_max = AC_Temp2Price_ideal_accurate(P_avg,P_sigma,P_cap,para,T_max)
        P_bid = (P_min+P_max)/2

    return P_bid,P_min,P_max,Q_min,Q_max
                
            
    