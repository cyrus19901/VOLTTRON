# -*- coding: utf-8 -*-
"""
Created on Wed Aug 15 13:07:42 2018

@author: vlac284
"""
from AC_Temp2Price_ideal_accurate import AC_Temp2Price_ideal_accurate

def AC_market_bid_ideal_accurate(P_avg,P_sigma,P_cap,para,T_a,halfband,status,mdt,A_ETP,B_ETP_ON,B_ETP_OFF):

    tmpON = compute_temp(A_ETP,B_ETP_ON,T_a,mdt)
    tmpOFF = compute_temp(A_ETP,B_ETP_OFF,T_a,mdt)
    
    if status == 0:
        if (T_a <= para.Tmin+halfband and tmpOFF <= para.Tmin+halfband):
            Q_max = 0
            T_min = para.Tmin
            Q_min = 0
            T_max = para.Tmin
       
        if (T_a < para.Tmin+halfband and tmpOFF > para.Tmin+halfband):
            [tOFF,fval,flag] = compute_time(A_ETP,B_ETP_OFF,T_a,para.Tmin+halfband)
            Q_max = (mdt-tOFF)/mdt*para.power
            T_min = para.Tmin
            Q_min = 0
            T_max = tmpOFF-halfband
            
        if (T_a == para.Tmin+halfband and tmpOFF > para.Tmin+halfband):
            if tmpON >= para.Tmin-halfband:
                Q_max = para.power
            else:
                [tON,fval,flag] = compute_time(A_ETP,B_ETP_ON,T_a,para.Tmin-halfband)
                Q_max = tON/mdt*power
        
            T_min = para.Tmin
            Q_min = 0
            T_max = tmpOFF-halfband
            
        if (T_a > para.Tmin+halfband):
            if tmpON >= para.Tmin-halfband:
                Q_max = para.power
                T_min = min(T_a-halfband,tmpON+halfband)
            else:
                [tON,fval,flag] = compute_time(A_ETP,B_ETP_ON,T_a,para.Tmin-halfband)
                Q_max = tON/mdt*para.power
                T_min = T_a-halfband
            
            if (tmpOFF <= para.Tmax+halfband):
                Q_min = 0
                T_max = max(T_a-halfband,tmpOFF-halfband)
            else:
                [tOFF,fval,flag] = compute_time(A_ETP,B_ETP_OFF,T_a,para.Tmax+halfband)
                Q_min = (mdt-tOFF)/mdt*para.power
                T_max = para.Tmax


    if status == 1:
        if (T_a >= para.Tmax-halfband and tmpON >= para.Tmax-halfband):
            Q_max = para.power
            T_min = para.Tmax
            Q_min = para.power
            T_max = para.Tmax
    
        if (T_a > para.Tmax-halfband and tmpON < para.Tmax-halfband):
            Q_max = para.power
            T_min = tmpON+halfband
            [tON,fval,flag] = compute_time(A_ETP,B_ETP_ON,T_a,para.Tmax-halfband)
            Q_min = tON/mdt*para.power
            T_max = para.Tmax
    
        if (T_a == para.Tmax-halfband and tmpON < para.Tmax-halfband):
            Q_max = para.power
            T_min = tmpON+halfband
            if tmpOFF <= para.Tmax+halfband:
                Q_min = 0
            else:
                [tOFF,fval,flag] = compute_time(A_ETP,B_ETP_OFF,T_a,para.Tmax+halfband)
                Q_min = (mdt-tOFF)/mdt*para.power
        
            T_max = para.Tmax
        
        if (T_a < para.Tmax-halfband):
            if tmpOFF <= para.Tmax+halfband:
                Q_min = 0
                T_max = max(T_a+halfband,tmpOFF-halfband)
            else:
                [tOFF,fval,flag] = compute_time(A_ETP,B_ETP_OFF,T_a,para.Tmax+halfband)
                Q_min = (mdt-tOFF)/mdt*para.power
                T_max = T_a+halfband
            
            if (tmpON >= para.Tmin-halfband):
                Q_max = para.power
                T_min = min(T_a+halfband,tmpON+halfband)
            else:
                [tON,fval,flag] = compute_time(A_ETP,B_ETP_ON,T_a,para.Tmin-halfband)
                Q_max = tON/mdt*para.power
                T_min = para.Tmin
            
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
