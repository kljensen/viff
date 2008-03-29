# Necessary because of the 'å' in 'Damgård': -*- coding: latin-1 -*-
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

"""VIFF runtime.

This is where the virtual ideal functionality is hiding! The runtime
is responsible for sharing inputs, handling communication, and running
the calculations.

Each player participating in the protocol will instantiate a
L{Runtime} object and use it for the calculations.

The Runtime returns L{Share} objects for most operations, and these
can be added, subtracted, and multiplied as normal thanks to
overloaded arithmetic operators. The runtime will take care of
scheduling things correctly behind the scenes.
"""
from __future__ import division

import marshal
from optparse import OptionParser, OptionGroup
from math import ceil
from collections import deque

from viff import shamir
from viff.prss import prss
from viff.field import GF256, FieldElement
from viff.util import wrapper

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.protocol import ClientFactory, ServerFactory
from twisted.protocols.basic import Int16StringReceiver


class Share(Deferred):
    """A shared number.

    The L{Runtime} operates on shares, represented by this class.
    Shares are asynchronous in the sense that they promise to attain a
    value at some point in the future.

    Shares overload the arithmetic operations so that C{x = a + b}
    will create a new share C{x}, which will eventually contain the
    sum of C{a} and C{b}. Each share is associated with a L{Runtime}
    and the arithmetic operations simply call back to that runtime.
    """

    def __init__(self, runtime, field, value=None):
        """Initialize a share.

        @param runtime: The L{Runtime} to use.
        @param field: The field where the value lies.
        @param value: The initial value of the share (if known).
        """
        assert field is not None, "Cannot construct share without a field."
        assert callable(field), "The field is not callable, wrong argument?"

        Deferred.__init__(self)
        self.runtime = runtime
        self.field = field
        if value is not None:
            self.callback(value)

    def __add__(self, other):
        """Addition."""
        return self.runtime.add(self, other)

    def __radd__(self, other):
        """Addition (reflected argument version)."""
        return self.runtime.add(other, self)

    def __sub__(self, other):
        """Subtraction."""
        return self.runtime.sub(self, other)

    def __rsub__(self, other):
        """Subtraction (reflected argument version)."""
        return self.runtime.sub(other, self)

    def __mul__(self, other):
        """Multiplication."""
        return self.runtime.mul(self, other)

    def __rmul__(self, other):
        """Multiplication (reflected argument version)."""
        return self.runtime.mul(other, self)

    def __xor__(self, other):
        """Exclusive-or."""
        return self.runtime.xor(self, other)

    def __rxor__(self, other):
        """Exclusive-or (reflected argument version)."""
        return self.runtime.xor(other, self)

    def __lt__(self, other):
        """Strictly less-than comparison."""
        # self < other <=> not (self >= other)
        return 1 - self.runtime.greater_than_equal(self, other)

    def __le__(self, other):
        """Less-than or equal comparison."""
        # self <= other <=> other >= self
        return self.runtime.greater_than_equal(other, self)

    def __gt__(self, other):
        """Strictly greater-than comparison."""
        # self > other <=> not (other >= self)
        return 1 - self.runtime.greater_than_equal(other, self)

    def __ge__(self, other):
        """Greater-than or equal comparison."""
        # self >= other
        return self.runtime.greater_than_equal(self, other)

    def clone(self):
        """Clone a share.

        Works like L{util.clone_deferred} except that it returns a new
        Share instead of a Deferred.
        """

        def split_result(result):
            clone.callback(result)
            return result
        clone = Share(self.runtime, self.field)
        self.addCallback(split_result)
        return clone


