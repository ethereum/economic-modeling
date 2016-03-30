import random
GENESIS = 0
LATENCY = 25
CLOCKOFFSET = 25
BLKTIME = 10
RUNTIME = 1000
MINERS = 10

time = [0]
next_id = [0]

miners = []
all_blocks = []

class Block():
    def __init__(self, num, parents):
        self.num = num
        self.parents = parents
        if self.num not in all_blocks:
            all_blocks.append(self.num)

def get_ancestors(block, out=None):
    if out is None:
        out = {}
    out[block.num] = True
    for p in block.parents:
        if p.num not in out:
            get_ancestors(p, out)
    return out

class Miner():
    def __init__(self):
        self.heads = [Block(-1, [])]
        self.listen_queue = {}
        self.blocks = {-1: self.heads[0]}
        self.scores = {}
        self.children = {}
        self.id = next_id[0]
        next_id[0] += 1
        self.time_offset = random.randrange(CLOCKOFFSET) - CLOCKOFFSET // 2

    def get_time(self):
        return time[0] + self.time_offset

    def mine(self):
        t = self.get_time()
        if t % len(miners) == self.id and random.random() < 1.0 / BLKTIME:
            new_blk = Block(t, self.heads[:2])
            for h in self.heads:
                assert new_blk.num > h.num, (new_blk, self.heads)
            print 'new block: %d, parents: %r' % (t, map(lambda x: x.num, self.heads[:2]))
            for miner in miners:
                recv_time = t + 1 + random.randrange(LATENCY)
                if recv_time not in miner.listen_queue:
                    miner.listen_queue[recv_time] = []
                miner.listen_queue[recv_time].append(new_blk)

    def request_block(self, num):
        for miner in miners:
            if num in miner.blocks:
                recv_time = self.get_time() + 1 + random.randrange(LATENCY)
                if recv_time not in self.listen_queue:
                    self.listen_queue[recv_time] = []
                self.listen_queue[recv_time].append(miner.blocks[num])

    def listen(self):
        t = self.get_time()
        if t in self.listen_queue:
            for blk in self.listen_queue[t]:
                have_parents = True
                for p in blk.parents:
                    if p.num not in self.blocks:
                        self.request_block(p.num)
                        have_parents = False
                if not have_parents:
                    print 'no parents :('
                    continue
                self.blocks[blk.num] = blk
                for p in blk.parents:
                    if p.num not in self.children:
                        self.children[p.num] = set([])
                    self.children[p.num].add(blk.num)
                print 'getting ancestors for %r (%d)' % (blk , blk.num)
                anc = list(get_ancestors(blk).keys())
                print 'ancestors', anc
                for num in anc:
                    self.scores[num] = self.scores.get(num, 0) + 1
                if len(self.scores):
                    head = self.get_head()
                    print 'head', head
                    head_ancestors = get_ancestors(self.blocks[head])
                    head2_candidates = [(x,y) for x,y in self.blocks.items() if x not in head_ancestors]
                    self.heads = [self.blocks[head]]
                    if len(head2_candidates):
                        head2 = max(head2_candidates)[1]
                        self.heads.append(head2)
                else:
                    self.heads = []
            del self.listen_queue[t]

    def get_head(self):
        h = -1
        while h in self.children and self.children[h]:
            best_child = None
            best_score = -9999
            for c in self.children[h]:
                if self.scores[c] > best_score:
                    best_child = c
                    best_score = self.scores[c]
            h = best_child
        return h

    def get_chain(self):
        h = [self.get_head()]
        while h[-1] >= 0:
            h.append(self.blocks[h[-1]].parents[0].num)
        return h

    def get_totchain(self, head=None, scanned=None):
        if head == None:
            head = self.get_head()
            scanned = {}
        h = []
        scanned[head] = True
        for p in self.blocks[head].parents:
            if p.num not in scanned:
                h.extend([x for x in self.get_totchain(p.num, scanned) if x not in h])
        h.append(head)
        return h

for i in range(MINERS):
    miners.append(Miner())

for i in range(RUNTIME):
    for m in miners:
        m.mine()
        m.listen()
    time[0] += 1

totcs = []

for m in miners:
    # print 'chain: %r (%d)' % (m.get_chain(), len(m.get_chain()))
    totcs.append(m.get_totchain())
    print 'totchain: %r (%d)' % (totcs[-1], len(totcs[-1]))
    if len(totcs) >= 2:
        if totcs[-1][:len(totcs[-2])] == totcs[-2][:len(totcs[-1])]:
            print 'Perfect match'
        else:
            print 'Match up to %d' % (min([x for x in range(min(len(totcs[-1]), len(totcs[-2]))) if totcs[-1][x] != totcs[-2][x]]) - 1)

print 'all blocks: %r (%d)' % (sorted(all_blocks), len(all_blocks))
