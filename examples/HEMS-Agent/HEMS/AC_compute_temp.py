import numpy as np

def AC_compute_temp(A,B,C,T_out,Q_i,Q_s,Q_h,T_a,mdt,ddt):

    temp = T_a;
    for i in np.arange(0,int(mdt/ddt)):
        temp = A*temp + B*T_out + C*Q_h + C*(0.5*Q_i+0.5*Q_s)
    return temp
