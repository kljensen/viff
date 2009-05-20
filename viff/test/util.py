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

"""Utility functions and classes used for testing."""

from twisted.internet.defer import Deferred, gatherResults, maybeDeferred
from twisted.trial.unittest import TestCase

from viff.passive import PassiveRuntime
from viff.runtime import Share, ShareExchanger, ShareExchangerFactory
from viff.field import GF
from viff.config import generate_configs, load_config
from viff.util import rand
from viff.test.loopback import loopbackAsync

from random import Random


def protocol(method):
    """Decorator for protocol tests.

    Using this decorator on a method in a class inheriting from
    L{RuntimeTestCase} will ensure that the method code is executed
    three times, each time with a different L{Runtime} object as
    argument. The code should use this Runtime as in a real protocol.

    The three runtimes are connected by L{create_loopback_runtime}.
    """

    def wrapper(self):

        def shutdown_protocols(result, runtime):
            # TODO: this should use runtime.shutdown instead.
            for protocol in runtime.protocols.itervalues():
                protocol.loseConnection()
            # If we were called as an errback, then returning the
            # result signals the original error to Trial.
            return result

        def cb_method(runtime):
            # Run the method with the runtime as argument:
            result = maybeDeferred(method, self, runtime)
            # Always call shutdown_protocols:
            result.addBoth(shutdown_protocols, runtime)
            return result

        for runtime in self.runtimes:
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

        result = gatherResults(self.runtimes + self.close_sentinels)
        result.addErrback(unpack)
        return result

    wrapper.func_name = method.func_name
    return wrapper


class RuntimeTestCase(TestCase):

    #: Number of players to test.
    num_players = 3
    #: Shamir sharing threshold.
    threshold = 1
    #: Default Runtime class to instantiate.
    runtime_class = PassiveRuntime

    #: A dictionary mapping player ids to pseudorandom generators.
    #:
    #: The generators have all been seeded with the same seed, which
    #: is again obtained from the viff.util.rand generator. A unit
    #: test should use these genrators when all players need to agree
    #: on the same randomness, e.g. to select the same random number
    #: or to sample the same subsequence from a sequence.
    shared_rand = None

    def assert_type(self, var, wanted_type):
        """Assert that C{var} has the type C{wanted_type}."""
        if not isinstance(var, wanted_type):
            msg = "Type should be %s, but is %s" % (wanted_type, var.__class__)
            raise self.failureException(msg)

    def setUp(self):
        """Configure and connect three Runtimes.

        .. warning::
        
           Subclasses that override this method *must* remember to do
           a super-call to it. Otherwise the runtimes wont be
           connected and :meth:`tearDown` wont work.
        """
        # Our standard 65 bit Blum prime
        self.Zp = GF(30916444023318367583)

        configs = generate_configs(self.num_players, self.threshold)
        self.protocols = {}

        # initialize the dictionary of random generators
        seed = rand.random()
        self.shared_rand = dict([(player_id, Random(seed))
                  for player_id in range(1, self.num_players + 1)])

        # This will be a list of Deferreds which will trigger when the
        # virtual connections between the players are closed.
        self.close_sentinels = []

        self.runtimes = []
        for id in reversed(range(1, self.num_players+1)):
            _, players = load_config(configs[id])
            self.create_loopback_runtime(id, players)

    def tearDown(self):
        """Ensure that all protocol transports are closed.

        This is normally done above when C{loseConnection} is called
        on the protocols, but it may happen that a test case is
        interrupted by a C{TimeoutError}, and so we do it here in all
        cases to avoid leaving scheduled calls lying around in the
        reactor.

        .. warning::
        
           Subclasses that override this method *must* remember to do
           a super-call to it. Otherwise the runtimes wont be
           disconnected and your test case will hang.
        """
        for protocol in self.protocols.itervalues():
            protocol.transport.close()

    def create_loopback_runtime(self, id, players):
        """Create a L{Runtime} connected with a loopback.

        This is used to connect Runtime instances without involving real
        network traffic -- this is transparent to the Runtime.

        @param id: ID of the player owning this Runtime.
        @param players: player configuration.
        """
        # This will yield a Runtime when all protocols are connected.
        result = Deferred()

        # Create a runtime that knows about no other players than itself.
        # It will eventually be returned in result when the factory has
        # determined that all needed protocols are ready.
        runtime = self.runtime_class(players[id], self.threshold)
        factory = ShareExchangerFactory(runtime, players, result)
        # We add the Deferred passed to ShareExchangerFactory and not
        # the Runtime, since we want everybody to wait until all
        # runtimes are ready.
        self.runtimes.append(result)

        for peer_id in players:
            if peer_id != id:
                protocol = ShareExchanger()
                protocol.factory = factory

                # Keys for when we are the client and when we are the server.
                client_key = (id, peer_id)
                server_key = (peer_id, id)
                # Store a protocol used when we are the server.
                self.protocols[server_key] = protocol

                if peer_id > id:
                    # Make a "connection" to the other player. We are
                    # the client (because we initiate the connection)
                    # and the other player is the server.
                    client = self.protocols[client_key]
                    server = self.protocols[server_key]
                    # The loopback connection pumps data back and
                    # forth, and when both sides has closed the
                    # connection, then the returned Deferred will
                    # fire.
                    sentinel = loopbackAsync(server, client)
                    self.close_sentinels.append(sentinel)


class BinaryOperatorTestCase:
    """Test a binary operator.

    This mix-in class should be used together with a RuntimeTestCase
    class, and the new class must define C{self.operator} to be a
    suitable operator.

    """

    a = 12345
    b = 6789

    def _verify(self, runtime, result, expected):
        self.assert_type(result, Share)
        opened = runtime.open(result)
        opened.addCallback(self.assertEquals, expected)
        return opened

    @protocol
    def test_op_share_int(self, runtime):
        share_a = Share(runtime, self.Zp, self.Zp(self.a))
        share_b = self.b
        return self._verify(runtime,
                            self.operator(share_a, share_b),
                            self.operator(self.a, self.b))

    @protocol
    def test_op_int_share(self, runtime):
        share_a = self.a
        share_b = Share(runtime, self.Zp, self.Zp(self.b))
        return self._verify(runtime,
                            self.operator(share_a, share_b),
                            self.operator(self.a, self.b))

    @protocol
    def test_op_share_element(self, runtime):
        share_a = Share(runtime, self.Zp, self.Zp(self.a))
        share_b = self.Zp(self.b)
        return self._verify(runtime,
                            self.operator(share_a, share_b),
                            self.operator(self.a, self.b))

    @protocol
    def test_op_element_share(self, runtime):
        share_a = self.Zp(self.a)
        share_b = Share(runtime, self.Zp, self.Zp(self.b))
        return self._verify(runtime,
                            self.operator(share_a, share_b),
                            self.operator(self.a, self.b))

    @protocol
    def test_op_share_share(self, runtime):
        share_a = Share(runtime, self.Zp, self.Zp(self.a))
        share_b = Share(runtime, self.Zp, self.Zp(self.b))
        return self._verify(runtime,
                            self.operator(share_a, share_b),
                            self.operator(self.a, self.b))
