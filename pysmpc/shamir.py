# Copyright 2007 Martin Geisler
#
# This file is part of PySMPC
#
# PySMPC is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PySMPC is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PySMPC in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

"""
Shamir sharing and recombination.
"""

import random, operator
    
def share(secret, threshold, num_players):
    """
    Shamir share secret into num_players shares with the given
    threshold. It holds that
    >>> from field import IntegerFieldElement
    >>> IntegerFieldElement.modulus = 47
    >>> secret = IntegerFieldElement(42)
    >>> recombine(share(secret, 7, 15)[:8]) == secret
    True
    """
    assert threshold > 0 and threshold < num_players
    
    # TODO: rnd = random.SystemRandom() and remove debugging-seed
    rnd = random.Random(0)
    coef = [secret]
    for j in range(threshold):
        # TODO: introduce a random() method in FieldElements.
        coef.append(rnd.randint(0, long(secret.modulus)-1))

    shares = []
    for i in range(1, num_players+1):
        cur_point = secret.field(i)
        cur_share = secret
        for j in range(1, threshold+1):
            cur_share += cur_point**j * coef[j]
        shares.append((cur_point, cur_share))

    return shares

def recombine(shares, x_recomb=0):
    """
    Recombines list of (xi, yi) pairs. Recombination is done in the
    optional point x.
    """
    result = 0
    for i, (x_i, y_i) in enumerate(shares):
        factors = [(x_k - x_recomb) / (x_k - x_i)
                   for k, (x_k, _) in enumerate(shares) if k != i]
        result += y_i * reduce(operator.mul, factors)

    return result
    

if __name__ == "__main__":
    import doctest
    doctest.testmod()
