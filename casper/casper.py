import copy, random, hashlib
from distributions import normal_distribution
import networksim
import voting_strategy
import math

# Number of validators
NUM_VALIDATORS = 20
# Block time
BLKTIME = 40
# 0 for no netsplits
# 1 for simulating a netsplit where 20% of validators jump off
# the network
# 2 for simulating the above netsplit, plus a 50-50 netsplit,
# plus reconvergence
NETSPLITS = 0
# Network latency
NETWORK_LATENCY = 100
# Check the equality of finalized states
CHECK_INTEGRITY = True
# The genesis state root
GENESIS_STATE = 0
# Broadcast success rate
BROADCAST_SUCCESS_RATE = 0.9
# Clock disparity
CLOCK_DISPARITY = 100
# Finality threshold
FINALITY_THRESHOLD = 0.000001

logging_level = 0


def log(s, lvl):
    if logging_level >= lvl:
        print(s)


# A signture specifies an initial height ("sign_from"), a finalized
# state from all blocks before that height and a list of probability
# bets from that height up to the latest height
class Signature():
    def __init__(self, signer, probs, state_roots, max_height, prev):
        # The ID of the signer
        self.signer = signer
        # List of probability bets, expressed in log odds
        self.probs = probs
        # Hash of the signature (for db storage purposes)
        self.hash = random.randrange(10**14)
        # State root changes
        self.state_roots = state_roots
        # Max height
        self.max_height = max_height
        # Previous signature
        self.prev = prev.hash if prev else None
        # Sequence number
        self.seq = prev.seq + 1 if prev else 0

    @property
    def sign_from(self):
        return self.max_height - len(self.probs)


# Right now, a block simply specifies a proposer and a height.
class Block():
    def __init__(self, maker, height):
        # The producer of the block
        self.maker = maker
        # The height of the block
        self.height = height
        # Hash of the signature (for db storage purposes)
        self.hash = random.randrange(10**20) + 10**21 + 10**23 * self.height


# A request to receive a block at a particular height
class BlockRequest():
    def __init__(self, sender, height):
        self.sender = sender
        self.ask_height = height
        self.hash = random.randrange(10**14)

# A request to receive the signature subsequent to a particular signature
class SignatureChildRequest():
    def __init__(self, sender, sighash, signer, ht=0):
        self.sender = sender
        self.sighash = sighash
        self.signer = signer
        self.ht = ht
        self.hash = random.randrange(10**14)


# Toy state transition function (in production, do sequential
# apply_transaction here)
def state_transition(state, block):
    return state if block is None else (state ** 3 + block.hash ** 5) % 10**40


