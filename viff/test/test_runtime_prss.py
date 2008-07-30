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

"""Tests for the prss based protocols in the viff.runtime."""

from viff.runtime import Share, gather_shares
from viff.test.util import RuntimeTestCase, protocol
from viff.field import GF256


class RuntimePrssTest(RuntimeTestCase):
    """Tests the prss based protocols in L{viff.runtime.Runtime}."""

    @protocol
    def test_prss_share_int(self, runtime):
        """Test sharing of a Zp element using PRSS."""
        a, b, c = runtime.prss_share(runtime.players, self.Zp,
                                     42 + runtime.id)

        self.assert_type(a, Share)
        self.assert_type(b, Share)
        self.assert_type(c, Share)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gather_shares([opened_a, opened_b, opened_c])

    @protocol
    def test_prss_share_bit(self, runtime):
        """Test sharing of a GF256 element using PRSS."""
        a, b, c = runtime.prss_share(runtime.players, GF256.field,
                                     42 + runtime.id)

        self.assert_type(a, Share)
        self.assert_type(b, Share)
        self.assert_type(c, Share)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gather_shares([opened_a, opened_b, opened_c])

    @protocol
    def test_prss_share_asymmetric(self, runtime):
        """Test asymmetric pseudo-random secret sharing."""
        # Share a single input -- the result should be a Share and not
        # a singleton list.
        if runtime.id == 2:
            b = runtime.prss_share([2], self.Zp, 42 + runtime.id)
        else:
            b = runtime.prss_share([2], self.Zp)

        # Share two inputs, but do it in "backwards" order.
        if runtime.id == 1 or runtime.id == 3:
            c, a = runtime.prss_share([3, 1], self.Zp, 42 + runtime.id)
        else:
            c, a = runtime.prss_share([3, 1], self.Zp)

        self.assert_type(a, Share)
        self.assert_type(b, Share)
        self.assert_type(c, Share)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gather_shares([opened_a, opened_b, opened_c])

    @protocol
    def test_prss_share_random_bit(self, runtime):
        """Tests the sharing of a 0/1 GF256 element using PRSS."""
        a = runtime.prss_share_random(field=GF256, binary=True)
        self.assert_type(a, Share)

        opened_a = runtime.open(a)
        opened_a.addCallback(self.assertIn, [GF256(0), GF256(1)])
        return opened_a

    @protocol
    def test_prss_share_random_int(self, runtime):
        """Tests the sharing of a 0/1 Zp element using PRSS."""
        a = runtime.prss_share_random(field=self.Zp, binary=True)
        self.assert_type(a, Share)

        opened_a = runtime.open(a)
        opened_a.addCallback(self.assertIn, [self.Zp(0), self.Zp(1)])
        return opened_a

    @protocol
    def test_prss_share_zero_bit(self, runtime):
        """Tests the sharing of a zero GF256 element using PRSS."""
        a = runtime.prss_share_zero(GF256)
        self.assert_type(a, Share)

        opened_a = runtime.open(a, threshold=2*runtime.threshold)
        opened_a.addCallback(self.assertEquals, GF256(0))
        return opened_a

    @protocol
    def test_prss_share_zero_int(self, runtime):
        """Tests the sharing of a zero Zp element using PRSS."""
        a = runtime.prss_share_zero(self.Zp)
        self.assert_type(a, Share)

        opened_a = runtime.open(a, threshold=2*runtime.threshold)
        opened_a.addCallback(self.assertEquals, self.Zp(0))
        return opened_a

    @protocol
    def test_prss_share_bit_double(self, runtime):
        """Tests sharing a bit over Zp and GF256."""
        bit_p, bit_b = runtime.prss_share_bit_double(self.Zp)

        self.assert_type(bit_p, Share)
        self.assertEquals(bit_p.field, self.Zp)
        self.assert_type(bit_b, Share)
        self.assertEquals(bit_b.field, GF256)

        result = gather_shares([runtime.open(bit_p), runtime.open(bit_b)])
        result.addCallback(lambda (a, b): self.assertEquals(a.value, b.value))
        return result

    @protocol
    def test_prss_shamir_share_bit_double(self, runtime):
        """Tests Shamir sharing a bit over Zp and GF256."""
        bit_p, bit_b = runtime.prss_shamir_share_bit_double(self.Zp)

        self.assert_type(bit_p, Share)
        self.assertEquals(bit_p.field, self.Zp)
        self.assert_type(bit_b, Share)
        self.assertEquals(bit_b.field, GF256)

        result = gather_shares([runtime.open(bit_p), runtime.open(bit_b)])
        result.addCallback(lambda (a, b): self.assertEquals(a.value, b.value))
        return result
