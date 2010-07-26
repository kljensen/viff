# Copyright 2010 VIFF Development Team.
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

from viff.runtime import Share, gather_shares
from viff.field import FieldElement

from viff.runtime import Runtime

class SimpleArithmeticRuntime(Runtime):
    """Provides methods for addition and subtraction.

    Provides set: {add, sub, mul}.
    Requires set: {self._plus((x, y), field),
                   self._minus((x, y), field),
                   self._plus_public(x, c, field),
                   self._minus_public_right(x, c, field),
                   self._minus_public_left(x, c, field),
                   self._wrap_in_share(x, field),
                   self._get_triple(field),
                   self._constant_multiply(x, c),
                   self.open(x),
                   self.increment_pc(),
                   self.activate_reactor()}.
    """

    def add(self, share_a, share_b):
        """Addition of shares.

        share_a is assumed to be an instance of Share.
        If share_b is also an instance of Share then self._plus gets called.
        If not then self._plus_public get called.
        """
        return self.both_shares(share_a, share_b, self._plus_public, self._plus)

    def both_shares(self, share_a, share_b, if_not, if_so):
        field = share_a.field
        if not isinstance(share_b, Share):
            if not isinstance(share_b, FieldElement):
                share_b = field(share_b)
            share_a.addCallbacks(if_not, self.error_handler, callbackArgs=(share_b, field))
            return share_a
        else:
            result = gather_shares([share_a, share_b])
            result.addCallbacks(if_so, self.error_handler, callbackArgs=(field,))
            return result

    def sub(self, share_a, share_b):
        """Subtraction of shares.

        If share_a is an instance of Share but not share_b, then self._minus_public_right gets called.
        If share_b is an instance of Share but not share_b, then self._minus_public_left gets called.
        If share_a and share_b are both instances of Share then self._minus get called.
        """
        if not isinstance(share_b, Share):
            field = share_a.field
            if not isinstance(share_b, FieldElement):
                share_b = field(share_b)
            share_a.addCallbacks(self._minus_public_right, self.error_handler, callbackArgs=(share_b, field))
            return share_a
        elif not isinstance(share_a, Share):
            field = share_b.field
            if not isinstance(share_a, FieldElement):
                share_a = field(share_a)
            share_b.addCallbacks(self._minus_public_left, self.error_handler, callbackArgs=(share_a, field))
            return share_b
        else:
            field = share_a.field
            result = gather_shares([share_a, share_b])
            result.addCallbacks(self._minus, self.error_handler, callbackArgs=(field,))
            return result

    def mul(self, share_x, share_y):
        """Multiplication of shares."""
        assert isinstance(share_x, Share) or isinstance(share_y, Share), \
            "At least one of share_x and share_y must be a Share."

        self.increment_pc()

        field = getattr(share_x, "field", getattr(share_y, "field", None))

        triple = self.triples.pop()
        return self._basic_multiplication(share_x,
                                          share_y,
                                          triple.a,
                                          triple.b,
                                          triple.c)

    def _cmul(self, share_x, share_y, field):
        """Multiplication of a share with a constant.

        Either share_x or share_y must be an OrlandiShare but not
        both. Returns None if both share_x and share_y are
        OrlandiShares.
        """
        if not isinstance(share_x, Share):
            # Then share_y must be a Share => local multiplication. We
            # clone first to avoid changing share_y.
            assert isinstance(share_y, Share), \
                "At least one of the arguments must be a share."
            result = share_y.clone()
            result.addCallback(self._constant_multiply, share_x)
            return result
        if not isinstance(share_y, Share):
            # Likewise when share_y is a constant.
            assert isinstance(share_x, Share), \
                "At least one of the arguments must be a share."
            result = share_x.clone()
            result.addCallback(self._constant_multiply, share_y)
            return result
        return None
    
    def _basic_multiplication(self, share_x, share_y, triple_a, triple_b, triple_c):
        """Multiplication of shares give a triple.

        Communication cost: ???.

        ``d = Open([x] - [a])``
        ``e = Open([y] - [b])``
        ``[z] = e[x] + d[y] - [de] + [c]``
        """
        assert isinstance(share_x, Share) or isinstance(share_y, Share), \
            "At least one of share_x and share_y must be a Share."

        self.increment_pc()

        field = getattr(share_x, "field", getattr(share_y, "field", None))
        n = field(0)

        cmul_result = self._cmul(share_x, share_y, field)
        if cmul_result is  not None:
            return cmul_result

        def multiply(ls):
            x, y, c, (d, e) = ls
            # [de]
            de = d * e
            # e[x]
            t1 = self._constant_multiply(x, e)
            # d[y]
            t2 = self._constant_multiply(y, d)
            # d[y] - [de]
            t3 = self._minus_public_right_without_share(t2, de, field)
            # d[y] - [de] + [c]
            z = self._plus((t3, c), field)
            t4 = self._plus((t3, c), field)
            # [z] = e[x] + d[y] - [de] + [c]
            z = self._plus((t1, t4), field)
            return self._wrap_in_share(z, field)

        # d = Open([x] - [a])
        # e = Open([y] - [b])
        de = self.open_two_values(share_x - triple_a, share_y - triple_b)
        # ds = self.open_multiple_values([share_x - triple_a, share_y - triple_b])
        result = gather_shares([share_x, share_y, triple_c, de])
        result.addCallbacks(multiply, self.error_handler)

        # do actual communication
        self.activate_reactor()

        return result
