import math

MAX_INTEREST_RATE = 4 * 10**-9 # 4 ppb/s, or 13.4% APR
MIN_DEPOSIT_SIZE = 1500
BLKTIME = 3
WITHDRAWAL_PERIOD = 10**7
TOTAL_DEPOSIT = 10**7

MAX_BET_LENGTH = int(math.log(WITHDRAWAL_PERIOD / BLKTIME) / math.log(4))
MAX_RETURN = MAX_INTEREST_RATE * TOTAL_DEPOSIT * BLKTIME
BET_MAXGAIN = MAX_RETURN / MAX_BET_LENGTH
BET_MAXLOSS = MIN_DEPOSIT_SIZE

# Best way I could find to compute the fixed point
MAXODDS = BET_MAXLOSS / (BET_MAXGAIN / 4)
MAXODDS = BET_MAXLOSS / (BET_MAXGAIN/4 + BET_MAXGAIN / (2*math.log(MAXODDS)))
MAXODDS = BET_MAXLOSS / (BET_MAXGAIN/4 + BET_MAXGAIN / (2*math.log(MAXODDS)))

B = BET_MAXGAIN / (2 * MAXODDS)
A = MAXODDS / math.log(MAXODDS) * B
# The above equations determine parameters fitted such that all three
# of the following are true:
#
# 1. 50% of the winnings come from a logarithmic component, 50% from a linear
#    component
# 2. The max winnings are set as above
# 3. The max losses are set as above

print A, B, MAXODDS, MAX_BET_LENGTH

def score_correct(logodds):
    odds = MAXODDS**(logodds / 255.)
    return math.log(odds) * A + odds * B

def score_incorrect(logodds):
    odds = MAXODDS**(logodds / 255.)
    return -odds * A - odds**2/2 * B
    
print score_correct(255)
print score_incorrect(255)
