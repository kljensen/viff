# Copyright 2007, 2008 VIFF Development Team.
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

"""Utility functions and classes used for testing."""

from twisted.internet.defer import Deferred, gatherResults
from twisted.trial.unittest import TestCase
from twisted.protocols.loopback import loopbackAsync

from viff.runtime import Runtime, ShareExchanger, ShareExchangerFactory
from viff.field import GF
from viff.config import generate_configs, load_config


def protocol(method):
    """Decorator for protocol tests.

    Using this decorator on a method in a class inheriting from
    L{RuntimeTestCase} will ensure that the method code is executed
    three times, each time with a different L{Runtime} object as
    argument. The code should use this Runtime as in a real protocol.

    The three runtimes are connected by L{create_loopback_runtime}.
    """
    def wrapper(self):
        def cb_method(runtime):
            return method(self, runtime)

        for runtime in self.runtimes.itervalues():
            runtime.addCallback(cb_method)

        def unpack(failure):
            # If one of the executions throw an exception, then
            # gatherResults will call its errback with a Failure
            # containing a FirstError, which in turn contains a
            # Failure wrapping the original exception. In the case of
            # a timeout we get a TimeoutError instead.
            #
            # This code first tries to unpack a FirstError and if that
            # fails it simply returns the Failure passed in. In both
            # cases, Trial will print the exception it in the summary
            # after the test run.
            try:
                return failure.value.subFailure
            except AttributeError:
                return failure

        result = gatherResults(self.runtimes.values())
        result.addErrback(unpack)
        return result

    wrapper.func_name = method.func_name
    return wrapper


def create_loopback_runtime(id, players, threshold, protocols):
    """Create a L{Runtime} connected with a loopback.

    This is used to connect Runtime instances without involving real
    network traffic -- this is transparent to the Runtime.

    @param id: ID of the player owning this Runtime.
    @param players: player configuration.
    @param threshold: security threshold.
    @param protocols: dictionary containing already established
    loopback connections.
    """
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

    #: Timeout in seconds per unit test.
    timeout = 3
    #: Number of players to test.
    num_players = 3
    #: Shamir sharing threshold.
    threshold = 1

    def setUp(self):
        """Configure and connect three Runtimes."""
        # Our standard 65 bit Blum prime
        self.Zp = GF(30916444023318367583)

        configs = generate_configs(self.num_players, self.threshold)
        protocols = {}

        self.runtimes = {}
        for id in reversed(range(1, self.num_players+1)):
            _, players = load_config(configs[id])
            self.runtimes[id] = create_loopback_runtime(id, players,
                                                        self.threshold,
                                                        protocols)
