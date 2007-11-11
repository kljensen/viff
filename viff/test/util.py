# Copyright 2007 Martin Geisler
#
# This file is part of VIFF
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

from twisted.internet import reactor
from twisted.trial.unittest import TestCase
from twisted.protocols.loopback import loopbackAsync

from viff.runtime import Runtime, ShareExchanger
from viff.field import GF
from viff.config import generate_configs, load_config

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
                protocol = ShareExchanger(id, self)
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
                    # the client (because we initiate the connection)
                    # and the other player is the server.
                    client = protocol
                    server = self.runtimes[id].real_protocols[self.id]
                    key = (self.id, id)
                    self.connections[key] = loopbackAsync(server, client)


class RuntimeTestCase(TestCase):
    
    def setUp(self):
        # Our standard 65 bit Blum prime 
        self.Zp = GF(30916444023318367583)

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
