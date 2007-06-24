# Copyright 2007 Martin Geisler
#
# This file is part of PySMPC
#
# PySMPC is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PySMPC is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PySMPC in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

# Extra debugging support which shows where each lingering deferred
# was created.
import twisted.internet.base
twisted.internet.base.DelayedCall.debug = True

from twisted.internet import reactor
from twisted.internet.defer import Deferred, succeed, gatherResults
from twisted.internet.protocol import Protocol
from twisted.trial.unittest import TestCase
from twisted.protocols.loopback import loopbackAsync

from pysmpc.field import IntegerFieldElement, GF256Element
from pysmpc.runtime import Runtime, ShareExchanger
from pysmpc.generate_config import generate_configs, load_config
from pysmpc import shamir


class LoopbackRuntime(Runtime):

    def __init__(self, players, id, threshold, connections, runtimes):
        self.connections = connections
        self.runtimes = runtimes
        self.real_protocols = {}
        Runtime.__init__(self, players, id, threshold)

    def connect(self):
        for id in self.players:
            # There is no connection back to ourselves
            if id != self.id:
                protocol = ShareExchanger(id)
                # The ShareExchanger protocol uses its factory for
                # accessing the incoming_shares dictionary, which
                # actually comes from the runtime. So self is an okay
                # factory here. TODO: Remove the factory?
                protocol.factory = self
                # TODO: is there any need to schedule this instead of
                # simply executing the callback directly? Or assign a
                # defer.succeed(protocol) to self.protocols[id].
                reactor.callLater(0, self.protocols[id].callback, protocol)
                self.real_protocols[id] = protocol

                if id > self.id:
                    # Make a "connection" to the other player. We are
                    # the client (because we innitiate the connection)
                    # and the other player is the server.
                    client = protocol
                    server = self.runtimes[id].real_protocols[self.id]
                    key = (self.id, id)
                    self.connections[key] = loopbackAsync(server, client)


# TODO: find a way to specify the program for each player once and run
# it several times.

class RuntimeTestCase(TestCase):
    
    def setUp(self):
        IntegerFieldElement.modulus = 1031

        configs = generate_configs(3, 1)
        connections = {}
        runtimes = {}

        id, players = load_config(configs[3])
        self.rt3 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[3] = self.rt3

        id, players = load_config(configs[2])
        self.rt2 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[2] = self.rt2

        id, players = load_config(configs[1])
        self.rt1 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[1] = self.rt1

    def test_open(self):
        """
        Shamir share a value and open it.
        """
        
        input = IntegerFieldElement(42)
        a, b, c = shamir.share(input, 1, 3)

        a = succeed(a[1])
        b = succeed(b[1])
        c = succeed(c[1])

        self.rt1.open(a)
        self.rt2.open(b)
        self.rt3.open(c)

        a.addCallback(self.assertEquals, input)
        b.addCallback(self.assertEquals, input)
        c.addCallback(self.assertEquals, input)

        return gatherResults([a, b, c])

    def test_open_deferred(self):
        """
        Shamir share a value and open it, but let some of the shares
        arrive "late" to the runtimes.
        """
        input = IntegerFieldElement(42)
        shares = shamir.share(input, 1, 3)
        
        a = Deferred()
        b = succeed(shares[1][1])
        c = Deferred()

        self.rt1.open(a)
        self.rt2.open(b)
        self.rt3.open(c)

        a.addCallback(self.assertEquals, input)
        b.addCallback(self.assertEquals, input)
        c.addCallback(self.assertEquals, input)

        # TODO: This looks funny because shamir.share return a list of
        # (player-id, share) tuples. Maybe it should be changed so
        # that it simply returns a list of shares?
        a.callback(shares[0][1])
        c.callback(shares[2][1])

        return gatherResults([a, b, c])

    # TODO: factor out common code from test_add* and test_sub*.

    def test_add(self):
        share_a = Deferred()
        share_b = succeed(IntegerFieldElement(200))
        share_c = self.rt1.add(share_a, share_b)

        share_c.addCallback(self.assertEquals, IntegerFieldElement(300))
        share_a.callback(IntegerFieldElement(100))
        return share_c

    def test_add_coerce(self):
        share_a = Deferred()
        share_b = IntegerFieldElement(200)
        share_c = self.rt1.add(share_a, share_b)

        share_c.addCallback(self.assertEquals, IntegerFieldElement(300))
        share_a.callback(IntegerFieldElement(100))
        return share_c

    def test_sub(self):
        share_a = succeed(IntegerFieldElement(200))
        share_b = Deferred()
        share_c = self.rt1.sub(share_a, share_b)

        share_c.addCallback(self.assertEquals, IntegerFieldElement(100))
        share_b.callback(IntegerFieldElement(100))
        return share_c

    def test_sub_coerce(self):
        share_a = IntegerFieldElement(200)
        share_b = Deferred()
        share_c = self.rt1.sub(share_a, share_b)

        share_c.addCallback(self.assertEquals, IntegerFieldElement(100))
        share_b.callback(IntegerFieldElement(100))
        return share_c

    def test_mul(self):
        shares_a = shamir.share(IntegerFieldElement(20), 1, 3)
        shares_b = shamir.share(IntegerFieldElement(30), 1, 3)

        res1 = self.rt1.mul(shares_a[0][1], shares_b[0][1])
        res2 = self.rt1.mul(shares_a[1][1], shares_b[1][1])
        res3 = self.rt1.mul(shares_a[2][1], shares_b[2][1])

        def recombine(shares):
            ids = map(IntegerFieldElement, range(1, len(shares) + 1))
            return shamir.recombine(zip(ids, shares))

        res = gatherResults([res1, res2, res3])
        res.addCallback(recombine)
        res.addCallback(self.assertEquals, IntegerFieldElement(600))

    def test_xor(self):

        def first(sequence):
            return [x[0] for x in sequence]

        def second(sequence):
            return [x[1] for x in sequence]

        results = []
        for a, b in (0,0), (0,1), (1,0), (1,1):
            int_a = IntegerFieldElement(a)
            int_b = IntegerFieldElement(b)

            bit_a = GF256Element(a)
            bit_b = GF256Element(b)
        
            int_a_shares = second(shamir.share(int_a, 1, 3))
            int_b_shares = second(shamir.share(int_b, 1, 3))

            bit_a_shares = second(shamir.share(bit_a, 1, 3))
            bit_b_shares = second(shamir.share(bit_b, 1, 3))

            int_res1 = self.rt1.xor_int(int_a_shares[0], int_b_shares[0])
            int_res2 = self.rt2.xor_int(int_a_shares[1], int_b_shares[1])
            int_res3 = self.rt3.xor_int(int_a_shares[2], int_b_shares[2])

            for res in int_res1, int_res2, int_res3:
                res.addCallback(self.assertEquals, IntegerFieldElement(a ^ b))

            bit_res1 = self.rt1.xor_bit(bit_a_shares[0], bit_b_shares[0])
            bit_res2 = self.rt2.xor_bit(bit_a_shares[1], bit_b_shares[1])
            bit_res3 = self.rt3.xor_bit(bit_a_shares[2], bit_b_shares[2])

            for res in bit_res1, bit_res2, bit_res3:
                res.addCallback(self.assertEquals, IntegerFieldElement(a ^ b))

            results.extend([int_res1, int_res2, int_res3,
                            bit_res1, bit_res2, bit_res3])
                
        return gatherResults(results)


