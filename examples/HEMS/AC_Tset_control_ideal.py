# -*- coding: utf-8 -*-
"""
Created on Wed Aug 15 12:45:55 2018

@author: vlac284
"""

def AC_Tset_control_ideal(P_clear,P_avg,P_sigma,para):

    T_set = 0
    
    if (P_clear <= P_avg):
        T_set = para['Tdesired']+(P_clear-P_avg)/(para['ratio']*P_sigma)*(para['Tdesired']-para['Tmin'])
    
    if (T_set < para['Tmin']):
        T_set = para['Tmin']

    if (P_clear > P_avg):
        T_set = para['Tdesired']+(P_clear-P_avg)/(para['ratio']*P_sigma)*(para['Tmax']-para['Tdesired'])
    
    if (T_set > para['Tmax']):
        T_set = para['Tmax']
    
    return T_set