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

import operator

import shamir


def prss(n, t, j, prns, field):
    """
    Generates a pseudo-random secret share for player j based on the
    pseuro-random numbers prns.

    An example with (n,t) = (3,1) and a modulus of 31:
    >>> from field import IntegerFieldElement
    >>> IntegerFieldElement.modulus = 31
    >>> prns = {frozenset([1,2]): 10, frozenset([1,3]): 20, frozenset([2,3]): 30}
    >>> prss(3, 1, 1, prns, IntegerFieldElement)
    {27}
    >>> prss(3, 1, 2, prns, IntegerFieldElement)
    {25}
    >>> prss(3, 1, 3, prns, IntegerFieldElement)
    {23}

    We see that the sharing is consistant because each subset of two
    players will recombine their shares to {29}.
    """
    result = 0
    all = frozenset(range(1,n+1))
    # TODO: generate_subsets could skip all subsets without j. Or
    # could we simply use the subsets given by prns.keys()?
    for subset in generate_subsets(all, n-t):
        if j in subset:
            points = [(field(x), 0) for x in all-subset]
            points.append((0,1))
            f_in_j = shamir.recombine(points, j)
            #print "points:", points
            #print "f(%s): %s" % (j, f_in_j)
            result += prns[subset] * f_in_j

    return result
    


def generate_subsets(s, size):
    """
    Generates the set of all subsets of a specific size:

    >>> generate_subsets(frozenset('abc'), 2)
    frozenset([frozenset(['c', 'b']), frozenset(['a', 'c']), frozenset(['a', 'b'])])

    Generating subsets larger than the initial set return the empty set:

    >>> generate_subsets(frozenset('a'), 2)
    frozenset([])
    """
    if len(s) > size:
        result = set()
        for e in s:
            result.update(generate_subsets(s - set([e]), size))
        return frozenset(result)
    elif len(s) == size:
        return frozenset([s])
    else:
        return frozenset()


if __name__ == "__main__":
    import doctest
    doctest.testmod()
