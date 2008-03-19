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

"""Tests for the asynchronous testing framework."""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import DeferredList
from twisted.internet.protocol import Protocol

from viff.test.loopback import loopbackAsync


class AsyncTest(TestCase):
    """Asynchronous tests."""

    def test_chunked_protocol(self):
        """Ensure that different protocol runs produce different traces.

        This is done by creating two client server pairs and testing
        that they receive messages in different chunks.
        """

        class TestProtocol(Protocol):
            """Simple protocol that stores any data received."""

            def __init__(self):
                self.data = []

            def dataReceived(self, data):
                """Store received data for later inspection."""
                self.data.append(data)

            def connectionMade(self):
                """Write some data and drop the connection."""
                self.transport.write("Hello there!")
                self.transport.write("This is my second message.")
                self.transport.write("Goodbye, it was nice talking to you.")
                self.transport.loseConnection()

        def check(_, server_a, client_a, server_b, client_b):
            """Test that the data sequence is different each time.

            The four parties record the data received, and these
            traces must be pair-wise different due to the simulated
            asynchronous behavior of the network.

            The first argument is from the DeferredList and is ignored.
            """
            self.failIfEqual(server_a.data, server_b.data)
            self.failIfEqual(client_a.data, client_b.data)

        server_a = TestProtocol()
        client_a = TestProtocol()
        closed_a = loopbackAsync(server_a, client_a)

        server_b = TestProtocol()
        client_b = TestProtocol()
        closed_b = loopbackAsync(server_b, client_b)

        closed = DeferredList([closed_a, closed_b])
        closed.addCallback(check, server_a, client_a, server_b, client_b)
        return closed

    def test_interleaving(self):
        """Ensure that protocol runs are interleaved differently each time."""

        class TestProtocol(Protocol):
            """Simple protocol that stores a trace of its invocations."""

            def __init__(self, name, trace):
                self.name = name
                self.trace = trace

            def connectionMade(self):
                """Begin conversation."""
                self.transport.write("Hello there, I'm happy to meet you! 1")

            def dataReceived(self, data):
                """Record in the trace that data was received."""
                self.trace.append(self.name)

                if "1" in data:
                    self.transport.write("I am pleased to meet you too! 2")
                if "2" in data:
                    self.transport.write("Okay, but I gotta go now... 3")
                if "3" in data:
                    self.transport.write("Goodbye! 4")
                if "4" in data:
                    self.transport.loseConnection()

        trace_a = []
        server_a = TestProtocol("Server", trace_a)
        client_a = TestProtocol("Client", trace_a)
        closed_a = loopbackAsync(server_a, client_a)

        trace_b = []
        server_b = TestProtocol("Server", trace_b)
        client_b = TestProtocol("Client", trace_b)
        closed_b = loopbackAsync(server_b, client_b)

        closed = DeferredList([closed_a, closed_b])
        closed.addCallback(lambda _: self.failIfEqual(trace_a, trace_b))
        return closed
