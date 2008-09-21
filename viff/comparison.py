# Copyright 2008 VIFF Development Team.
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

"""Comparison protocols. The mixin classes defined here provide a
:meth:`greater_than_equal` method to the :class:`Runtime
<viff.runtime.Runtime>` they are mixed with.
"""

__docformat__ = "restructuredtext"

import math

from viff.util import rand
from viff.runtime import Runtime, Share, gather_shares, increment_pc
from viff.active import ActiveRuntime
from viff.field import GF256, FieldElement


class ComparisonToft05Mixin:
    """Comparison by Tomas Toft, 2005."""

    @increment_pc
    def convert_bit_share(self, share, dst_field):
        """Convert a 0/1 share into dst_field."""
        bit = rand.randint(0, 1)
        dst_shares = self.prss_share(self.players, dst_field, bit)
        src_shares = self.prss_share(self.players, share.field, bit)

        # TODO: Using a parallel reduce below seems to be slower than
        # using the built-in reduce.

        # We open tmp and convert the value into a field element from
        # the dst_field.
        tmp = self.open(reduce(self.xor, src_shares, share))
        tmp.addCallback(lambda i: dst_field(i.value))
        # Must update field on Share when we change the field of the
        # the value within
        tmp.field = dst_field
        return reduce(self.xor, dst_shares, tmp)

    @increment_pc
    def greater_than_equal(self, share_a, share_b):
        """Compute ``share_a >= share_b``.

        Both arguments must be from the same field. The result is a
        :class:`GF256 <viff.field.GF256>` share.

        :warning:
           The result type (:class:`viff.field.GF256`) is different
           from the argument types (general field elements).

        """
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            share_b = Share(self, field, share_b)

        l = self.options.bit_length
        m = l + self.options.security_parameter
        t = m + 1

        # Preprocessing begin
        assert 2**(l+1) + 2**t < field.modulus, "2^(l+1) + 2^t < p must hold"
        assert self.num_players + 2 < 2**l

        bits = [self.prss_share_bit_double(field) for _ in range(m)]
        int_bits = [a for (a, _) in bits]
        bit_bits = [b for (_, b) in bits]

        def bits_to_int(bits):
            """Converts a list of bits to an integer."""
            return sum([2**i * b for i, b in enumerate(bits)])

        int_b = gather_shares(int_bits)
        int_b.addCallback(bits_to_int)
        # Preprocessing done

        a = share_a - share_b + 2**l
        T = self.open(2**t - int_b + a)

        result = gather_shares([T] + bit_bits)
        self.schedule_callback(result, self._finish_greater_than_equal, l)
        return result

    @increment_pc
    def _finish_greater_than_equal(self, results, l):
        """Finish the calculation."""
        T = results[0]
        bit_bits = results[1:]

        vec = [(GF256(0), GF256(0))]

        # Calculate the vector, using only the first l bits
        for i, bi in enumerate(bit_bits[:l]):
            Ti = GF256(T.bit(i))
            ci = Share(self, GF256, bi ^ Ti)
            vec.append((ci, Ti))

        # Reduce using the diamond operator. We want to do as much
        # as possible in parallel while being careful not to
        # switch the order of elements since the diamond operator
        # is non-commutative.
        while len(vec) > 1:
            tmp = []
            while len(vec) > 1:
                tmp.append(self._diamond(vec.pop(0), vec.pop(0)))
            if len(vec) == 1:
                tmp.append(vec[0])
            vec = tmp

        return GF256(T.bit(l)) ^ (bit_bits[l] ^ vec[0][1])

    @increment_pc
    def _diamond(self, (top_a, bot_a), (top_b, bot_b)):
        """The "diamond-operator".

        Defined by::

          (x, X) `diamond` (0, Y) = (0, Y)
          (x, X) `diamond` (1, Y) = (x, X)
        """
        top = top_a * top_b
        bot = top_b * (bot_a ^ bot_b) ^ bot_b
        return (top, bot)


class Toft05Runtime(ComparisonToft05Mixin, Runtime):
    """Default mix of :class:`ComparisonToft05Mixin` and
    :class:`Runtime <viff.runtime.Runtime>`."""
    pass

class ActiveToft05Runtime(ComparisonToft05Mixin, ActiveRuntime):
    """Default mix of :class:`ComparisonToft05Mixin` and
    :class:`ActiveRuntime <viff.runtime.ActiveRuntime>`."""
    pass


