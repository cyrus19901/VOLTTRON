# -*- coding: utf-8 -*-
"""
Created on Wed Aug 15 12:32:21 2018

@author: vlac284
"""

def AC_Status_update(Dtemp_current,halfband,T_set,Dstatus_current):
    
    # ind_below = Dtemp_current <= (T_set-halfband)
    # ind_above = Dtemp_current >= (T_set+halfband)
    # ind_inside = Dtemp_current > T_set-halfband and Dtemp_current < T_set+halfband
    # print("++++++++++++here+++++++++++++++")
    # print(Dtemp_current)
    # print(T_set-halfband)
    # print(T_set + halfband)
    # print("++++++++++++here+++++++++++++++")
    if Dtemp_current <= (T_set-halfband):
        Dstatus_update = 0

    elif Dtemp_current >= (T_set+halfband):
        Dstatus_update = 1

    elif Dtemp_current > T_set-halfband and Dtemp_current < T_set+halfband:
        Dstatus_update = Dstatus_current
    return Dstatus_update