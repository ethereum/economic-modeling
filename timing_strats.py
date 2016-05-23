import random
# Clock offset
CLOCKOFFSET = 10
# Block time
BLKTIME = 40
# Algorithm run time
RUNTIME = 500000
# Block reward
BLKREWARD = 1
# Reward for including x ticks' worth of transactions
# Linear by default, but sublinear formulas are
# probably most accurate
get_txreward = lambda ticks: 0.00001 * ticks
# Scoring penalty function
get_score_addition = lambda skips: 1.0 - 0.00001 * skips
# Latency function
latency = lambda: int(random.expovariate(1) * 15)

BLANK_STATE = {'transactions': 0}

time = [0]

validators = []
next_id = [0]

timeslots = []

class Block():
    def __init__(self, parent, state, number):
        self.hash = random.randrange(10**20)
        self.prevhash = parent.hash if parent else 0
        self.state = state
        self.number = number
        self.height = parent.height + 1 if parent else 0

GENESIS = Block(None, BLANK_STATE, 0)

# Insert a key/value pair into a state
# This is abstracted away into a method to make it easier to
# swap the state out with an immutable dict library or whatever
# else to increase efficiency
def update_state(s, k, v):
    s2 = {_k: _v for _k, _v in s.items()}
    s2[k] = v
    return s2

# Get a key from a state, default zero
def get_state(s, k):
    return s.get(k, 0)


class Validator():
    def __init__(self, strategy):
        # The block that the validator considers to be the head
        self.head = GENESIS
        # A map of tick -> blocks that the validator will receive
        # during that tick
        self.listen_queue = {}
        # Blocks that the validator knows about
        self.blocks = {GENESIS.hash: GENESIS}
        # Scores (~= total difficulty) for those blocks
        self.scores = {GENESIS.hash: 0}
        # When the validator received each block
        self.time_received = {GENESIS.hash: 0}
        # Blocks received too early and scheduled to be processed later
        self.alotted = {}
        # This validator's clock is off by this number of ticks
        self.time_offset = random.randrange(CLOCKOFFSET) - CLOCKOFFSET // 2
        # Set the validator's strategy
        self.set_strategy(strategy)
        # Keeps track of the highest block number a validator has already
        # produced a block at
        self.min_number = 0
        # The validator's ID
        self.id = next_id[0]
        next_id[0] += 1

    def set_strategy(self, strategy):
        # The number of ticks a validator waits before producing a block
        self.produce_delay = strategy[0]
        # The number of extra ticks a validator waits per skip (ie.
        # if you skip two validator slots then wait this number of ticks
        # times two) before producing a block
        self.per_block_produce_delay = strategy[1]
        # The number of extra ticks a validator waits per skip before
        # accpeint a block
        self.per_block_accept_delay = strategy[2]
        

    # Get the time from the validator's point of view
    def get_time(self):
        return max(time[0] + self.time_offset, 0)

    # Add a block to the listen queue at the given time
    def add_to_listen_queue(self, time, obj):
        if time not in self.listen_queue:
            self.listen_queue[time] = []
        self.listen_queue[time].append(obj)

    def mine(self):
        # Is it time to produce a block?
        t = self.get_time()
        skips = 0
        while timeslots[self.head.number + 1 + skips] != self.id:
            skips += 1
        # If it is...
        if t >= self.time_received[self.head.hash] + self.produce_delay + self.per_block_produce_delay * skips \
                and self.head.number >= self.min_number:
            # Compute my block reward
            my_reward = BLKREWARD + get_txreward(time[0] - self.head.state['transactions'])
            # Claim the reward from the transactions since the parent
            new_state = update_state(self.head.state, 'transactions', time[0])
            # Apply the block reward
            new_state = update_state(new_state, self.id, get_state(new_state, self.id) + my_reward)
            # Create the block
            b = Block(self.head, new_state, self.head.number + 1 + skips)
            print '---------> Validator %d makes block with hash %d and parent %d (%d skips) at time %d' % (self.id, b.hash, b.prevhash, skips, time[0])
            # Broadcast it
            for validator in validators:
                recv_time = time[0] + 1 + latency()
                # print 'broadcasting, delay %d' % (recv_time - t)
                validator.add_to_listen_queue(recv_time, b)
            # Can't produce a block at this height anymore
            self.min_number = b.number

    # If a validator realizes that it "should" have a block but doesn't,
    # it can use this method to request it from the network
    def request_block(self, hash):
        for validator in validators:
            if hash in validator.blocks:
                recv_time = time[0] + 1 + latency()
                self.add_to_listen_queue(recv_time, validator.blocks[hash])

    # Process all blocks that it should receive during the current tick
    def listen(self):
        t = self.get_time()
        if time[0] in self.listen_queue:
            for blk in self.listen_queue[time[0]]:
                # Parent not found
                if blk.prevhash not in self.blocks and blk.prevhash not in self.alotted:
                    self.request_block(blk.prevhash)
                    print 'skipping: parent %d not found' % blk.prevhash
                    continue
                # Parent found but not yet received; then, receive the child
                # immediately after the parent
                elif blk.prevhash not in self.blocks:
                    assert self.alotted[blk.prevhash] >= time[0]
                    self.add_to_listen_queue(self.alotted[blk.prevhash] + 2, blk)
                    self.alotted[blk.hash] = self.alotted[blk.prevhash] + 2
                    continue
                # Already processed?
                if blk.hash in self.blocks or blk.hash in self.alotted and self.alotted[blk.hash] > time[0]:
                    # print 'skipping: already processed'
                    continue
                # Too early? Re-append at earliest allowed time
                parent = self.blocks[blk.prevhash]
                skips = blk.number - parent.number - 1
                alotted_recv_time = self.time_received[parent.hash] + skips * self.per_block_accept_delay
                if t < alotted_recv_time:
                    self.add_to_listen_queue(alotted_recv_time - t + time[0], blk)
                    self.alotted[blk.hash] = alotted_recv_time - t + time[0]
                    print 'too early, delaying %d (%d vs %d)' % (blk.hash, t, alotted_recv_time)
                    continue
                # Add the block and compute the score
                print 'Validator %d receives block with hash %d at time %d' % (self.id, blk.hash, time[0])
                if blk.hash in self.alotted:
                    del self.alotted[blk.hash]
                self.blocks[blk.hash] = blk
                self.scores[blk.hash] = self.scores[blk.prevhash] + get_score_addition(skips)
                self.time_received[blk.hash] = t
                if self.scores[blk.hash] > self.scores[self.head.hash]:
                    self.head = blk
            del self.listen_queue[time[0]]
            for x in self.alotted:
                assert self.alotted[x] > time[0]