class ShareList(Share):
    """Create a share that waits on a number of other shares.

    Roughly modelled after the Twisted C{DeferredList} class.
    """

    def __init__(self, shares, threshold=None):
        """Initialize a share list.

        @param shares: non-empty list of L{Share} objects.
        @param threshold: number of shares to wait for. This is either
        a number such that C{0 < threshold <= len(shares)} or C{None}
        if all shares should be waited for.
        """
        assert len(shares) > 0, "Cannot create empty ShareList"
        assert threshold is None or 0 < threshold <= len(shares), \
            "Threshold out of range"

        Share.__init__(self, shares[0].runtime, shares[0].field)

        self.results = [None] * len(shares)
        if threshold is None:
            self.missing_shares = len(shares)
        else:
            self.missing_shares = threshold

        for index, share in enumerate(shares):
            share.addCallbacks(self._callback_fired, self._callback_fired,
                               callbackArgs=(index, True),
                               errbackArgs=(index, False))

    def _callback_fired(self, result, index, success):
        self.results[index] = (success, result)
        self.missing_shares -= 1
        if not self.called and self.missing_shares == 0:
            self.callback(self.results)
        return result


def gather_shares(shares):
    """Gather shares.

    Roughly modelled after the Twisted C{gatherResults} function.
    """

    def filter_results(results):
        return [share for (_, share) in results]
    share_list = ShareList(shares)
    share_list.addCallback(filter_results)
    return share_list


class ShareExchanger(Int16StringReceiver):
    """Send and receive shares.

    All players are connected by pair-wise connections and this
    Twisted protocol is one such connection. It is used to send and
    receive shares from one other player.

    The C{marshal} module is used for converting the data to bytes for
    the network and to convert back again to structured data.
    """

    def __init__(self):
        self.peer_id = None

        #: Data expected to be received in the future.
        #:
        #: Data from our peer is put here, either as an empty Deferred
        #: if we are waiting on input from the player, or the data
        #: itself if data is received from the other player before we
        #: are ready to use it.
        #:
        #: @type: C{dict} from C{(program_counter, data_type)} to
        #: deferred data.
        self.incoming_data = {}

    def connectionMade(self):
        self.sendString(str(self.factory.runtime.id))
        try:
            self.peer_cert = self.transport.socket.peer_certificate
        except AttributeError:
            self.peer_cert = None

    def stringReceived(self, string):
        """Called when a share is received.

        The string received is unmarshalled into the program counter,
        and a data part. The data is passed the appropriate Deferred
        in L{self.incoming_data}.

        @param string: bytes from the network.
        @type string: C{(program_counter, data)} in
        marshalled form
        """
        if self.peer_id is None:
            # TODO: Handle ValueError if the string cannot be decoded.
            self.peer_id = int(string)
            if self.peer_cert:
                # The player ID are stored in the serial number of the
                # certificate -- this makes it easy to check that the
                # player is who he claims to be.
                if self.peer_cert.serial_number != self.peer_id:
                    print "Peer %s claims to be %d, aborting!" \
                        % (self.peer_cert.subject, self.peer_id)
                    self.transport.loseConnection()

            self.factory.identify_peer(self)
        else:
            program_counter, data_type, data = marshal.loads(string)
            key = (program_counter, data_type)

            deq = self.incoming_data.setdefault(key, deque())
            if deq and isinstance(deq[0], Deferred):
                deferred = deq.popleft()
                deferred.callback(data)
            else:
                deq.append(data)

            # TODO: marshal.loads can raise EOFError, ValueError, and
            # TypeError. They should be handled somehow.

    def sendData(self, program_counter, data_type, data):
        send_data = (program_counter, data_type, data)
        self.sendString(marshal.dumps(send_data))

    def sendShare(self, program_counter, share):
        """Send a share.

        The program counter and the share are marshalled and sent to
        the peer.

        @param program_counter: the program counter associated with
        the share.
        """
        self.sendData(program_counter, "share", share.value)

    def loseConnection(self):
        """Disconnect this protocol instance."""
        self.transport.loseConnection()


class ShareExchangerFactory(ServerFactory, ClientFactory):
    """Factory for creating ShareExchanger protocols."""

    protocol = ShareExchanger

    def __init__(self, runtime, players, protocols_ready):
        """Initialize the factory."""
        self.runtime = runtime
        self.players = players
        self.needed_protocols = len(players) - 1
        self.protocols_ready = protocols_ready

    def identify_peer(self, protocol):
        self.runtime.add_player(self.players[protocol.peer_id], protocol)
        self.needed_protocols -= 1
        if self.needed_protocols == 0:
            self.protocols_ready.callback(self.runtime)