# A validator
class Validator():
    def __init__(self, pos, network, default_vote=voting_strategy.default_vote, vote=voting_strategy.vote):
        # Map from height to {node_id: latest_bet}
        self.received_signatures = []
        # List of received blocks
        self.received_blocks = []
        # Own probability estimates
        self.probs = []
        # All objects that this validator has received; basically a database
        self.received_objects = {}
        # Time when the object was received
        self.time_received = {}
        # The validator's ID, and its position in the queue
        self.pos = self.id = pos
        # The offset of this validator's clock vs. real time
        self.time_offset = normal_distribution(0, CLOCK_DISPARITY)()
        # The highest height that this validator has seen
        self.max_height = 0
        # The validator's hash chain
        self.finalized_hashes = []
        # Finalized states
        self.states = []
        # The highest height that the validator has finalized
        self.max_finalized_height = -1
        # The network object
        self.network = network
        # Last time signed
        self.last_time_signed = 0
        # Next height to mine
        self.next_height = self.pos
        # Own most recent signature
        self.most_recent_sig = None
        # Most recent signatures of other validators
        self.most_recent_sigs = {}
        # Voting methods
        self.vote = vote
        self.default_vote = default_vote

    # Get the local time from the point of view of this validator, using the
    # validator's offset from real time
    def get_time(self):
        return self.network.time + self.time_offset

    # Broadcast an object to the network
    def broadcast(self, obj):
        self.network.broadcast(self, obj)

    # Create a signature
    def sign(self):
        # Initialize the probability array, the core of the signature
        best_guesses = [None] * len(self.received_blocks)
        sign_from = max(0, self.max_finalized_height - 3)
        while not self.received_blocks[sign_from] and sign_from:
            sign_from -= 1
        for i, b in list(enumerate(self.received_blocks))[sign_from:]:
            # print i, b
            # Compute this validator's own initial vote based on when the block
            # was received, compared to what time the block should have arrived
            received_time = self.time_received[b.hash] if b is not None else None
            # if received_time:
            #     print 'delta', received_time - BLKTIME * i
            my_opinion = self.default_vote(BLKTIME * i, received_time, self.get_time(), blktime=BLKTIME)
            # Get others' bets on this height
            votes = self.received_signatures[i].values() if i < len(self.received_signatures) else []
            votes = [x for x in votes if x != 0]
            # Fill in the not-yet-received votes with this validator's default bet
            votes += [my_opinion] * (NUM_VALIDATORS - len(votes))
            vote_from_signatures = self.vote(votes)
            # If you have not received a block, reserve judgement
            bg = min(vote_from_signatures, 1 if self.received_blocks[i] is not None else my_opinion)
            # Add the bet to the list
            best_guesses[i] = bg
            # Request a block if we should have it, and should have had it for
            # a long time, but don't
            if vote_from_signatures > 0.9 and self.received_blocks[i] is None:
                self.broadcast(BlockRequest(self.id, i))
            elif i < len(self.received_blocks) - 50 and self.received_blocks[i] is None:
                if random.random() < 0.05:
                    self.broadcast(BlockRequest(self.id, i))
            # Block finalized
            if best_guesses[i] >= 1 - FINALITY_THRESHOLD:
                while len(self.finalized_hashes) <= i:
                    self.finalized_hashes.append(None)
                self.finalized_hashes[i] = self.received_blocks[i].hash
            # Absense of the block finalized
            elif best_guesses[i] <= FINALITY_THRESHOLD:
                while len(self.finalized_hashes) <= i:
                    self.finalized_hashes.append(None)
                self.finalized_hashes[i] = False
        # Add to the list of finalized states
        while self.max_finalized_height < len(self.finalized_hashes) - 1 \
                and self.finalized_hashes[self.max_finalized_height + 1] is not None:
            self.max_finalized_height += 1
            last_state = self.states[self.max_finalized_height - 1] if self.max_finalized_height else GENESIS_STATE
            assert len(self.states) == len(self.received_blocks), (len(self.states), len(self.received_blocks))
            self.states[self.max_finalized_height] = state_transition(last_state, self.received_blocks[self.max_finalized_height])
        self.probs = self.probs[:sign_from] + best_guesses[sign_from:]
        new_states = [self.states[self.max_finalized_height] if self.max_finalized_height >= 0 else GENESIS_STATE]
        diff_index = 0
        for i in range(-1, -min(len(new_states), len(self.states))-1, -1):
            if new_states[i] != self.states[i]:
                self.states[i] = new_states[i]
                diff_index = i
        log('Making signature: %r' % self.probs[-10:], lvl=1)
        sign_from_state = self.states[sign_from - 1] if sign_from > 0 else GENESIS_STATE
        s = Signature(self.pos, map(lambda x: min(1 - FINALITY_THRESHOLD, max(FINALITY_THRESHOLD, x)), self.probs[sign_from:]), self.states[diff_index:], len(self.received_blocks), self.most_recent_sig)
        self.most_recent_sig = s
        all_signatures.append((s, self.get_time()))
        return s

    def on_receive(self, obj):
        if isinstance(obj, list):
            for _obj in obj:
                self.on_receive(_obj)
            return
        # Ignore objects that we already know about
        if obj.hash in self.received_objects:
            return
        # When receiving a block
        if isinstance(obj, Block):
            log('received block: %d %d' % (obj.height, obj.hash), lvl=2)
            while len(self.received_blocks) <= obj.height:
                self.received_blocks.append(None)
                self.states.append(None)
            self.received_blocks[obj.height] = obj
            self.time_received[obj.hash] = self.get_time()
            # Upon receiving a new block, make a new signature
            s = self.sign()
            self.network.broadcast(self, s)
            self.on_receive(s)
            self.network.broadcast(self, obj)
        # When receiving a signature
        elif isinstance(obj, Signature):
            smrs = self.most_recent_sigs
            latest_sig_hash = (smrs[obj.signer].hash if obj.signer in smrs else None)
            latest_sig_seq = (smrs[obj.signer].seq if obj.signer in smrs else -1)
            # print 'sig', obj.hash, obj.prev, (smrs[obj.signer].hash if obj.signer in smrs else None) == obj.prev
            if latest_sig_hash == obj.prev:
                sf = obj.sign_from
                while len(self.received_signatures) <= len(obj.probs) + sf:
                    self.received_signatures.append({})
                for i, p in enumerate(obj.probs):
                    self.received_signatures[i + sf][obj.signer] = p
                self.network.broadcast(self, obj)
                self.most_recent_sigs[obj.signer] = obj
                log('upgraded signature: '+str(obj.seq), lvl=2)
            else:
                # print 'newseq', obj.seq, 'oldseq', latest_sig_seq
                self.broadcast(SignatureChildRequest(self.id, latest_sig_hash, obj.signer, [smrs[obj.signer].seq, smrs[obj.signer].prev] if obj.signer in smrs else None))
                return
        elif isinstance(obj, SignatureChildRequest):
            log('Processing SignatureChildRequest', lvl=2)
            x = [self.most_recent_sigs.get(obj.signer, None)]
            while 1:
                if x[-1] is None:
                    log('SignatureChildRequest fail', lvl=2)
                    break
                # print x.hash, x.signer, x.seq, x.prev
                if x[-1].prev == obj.sighash:
                    self.network.direct_send(obj.sender, x[::-1])
                    log('SignatureChildRequest success: %r' % [a.seq for a in x[::-1]], lvl=2)
                    break
                x.append(self.received_objects[x[-1].prev] if x[-1].prev is not None else None)
        # Received a block request, respond if we have it
        elif isinstance(obj, BlockRequest):
            if obj.ask_height < len(self.received_blocks):
                if self.received_blocks[obj.ask_height] is not None:
                    self.network.direct_send(obj.sender, self.received_blocks[obj.ask_height])
        self.received_objects[obj.hash] = obj
        self.time_received[obj.hash] = self.get_time()

    # Run every tick
    def tick(self):
        mytime = self.get_time()
        target_time = BLKTIME * self.next_height
        if mytime >= target_time:
            o = Block(self.pos, self.next_height)
            self.next_height += NUM_VALIDATORS
            log('making block: %d %d' % (o.height, o.hash), lvl=1)
            if random.random() < BROADCAST_SUCCESS_RATE:
                self.network.broadcast(self, o)
            while len(self.received_blocks) <= o.height:
                self.received_blocks.append(None)
                self.states.append(None)
            self.received_blocks[o.height] = o
            self.received_objects[o.hash] = o
            self.time_received[o.hash] = mytime
            return o