class ComparisonToft07Mixin:

    """Efficient comparison by Tomas Toft 2007. This mixin provides a
    :meth:`greater_than_equal` method which can compare Zp field
    elements and gives a secret result shared over Zp.
    """

    @increment_pc
    def convert_bit_share(self, share, dst_field):
        """Convert a 0/1 share into *dst_field*."""
        l = self.options.security_parameter + math.log(dst_field.modulus, 2)
        # TODO assert field sizes are OK...

        this_mask = rand.randint(0, (2**l) -1)

        # Share large random values in the big field and reduced ones
        # in the small...
        src_shares = self.prss_share(self.players, share.field, this_mask)
        dst_shares = self.prss_share(self.players, dst_field, this_mask)

        tmp = reduce(self.add, src_shares, share)

        # We open tmp and convert the value into a field element from
        # the dst_field.
        tmp = self.open(tmp)

        tmp.addCallback(lambda i: dst_field(i.value))
        # Must update field on Share when we change the field of the
        # the value within
        tmp.field = dst_field

        full_mask = reduce(self.add, dst_shares)
        return tmp - full_mask

    @increment_pc
    def greater_than_equal_preproc(self, field, smallField=None):
        """Preprocessing for :meth:`greater_than_equal`."""
        if smallField is None:
            smallField = field

        # Need an extra bit to avoid troubles with equal inputs
        l = self.options.bit_length + 1
        k = self.options.security_parameter

        # TODO: verify asserts are correct...
        assert field.modulus > 2**(l+2) + 2**(l+k), "Field too small"
        assert smallField.modulus > 3 + 3*l, "smallField too small"

        # TODO: do not generate all bits, only $l$ of them
        # could perhaps do PRSS over smaller subset?
        r_bitsField = [self.prss_share_random(field, True) for _ in range(l+k)]

        # TODO: compute r_full from r_modl and top bits, not from scratch
        r_full = 0
        for i, b in enumerate(r_bitsField):
            r_full = r_full + b * 2**i

        r_bitsField = r_bitsField[:l]
        r_modl = 0
        for i, b in enumerate(r_bitsField):
            r_modl = r_modl + b * 2**i

        # Transfer bits to smallField
        if field is smallField:
            r_bits = r_bitsField
        else:
            r_bits = [self.convert_bit_share(bit, smallField) \
                      for bit in r_bitsField]

        s_bit = self.prss_share_random(field, binary=True)

        s_bitSmallField = self.convert_bit_share(s_bit, smallField)
        s_sign = 1 + s_bitSmallField * -2

        # m: uniformly random -- should be non-zero, however, this
        # happens with negligible probability
        # TODO: small field, no longer negligible probability of zero -- update
        mask = self.prss_share_random(smallField, False)
        #mask_2 = self.prss_share_random(smallField, False)
        #mask_OK = self.open(mask * mask_2)
        #dprint("Mask_OK: %s", mask_OK)

        return field, smallField, s_bit, s_sign, mask, r_full, r_modl, r_bits

        ##################################################
        # Preprocessing done
        ##################################################

    @increment_pc
    def greater_than_equal_online(self, share_a, share_b, preproc, field):
        """Compute ``share_a >= share_b``. Result is secret shared."""
        # increment l as a, b are increased
        l = self.options.bit_length + 1
        # a = 2a+1; b= 2b // ensures inputs not equal
        share_a = 2 * share_a + 1
        share_b = 2 * share_b

        ##################################################
        # Unpack preprocessing
        ##################################################
        #TODO: assert fields are the same...
        field, smallField, s_bit, s_sign, mask, r_full, r_modl, r_bits = preproc
        assert l == len(r_bits), "preprocessing does not match " \
            "online parameters"

        ##################################################
        # Begin online computation
        ##################################################
        # c = 2**l + a - b + r
        z = share_a - share_b + 2**l
        c = self.open(r_full + z)

        self.schedule_callback(c, self._finish_greater_than_equal,
                               field, smallField, s_bit, s_sign, mask,
                               r_modl, r_bits, z)
        return c

    @increment_pc
    def _finish_greater_than_equal(self, c, field, smallField, s_bit, s_sign,
                               mask, r_modl, r_bits, z):
        """Finish the calculation."""
        # increment l as a, b are increased
        l = self.options.bit_length + 1
        c_bits = [smallField(c.bit(i)) for i in range(l)]

        sumXORs = [0]*l
        # sumXORs[i] = sumXORs[i+1] + r_bits[i+1] + c_(i+1)
        #                           - 2*r_bits[i+1]*c_(i+1)
        for i in range(l-2, -1, -1):
            # sumXORs[i] = \sum_{j=i+1}^{l-1} r_j\oplus c_j
            sumXORs[i] = sumXORs[i+1] + (r_bits[i+1] ^ c_bits[i+1])
        E_tilde = []
        for i in range(len(r_bits)):
            ## s + rBit[i] - cBit[i] + 3 * sumXors[i];
            e_i = s_sign + (r_bits[i] - c_bits[i])
            e_i = e_i + 3 * sumXORs[i]
            E_tilde.append(e_i)
        E_tilde.append(mask) # Hack: will mult e_i and mask...

        while len(E_tilde) > 1:
            # TODO: pop() ought to be preferred? No: it takes the
            # just appended and thus works linearly... try with
            # two lists instead, pop(0) is quadratic if it moves
            # elements.
            E_tilde.append(E_tilde.pop(0) * E_tilde.pop(0))

        E_tilde[0] = self.open(E_tilde[0])
        E_tilde[0].addCallback(lambda bit: field(bit.value != 0))
        non_zero = E_tilde[0]

        # UF == underflow
        UF = non_zero ^ s_bit

        # conclude the computation -- compute final bit and map to 0/1
        # return  2^(-l) * (z - (c%2**l - r%2**l + UF*2**l))
        #
        c_mod2l = c.value % 2**l
        result = (c_mod2l - r_modl) + UF * 2**l
        return (z - result) * ~field(2**l)
    # END _finish_greater_than

    @increment_pc
    def greater_than_equal(self, share_a, share_b):
        """Compute ``share_a >= share_b``.

        Both arguments must be shares from the same field. The result
        is a new 0/1 share from the field.
        """
        # TODO: Make all input-taking methods do coercion like this.
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            if not isinstance(share_a, FieldElement):
                share_a = field(share_a)
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            if not isinstance(share_b, FieldElement):
                share_b = field(share_b)
            share_b = Share(self, field, share_b)

        preproc = self.greater_than_equal_preproc(field)
        return self.greater_than_equal_online(share_a, share_b, preproc,
                                              field)


class Toft07Runtime(ComparisonToft07Mixin, Runtime):
    """Default mix of :class:`ComparisonToft07Mixin` and
    :class:`Runtime <viff.runtime.Runtime>`.
    """
    pass

class ActiveToft07Runtime(ComparisonToft07Mixin, ActiveRuntime):
    """Default mix of :class:`ComparisonToft07Mixin` and
    :class:`ActiveRuntime <viff.runtime.ActiveRuntime>`."""
    pass
