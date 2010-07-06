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
from viff.bedoza import BeDOZaRuntime, BeDOZaShare, BeDOZaKeyList, BeDOZaMessageList
from viff.field import FieldElement, GF
from viff.util import rand

class KeyLoaderTest(RuntimeTestCase):
    """Test of KeyLoader."""

    # Number of players.
    num_players = 3

    runtime_class = BeDOZaRuntime

    @protocol
    def test_load_keys(self, runtime):
        """Test loading of keys."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        keys = runtime.load_keys(self.Zp)
        keys1 = keys[1]
        keys2 = keys[2]
        keys3 = keys[3]
        if runtime.id == 1:
            betas = keys1[1]
            self.assertEquals(betas[0], 1)
            self.assertEquals(betas[1], 2)
            self.assertEquals(betas[2], 3)
        if runtime.id == 2:
            betas = keys2[1]
            self.assertEquals(betas[0], 4)
            self.assertEquals(betas[1], 5)
            self.assertEquals(betas[2], 6)
        if runtime.id == 3:
            betas = keys3[1]
            self.assertEquals(betas[0], 7)
            self.assertEquals(betas[1], 8)
            self.assertEquals(betas[2], 9)

    @protocol
    def test_authentication_codes(self, runtime):
        """Test generating random shares."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        runtime.keys = runtime.load_keys(self.Zp)

        v = self.Zp(2)
        alpha = runtime.get_keys()[0]
        codes = self.num_players * [None]

        for xid in runtime.players.keys():
            keys = map(lambda (alpha, akeys): (alpha, akeys[xid - 1]), runtime.keys.values())
            codes[xid-1] = runtime.authentication_codes(keys, v).auth_codes
        
        if runtime.id == 1:
            my_codes = codes[0]
            self.assertEquals(my_codes[0], self.Zp(5))
            self.assertEquals(my_codes[1], self.Zp(10))
            self.assertEquals(my_codes[2], self.Zp(15))
        if runtime.id == 2:
            my_codes = codes[1]
            self.assertEquals(my_codes[0], self.Zp(6))
            self.assertEquals(my_codes[1], self.Zp(11))
            self.assertEquals(my_codes[2], self.Zp(16))
        if runtime.id == 3:
            my_codes = codes[2]
            self.assertEquals(my_codes[0], self.Zp(7))
            self.assertEquals(my_codes[1], self.Zp(12))
            self.assertEquals(my_codes[2], self.Zp(17))

    @protocol
    def test_messagelist(self, runtime):
        """Test loading of keys."""

        Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        m1 = BeDOZaMessageList([Zp(2), Zp(34)])
        m2 = BeDOZaMessageList([Zp(11), Zp(4)])
        m3 = m1 + m2
        self.assertEquals(m3.auth_codes[0], 13)
        self.assertEquals(m3.auth_codes[1], 38)
        self.assertEquals(len(m3.auth_codes), 2)
        return m3
        


class BeDOZaBasicCommandsTest(RuntimeTestCase):
    """Test for basic commands."""

    # Number of players.
    num_players = 3

    runtime_class = BeDOZaRuntime

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

