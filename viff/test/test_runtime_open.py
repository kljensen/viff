# Copyright 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

"""Tests for the open protocol in the viff.runtime."""

from twisted.internet.defer import gatherResults

from viff.runtime import Share, gather_shares
from viff.test.util import RuntimeTestCase, protocol


class RuntimeOpenTest(RuntimeTestCase):
    """Tests the open protocol in L{viff.runtime.Runtime}."""

    # TODO: Test open of GF256 sharings?
    # TODO: Test with various threshold?

    @protocol
    def test_all_players_receive_implicit(self, runtime):
        """Shamir share and open Zp(42)."""
        # The parties have shares 43, 44, 45 respectively.
        share = Share(runtime, self.Zp, self.Zp(42 + runtime.id))
        opened = runtime.open(share)
        self.assertTrue(isinstance(opened, Share))
        opened.addCallback(self.assertEquals, 42)
        return opened

    @protocol
    def test_open_does_not_mutate_share(self, runtime):
        """Test that opening a share does not change it."""
        # The parties have shares 43, 44, 45 respectively.
        share = Share(runtime, self.Zp, self.Zp(42 + runtime.id))
        opened = runtime.open(share)
        opened.addCallback(self.assertEquals, 42)
        share.addCallback(self.assertEquals, 42 + runtime.id)
        return opened

    @protocol
    def test_different_subsets_of_receivers_get_the_same_result(self, runtime):
        """Test that two different subsets of the players obtain the same
        result."""
        res = []
        share = runtime.prss_share_random(self.Zp)
        a = runtime.open(share)
        res.append(a)
        receivers = runtime.players.keys()[0:2]
        if runtime.id in receivers:
            b = runtime.open(share, receivers)
            c = gather_shares([a, b])
            c.addCallback(lambda (a, b): self.assertEquals(a, b))
            res.append(c)
        else:
            runtime.open(share, receivers)
        return gatherResults(res)

    def _test_open(self, runtime, receivers):

        # TODO: Test also with more natural sharings.
        secret = 42
        share = Share(runtime, self.Zp, self.Zp(secret + runtime.id))

        if runtime.id in receivers:
            opened = runtime.open(share, receivers)
            self.assertTrue(isinstance(opened, Share))
            opened.addCallback(self.assertEquals, secret)
            return opened
        else:
            foo = runtime.open(share, receivers)
            self.assertEquals(None, foo)

    @protocol
    def test_all_players_receive_explicit(self, runtime):
        """Tests symmetric opening of Shamir sharing, i.e. where
        all players receive the result."""
        receivers = range(1, len(runtime.players) + 1)
        return self._test_open(runtime, receivers)

    @protocol
    def test_all_but_one_player_receive(self, runtime):
        """Tests asymmetric opening of Shamir shares where
        all but one player receive the result."""
        r = self.shared_rand[runtime.id]
        receivers = r.sample(range(1, len(runtime.players) + 1),
                             len(runtime.players) - 1)
        return self._test_open(runtime, receivers)

    @protocol
    def test_only_one_player_receives(self, runtime):
        """Tests opening of Shamir sharing where only
        one player receives the result."""
        r = self.shared_rand[runtime.id]
        receiver = r.sample(range(1, len(runtime.players) + 1), 1)
        return self._test_open(runtime, receiver)

    @protocol
    def test_random_number_of_players_receive(self, runtime):
        """Tests opening of Shamir sharing where some random
        number of players (between 2 and number of players - 1)
        submit their shares."""
        r = self.shared_rand[runtime.id]
        no_of_receivers = r.randint(2, len(runtime.players) - 1)
        receivers = r.sample(range(1, len(runtime.players) + 1),
                             no_of_receivers)
        return self._test_open(runtime, receivers)
