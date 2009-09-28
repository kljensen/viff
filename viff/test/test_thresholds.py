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

"""Test different thresholds."""

import operator

from viff.runtime import Share
from viff.comparison import Toft07Runtime
from viff.test.util import RuntimeTestCase, protocol


class Tests:
    """Test L{viff.runtime.Runtime} with a given threshold.

    This mixin class should be used with a L{RuntimeTestCase} which
    specifies a number of players and a threshold. The unit tests here
    have been designed to work with any number of players greater than
    two and any threshold.
    """

    runtime_class = Toft07Runtime

    def _test_binop(self, runtime, op):
        a, b = 12345, 34567
        share_a = Share(runtime, self.Zp, self.Zp(a + runtime.id))
        share_b = Share(runtime, self.Zp, self.Zp(b - runtime.id))

        expected = self.Zp(op(a, b))
        result = op(share_a, share_b)

        opened = runtime.open(result)
        opened.addCallback(self.assertEquals, expected)
        return opened

    @protocol
    def test_add(self, runtime):
        """Test addition."""
        return self._test_binop(runtime, operator.add)

    @protocol
    def test_sub(self, runtime):
        """Test subtraction."""
        return self._test_binop(runtime, operator.sub)

    @protocol
    def test_mul(self, runtime):
        """Test multiplication."""
        return self._test_binop(runtime, operator.mul)

    @protocol
    def test_ge(self, runtime):
        """Test greater-than-equal."""
        return self._test_binop(runtime, operator.ge)

    @protocol
    def test_open(self, runtime):
        """Test opening of a single sharing."""
        share = Share(runtime, self.Zp, self.Zp(117 + runtime.id))
        opened = runtime.open(share)
        opened.addCallback(self.assertEquals, 117)
        return opened

    @protocol
    def test_shamir_share(self, runtime):
        """Test a Shamir sharing by Player 2."""
        if runtime.id == 2:
            number = 117
        else:
            number = None
        x = runtime.open(runtime.shamir_share([2], self.Zp, number))
        x.addCallback(self.assertEquals, 117)
        return x


class Players3Threshold1Test(Tests, RuntimeTestCase):
    num_players = 3
    threshold = 1

class Players4Threshold1Test(Tests, RuntimeTestCase):
    num_players = 4
    threshold = 1

class Players5Threshold2Test(Tests, RuntimeTestCase):
    num_players = 5
    threshold = 2

class Players6Threshold2Test(Tests, RuntimeTestCase):
    num_players = 6
    threshold = 2

class Players7Threshold3Test(Tests, RuntimeTestCase):
    num_players = 7
    threshold = 3

class Players8Threshold3Test(Tests, RuntimeTestCase):
    num_players = 8
    threshold = 3

class Players9Threshold4Test(Tests, RuntimeTestCase):
    num_players = 9
    threshold = 4
