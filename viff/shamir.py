# Copyright 2007, 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

"""Shamir sharing and recombination.

Based on the paper "How to share a secret" by Adi Shamir in
I{Communications of the ACM} B{22} (11): 612-613.
"""

import operator
from viff.util import rand
    
def share(secret, threshold, num_players):
    """Shamir share secret.

    It holds that sharing and recombination cancels each other:

    >>> from field import GF
    >>> Zp = GF(47)
    >>> secret = Zp(42)
    >>> recombine(share(secret, 7, 15)[:8]) == secret
    True

    @param secret: the secret to be shared.
    @type secret: a field element

    @param threshold: maximum number of shares that reveal nothing
    about the secret.
    @type threshold: integer

    @param num_players: number of players.
    @type num_players: integer

    @return: shares, one for each player.
    @returntype: C{list} of (player id, share) pairs
    """
    assert threshold > 0 and threshold < num_players
    
    coef = [secret]
    for j in range(threshold):
        # TODO: introduce a random() method in FieldElements so that
        # this wont have to be a long when we are sharing a
        # GMPIntegerFieldElement.
        coef.append(rand.randint(0, long(secret.modulus)-1))

    shares = []
    for i in range(1, num_players+1):
        # Instead of calculating s_i as
        #
        #   s_i = s + a_1 x_i + a_2 x_i^2 + ... + a_t x_i^t
        #
        # we avoid the exponentiations by calculating s_i by
        #
        #   s_i = s + x_i (a_1 + x_i (a_2 + x_i ( ... (a_t) ... )))
        #
        # This is a little faster, even for small n and t.
        cur_point = secret.field(i)
        cur_share = coef[threshold]
        # Go backwards from threshold-1 down to 0
        for j in range(threshold-1, -1, -1):
            cur_share = coef[j] + cur_point * cur_share

        shares.append((cur_point, cur_share))

    return shares

#: Cached recombination vectors.
#:
#: The recombination vector used by L{recombine} depends only on the
#: recombination point and the player IDs of the shares, and so it can
#: be cached for efficiency.
_recombination_vectors = {}

def recombine(shares, x_recomb=0):
    """Recombines list of (xi, yi) pairs.

    Recombination is done in the optional point M{x}.

    @param shares: M{threshold+1} shares.
    @type shares: C{list} of (player id, share) pairs
    """
    xs = [x_i for (x_i, _) in shares]
    ys = [y_i for (_, y_i) in shares]
    try:
        key = tuple(xs) + (x_recomb,)
        vector = _recombination_vectors[key]
    except KeyError:
        vector = []
        for i, x_i in enumerate(xs):
            factors = [(x_k - x_recomb) / (x_k - x_i)
                       for k, x_k in enumerate(xs) if k != i]
            vector.append(reduce(operator.mul, factors))
        _recombination_vectors[key] = vector
    return sum(map(operator.mul, ys, vector))

if __name__ == "__main__":
    import doctest
    doctest.testmod()