# Sample the average network latency
latency_sample = sum([latency() for i in range(100)]) // 100

# Define the strategies of the validators
strategy_groups = [
    #((time before publishing a block, time per skip to wait before accepting a block, time per skip to wait before publishing), number of validators with this strategy)
    ((20, BLKTIME, BLKTIME), 32),
    ((20, int(BLKTIME * 0.67), BLKTIME), 3),
    ((20, int(BLKTIME * 1.33), BLKTIME), 3),
    ((0, BLKTIME, BLKTIME), 3),
    ((40, BLKTIME, BLKTIME), 3),
    ((20, BLKTIME, int(BLKTIME * 1.33)), 3),
    ((20, BLKTIME, int(BLKTIME * 0.67)), 3),
]
sgstarts = [0]

for s, c in strategy_groups:
    sgstarts.append(sgstarts[-1] + c)
    for i in range(c):
        validators.append(Validator(s))

# Force fairness in the random selection; this is unrealistic
# but helps to remove a confounder from the statistical analysis
for i in range(RUNTIME // len(validators) // 20):
    new_timeslots = range(len(validators)) * 20
    random.shuffle(new_timeslots)
    timeslots.extend(new_timeslots)

# Run the simulation
for i in range(RUNTIME):
    for m in validators:
        m.mine()
        m.listen()
    time[0] += 1

print 'Head block number:', validators[0].head.number
print 'Head block height:', validators[0].head.height
print validators[0].head.state

for i, ((s, c), pos) in enumerate(zip(strategy_groups, sgstarts)):
    totrev = 0
    for j in range(pos, pos + c):
        totrev += validators[0].head.state.get(j, 0)
    print 'Strategy group %d: average %d' % (i, totrev * 1.0 / c)