def increment_pc(method):
    """Make method automatically increment the program counter.

    Adding this decorator to a L{Runtime} method will ensure that the
    program counter is incremented correctly when entering the method.

    @param method: the method.
    @type method: a method of L{Runtime}
    """

    @wrapper(method)
    def inc_pc_wrapper(self, *args, **kwargs):
        try:
            self.program_counter[-1] += 1
            self.program_counter.append(0)
            return method(self, *args, **kwargs)
        finally:
            self.program_counter.pop()
    return inc_pc_wrapper


class BasicRuntime:
    """Basic VIFF runtime with no crypto.

    This runtime contains only the most basic operations needed such
    as the program counter, the list of other players, etc.
    """

    @staticmethod
    def add_options(parser):
        group = OptionGroup(parser, "VIFF Runtime Options")
        parser.add_option_group(group)

        group.add_option("-l", "--bit-length", type="int", metavar="L",
                         help=("Maximum bit length of input numbers for "
                               "comparisons."))
        group.add_option("-k", "--security-parameter", type="int", metavar="K",
                         help=("Security parameter. Comparisons will leak "
                               "information with probability 2**-K."))
        group.add_option("--no-tls", action="store_false", dest="tls",
                         help="Disable the use secure TLS connections.")
        group.add_option("--tls", action="store_true",
                         help=("Enable the use secure TLS connections "
                               "(if the GNUTLS bindings are available)."))
        group.add_option("--deferred-debug", action="store_true",
                         help="Enable extra debug out for deferreds.")

        parser.set_defaults(bit_length=32,
                            security_parameter=30,
                            tls=True,
                            deferred_debug=False)

    def __init__(self, player, threshold, options=None):
        """Initialize runtime.

        Initialized a runtime owned by the given, the threshold, and
        optionally a set of options. The runtime has no network
        connections and knows of no other players -- the
        L{create_runtime} function should be used instead to create a
        usable runtime.
        """
        #: ID of this player.
        self.id = player.id
        #: Shamir secret sharing threshold.
        self.threshold = threshold

        if options is None:
            parser = OptionParser()
            self.add_options(parser)
            self.options = parser.get_default_values()
        else:
            self.options = options

        if self.options.deferred_debug:
            from twisted.internet import defer
            defer.setDebugging(True)

        #: Current program counter.
        #:
        #: Whenever a share is sent over the network, it must be
        #: uniquely identified so that the receiving player known what
        #: operation the share is a result of. This is done by
        #: associating a X{program counter} with each operation.
        #:
        #: Keeping the program counter synchronized between all
        #: players ought to be easy, but because of the asynchronous
        #: nature of network protocols, all players might not reach
        #: the same parts of the program at the same time.
        #:
        #: Consider two players M{A} and M{B} who are both waiting on
        #: the variables C{a} and C{b}. Callbacks have been added to
        #: C{a} and C{b}, and the question is what program counter the
        #: callbacks should use when sending data out over the
        #: network.
        #:
        #: Let M{A} receive input for C{a} and then for C{b} a little
        #: later, and let M{B} receive the inputs in reversed order so
        #: that the input for C{b} arrives first. The goal is to keep
        #: the program counters synchronized so that program counter
        #: M{x} refers to the same operation on all players. Because
        #: the inputs arrive in different order at different players,
        #: incrementing a simple global counter is not enough.
        #:
        #: Instead, a I{tree} is made, which follows the tree of
        #: execution. At the top level the program counter starts at
        #: C{[0]}. At the next operation it becomes C{[1]}, and so on.
        #: If a callback is scheduled (see L{schedule_callback}) at
        #: program counter C{[x, y, z]}, any calls it makes will be
        #: numbered C{[x, y, z, 1]}, then C{[x, y, z, 2]}, and so on.
        #:
        #: Maintaining such a tree of program counters ensures that
        #: different parts of the program execution never reuses the
        #: same program counter for different variables.
        #:
        #: The L{increment_pc} decorator is responsible for
        #: dynamically building the tree as the execution unfolds and
        #: L{schedule_callback} is responsible for scheduling
        #: callbacks with the correct program counter.
        #:
        #: @type: C{list} of integers.
        self.program_counter = [0]

        #: Connections to the other players.
        #:
        #: @type: C{dict} from Player ID to L{ShareExchanger} objects.
        self.protocols = {}

        #: Number of known players.
        #:
        #: Equal to C{len(players)}, but storing it here is more
        #: direct.
        self.num_players = 0

        #: Information on players.
        #:
        #: @type: C{dict} from player_id to L{Player} objects.
        self.players = {}
        # Add ourselves, but with no protocol since we wont be
        # communicating with ourselves.
        self.add_player(player, None)

    def add_player(self, player, protocol):
        self.players[player.id] = player
        self.num_players = len(self.players)
        # There is no protocol for ourselves, so we wont add that:
        if protocol is not None:
            self.protocols[player.id] = protocol

    def shutdown(self):
        """Shutdown the runtime.

        All connections are closed and the runtime cannot be used
        again after this has been called.
        """

        def stop(_):
            print "Initiating shutdown sequence."
            for protocol in self.protocols.itervalues():
                protocol.loseConnection()
            reactor.stop()

        sync = self.synchronize()
        sync.addCallback(stop)

    def wait_for(self, *vars):
        """Make the runtime wait for the variables given.

        The runtime is shut down when all variables are calculated.

        @param vars: variables to wait for.
        @type  vars: list of L{Deferred}s
        """
        dl = DeferredList(vars)
        dl.addCallback(lambda _: self.shutdown())

    def schedule_callback(self, deferred, func, *args, **kwargs):
        """Schedule a callback on a deferred with the correct program
        counter.

        If a callback depends on the current program counter, then use
        this method to schedule it instead of simply calling
        addCallback directly. Simple callbacks that are independent of
        the program counter can still be added directly to the
        Deferred as usual.

        Any extra arguments are passed to the callback as with
        addCallback.

        @param deferred: the Deferred.
        @param func: the callback.
        @param args: extra arguments.
        @param kwargs: extra keyword arguments.
        """
        # TODO, http://tracker.viff.dk/issue22: When several callbacks
        # are scheduled from the same method, they all save the same
        # program counter. Simply decorating callback with increase_pc
        # does not seem to work (the multiplication benchmark hangs).
        # This should be fixed.
        saved_pc = self.program_counter[:]

        @wrapper(func)
        def callback_wrapper(*args, **kwargs):
            """Wrapper for a callback which ensures a correct PC."""
            try:
                current_pc = self.program_counter
                self.program_counter = saved_pc
                return func(*args, **kwargs)
            finally:
                self.program_counter = current_pc

        deferred.addCallback(callback_wrapper, *args, **kwargs)

    @increment_pc
    def synchronize(self):
        shares = [self._exchange_shares(player, GF256(0))
                  for player in self.players]
        result = gather_shares(shares)
        result.addCallback(lambda _: None)
        return result

    def _expect_data(self, peer_id, data_type, deferred):
        assert peer_id != self.id, "Do not expect data from yourself!"
        # Convert self.program_counter to a hashable value in order to
        # use it as a key in self.protocols[peer_id].incoming_data.
        pc = tuple(self.program_counter)
        key = (pc, data_type)

        deq = self.protocols[peer_id].incoming_data.setdefault(key, deque())
        if deq and not isinstance(deq[0], Deferred):
            # We have already received some data from the other side.
            data = deq.popleft()
            deferred.callback(data)
        else:
            # We have not yet received anything from the other side.
            deq.append(deferred)

    def _exchange_shares(self, peer_id, field_element):
        """Exchange shares with another player.

        We send the player our share and record a Deferred which will
        trigger when the share from the other side arrives.
        """
        assert isinstance(field_element, FieldElement)

        if peer_id == self.id:
            return Share(self, field_element.field, field_element)
        else:
            share = self._expect_share(peer_id, field_element.field)
            pc = tuple(self.program_counter)
            self.protocols[peer_id].sendShare(pc, field_element)
            return share

    def _expect_share(self, peer_id, field):
        share = Share(self, field)
        share.addCallback(lambda value: field(value))
        self._expect_data(peer_id, "share", share)
        return share


