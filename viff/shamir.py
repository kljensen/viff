# Copyright 2007, 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License (LGPL) as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General
# Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with VIFF. If not, see <http://www.gnu.org/licenses/>.

"""Shamir secret sharing and recombination. Based on the paper *How to
share a secret* by Adi Shamir in *Communications of the ACM* **22**
(11): 612-613.
"""

import operator
from viff.util import rand, fake


@fake(lambda s, t, n: [(s.field(i+1), s) for i in range(n)])
def share(secret, threshold, num_players):
    """Shamir share secret.

    The *threshold* indicates the maximum number of shares that reveal
    nothing about *secret*. The return value is a list of ``(player
    id, share)`` pairs.

    It holds that sharing and recombination cancels each other:

    >>> from field import GF
    >>> Zp = GF(47)
    >>> secret = Zp(42)
    >>> recombine(share(secret, 7, 15)[:8]) == secret
    True

    The threshold can range from zero (for a dummy-sharing):

    >>> share(Zp(10), 0, 5)
    [({1}, {10}), ({2}, {10}), ({3}, {10}), ({4}, {10}), ({5}, {10})]

    up to but not including *num_players*:

    >>> share(Zp(10), 5, 5)
    Traceback (most recent call last):
      ...
    AssertionError: Threshold out of range
    """
    assert threshold >= 0 and threshold < num_players, "Threshold out of range"

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
            cur_share = coef[j] + cur_share * cur_point

        shares.append((cur_point, cur_share))

    return shares

#: Cached recombination vectors.
#:
#: The recombination vector used by `recombine` depends only on the
#: recombination point and the player IDs of the shares, and so it can
#: be cached for efficiency.
_recombination_vectors = {}


@fake(lambda s, x=0: s[0][1])
def recombine(shares, x_recomb=0):
    """Recombines list of ``(xi, yi)`` pairs.

    Shares is a list of *threshold* + 1 ``(player id, share)`` pairs.
    Recombination is done in the optional point *x_recomb*.
    
    Note that player ids must be elements in the same field as the
    shares or otherwise the algorithm will not work.
    
    >>> from field import GF
    >>> Zp = GF(19)
    >>> shares = [(Zp(i), 7 * Zp(i) + 3) for i in range(1, 4)]
    >>> print shares
    [({1}, {10}), ({2}, {17}), ({3}, {5})]
    >>> del(shares[1])
    >>> recombine(shares)
    {3}
    """
    xs, ys = zip(*shares)
    key = xs + (x_recomb, )
    try:
        vector = _recombination_vectors[key]
    except KeyError:
        vector = []
        for i, x_i in enumerate(xs):
            factors = [(x_k - x_recomb) / (x_k - x_i)
                       for k, x_k in enumerate(xs) if k != i]
            vector.append(reduce(operator.mul, factors))
        _recombination_vectors[key] = vector
    return sum(map(operator.mul, ys, vector))


def verify_sharing(shares, degree):
    """Verifies that a sharing is correct.

    It is verified that the given shares correspond to points on a
    polynomial of at most the given degree.

    >>> from field import GF
    >>> Zp = GF(47)
    >>> shares = [(Zp(i), Zp(i**2)) for i in range(1, 6)]
    >>> print shares
    [({1}, {1}), ({2}, {4}), ({3}, {9}), ({4}, {16}), ({5}, {25})]
    >>> verify_sharing(shares, 2)
    True
    >>> verify_sharing(shares, 1)
    False
    """
    used_shares = shares[0:degree+1]
    for i in range(degree+1, len(shares)+1):
        if recombine(used_shares, i) != shares[i-1][1]:
            return False

    return True


if __name__ == "__main__":
    import doctest    #pragma NO COVER
    doctest.testmod() #pragma NO COVER
