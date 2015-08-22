import random

# The voting strategy. Validators see what every other validator's most
# recent vote for very particular block, in the format
#
# {
#    blockhash1: [vote1, vote2, vote3...],
#    blockhash2: [vote1, vote2, vote3...],
#    ...
# }
#
# Where the votes are probabilities with 0 < p < 1 (see
# http://lesswrong.com/lw/mp/0_and_1_are_not_probabilities/ !), and the
# strategy should itself return an object of the format
# {
#    blockhash1: vote,
#    blockhash2: vote,
#    ...
# }


def vote(probs, default_judgements, num_validators):
    pass1 = {k: get_vote_from_scores(v, num_validators)
             for k, v in probs.items() if k in default_judgements}
    pass2 = normalize(pass1, num_validators, default_judgements)
    return pass2


# Get the 33rd percentile of votes from other users
def get_vote_from_scores(probs, num_validators):
    extended_probs = [0] * (num_validators - len(probs)) + sorted(probs)
    return extended_probs[num_validators // 3]


# Given a set of independently computed block probabilities, "normalize" the
# probabilities (ie. make sure they sum to at most 1; less than 1 is fine
# because the difference reflects the probability that some as-yet-unknown
# block will ultimately be finalized)
def normalize(block_results, num_validators, default_judgements):
    # Trivial base case
    if len(default_judgements) == 0:
        return {}
    block_results = {k:block_results.get(k, 0) for k in default_judgements}
    unclaimed = 1.0 - sum(block_results.values())
    # First pass: 0.8 + 0.2 * (33rd percentile of others' votes)
    maxkey = max(block_results.keys(), key=lambda x: block_results[x])
    a1 = {k: (0.8 + v * 0.2 if k == maxkey else 0)
          for k, v in block_results.items()}
    # Second pass: first impressions
    a2 = {k: v * (1 - sum(a1)) for k, v in default_judgements.items()}
    o = {k: max(a1[k], a2[k]) for k in block_results.keys()}
    # assert sum(o.values()) <= 1, (o, sum(o.values()), sumprob)
    for k, v in o.items():
        if v > 0.9999:
            pass  # print k, v, a, o, sumprob, newsumprob
    return o