class Runtime(BasicRuntime):
    """The VIFF runtime.

    The runtime is used for sharing values (L{shamir_share} or
    L{prss_share}) into L{Share} object and opening such shares
    (L{open}) again. Calculations on shares is normally done through
    overloaded arithmetic operations, but it is also possible to call
    L{add}, L{mul}, etc. directly if one prefers.

    Each player in the protocol uses a Runtime object. To create an
    instance and connect it correctly with the other players, please
    use the L{create_runtime} function instead of instantiating a
    Runtime directly. The L{create_runtime} function will take care of
    setting up network connections and return a Deferred which
    triggers with the Runtime object when it is ready.
    """

    def __init__(self, player, threshold, options=None):
        """Initialize runtime."""
        BasicRuntime.__init__(self, player, threshold, options)

        #: Echo counters for Bracha broadcast.
        self._bracha_echo = {}
        #: Ready counters for Bracha broadcast.
        self._bracha_ready = {}
        #: Have we sent a ready message?
        self._bracha_sent_ready = {}
        #: Have we delivered the message?
        self._bracha_delivered = {}

    @increment_pc
    def open(self, share, receivers=None, threshold=None):
        """Open a secret sharing.

        Communication cost: every player sends one share to each
        receiving player.

        @param share: the player's private part of the sharing to open.
        @type share: Share

        @param receivers: the IDs of the players that will eventually
            obtain the opened result or None if all players should
            obtain the opened result.
        @type receivers: None or a C{list} of integers

        @param threshold: the threshold used to open the sharing or None
            if the runtime default should be used.
        @type threshold: integer or None

        @return: the result of the opened sharing if the player's ID
            is in C{receivers}, otherwise None.
        @returntype: Share or None
        """
        assert isinstance(share, Share)
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()
        if threshold is None:
            threshold = self.threshold

        def exchange(share):
            # Send share to all receivers.
            for peer_id in receivers:
                if peer_id != self.id:
                    pc = tuple(self.program_counter)
                    self.protocols[peer_id].sendShare(pc, share)
            # Receive and recombine shares if this player is a receiver.
            if self.id in receivers:
                deferreds = []
                for peer_id in self.players:
                    if peer_id == self.id:
                        d = Share(self, share.field, (share.field(peer_id), share))
                    else:
                        d = self._expect_share(peer_id, share.field)
                        self.schedule_callback(d, lambda s, peer_id: (s.field(peer_id), s), peer_id)
                    deferreds.append(d)
                # TODO: This list ought to trigger as soon as more than
                # threshold shares has been received.
                return self._recombine(deferreds, threshold)

        result = share.clone()
        self.schedule_callback(result, exchange)
        if self.id in receivers:
            return result

    def add(self, share_a, share_b):
        """Addition of shares.

        Communication cost: none.
        """
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            share_b = Share(self, field, share_b)

        result = gather_shares([share_a, share_b])
        result.addCallback(lambda (a, b): a + b)
        return result

    def sub(self, share_a, share_b):
        """Subtraction of shares.

        Communication cost: none.
        """
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            share_b = Share(self, field, share_b)

        result = gather_shares([share_a, share_b])
        result.addCallback(lambda (a, b): a - b)
        return result

    @increment_pc
    def mul(self, share_a, share_b):
        """Multiplication of shares.

        Communication cost: 1 Shamir sharing.
        """
        # TODO:  mul accept FieldElements and do quick local
        # multiplication in that case. If two FieldElements are given,
        # return a FieldElement.
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            share_b = Share(self, field, share_b)

        result = gather_shares([share_a, share_b])
        result.addCallback(lambda (a, b): a * b)
        self.schedule_callback(result, self._shamir_share)
        self.schedule_callback(result, self._recombine,
                               threshold=2*self.threshold)
        return result

    @increment_pc
    def xor(self, share_a, share_b):
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            if not isinstance(share_a, FieldElement):
                share_a = field(share_a)
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            if not isinstance(share_b, FieldElement):
                share_b = field(share_b)
            share_b = Share(self, field, share_b)

        if field is GF256:
            return share_a + share_b
        else:
            return share_a + share_b - 2 * share_a * share_b

    @increment_pc
    def prss_share(self, inputters, field, element=None):
        """Creates pseudo-random secret sharings.

        This protocol creates a secret sharing for each player in the
        subset of players specified in C{inputters}. The protocol uses the
        pseudo-random secret sharing technique described in the paper "Share
        Conversion, Pseudorandom Secret-Sharing and Applications to Secure
        Computation" by Ronald Cramer, Ivan Damgård, and Yuval Ishai in Proc.
        of TCC 2005, LNCS 3378.
        U{Download <http://www.cs.technion.ac.il/~yuvali/pubs/CDI05.ps>}.

        Communication cost: Each inputter does one broadcast.

        @param inputters: The IDs of the players that will share a secret.
        @type inputters: C{list} of integers

        @param field: The field over which to share all the secrets.
        @type field: L{FieldElement}

        @param element: The secret that this player shares or C{None} if this
            player is not in C{inputters}.
        @type element: int, long, or None

        @return: A list of shares corresponding to the secrets submitted by
            the players in C{inputters}.
        @returntype: C{List} of C{Shares}
        """
        # Verifying parameters.
        if element is None:
            assert self.id not in inputters, "No element given."
        else:
            assert self.id in inputters, \
                "Element given, but we are not sharing?"

        n = self.num_players

        # Key used for PRSS.
        key = tuple(self.program_counter)

        # The shares for which we have all the keys.
        all_shares = []

        # Shares we calculate from doing PRSS with the other players.
        tmp_shares = {}

        prfs = self.players[self.id].dealer_prfs(field.modulus)

        # Compute and broadcast correction value.
        if self.id in inputters:
            for player in self.players:
                share = prss(n, player, field, prfs[self.id], key)
                all_shares.append((field(player), share))
            shared = shamir.recombine(all_shares[:self.threshold+1])
            correction = element - shared
            # if this player is inputter then broadcast correction value
            # TODO: more efficient broadcast?
            pc = tuple(self.program_counter)
            for peer_id in self.players:
                if self.id != peer_id:
                    self.protocols[peer_id].sendShare(pc, correction)

        # Receive correction value from inputters and compute share.
        result = []
        for player in inputters:
            tmp_shares[player] = prss(n, self.id, field, prfs[player], key)
            if player == self.id:
                d = Share(self, field, correction)
            else:
                d = self._expect_share(player, field)
            d.addCallback(lambda c, s: s + c, tmp_shares[player])
            result.append(d)

        # Unpack a singleton list.
        if len(result) == 1:
            return result[0]
        else:
            return result

    @increment_pc
    def prss_share_random(self, field, binary=False):
        """Generate shares of a uniformly random element from the field given.

        If binary is True, a 0/1 element is generated. No player
        learns the value of the element.

        Communication cost: none if binary=False, 1 open otherwise.
        """
        if field is GF256 and binary:
            modulus = 2
        else:
            modulus = field.modulus

        # Key used for PRSS.
        prss_key = tuple(self.program_counter)
        prfs = self.players[self.id].prfs(modulus)
        share = prss(self.num_players, self.id, field, prfs, prss_key)

        if field is GF256 or not binary:
            return Share(self, field, share)

        # Open the square and compute a square-root
        result = self.open(self.mul(share, share), threshold=2*self.threshold)

        def finish(square, share, binary):
            if square == 0:
                # We were unlucky, try again...
                return self.prss_share_random(field, binary)
            else:
                # We can finish the calculation
                root = square.sqrt()
                # When the root is computed, we divide the share and
                # convert the resulting -1/1 share into a 0/1 share.
                return Share(self, field, (share/root + 1) / 2)

        self.schedule_callback(result, finish, share, binary)
        return result

    @increment_pc
    def _shamir_share(self, number):
        """Share a FieldElement using Shamir sharing.

        Returns a list of (id, share) pairs.
        """
        shares = shamir.share(number, self.threshold, self.num_players)

        result = []
        for peer_id, share in shares:
            d = self._exchange_shares(peer_id.value, share)
            d.addCallback(lambda share, peer_id: (peer_id, share), peer_id)
            result.append(d)

        return result

    @increment_pc
    def shamir_share(self, inputters, field, number=None):
        """Secret share C{number} over C{field} using Shamir's method.

        Returns a list of shares.

        Communication cost: n elements transmitted.
        """
        assert number is None or self.id in inputters

        results = []
        for peer_id in inputters:
            if peer_id == self.id:
                pc = tuple(self.program_counter)
                shares = shamir.share(field(number), self.threshold,
                                      self.num_players)
                for other_id, share in shares:
                    if other_id.value == self.id:
                        results.append(Share(self, share.field, share))
                    else:
                        self.protocols[other_id.value].sendShare(pc, share)
            else:
                results.append(self._expect_share(peer_id, field))

        # Unpack a singleton list.
        if len(results) == 1:
            return results[0]
        else:
            return results

    @increment_pc
    def _broadcast(self, sender, message=None):
        """Perform a Bracha broadcast.

        A Bracha broadcast is reliable against an active adversary
        corrupting up to t < n/3 of the players. For more details, see
        the paper "An asynchronous [(n-1)/3]-resilient consensus
        protocol" by G. Bracha in Proc. 3rd ACM Symposium on
        Principles of Distributed Computing, 1984, pages 154-162.

        @param sender: the sender of the broadcast message.
        @param message: the broadcast message, used only by the sender.
        """

        result = Deferred()
        pc = tuple(self.program_counter)
        n = self.num_players
        t = self.threshold

        # For each distinct message (and program counter) we save a
        # dictionary for each of the following variables. The reason
        # is that we need to count for each distinct message how many
        # echo and ready messages we have received.
        self._bracha_echo[pc] = {}
        self._bracha_ready[pc] = {}
        self._bracha_sent_ready[pc] = {}
        self._bracha_delivered[pc] = {}

        def unsafe_broadcast(data_type, message):
            # Performs a regular broadcast without any guarantees. In
            # other words, it sends the message to each player except
            # for this one.
            for protocol in self.protocols.itervalues():
                protocol.sendData(pc, data_type, message)

        def echo_received(message, peer_id):
            # This is called when we receive an echo message. It
            # updates the echo count for the message and enters the
            # ready state if the count is high enough.
            ids = self._bracha_echo[pc].setdefault(message, [])
            ready = self._bracha_sent_ready[pc].setdefault(message, False)

            if peer_id not in ids:
                ids.append(peer_id)
                if len(ids) >= ceil((n+t+1)/2) and not ready:
                    self._bracha_sent_ready[pc][message] = True
                    unsafe_broadcast("ready", message)
                    ready_received(message, self.id)

        def ready_received(message, peer_id):
            # This is called when we receive a ready message. It
            # updates the ready count for the message. Depending on
            # the count, we may either stay in the same state or enter
            # the ready or delivered state.
            ids = self._bracha_ready[pc].setdefault(message, [])
            ready = self._bracha_sent_ready[pc].setdefault(message, False)
            delivered = self._bracha_delivered[pc].setdefault(message, False)
            if peer_id not in ids:
                ids.append(peer_id)
                if len(ids) == t+1 and not ready:
                    self._bracha_sent_ready[pc][message] = True
                    unsafe_broadcast("ready", message)
                    ready_received(message, self.id)

                elif len(ids) == 2*t+1 and not delivered:
                    self._bracha_delivered[pc][message] = True
                    result.callback(message)

        def send_received(message):
            # This is called when we receive a send message. We react
            # by sending an echo message to each player. Since the
            # unsafe broadcast doesn't send a message to this player,
            # we simulate it by calling the echo_received function.
            unsafe_broadcast("echo", message)
            echo_received(message, self.id)


        # In the following we prepare to handle a send message from
        # the sender and at most one echo and one ready message from
        # each player.
        d_send = Deferred().addCallback(send_received)
        self._expect_data(sender, "send", d_send)

        for peer_id in self.players:
            if peer_id != self.id:
                d_echo = Deferred().addCallback(echo_received, peer_id)
                self._expect_data(peer_id, "echo", d_echo)

                d_ready = Deferred().addCallback(ready_received, peer_id)
                self._expect_data(peer_id, "ready", d_ready)

        # If this player is the sender, we transmit a send message to
        # each player. We send one to this player by calling the
        # send_received function.
        if self.id == sender:
            unsafe_broadcast("send", message)
            send_received(message)

        return result

    @increment_pc
    def broadcast(self, senders, message=None):
        """Perform one or more Bracha broadcast(s).

        The list of senders given will determine the subset of players
        who wish to broadcast a message. If this player wishes to
        broadcast, its ID must be in the list of senders and the
        optional message parameter must be used.

        If the list of senders consists only of a single sender, the
        result will be a single element, otherwise it will be a list.

        A Bracha broadcast is reliable against an active adversary
        corrupting up to t < n/3 of the players. For more details, see
        the paper "An asynchronous [(n-1)/3]-resilient consensus
        protocol" by G. Bracha in Proc. 3rd ACM Symposium on
        Principles of Distributed Computing, 1984, pages 154-162.

        @param senders: the list of senders.
        @param message: the broadcast message, used if this player is
        a sender.
        """
        assert message is None or self.id in senders

        result = []

        for sender in senders:
            if sender == self.id:
                result.append(self._broadcast(sender, message))
            else:
                result.append(self._broadcast(sender))

        if len(result) == 1:
            return result[0]

        return result

    @increment_pc
    def _recombine(self, shares, threshold):
        """Shamir recombine a list of deferred (id,share) pairs."""
        assert len(shares) > threshold

        def filter_good_shares(results):
            # Filter results, which is a list of (success, share)
            # pairs.
            return [result[1] for result in results
                    if result is not None and result[0]][:threshold+1]

        result = ShareList(shares, threshold+1)
        result.addCallback(filter_good_shares)
        result.addCallback(shamir.recombine)
        return result


