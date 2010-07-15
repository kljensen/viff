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

import sys

from twisted.internet.defer import gatherResults, DeferredList

from viff.test.util import RuntimeTestCase, protocol
from viff.runtime import gather_shares, Share
from viff.config import generate_configs
from viff.bedoza import BeDOZaRuntime, BeDOZaShare, BeDOZaShareContents, BeDOZaKeyList, BeDOZaMACList
from viff.field import FieldElement, GF
from viff.util import rand

class KeyLoaderTest(RuntimeTestCase):
    """Test of KeyLoader."""

    # Number of players.
    num_players = 3

    runtime_class = BeDOZaRuntime

    @protocol
    def test_messagelist(self, runtime):
        """Test loading of keys."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        m1 = BeDOZaMACList([Zp(2), Zp(34)])
        m2 = BeDOZaMACList([Zp(11), Zp(4)])
        m3 = m1 + m2
        self.assertEquals(m3.macs[0], 13)
        self.assertEquals(m3.macs[1], 38)
        self.assertEquals(len(m3.macs), 2)
        return m3
        


class BeDOZaBasicCommandsTest(RuntimeTestCase):
    """Test for basic commands."""

    # Number of players.
    num_players = 3

    runtime_class = BeDOZaRuntime

    timeout = 3
    
    @protocol
    def test_random_share(self, runtime):
        """Test creation of a random shared number."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(True, True)

        x = runtime.random_share(Zp)
        d = runtime.open(x)
        d.addCallback(check)
        return d

    @protocol
    def test_plus(self, runtime):
        """Test addition of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)
       
        x = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(3), Zp(4), Zp(1)]), BeDOZaMACList([Zp(2), Zp(74), Zp(23), Zp(2)]))
        y = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(5), Zp(2), Zp(7)]), BeDOZaMACList([Zp(2), Zp(74), Zp(23), Zp(2)]))
        z = runtime._plus((x, y), Zp)
        self.assertEquals(z.get_value(), Zp(4))
        self.assertEquals(z.get_keys(), BeDOZaKeyList(Zp(23), [Zp(8), Zp(6), Zp(8)]))
        self.assertEquals(z.get_macs(), BeDOZaMACList([Zp(4), Zp(148), Zp(46), Zp(4)]))

    @protocol
    def test_sum(self, runtime):
        """Test addition of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 12)

        x2 = runtime.random_share(Zp)
        y2 = runtime.random_share(Zp)
        z2 = runtime.add(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_plus(self, runtime):
        """Test addition of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 12)

        x2 = runtime.random_share(Zp)
        y2 = runtime.random_share(Zp)
        z2 = x2 + y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_constant_right(self, runtime):
        """Test addition of secret shared number and a public number."""

        Zp = GF(31)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, 13)

        x2 = runtime.random_share(Zp)
        z2 = x2 + y1
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_constant_left(self, runtime):
        """Test addition of a public number and secret shared number."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, 13)

        x2 = runtime.random_share(Zp)
        z2 = y1 + x2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_minus(self, runtime):
        """Test subtraction of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)
       
        x = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(5), Zp(4), Zp(7)]), BeDOZaMACList([Zp(2), Zp(75), Zp(23), Zp(2)]))
        y = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(3), Zp(2), Zp(1)]), BeDOZaMACList([Zp(2), Zp(74), Zp(23), Zp(2)]))
        z = runtime._minus((x, y), Zp)
        self.assertEquals(z.get_value(), Zp(0))
        self.assertEquals(z.get_keys(), BeDOZaKeyList(Zp(23), [Zp(2), Zp(2), Zp(6)]))
        self.assertEquals(z.get_macs(), BeDOZaMACList([Zp(0), Zp(1), Zp(0), Zp(0)]))

    @protocol
    def test_sub(self, runtime):
        """Test subtraction of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 0)

        x2 = runtime.random_share(Zp)
        y2 = runtime.random_share(Zp)
        z2 = runtime.sub(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_minus(self, runtime):
        """Test subtraction of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 0)

        x2 = runtime.random_share(Zp)
        y2 = runtime.random_share(Zp)
        z2 = x2 - y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_constant_right(self, runtime):
        """Test subtraction of secret shared number and a public number."""

        Zp = GF(31)

        y = 4

        def check(v):
            self.assertEquals(v, 2)

        x2 = runtime.random_share(Zp)
        z2 = x2 - y
        d = runtime.open(x2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_constant_left(self, runtime):
        """Test subtraction of a public number and secret shared number."""

        Zp = GF(31)

        y = 8

        def check(v):
            self.assertEquals(v, 2)

        x2 = runtime.random_share(Zp)
        z2 = y - x2
        d = runtime.open(x2)
        d.addCallback(check)
        return d

    @protocol
    def test_constant_multiplication_constant_left(self, runtime):
        """Test multiplication of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 6
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.random_share(Zp)

        z2 = runtime._cmul(Zp(y1), x2, Zp)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_constant_multiplication_constant_right(self, runtime):
        """Test multiplication of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 6
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.random_share(Zp)

        z2 = runtime._cmul(x2, Zp(y1), Zp)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_get_triple(self, runtime):
        """Test generation of a triple."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)
      
        def check((a, b, c)):
            self.assertEquals(c, a * b)

        (a, b, c), _ = runtime._get_triple(Zp)
        d1 = runtime.open(a)
        d2 = runtime.open(b)
        d3 = runtime.open(c)
        d = gather_shares([d1, d2, d3])
        d.addCallback(check)
        return d

    @protocol
    def test_basic_multiply(self, runtime):
        """Test multiplication of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 6
        y1 = 6

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.random_share(Zp)
        y2 = runtime.random_share(Zp)

        (a, b, c), _ = runtime._get_triple(Zp)
        z2 = runtime._basic_multiplication(x2, y2, a, b, c)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_mul_mul(self, runtime):
        """Test multiplication of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 6
        y1 = 6

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.random_share(Zp)
        y2 = runtime.random_share(Zp)

        z2 = x2 * y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d
    @protocol
    def test_basic_multiply_constant_right(self, runtime):
        """Test multiplication of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 6
        y1 = 6

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.random_share(Zp)

        (a, b, c), _ = runtime._get_triple(Zp)
        z2 = runtime._basic_multiplication(x2, Zp(y1), a, b, c)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_basic_multiply_constant_left(self, runtime):
        """Test multiplication of two numbers."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 6
        y1 = 6

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.random_share(Zp)

        (a, b, c), _ = runtime._get_triple(Zp)
        z2 = runtime._basic_multiplication(Zp(y1), x2, a, b, c)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_open_multiple_secret_share(self, runtime):
        """Test sharing and open of a number."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(ls):
            for v in ls:
                self.assertEquals(v, 6)

        x = runtime.random_share(Zp)
        y = runtime.random_share(Zp)
        d = runtime.open_multiple_values([x, y])
        d.addCallback(check)
        return d

    @protocol
    def test_open_two_secret_share(self, runtime):
        """Test sharing and open of a number."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check((a, b)):
            self.assertEquals(a, 6)
            self.assertEquals(b, 6)

        x = runtime.random_share(Zp)
        y = runtime.random_share(Zp)
        d = runtime.open_two_values(x, y)
        d.addCallback(check)
        return d
