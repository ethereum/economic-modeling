from ethereum.casper_utils import RandaoManager, get_skips_and_block_making_time, \
    generate_validation_code, call_casper
from ethereum.utils import sha3, hash32, privtoaddr
from ethereum.block import Block
from ethereum.transactions import Transaction
from ethereum.chain import Chain
import networksim
import rlp
import random

EPOCH_LENGTH = 10000
validatorSizes = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]

class ChildRequest(rlp.Serializable):
    fields = [
        ('prevhash', hash32)
    ]

    def __init__(self, prevhash):
        self.prevhash = prevhash

class Validator():
    def __init__(self, genesis, key, network, env):
        self.chain = Chain(genesis, env=env)
        self.key = key
        self.randao = RandaoManager(sha3(self.key))
        self.network = network
        self.received_objects = {}
        self.skips_when_creating = None
        self.eligible_to_create = None
        self.indices = None
        self.validation_code = generate_validation_code(privtoaddr(key))
        self.used_parents = {}
        self.time_offset = random.randrange(5) - 2
        self.find_my_indices()

    def find_my_indices(self):
        self.indices = None
        for i in range(len(validatorSizes)):
            valcount = call_casper(self.chain.state, 'getValidatorCount', [i])
            for j in range(valcount):
                valcode = call_casper(self.chain.state, 'getValidationCode', [i, j])
                if valcode == self.validation_code:
                    self.indices = i, j
                    print 'Found indices: %d %d' % (i, j)
                    return
        print 'Not in current validator set'

    def get_timestamp(self):
        return self.network.time + self.time_offset

    def on_receive(self, obj):
        if isinstance(obj, list):
            for _obj in obj:
                self.on_receive(_obj)
            return
        if obj.hash in self.received_objects:
            return
        if isinstance(obj, Block):
            try:
                old_head = self.chain.head_hash
                self.chain.add_block(obj)
                self.network.broadcast(ChildRequest(obj.header.hash))
                new_head = self.chain.head_hash
                if new_head != old_head:
                    if self.chain.state.block_number % EPOCH_LENGTH == 0:
                        self.find_my_indices()
                    if self.indices:
                        self.skips_when_creating, self.eligible_to_create = get_skips_and_block_making_time(self.chain, self.indices)
            except Exception, e:
                print e
        elif isinstance(obj, Transaction):
            self.chain.add_transaction(obj)

    def tick(self):
        if self.eligible_to_create and self.get_timestamp() >= self.eligible_to_create and self.chain.head_hash not in self.used_parents:
            self.used_parents[self.chain.head_hash] = True
            b = self.make_block(self.chain, self.key, self.randao, self.indices)
            self.network.broadcast(b)