validator_list = []
future = {}
discarded = {}
finalized_blocks = {}
all_signatures = []
now = [0]


def who_heard_of(h, n):
    o = ''
    for x in n.agents:
        o += '1' if h in x.received_objects else '0'
    return o


def get_opinions(n):
    o = []
    maxheight = 0
    for x in n.agents:
        maxheight = max(maxheight, len(x.probs))
    for h in range(maxheight):
        p = ''
        q = ''
        for x in n.agents:
            if len(x.probs) <= h:
                p += '_'
            else:
                odds = math.log(x.probs[h] / (1 - x.probs[h])) / math.log(FINALITY_THRESHOLD) * 10
                if odds <= -10:
                    p += '-'
                elif odds >= 10:
                    p += '+'
                else:
                    p += str(int(odds * 10) * 0.1)+','
            q += 'n' if len(x.received_blocks) <= h or x.received_blocks[h] is None else 'y'
        o.append((h, p, q))
    return o


def get_finalization_heights(n):
    o = []
    for x in n.agents:
        o.append(x.max_finalized_height)
    return o


# Check how often blocks that are assigned particular probabilities of
# finalization by our algorithm are actually finalized
def calibrate(finalized_hashes):
    threshold_odds = [FINALITY_THRESHOLD ** (x * 0.1) for x in range(-10, 11)]
    thresholds = [x / (1 + x) for x in threshold_odds]
    signed = [0] * (len(thresholds) - 1)
    _finalized = [0] * (len(thresholds) - 1)
    _discarded = [0] * (len(thresholds) - 1)
    for s, _ in all_signatures:
        sf = s.sign_from
        for i, prob in enumerate(s.probs):
            if i + sf >= len(finalized_hashes):
                continue
            actual_result = 1 if finalized_hashes[i + sf] else 0
            index = 0
            while index + 2 < len(thresholds) and prob > thresholds[index + 1]:
                index += 1
            signed[index] += 1
            if actual_result == 1:
                _finalized[index] += 1
            elif actual_result == 0:
                _discarded[index] += 1
    for i in range(len(thresholds) - 1):
        if _finalized[i] + _discarded[i]:
            print 'Probability from %f to %f: %f (%d of %d)' % (thresholds[i], thresholds[i+1], _finalized[i] * 1.0 / (_finalized[i] + _discarded[i]), _finalized[i], _finalized[i] + _discarded[i])
    print 'Percentage of block heights filled: %f%%' % (len([x for x in finalized_hashes if x]) * 100.0 / len(finalized_hashes))


