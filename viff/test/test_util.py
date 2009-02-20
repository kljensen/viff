# Copyright 2007, 2008 VIFF Development Team.
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

"""Tests for viff.util."""

import os

from viff.util import deep_wait
from viff.field import GF, GF256
from viff import shamir, prss

from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred

#: Declare doctests for Trial.
__doctests__ = ['viff.util']


class FakeTest(TestCase):
    """Tests for :func:`viff.util.fake`."""

    # Modules which will be reloaded with and without VIFF_FAKE set in
    # the environment.
    _modules = [shamir, prss]

    def setUp(self):
        self.field = GF(1031)

        os.environ['VIFF_FAKE'] = "*"
        for module in self._modules:
            reload(module)

    def tearDown(self):
        del os.environ['VIFF_FAKE']
        for module in self._modules:
            reload(module)

    def test_shamir_share(self):
        secret = self.field(17)
        shares = shamir.share(secret, 1, 3)
        self.assertEquals(shares[0][1], secret)
        self.assertEquals(shares[1][1], secret)
        self.assertEquals(shares[2][1], secret)

    def test_shamir_recombine(self):
        shares = [(1, 1), None, None]
        self.assertEquals(shamir.recombine(shares), 1)

    def test_prss(self):
        share = prss.prss(None, None, self.field, None, None)
        self.assertEquals(share, self.field(7))

    def test_prss_lsb(self):
        (share, bit) = prss.prss_lsb(None, None, self.field, None, None)
        self.assertEquals(share, self.field(7))
        self.assertEquals(bit, GF256(1))

    def test_prss_zero(self):
        share = prss.prss_zero(None, None, None, self.field, None, None)
        self.assertEquals(share, self.field(0))


class DeepWaitTest(TestCase):
    """Tests for :func:`viff.util.deep_wait`."""

    def setUp(self):
        self.calls = []

    def test_trivial_wait(self):
        w = deep_wait("not a Deferred")
        w.addCallback(lambda _: self.calls.append("w"))
        self.assertIn("w", self.calls)

    def test_simple_wait(self):
        a = Deferred()
        a.addCallback(self.calls.append)

        w = deep_wait(a)
        w.addCallback(lambda _: self.calls.append("w"))

        self.assertNotIn("w", self.calls)
        a.callback("a")
        self.assertIn("w", self.calls)

    def test_tuple_wait(self):
        a = Deferred()
        b = Deferred()

        a.addCallback(self.calls.append)
        b.addCallback(self.calls.append)

        w = deep_wait((a, 123, b))
        w.addCallback(lambda _: self.calls.append("w"))

        self.assertNotIn("w", self.calls)
        a.callback("a")
        self.assertNotIn("w", self.calls)
        b.callback("b")
        self.assertIn("w", self.calls)

    def test_list_wait(self):
        a = Deferred()
        b = Deferred()

        a.addCallback(self.calls.append)
        b.addCallback(self.calls.append)

        w = deep_wait([a, 123, b])
        w.addCallback(lambda _: self.calls.append("w"))

        self.assertNotIn("w", self.calls)
        a.callback("a")
        self.assertNotIn("w", self.calls)
        b.callback("b")
        self.assertIn("w", self.calls)

    def test_deep_wait(self):
        a = Deferred()
        b = Deferred()

        def return_b(_):
            """Callbacks which return a Deferred."""
            self.calls.append("return_b")
            return b

        a.addCallback(self.calls.append)
        a.addCallback(return_b)

        w = deep_wait(a)
        w.addCallback(lambda _: self.calls.append("w"))

        self.assertNotIn("a", self.calls)
        a.callback("a")
        self.assertIn("a", self.calls)
        self.assertIn("return_b", self.calls)
        self.assertNotIn("w", self.calls)
        self.assertNotIn("b", self.calls)

        b.callback("b")
        self.assertIn("w", self.calls)

    def test_mixed_deep_wait(self):
        a = Deferred()
        b = Deferred()

        def return_mix(_):
            """Callbacks which return a Deferred and an integer."""
            self.calls.append("return_mix")
            return (b, 42)

        a.addCallback(self.calls.append)
        a.addCallback(return_mix)

        w = deep_wait(a)
        w.addCallback(lambda _: self.calls.append("w"))

        self.assertNotIn("a", self.calls)
        a.callback("a")
        self.assertIn("a", self.calls)
        self.assertIn("return_mix", self.calls)
        self.assertNotIn("w", self.calls)

        b.callback("b")
        self.assertIn("w", self.calls)

    def test_complex_deep_wait(self):
        a = Deferred()
        b = Deferred()
        c = Deferred()
        d = Deferred()

        a.addCallback(self.calls.append)
        b.addCallback(self.calls.append)
        c.addCallback(self.calls.append)
        d.addCallback(self.calls.append)

        def return_b(_):
            self.calls.append("return_b")
            return (b, 42)

        def return_c_d(_):
            self.calls.append("return_c")
            return [(1, 2), "testing", [c, True], (d, 10)]

        a.addCallback(return_b)
        b.addCallback(return_c_d)

        w = deep_wait(a)
        w.addCallback(lambda _: self.calls.append("w"))

        a.callback("a")
        self.assertNotIn("w", self.calls)

        c.callback("c")
        self.assertNotIn("w", self.calls)

        b.callback("b")
        self.assertNotIn("w", self.calls)

        d.callback("d")
        self.assertIn("w", self.calls)
