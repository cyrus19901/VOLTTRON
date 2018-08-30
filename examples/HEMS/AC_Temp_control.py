# -*- coding: utf-8 -*-
"""
Created on Wed Aug 15 11:49:14 2018

@author: vlac284
"""


import numpy as np

def AC_Temp_control(Dtemp_current,A_etp,B_etp_on,B_etp_off,halfband,T_set,Dstatus_current,ddt):

    eAt = 0.9950
    factor = 0
    # print(Dtemp_current)
    if (Dstatus_current == 1):
        Dtemp_next =  eAt * Dtemp_current + 0.0083 * B_etp_on  #A_etp\(eAt-eye(1)) = 0.0083
        Dstatus_next = Dstatus_current

        #find index of Ta compoments outside range

        if (Dtemp_next <= T_set-halfband): # need to turn off, since temperature goes below the deadband
            Dtemp_next = Dtemp_current
            sub_ddt = 1/3600
            for t in np.arange(sub_ddt,ddt+sub_ddt,sub_ddt):
                if Dstatus_next == 1:
                    factor = factor+sub_ddt/ddt
                    Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_on) * sub_ddt
                    if (Dtemp_next <= T_set-halfband):
                        Dstatus_next = 0
                else:
                    Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_off) * sub_ddt
            factor = factor-1

    else:

        Dtemp_next = eAt * Dtemp_current + 0.0083 * B_etp_off
        Dstatus_next = Dstatus_current

        #find index of Ta compoments outside range

        if (Dtemp_next >= T_set+halfband):
            # need to turn on, since temperature goes beyond the deadband
            Dtemp_next= Dtemp_current

            sub_ddt = 1/3600
            for t in np.arange(sub_ddt,ddt+sub_ddt,sub_ddt):
                if Dstatus_next == 0:
                    Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_off) * sub_ddt
                    if (Dtemp_next >= T_set+halfband):
                        Dstatus_next = 1
                else:
                    factor = factor+sub_ddt/ddt
                    Dtemp_next = Dtemp_next + (A_etp * Dtemp_next + B_etp_on) * sub_ddt

    return Dtemp_next, Dstatus_next,factor