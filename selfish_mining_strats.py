import random
import sys

def test_strat(strat, hashpower, gamma, reward, fees):
    me_reward = 0
    them_reward = 0
    me_blocks = 0
    them_blocks = 0
    time_elapsed = 0
    for i in range(25000):
        if random.random() < hashpower:
            me_blocks += 1
        else:
            them_blocks += 1
        time_elapsed += random.expovariate(1)
        if me_blocks >= len(strat) or them_blocks >= len(strat[me_blocks]) or strat[me_blocks][them_blocks] == 1:
            if me_blocks > them_blocks or (me_blocks == them_blocks and random.random() < gamma):
                me_reward += me_blocks * reward + time_elapsed * fees
            else:
                them_reward += them_blocks * reward + time_elapsed * fees
            me_blocks = 0
            them_blocks = 0
            time_elapsed = 0
    return me_reward, them_reward

def gen_selfish_mining_strat():
    o = [([0] * 20) for i in range(20)]
    for me in range(20):
        for them in range(20):
            if them == me + 1:
                o[me][them] = 1
            if me >= 2 and me == them + 1:
                o[me][them] = 1
            # if me >= 2 and me == them:
            #     o[me][them] = 1
    return o

s = gen_selfish_mining_strat()

if len(sys.argv) < 3:
    print "Run \"python sm_strats.py x y\" where x is the level of block rewards and y is the level of fees"
    sys.exit()

for i in range(1, 50):
    x, y = test_strat(s, i * 0.01, 0, int(sys.argv[1]), int(sys.argv[2]))
    print '%d%% hashpower, %f%% of rewards' % (i, x * 100.0 / (x + y))
