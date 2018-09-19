import numpy as np
from power_response import power_response


def market_clear_ideal_accurate_1AC(P_min, P_max, Q_max, Q_min, P_R, P_cap, Q_uc, Q_lim):
    Q_clear_AC_dn = power_response(P_min, P_max, Q_max, Q_min, P_R)
    Q_clear = Q_clear_AC_dn
    # print(Q_clear)
    range = 0
    if (Q_clear <= (Q_lim - Q_uc)):
        P_clear = P_R
    else:
        P = np.arange(P_cap, 0, -0.001)
        Q_clear = np.zeros((1, len(P)))[0]
        Q_error = np.zeros((1, len(P)))[0]
        for i in np.arange(0, len(P)):
            Q_clear_AC_dn = power_response(P_min, P_max, Q_max, Q_min, P[i])
            Q_clear[i] = Q_clear_AC_dn
            Q_error[i] = Q_clear[i] - (Q_lim - Q_uc)
            if (Q_error[i] >= 0):
                range = i
                break
        if (Q_error[range] == 0):

            P_clear = P[range]
            Q_clear = Q_clear[range]
        else:
            if range == 1:
                P_clear = P[range]
                Q_clear = Q_clear[range]
            else:
                P_clear = P[range - 1]
                Q_clear = Q_clear[range - 1]

    return P_clear, Q_clear