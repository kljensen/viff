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

import operator

from twisted.internet.defer import gatherResults

from viff.test.util import RuntimeTestCase, protocol, BinaryOperatorTestCase
from viff.runtime import Share
from viff.active import BasicActiveRuntime, ActiveRuntime, \
    BrachaBroadcastMixin, TriplesHyperinvertibleMatricesMixin

class MulTest(BinaryOperatorTestCase, RuntimeTestCase):
    operator = operator.mul
    runtime_class = ActiveRuntime

class TriplesHyper(BasicActiveRuntime, TriplesHyperinvertibleMatricesMixin):
    pass

class TriplesHyperTest(RuntimeTestCase):
    """Test for preprocessing with hyperinvertible matrices."""

    #: Number of players.
    #:
    #: The protocols for active security needs n > 3t+1, so with the
    #: default threshold of t=1, we need n=4.
    num_players = 4

    runtime_class = TriplesHyper

    @protocol
    def test_single_share_random(self, runtime):
        """Test sharing of random numbers."""
        T = runtime.num_players - 2 * runtime.threshold

        def check(shares):
            # Check that we got the expected number of shares.
            self.assertEquals(len(shares), T)

            results = []
            for share in shares:
                self.assert_type(share, Share)

        shares = runtime.single_share_random(T, runtime.threshold, self.Zp)
        shares.addCallback(check)
        return shares

    @protocol
    def test_double_share_random(self, runtime):
        """Test double-share random numbers."""
        T = runtime.num_players - 2 * runtime.threshold

        def verify(shares):
            """Verify that the list contains two equal shares."""
            self.assertEquals(shares[0], shares[1])

        def check(double):
            r_t, r_2t = double

            # Check that we got the expected number of shares.
            self.assertEquals(len(r_t), T)
            self.assertEquals(len(r_2t), T)

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

        double = runtime.double_share_random(T, runtime.threshold,
                                             2*runtime.threshold, self.Zp)
        runtime.schedule_callback(double, check)
        return double

    @protocol
    def test_generate_triples(self, runtime):
        """Test generation of multiplication triples."""

        def verify(triple):
            """Verify a multiplication triple."""
            self.assertEquals(triple[0] * triple[1], triple[2])

        def check(triple):
            a, b, c = triple
            self.assert_type(a, self.Zp)
            self.assert_type(b, self.Zp)
            self.assert_type(c, self.Zp)
            open_a = runtime.open(Share(self, self.Zp, a))
            open_b = runtime.open(Share(self, self.Zp, b))
            open_c = runtime.open(Share(self, self.Zp, c))
            result = gatherResults([open_a, open_b, open_c])
            result.addCallback(verify)
            return result

        triples = runtime.generate_triples(self.Zp)
        self.assertEquals(len(triples), runtime.num_players - 2*runtime.threshold)

        for triple in triples:
            runtime.schedule_callback(triple, check)
        return triples


class BrachaBroadcastRuntime(ActiveRuntime, BrachaBroadcastMixin):
    pass

class BrachaBroadcastTest(RuntimeTestCase):
    """Test for active security."""

    #: Number of players.
    #:
    #: The protocols for active security needs n > 3t+1, so with the
    #: default threshold of t=1, we need n=4.
    num_players = 4

    runtime_class = BrachaBroadcastRuntime

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
