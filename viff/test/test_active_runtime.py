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

from twisted.internet.defer import gatherResults

from viff.test.util import RuntimeTestCase, protocol
from viff.runtime import ActiveRuntime, Share


class ActiveRuntimeTest(RuntimeTestCase):
    """Test for active security."""

    #: Number of players.
    #:
    #: The protocols for active security needs n > 3t+1, so with the
    #: default threshold of t=1, we need n=4.
    num_players = 4

    runtime_class = ActiveRuntime

    @protocol
    def test_broadcast(self, runtime):
        """Test Bracha broadcast."""
        # TODO: Figure out how to introduce network errors and test
        # those too.
        if runtime.id == 1:
            x = runtime.broadcast([1], "Hello world!")
        else:
            x = runtime.broadcast([1])

        if runtime.id == 2:
            y, z = runtime.broadcast([2, 3], "Hello two!")
        elif runtime.id == 3:
            y, z = runtime.broadcast([2, 3], "Hello three!")
        else:
            y, z = runtime.broadcast([2, 3])

        x.addCallback(self.assertEquals, "Hello world!")
        y.addCallback(self.assertEquals, "Hello two!")
        z.addCallback(self.assertEquals, "Hello three!")
        return gatherResults([x, y, z])

    @protocol
    def test_double_share_random(self, runtime):
        """Test double-share random numbers."""
        T = runtime.num_players - 2 * runtime.threshold
        from viff.field import GF
        self.Zp = GF(11)

        r_t, r_2t = runtime.double_share_random(T,
                                                runtime.threshold,
                                                2*runtime.threshold,
                                                self.Zp)

        # Check that we got the expected number of shares.
        self.assertEquals(len(r_t), T)
        self.assertEquals(len(r_2t), T)

        def verify(shares):
            """Verify that the list contains two equal shares."""
            self.assertEquals(shares[0], shares[1])

        results = []
        for a, b in zip(r_t, r_2t):
            self.assert_type(a, Share)
            self.assert_type(b, Share)
            open_a = runtime.open(a)
            open_b = runtime.open(b, threshold=2*runtime.threshold)
            result = gatherResults([open_a, open_b])
            result.addCallback(verify)
            results.append(result)
        return gatherResults(results)

    @protocol
    def test_generate_triples(self, runtime):
        """Test generation of multiplication triples."""
        triples = runtime.generate_triples(self.Zp)

        def verify(triple):
            """Verify a multiplication triple."""
            self.assertEquals(triple[0] * triple[1], triple[2])

        results = []
        for a, b, c in triples:
            self.assert_type(a, Share)
            self.assert_type(b, Share)
            self.assert_type(c, Share)
            open_a = runtime.open(a)
            open_b = runtime.open(b)
            open_c = runtime.open(c)
            result = gatherResults([open_a, open_b, open_c])
            result.addCallback(verify)
            results.append(result)
        return gatherResults(results)
