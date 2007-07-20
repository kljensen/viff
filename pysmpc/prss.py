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

import operator, sha
from math import log, ceil

from struct import pack, unpack

from pysmpc import shamir


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


class PRF(object):
    """
    Models a pseudo random function (a PRF).

    The numbers are based on a SHA1 hash of the initial key.
    """

    def __init__(self, key, max):
        """
        Creates the PRF keyed with the given key and max. The key must
        be a string whereas the max must be a number. Output value
        will be in the range zero to max, with zero included and max
        excluded.
        
        So to make a PRF what generates numbers less than 1000 do:
        >>> f = PRF("key", 1000)

        The PRF can be evaluated by calling it on some input:
        >>> f("input")
        327L

        Creating another PRF with the same key gives identical results
        since f and g are deterministic functions, depending only on
        the key:
        >>> g = PRF("key", 1000)
        >>> g("input")
        327L
        
        >>> [f(i) for i in range(100)] == [g(i) for i in range(100)]
        True

        Both the key and the max is used when the PRF is keyed. This
        means that
        >>> f = PRF("key", 1000)
        >>> g = PRF("key", 10000)
        >>> [f(i) for i in range(100)] == [g(i) for i in range(100)]
        False

        Should the max given be too large, an error is raised:
        >>> prf = PRF("key", 2**161)
        Traceback (most recent call last):
            ...
        ValueError: max cannot be larger than 160 bit
        """
        # Use log2 to calculate the number of bits in max, then round
        # up and split it into the number of bytes and bits needed.
        bit_length = int(ceil(log(max, 2)))
        if bit_length > sha.digest_size * 8:
            raise ValueError("max cannot be larger than %d bit" %
                             (sha.digest_size * 8))
        
        self.max = max
        self.bytes = (bit_length // 8) + 1
        self.bits = bit_length % 8

        # Store a sha1 instance already keyed by the key and the
        # maximum. The maximum is included as well since we want
        # f("input", 100) and g("input", 1000) to generate different
        # output.
        self.sha1 = sha.new(key + str(max))

    def __call__(self, input):
        """Return a number based on input.

        If the input is not already a string, it is hashed (using the
        normal Python hash built-in) and the hash value is used
        instead. The hash value is a 32 bit value, so a string should
        be given if one wants to evaluate the PRF on more that 2**32
        different values.

        Example:
        >>> prf = PRF("key", 1000)
        >>> prf(1), prf(2), prf(3)
        (714L, 80L, 617L)
        
        Since prf is a function we can of course evaluate the same
        input to get the same output:
        >>> prf(1)
        714L

        The prf can take arbitrary input:
        >>> prf(("input", 123))
        474L

        but it must be hashable:
        >>> prf(["input", 123])
        Traceback (most recent call last):
            ...
        TypeError: list objects are unhashable
        """
        # We can only feed str data to sha1 instance, so we must
        # convert the input. 
        if not isinstance(input, str):
            input = pack("L", hash(input))

        while True:
            # Copy the already keyed sha1 instance.
            sha1 = self.sha1.copy()
            sha1.update(input)
            # Extract the needed number of bytes plus one to
            # accommodate for the extra bits needed.
            digest = sha1.digest()
            rand_bytes = digest[:self.bytes]
            # Convert this to a long and shift it to get rid of the
            # surplus bits.
            result = self._bytestolong(rand_bytes) >> (8 - self.bits)

            if result < self.max:
                return result
            else:
                # TODO: is this safe? The first idea was to append a
                # fixed string (".") every time, but that makes f("a")
                # and f("a.") return the same number.
                #
                # The final byte of the digest depends on the key
                # which means that it should not be possible to
                # predict it and so it should be hard to find pairs of
                # inputs which give the same output value.
                input += digest[-1]
            
    def _bytestolong(self, bytes):
        """Convert a byte string to a long integer.

        Taken from a message on comp.lang.python by Tim Peters:

        http://groups.google.com/group/comp.lang.python/msg/912f4203a942713f
        """
        nchunks, leftover = divmod(len(bytes), 4)
        if leftover:
            bytes = '\000' * (4 - leftover) + bytes
            nchunks = nchunks + 1
        pieces = unpack(">%dI" % nchunks, bytes)

        # TODO: Can be skipped?
        pieces = list(pieces)
        pieces.reverse()    # least-significant first

        nbits = 32
        while nchunks > 1:
            j = 0
            odd = nchunks & 1
            nchunks = nchunks >> 1
            for i in xrange(nchunks):
                pieces[i] = pieces[j] | (pieces[j + 1] << nbits)
                j = j + 2
            if odd:
                pieces[nchunks] = pieces[j]
                nchunks = nchunks + 1
            nbits = nbits << 1
        return pieces[0]        


if __name__ == "__main__":
    import doctest
    doctest.testmod()