def calc_rewards(finalized_hashes):
    most_recent = {}
    gains = {}
    losses = {}
    total_gains = {}
    total_losses = {}
    for s, t in all_signatures:
        if s.max_height >= len(finalized_hashes):
            continue
        prevsig, prevtime = most_recent.get(s.signer, (None, 0))
        td = t - prevtime
        if prevsig:
            sf = s.sign_from
            for i, p in enumerate(s.probs):
                h = sf + i
                oddspos, oddsneg = p / (1 - p), (1 - p) / p
                if h < len(finalized_hashes):
                    if finalized_hashes[h] is False:
                        score_delta = oddsneg - oddspos * oddspos
                    else:
                        score_delta = oddspos - oddsneg * oddsneg
                    if score_delta >= 0:
                        gains[s.signer][h] = (gains[s.signer][h-1] if h else 0) + score_delta
                        losses[s.signer][h] = (losses[s.signer][h-1] if h else 0)
                    else:
                        if (p < 0.1 or p > 0.9) and s.signer:
                            print s.signer, finalized_hashes[h] is not False, oddspos, oddsneg, score_delta
                        gains[s.signer][h] = (gains[s.signer][h-1] if h else 0)
                        losses[s.signer][h] = (losses[s.signer][h-1] if h else 0) - score_delta
            # print 'Validator %d, total gains: %d total losses %d' % (s.signer, gains[h] - (gains[h-200] if h > 200 else 0), losses[h] - (losses[h-200] if h > 200 else 0))
            total_gains[s.signer] += gains[s.signer][h] - (gains[s.signer][h-200] if h > 200 else 0)
            total_losses[s.signer] += losses[s.signer][h] - (losses[s.signer][h-200] if h > 200 else 0)
        else:
            gains[s.signer], losses[s.signer] = [0] * 10000, [0] * 10000
            total_gains[s.signer], total_losses[s.signer] = 0, 0
        most_recent[s.signer] = s, t
    return total_gains, total_losses

def run(steps=4000):
    n = networksim.NetworkSimulator(latency=NETWORK_LATENCY)
    for i in range(NUM_VALIDATORS):
        if i == 0:
            n.agents.append(Validator(i, n, vote=voting_strategy.craycray_vote))
        elif i % 2:
            n.agents.append(Validator(i, n, vote=voting_strategy.aggressive_vote))
        else:
            n.agents.append(Validator(i, n))
    n.generate_peers(3)
    while len(all_signatures):
        all_signatures.pop()
    for x in future.keys():
        del future[x]
    for x in finalized_blocks.keys():
        del finalized_blocks[x]
    for x in discarded.keys():
        del discarded[x]
    for i in range(steps):
        n.tick()
        if i % 500 == 0:
            minmax = 99999999999999999
            for x in n.agents:
                minmax = min(minmax, x.max_finalized_height - 10)
            print get_opinions(n)[max(minmax, 0):]
            finalized0 = [(v.max_finalized_height, v.finalized_hashes) for v in n.agents]
            if CHECK_INTEGRITY:
                finalized = sorted(finalized0, key=lambda x: len(x[1]))
                for j in range(len(n.agents) - 1):
                    for k in range(len(finalized[j][1])):
                        if finalized[j][1][k] is not None and finalized[j+1][1][k] is not None:
                            if finalized[j][1][k] != finalized[j+1][1][k]:
                                print finalized[j]
                                print finalized[j+1]
                                raise Exception("Finalization mismatch: %r %r" % (finalized[j][1][k], finalized[j+1][1][k]))
            print 'Finalized status: %r' % [x[0] for x in finalized0]
            _all = finalized0[0][1]
            _pos = len([x for x in _all if x])
            _neg = len([x for x in _all if not x])
            print 'Finalized blocks: %r (%r positive, %r negative)' % (len(_all), _pos, _neg)
        if i == 10000 and NETSPLITS >= 1:
            print "###########################################################"
            print "Knocking off 20% of the network!!!!!"
            print "###########################################################"
            n.knock_offline_random(NUM_VALIDATORS // 5)
        if i == 20000 and NETSPLITS >= 2:
            print "###########################################################"
            print "Simluating a netsplit!!!!!"
            print "###########################################################"
            n.generate_peers()
            n.partition()
        if i == 30000 and NETSPLITS >= 1:
            print "###########################################################"
            print "Network health back to normal!"
            print "###########################################################"
            n.generate_peers()
    calibrate(n.agents[0].finalized_hashes[:n.agents[0].max_finalized_height + 1])
    gains, losses = calc_rewards(n.agents[0].finalized_hashes[:n.agents[0].max_finalized_height + 1])
    for (k, g), (_, l) in zip(gains.items(), losses.items()):
        print 'Agent %d got a total reward of %d with %d gains and %d losses' % (k, g - l, g, l)
