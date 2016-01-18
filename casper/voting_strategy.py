import random
import math

# The voting strategy. Validators see what every other validator votes,
# and return their vote.
#
# Remember, 0 and 1 are not probabilities!
# http://lesswrong.com/lw/mp/0_and_1_are_not_probabilities/ !)

def default_vote(scheduled_time, received_time, now, **kwargs):
    if received_time is None:
        time_delta = now - scheduled_time
        my_opinion_prob = 1 if time_delta < kwargs["blktime"] * 4 else 4.0 / (4 + time_delta * 1.0 / kwargs["blktime"])
        return 0.5 if random.random() < my_opinion_prob else 0.3
    else:
        time_delta = received_time * 0.98 + now * 0.02 - scheduled_time
        my_opinion_prob = 1 if abs(time_delta) < kwargs["blktime"] * 4 else 4.0 / (4 + abs(time_delta) * 1.0 / kwargs["blktime"])
        return 0.7 if random.random() < my_opinion_prob else 0.3
    

def vote(probs):
    if len(probs) == 0:
        return 0.5
    probs = sorted(probs)
    if probs[len(probs)/3] >= 0.7:
        return 0.84 + probs[len(probs)/3] * 0.16
    elif probs[len(probs)*2/3] <= 0.3:
        return probs[len(probs)*2/3] * 0.16
    else:
        return max(0.2, min(0.8, probs[len(probs)/2] * 3 - 0.8 - random.random() * 0.4))

FINALITY_THRESHOLD = 0.000001

def aggressive_vote(probs):
    if len(probs) == 0:
        return 0.5
    probs = sorted(probs)
    if probs[len(probs)/3] >= 0.9:
        return 1 - FINALITY_THRESHOLD
    elif probs[len(probs)*2/3] <= 0.1:
        return FINALITY_THRESHOLD
    if probs[len(probs)/3] >= 0.7:
        return 0.92
    elif probs[len(probs)*2/3] <= 0.3:
        return 0.08
    else:
        return max(0.2, min(0.8, probs[len(probs)/2] * 3 - 0.8 - random.random() * 0.4))

def craycray_vote(probs):
    if len(probs) == 0:
        return 0.5
    probs = sorted(probs)
    if probs[len(probs)/3] >= 1 - FINALITY_THRESHOLD:
        return 1 - FINALITY_THRESHOLD
    elif probs[len(probs)*2/3] <= FINALITY_THRESHOLD:
        return FINALITY_THRESHOLD
    elif random.choice((0, 1)):
        o = FINALITY_THRESHOLD * 2 + (1 - FINALITY_THRESHOLD * 4) * 0.5 ** random.randrange(0, int(math.log(1 / FINALITY_THRESHOLD) / math.log(2)))
        return o
    else:
        o = 1 - FINALITY_THRESHOLD * 2 - (1 - FINALITY_THRESHOLD * 4) * 0.5 ** random.randrange(0, int(math.log(1 / FINALITY_THRESHOLD) / math.log(2)))
        return o