class ShareTestCase(TestCase):

    def setUp(self):
        IntegerFieldElement.modulus = 1031

    def test_share(self):
        configs = generate_configs(3, 1)
        connections = {}
        runtimes = {}

        id, players = load_config(configs[3])
        rt3 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[3] = rt3

        id, players = load_config(configs[2])
        rt2 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[2] = rt2

        id, players = load_config(configs[1])
        rt1 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[1] = rt1

        a = IntegerFieldElement(10)
        b = IntegerFieldElement(20)
        c = IntegerFieldElement(30)

        a1, b1, c1 = rt1.shamir_share(a)
        a2, b2, c2 = rt2.shamir_share(b)
        a3, b3, c3 = rt3.shamir_share(c)

        def check_recombine(shares, value):
            ids = map(IntegerFieldElement, range(1, len(shares) + 1))
            self.assertEquals(shamir.recombine(zip(ids, shares)), value)

        a_shares = gatherResults([a1, a2, a3])
        a_shares.addCallback(check_recombine, a)

        b_shares = gatherResults([b1, b2, b3])
        b_shares.addCallback(check_recombine, b)

        c_shares = gatherResults([c1, c2, c3])
        c_shares.addCallback(check_recombine, c)

        rt1.open(a1)
        rt2.open(a2)
        rt3.open(a3)

        rt1.open(b1)
        rt2.open(b2)
        rt3.open(b3)

        rt1.open(c1)
        rt2.open(c2)
        rt3.open(c3)

        a1.addCallback(self.assertEquals, a)
        a2.addCallback(self.assertEquals, a)
        a3.addCallback(self.assertEquals, a)

        b1.addCallback(self.assertEquals, b)
        b2.addCallback(self.assertEquals, b)
        b3.addCallback(self.assertEquals, b)

        c1.addCallback(self.assertEquals, c)
        c2.addCallback(self.assertEquals, c)
        c3.addCallback(self.assertEquals, c)

        # TODO: ought to wait on connections.values() as well
        wait = gatherResults([a1, a2, a3, b1, b2, b3, c1, c2, c3])
        return wait

    test_share.timeout = 1




class ComparisonTestCase(TestCase):

    skip = "Not yet reliable."

    def test_compare(self):
        IntegerFieldElement.modulus = 2039

        configs = generate_configs(3, 1)
        connections = {}
        runtimes = {}

        id, players = load_config(configs[3])
        rt3 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[3] = rt3

        id, players = load_config(configs[2])
        rt2 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[2] = rt2

        id, players = load_config(configs[1])
        rt1 = LoopbackRuntime(players, id, 1, connections, runtimes)
        runtimes[1] = rt1

        a = IntegerFieldElement(10)
        b = IntegerFieldElement(20)
        c = IntegerFieldElement(30)

        a1, b1, c1 = rt1.shamir_share(a)
        a2, b2, c2 = rt2.shamir_share(b)
        a3, b3, c3 = rt3.shamir_share(c)

        res_ab1 = rt1.greater_than(a1, b1)
        res_ab2 = rt2.greater_than(a2, b2)
        res_ab3 = rt3.greater_than(a3, b3)

        rt1.open(res_ab1)
        rt2.open(res_ab2)
        rt3.open(res_ab3)

        res_ab1.addCallback(self.assertEquals, GF256Element(a >= b))
        #res_ab2.addCallback(self.assertEquals, GF256Element(a >= b))
        #res_ab3.addCallback(self.assertEquals, GF256Element(a >= b))

        #wait = gatherResults([a1, a2, a3, b1, b2, b3, c1, c2, c3,
        #                      res_ab1, res_ab2, res_ab3])
        return gatherResults([a1, a2, a3, b1, b2, b3, c1, c2, c3,
                              res_ab1, res_ab2, res_ab3])

    
