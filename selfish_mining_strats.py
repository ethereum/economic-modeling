import random
import sys

def test_strat(strat, hashpower, gamma, reward, fees, rounds=25000):
    me_reward = 0
    them_reward = 0
    me_blocks = 0
    them_blocks = 0
    time_elapsed = 0
    uncles_produced = 0
    uncle_rewards = 0
    for i in range(rounds):
        if random.random() < hashpower:
            me_blocks += 1
            last_is_me = 1
        else:
            them_blocks += 1
            last_is_me = 0
        time_elapsed += random.expovariate(1)
        # "Adopt" or "override"
        if me_blocks >= len(strat) or them_blocks >= len(strat[me_blocks]) or strat[me_blocks][them_blocks] == 1:
            if me_blocks > them_blocks or (me_blocks == them_blocks and random.random() < gamma):
                me_reward += me_blocks * reward + time_elapsed * fees
                if me_blocks < 7:
                    them_reward += them_blocks * (0.875 - 0.125 * me_blocks)
            else:
                them_reward += them_blocks * reward + time_elapsed * fees
                if them_blocks < 7:
                    me_reward += me_blocks * (0.875 - 0.125 * them_blocks)
            me_blocks = 0
            them_blocks = 0
            time_elapsed = 0
        # "Match"
        elif strat[me_blocks][them_blocks] == 2 and not last_is_me:
            if random.random() < gamma:
                me_reward += me_blocks * reward + time_elapsed * fees
                me_blocks = 0
                them_blocks = 0
                time_elapsed = 0
                if them_blocks < 7:
                    them_reward += them_blocks * (0.875 - 0.125 * me_blocks)
    return me_reward, them_reward

# A 20x20 array meaning "what to do if I made i blocks and the network
# made j blocks?". 1 = publish, 0 = do nothing.
def gen_selfish_mining_strat(optimistic=True):
    o = [([0] * 20) for i in range(20)]
    for me in range(20):
        for them in range(20):
            # Adopt
            if them == 1 and me == 0:
                o[me][them] = 1
            if them == me + 1:
                o[me][them] = 1
            # Overtake
            if me >= 2 and me == them + 1:
                o[me][them] = 1
            # Match
            if me >= 1 and me == them:
                o[me][them] = 2
    return o


dic = {"rewards": 1, "fees": 0, "gamma": 0.5, "optimistic": False}
for a in sys.argv[1:]:
    param, val = a[:a.index('=')], a[a.index('=')+1:]
    if param == 'optimistic':
        dic[param] = (val in ('true', 'True', '1'))
    else:
        dic[param] = float(val)
print dic
s = gen_selfish_mining_strat(dic["optimistic"])
for i in range(1, 50):
    x, y = test_strat(s, i * 0.01, dic["gamma"], dic["rewards"], dic["fees"], rounds=200000)
    print '%d%% hashpower, %f%% of rewards' % (i, x * 100.0 / (x + y))
