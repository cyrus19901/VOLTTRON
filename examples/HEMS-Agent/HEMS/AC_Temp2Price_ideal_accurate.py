# -*- coding: utf-8 -*-
"""
Created on Wed Aug 15 12:42:12 2018

@author: vlac284
"""

def AC_Temp2Price_ideal_accurate(P_avg,P_sigma,P_cap,para,Temp):

	if Temp <= para["Tdesired"]:

		Price = P_avg+(Temp-para["Tdesired"])*para["ratio"] * P_sigma/(para["Tdesired"]-para["Tmin"])

	if Temp >= para["Tdesired"]:

		Price = P_avg+(Temp-para["Tdesired"])*para["ratio"] * P_sigma/(para["Tmax"]-para["Tdesired"])

	if Price < max(P_avg - para["ratio"]*P_sigma,0):
		Price = 0
	if Price > min(P_cap,P_avg + para["ratio"]*P_sigma):
		Price = P_cap

	return Price

