# Copyright 2007 Martin Geisler
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

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, gatherResults
from twisted.trial.unittest import TestCase
from twisted.protocols.loopback import loopbackAsync

from viff.runtime import Runtime, ShareExchanger, ShareExchangerFactory
from viff.field import GF
from viff.config import generate_configs, load_config

def protocol(method):
    def wrapper(self):
        def cb_method(runtime):
            return method(self, runtime)

        self.rt1.addCallback(cb_method)
        self.rt2.addCallback(cb_method)
        self.rt3.addCallback(cb_method)
        return gatherResults([self.rt1, self.rt2, self.rt3])
    wrapper.func_name = method.func_name
    return wrapper

def create_loopback_runtime(id, players, threshold, protocols):
    # This will yield a Runtime when all protocols are connected.
    result = Deferred()

    # Create a runtime that knows about no other players than itself.
    # It will eventually be returned in result when the factory has
    # determined that all needed protocols are ready.
    runtime = Runtime(players[id], threshold)
    needed_protocols = len(players) - 1
    factory = ShareExchangerFactory(runtime, players, needed_protocols, result)

    for peer_id in players:
        if peer_id != id:
            protocol = ShareExchanger()
            protocol.factory = factory

            # Keys for when we are the client and when we are the server.
            client_key = (id, peer_id)
            server_key = (peer_id, id)
            # Store a protocol used when we are the server.
            protocols[server_key] = protocol

            if peer_id > id:
                # Make a "connection" to the other player. We are
                # the client (because we initiate the connection)
                # and the other player is the server.
                client = protocols[client_key]
                server = protocols[server_key]
                loopbackAsync(server, client)

    return result

class RuntimeTestCase(TestCase):
    
    def setUp(self):
        # Our standard 65 bit Blum prime 
        self.Zp = GF(30916444023318367583)

        configs = generate_configs(3, 1)
        protocols = {}

        id, players = load_config(configs[3])
        self.rt3 = create_loopback_runtime(id, players, 1, protocols)

        id, players = load_config(configs[2])
        self.rt2 = create_loopback_runtime(id, players, 1, protocols)

        id, players = load_config(configs[1])
        self.rt1 = create_loopback_runtime(id, players, 1, protocols)
