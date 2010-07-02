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
from viff.bedoza import BeDOZaRuntime, BeDOZaShare
from viff.field import FieldElement, GF
from viff.util import rand

class BeDOZaBasicCommandsTest(RuntimeTestCase):
    """Test for basic commands."""

    # Number of players.
    num_players = 3

    runtime_class = BeDOZaRuntime

    @protocol
    def test_secret_share(self, runtime):
        """Test sharing of random numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check((xi, Ks)):
            # Check that we got the expected number of shares.
            self.assert_type(xi, FieldElement)
            self.assert_type(Ks[0], FieldElement)
            self.assert_type(Ks[1], FieldElement)
            self.assert_type(Ks[2], FieldElement)

        if 1 == runtime.id:
            share = runtime.secret_share([1], self.Zp, 42)
        else:
            share = runtime.secret_share([1], self.Zp)
        share.addCallback(check)
        return share

    @protocol
    def test_open_secret_share(self, runtime):
        """Test sharing and open of a number."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 42)

        if 1 == runtime.id:
            x = runtime.secret_share([1], self.Zp, 42)
        else:
            x = runtime.secret_share([1], self.Zp)
        d = runtime.open(x)
        d.addCallback(check)
        return d

    @protocol
    def test_random_share(self, runtime):
        """Test creation of a random shared number."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(True, True)

        x = runtime.random_share(self.Zp)
        d = runtime.open(x)
        d.addCallback(check)
        return d

    @protocol
    def test_sum(self, runtime):
        """Test addition of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 + y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = runtime.add(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_plus(self, runtime):
        """Test addition of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 + y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = x2 + y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_constant(self, runtime):
        """Test addition of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 + y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        z2 = x2 + y1
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub(self, runtime):
        """Test subtration of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 - y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = runtime.sub(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_minus(self, runtime):
        """Test subtration of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 - y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = x2 - y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_constant(self, runtime):
        """Test subtration of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 - y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        z2 = x2 - y1
        d = runtime.open(z2)
        d.addCallback(check)
        return d

BeDOZaBasicCommandsTest.skip = "Skipped because the tested code is not implemented."
