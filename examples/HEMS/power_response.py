# -*- coding: utf-8 -*-
"""
Created on Wed Aug 15 13:05:10 2018

@author: vlac284
"""
#0.1809,0.2252,4130,0
def power_response(P_min,P_max,Q_max,Q_min,P):

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