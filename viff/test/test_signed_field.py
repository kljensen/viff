# Copyright 2009 VIFF Development Team.
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

# Import system packages.
import sys

from twisted.trial.unittest import TestCase

# Import VIFF packages.
from viff.field import GF

p = 30916444023318367583
Zp = GF(p)

class SignedVsUnsignedTest(TestCase):

    def test_zero_minus_one_signed(self):
        x = Zp(0)
        y = Zp(1)
        z = x - y
        self.assertEquals(z.signed(), -1)       

    def test_zero_minus_one_unsigned(self):
        x = Zp(0)
        y = Zp(1)
        z = x - y
        self.assertEquals(z.unsigned(), p-1)       

    def test_maxint_plus_42_signed(self):
        x = Zp(p)
        y = Zp(42)
        z = x + y
        self.assertEquals(z.signed(), 42)

    def test_little_subtracted_big_signed(self):
        x = Zp(14)
        y = Zp(42)
        z = x - y
        self.assertEquals(z.signed(), -28)       

    def test_little_subtracted_big_unsigned(self):
        x = Zp(14)
        y = Zp(42)
        z = x - y
        self.assertEquals(z.unsigned(), p-28)       

    def test_big_subtracted_little_signed(self):
        x = Zp(42)
        y = Zp(14)
        z = x - y
        self.assertEquals(z.signed(), 28)       

    def test_big_subtracted_little_unsigned(self):
        x = Zp(42)
        y = Zp(14)
        z = x - y
        self.assertEquals(z.unsigned(), 28)       

    def test_little_add_big_signed(self):
        x = Zp(1)
        y = Zp(p)
        z = x + y
        self.assertEquals(z.signed(), 1)

    def test_little_add_big_unsigned(self):
        x = Zp(1)
        y = Zp(p)
        z = x + y
        self.assertEquals(z.unsigned(), 1)

    def test_maxint_signed(self):
        phalf = (p-1)/2
        x = Zp(phalf)
        y = Zp(1)
        z = x + y 
        self.assertEquals(z.signed(), -phalf)
