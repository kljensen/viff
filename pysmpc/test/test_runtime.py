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
from twisted.internet.defer import gatherResults
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
                    self.connections[(self.id, id)] = loopbackAsync(server, client)

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
            shares = [(IntegerFieldElement(i+1), s) for i,s in enumerate(shares)]
            self.assertEquals(shamir.recombine(shares), value)

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