def create_runtime(id, players, threshold, options=None, runtime_class=Runtime):
    """Create a L{Runtime} and connect to the other players.

    This function should be used in normal programs instead of
    instantiating the Runtime directly. This function makes sure that
    the Runtime is correctly connected to the other players.

    The return value is a Deferred which will trigger when the runtime
    is ready. Add your protocol as a callback on this Deferred using
    code like this::

        def protocol(runtime):
            a, b, c = runtime.shamir_share(input)

            a = runtime.open(a)
            b = runtime.open(b)
            c = runtime.open(c)

            dprint("Opened a: %s", a)
            dprint("Opened b: %s", b)
            dprint("Opened c: %s", c)

            runtime.wait_for(a,b,c)

        pre_runtime = create_runtime(id, players, 1)
        pre_runtime.addCallback(protocol)

    This is the general template which VIFF programs should follow.
    Please see the example applications for more examples.

    """
    # This will yield a Runtime when all protocols are connected.
    result = Deferred()

    # Create a runtime that knows about no other players than itself.
    # It will eventually be returned in result when the factory has
    # determined that all needed protocols are ready.
    runtime = runtime_class(players[id], threshold, options)
    factory = ShareExchangerFactory(runtime, players, result)

    if options and options.tls:
        print "Using TLS"
        try:
            from gnutls.interfaces.twisted import X509Credentials
            from gnutls.crypto import X509Certificate, X509PrivateKey
        except ImportError:
            # TODO: Return a failed Deferred instead.
            print "Could not import Python GNUTLS module, aborting!"
            return

        # TODO: Make the file names configurable.
        cert = X509Certificate(open('player-%d.cert' % id).read())
        key = X509PrivateKey(open('player-%d.key' % id).read())
        ca = X509Certificate(open('ca.cert').read())
        cred = X509Credentials(cert, key, [ca])
        cred.verify_peer = True
        reactor.listenTLS(players[id].port, factory, cred)
    else:
        print "Not using TLS"
        reactor.listenTCP(players[id].port, factory)

    for peer_id, player in players.iteritems():
        if peer_id > id:
            print "Will connect to %s" % player
            if options and options.tls:
                reactor.connectTLS(player.host, player.port, factory, cred)
            else:
                reactor.connectTCP(player.host, player.port, factory)

    return result
