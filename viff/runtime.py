# Necessary because of the 'å' in 'Damgård': -*- coding: latin-1 -*-
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
from viff.matrix import Matrix, hyper
from viff.util import wrapper, rand

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, gatherResults, succeed
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

    Roughly modelled after the Twisted C{DeferredList} class. The
    advantage of this class is that it is a L{Share} (not just a
    C{Deferred}) and that it can be made to trigger when a certain
    threshold of the shares are ready. This example shows how the
    C{pprint} callback is triggered when C{a} and C{c} are ready:

    >>> from pprint import pprint
    >>> from viff.field import GF256
    >>> a = Share(None, GF256)
    >>> b = Share(None, GF256)
    >>> c = Share(None, GF256)
    >>> shares = ShareList([a, b, c], threshold=2)
    >>> shares.addCallback(pprint)           # doctest: +ELLIPSIS
    <ShareList at 0x...>
    >>> a.callback(10)
    >>> c.callback(20)
    [(True, 10), None, (True, 20)]

    The C{pprint} function is called with a list of pairs. The first
    component of each pair is a boolean indicating if the callback or
    errback method was called on the corresponding L{Share}, and the
    second component is the value given to the callback/errback.

    If a threshold less than the full number of shares is used, some
    of the pairs may be missing and C{None} is used instead. In the
    example above the C{b} Share arrived later than C{a} and C{c}, and
    so the list contains a C{None} on its place.
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

    Roughly modelled after the Twisted C{gatherResults} function. It
    takes a list of shares and returns a new L{Share} which will be
    triggered with a list of values, namely the values from the
    initial shares:

    >>> from pprint import pprint
    >>> from viff.field import GF256
    >>> a = Share(None, GF256)
    >>> b = Share(None, GF256)
    >>> shares = gather_shares([a, b])
    >>> shares.addCallback(pprint)           # doctest: +ELLIPSIS
    <ShareList at 0x...>
    >>> a.callback(10)
    >>> b.callback(20)
    [10, 20]

    @param shares: the shares.
    @type shares: C{list} of L{Share} objects
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


def preprocess(generator):
    """Track calls to this method.

    The decorated method will be replaced with a proxy method which
    first tries to get the data needed from C{self._pool}, and if that
    fails it falls back to the original method.

    The C{generator} method is only used to record where the data
    should be generated from, the method is not actually called.

    @param generator: Use this method as the generator for
    pre-processed data.
    @type generator: C{str}
    """

    def preprocess_decorator(method):

        @wrapper(method)
        def preprocess_wrapper(self, *args, **kwargs):
            pc = tuple(self.program_counter)
            try:
                return self._pool[pc]
            except KeyError:
                key = (generator, args)
                pcs = self._needed_data.setdefault(key, [])
                pcs.append(pc)
                return method(self, *args, **kwargs)

        return preprocess_wrapper
    return preprocess_decorator


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
                         help="Disable the use of secure TLS connections.")
        group.add_option("--tls", action="store_true",
                         help=("Enable the use of secure TLS connections "
                               "(if the GNUTLS bindings are available)."))
        group.add_option("--deferred-debug", action="store_true",
                         help="Enable extra debug output for deferreds.")

        try:
            import gnutls
            have_gnutls = True
        except ImportError:
            have_gnutls = False

        parser.set_defaults(bit_length=32,
                            security_parameter=30,
                            tls=have_gnutls,
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

        #: Pool of preprocessed data.
        self._pool = {}
        #: Description of needed preprocessed data.
        self._needed_data = {}

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

    @increment_pc
    def preprocess(self, program):
        """Generate preprocess material.

        The C{program} specifies which methods to call and with which
        arguments. The generator methods called must adhere to the
        following interface:

          - They must return a C{(int, Deferred)} tuple where the
            C{int} tells us how many items of pre-processed data the
            Deferred will yield.

          - The Deferred must yield a C{list} of the promissed length.

          - The C{list} contains the actual data. This data can be
            either a Deferred or a C{tuple} of Deferreds.

        The L{ActiveRuntime.generate_triples} method is an example of
        a method fulfilling this interface.

        @param program: A description of the needed data.
        @type program: C{dict} mapping C{(str, args)} tuples to
        program counters
        """

        def update(results, program_counters):
            # We concatenate the sub-lists in results.
            results = sum(results, [])

            wait_list = []
            for result in results:
                # We allow pre-processing methods to return tuples of
                # shares or individual shares as their result. Here we
                # deconstruct result (if possible) and wait on its
                # individual parts.
                if isinstance(result, tuple):
                    wait_list.extend(result)
                else:
                    wait_list.append(result)

            # The pool must map program counters to Deferreds to
            # present a uniform interface for the functions we
            # pre-process.
            results = map(succeed, results)

            # Update the pool with pairs of program counter and data.
            self._pool.update(zip(program_counters, results))
            # Return a Deferred that waits on the individual results.
            # This is important to make it possible for the players to
            # avoid starting before the pre-processing is complete.
            return gatherResults(wait_list)

        wait_list = []
        for ((generator, args), program_counters) in program.iteritems():
            print "Preprocessing %s (%d items)" % (generator, len(program_counters))
            func = getattr(self, generator)
            results = []
            items = 0
            while items < len(program_counters):
                item_count, result = func(*args)
                items += item_count
                results.append(result)
            ready = gatherResults(results)
            ready.addCallback(update, program_counters)
            wait_list.append(ready)
        return DeferredList(wait_list)

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
        assert isinstance(share_a, Share) or isinstance(share_b, Share), \
            "At least one of share_a and share_b must be a Share."

        if not isinstance(share_a, Share):
            # Then share_b must be a Share => local multiplication. We
            # clone first to avoid changing share_b.
            result = share_b.clone()
            result.addCallback(lambda b: share_a * b)
            return result
        if not isinstance(share_b, Share):
            # Likewise when share_b is a constant.
            result = share_a.clone()
            result.addCallback(lambda a: a * share_b)
            return result

        # At this point both share_a and share_b must be Share
        # objects. So we wait on them, multiply and reshare.
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
        result = self.open(Share(self, field, share*share),
                           threshold=2*self.threshold)

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
    def shamir_share(self, inputters, field, number=None, threshold=None):
        """Secret share C{number} over C{field} using Shamir's method.

        The number is shared using polynomial of degree C{threshold}
        (defaults to L{self.threshold}). Returns a list of shares
        unless unless there is only one inputter in which case the
        share is returned directly.

        Communication cost: n elements transmitted.
        """
        assert number is None or self.id in inputters
        if threshold is None:
            threshold = self.threshold

        results = []
        for peer_id in inputters:
            if peer_id == self.id:
                pc = tuple(self.program_counter)
                shares = shamir.share(field(number), threshold,
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


class ActiveRuntime(Runtime):
    """A runtime secure against active adversaries.

    This class currently inherits most of its functionality from the
    normal L{Runtime} class and is thus I{not} yet secure.
    """

    def __init__(self, player, threshold, options=None):
        """Initialize runtime."""

        #: A hyper-invertible matrix.
        #:
        #: It should be suitable for L{self.num_players} players, but
        #: since we don't know the total number of players yet, we set
        #: it to C{None} here and update it as necessary.
        self._hyper = None
        Runtime.__init__(self, player, threshold, options)

    @increment_pc
    def mul(self, share_x, share_y):
        """Multiplication of shares.

        Preprocessing: 1 multiplication triple.
        Communication: 2 openings.
        """
        assert isinstance(share_x, Share) or isinstance(share_y, Share), \
            "At least one of share_x and share_y must be a Share."

        if not isinstance(share_x, Share):
            # Then share_y must be a Share => local multiplication. We
            # clone first to avoid changing share_y.
            result = share_y.clone()
            result.addCallback(lambda y: share_x * y)
            return result
        if not isinstance(share_y, Share):
            # Likewise when share_y is a constant.
            result = share_x.clone()
            result.addCallback(lambda x: x * share_y)
            return result

        # At this point both share_x and share_y must be Share
        # objects. We multiply them via a multiplication triple.
        def finish_mul(triple):
            a, b, c = triple
            d = self.open(share_x - a)
            e = self.open(share_y - b)

            # TODO: We ought to be able to simply do
            #
            #   return d*e + d*y + e*x + c
            #
            # but that leads to infinite recursion since d and e are
            # Shares, not FieldElements. So we have to do a bit more
            # work... The following callback also leads to recursion, but
            # only one level since d and e are FieldElements now, which
            # means that we return in the above if statements.
            result = gather_shares([d, e])
            result.addCallback(lambda (d,e): d*e + d*b + e*a + c)
            return result

        # This will be the result, a Share object.
        result = Share(self, share_x.field)
        # This is the Deferred we will do processing on.
        triple = self.get_triple(share_x.field)
        self.schedule_callback(triple, finish_mul)
        # We add the result to the chains in triple.
        triple.chainDeferred(result)
        return result

    @increment_pc
    def single_share_random(self, T, degree, field):
        """Share a random secret.

        The guarantee is that a number of shares are made and out of
        those, the T that are returned by this method will be correct
        sharings of a random number using C{degree} as the polynomial
        degree.

        @param T: The number of shares output.
        @param degree: The degree of the polynomial.
        @param field: The field over which to share the secret.
        """
        # TODO: Move common code between single_share and
        # double_share_random out to their own methods.
        inputters = range(1, self.num_players + 1)
        if self._hyper is None:
            self._hyper = hyper(self.num_players, field)

        # Generate a random element.
        si = rand.randint(0, field.modulus - 1)

        # Every player shares the random value with two thresholds.
        shares = self.shamir_share(inputters, field, si, degree)

        # Turn the shares into a column vector.
        svec = Matrix([shares]).transpose()

        # Apply the hyper-invertible matrix to svec1 and svec2.
        rvec = (self._hyper * svec)

        # Get back to normal lists of shares.
        svec = svec.transpose().rows[0]
        rvec = rvec.transpose().rows[0]

        def verify(shares):
            """Verify shares.

            It is checked that they correspond to polynomial of the
            expected degree.

            If the verification succeeds, the T shares are returned,
            otherwise the errback is called.
            """
            # TODO: This is necessary since shamir.recombine expects
            # to receive a list of *pairs* of field elements.
            shares = map(lambda (i, s): (field(i+1), s), enumerate(shares))

            # Verify the sharings. If any of the assertions fail and
            # raise an exception, the errbacks will be called on the
            # share returned by single_share_random.
            assert shamir.verify_sharing(shares, degree), "Could not verify"

            # If we reach this point the n - T shares were verified
            # and we can safely return the first T shares.
            return rvec[:T]

        def exchange(svec):
            """Exchange and (if possible) verify shares."""
            pc = tuple(self.program_counter)

            # We send our shares to the verifying players.
            for offset, share in enumerate(svec):
                if T+1+offset != self.id:
                    self.protocols[T+1+offset].sendShare(pc, share)

            if self.id > T:
                # The other players will send us their shares of si_1
                # and si_2 and we will verify it.
                si = []
                for peer_id in inputters:
                    if self.id == peer_id:
                        si.append(Share(self, field, svec[peer_id - T - 1]))
                    else:
                        si.append(self._expect_share(peer_id, field))
                result = gatherResults(si)
                self.schedule_callback(result, verify)
                return result
            else:
                # We cannot verify anything, so we just return the
                # first T shares.
                return rvec[:T]

        result = gather_shares(svec[T:])
        self.schedule_callback(result, exchange)
        return result

    @increment_pc
    def double_share_random(self, T, d1, d2, field):
        """Double-share a random secret using two polynomials.

        The guarantee is that a number of shares are made and out of
        those, the T that are returned by this method will be correct
        double-sharings of a random number using d1 and d2 as the
        polynomial degrees.

        @param T: The number of double-shares output.
        @param d1: The degree of the first polynomial.
        @param d2: The degree of the second polynomial.
        @param field: The field over which to share the secret.
        """
        inputters = range(1, self.num_players + 1)
        if self._hyper is None:
            self._hyper = hyper(self.num_players, field)

        # Generate a random element.
        si = rand.randint(0, field.modulus - 1)

        # Every player shares the random value with two thresholds.
        d1_shares = self.shamir_share(inputters, field, si, d1)
        d2_shares = self.shamir_share(inputters, field, si, d2)

        # Turn the shares into a column vector.
        svec1 = Matrix([d1_shares]).transpose()
        svec2 = Matrix([d2_shares]).transpose()

        # Apply the hyper-invertible matrix to svec1 and svec2.
        rvec1 = (self._hyper * svec1)
        rvec2 = (self._hyper * svec2)

        # Get back to normal lists of shares.
        svec1 = svec1.transpose().rows[0]
        svec2 = svec2.transpose().rows[0]
        rvec1 = rvec1.transpose().rows[0]
        rvec2 = rvec2.transpose().rows[0]

        def verify(shares):
            """Verify shares.

            It is checked that they correspond to polynomial of the
            expected degrees and that they can be recombined to the
            same value.

            If the verification succeeds, the T double shares are
            returned, otherwise the errback is called.
            """
            si_1, si_2 = shares

            # TODO: This is necessary since shamir.recombine expects
            # to receive a list of *pairs* of field elements.
            si_1 = map(lambda (i, s): (field(i+1), s), enumerate(si_1))
            si_2 = map(lambda (i, s): (field(i+1), s), enumerate(si_2))

            # Verify the sharings. If any of the assertions fail and
            # raise an exception, the errbacks will be called on the
            # double share returned by double_share_random.
            assert shamir.verify_sharing(si_1, d1), "Could not verify si_1"
            assert shamir.verify_sharing(si_2, d2), "Could not verify si_2"
            assert shamir.recombine(si_1[:d1+1]) == shamir.recombine(si_2[:d2+1]), \
                "Shares do not recombine to the same value"

            # If we reach this point the n - T shares were verified
            # and we can safely return the first T shares.
            return (rvec1[:T], rvec2[:T])

        def exchange(shares):
            """Exchange and (if possible) verify shares."""
            svec1, svec2 = shares
            pc = tuple(self.program_counter)

            # We send our shares to the verifying players.
            for offset, (s1, s2) in enumerate(zip(svec1, svec2)):
                if T+1+offset != self.id:
                    self.protocols[T+1+offset].sendShare(pc, s1)
                    self.protocols[T+1+offset].sendShare(pc, s2)

            if self.id > T:
                # The other players will send us their shares of si_1
                # and si_2 and we will verify it.
                si_1 = []
                si_2 = []
                for peer_id in inputters:
                    if self.id == peer_id:
                        si_1.append(Share(self, field, svec1[peer_id - T - 1]))
                        si_2.append(Share(self, field, svec2[peer_id - T - 1]))
                    else:
                        si_1.append(self._expect_share(peer_id, field))
                        si_2.append(self._expect_share(peer_id, field))
                result = gatherResults([gatherResults(si_1), gatherResults(si_2)])
                self.schedule_callback(result, verify)
                return result
            else:
                # We cannot verify anything, so we just return the
                # first T shares.
                return (rvec1[:T], rvec2[:T])

        result = gather_shares([gather_shares(svec1[T:]), gather_shares(svec2[T:])])
        self.schedule_callback(result, exchange)
        return result

    @increment_pc
    @preprocess("generate_triples")
    def get_triple(self, field):
        # This is a waste, but this function is only called if there
        # are no pre-processed triples left.
        count, result = self.generate_triples(field)
        result.addCallback(lambda triples: triples[0])
        return result

    @increment_pc
    def generate_triples(self, field):
        """Generate multiplication triples.

        These are random numbers M{a}, M{b}, and M{c} such that M{c =
        ab}. This function can be used in pre-processing.

        @return: Number of triples returned and a Deferred which will
        yield a C{list} of 3-tuples.
        @returntype: (C{int}, C{list} of Deferred C{(Share, Share,
        Share)})
        """
        n = self.num_players
        t = self.threshold
        T = n - 2*t

        def make_triple(shares):
            a_t, b_t, (r_t, r_2t) = shares

            c_2t = []
            for i in range(T):
                # Multiply a[i] and b[i] without resharing.
                ci = gather_shares([a_t[i], b_t[i]])
                ci.addCallback(lambda (ai, bi): ai * bi)
                c_2t.append(ci)

            d_2t = [c_2t[i] - r_2t[i] for i in range(T)]
            d = [self.open(d_2t[i], threshold=2*t) for i in range(T)]
            c_t = [r_t[i] + d[i] for i in range(T)]
            return zip(a_t, b_t, c_t)

        single_a = self.single_share_random(T, t, field)
        single_b = self.single_share_random(T, t, field)
        double_c = self.double_share_random(T, t, 2*t, field)

        result = gatherResults([single_a, single_b, double_c])
        self.schedule_callback(result, make_triple)
        return T, result

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

        bracha_echo = {}
        bracha_ready = {}
        bracha_sent_ready = {}
        bracha_delivered = {}
        
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
            ids = bracha_echo.setdefault(message, [])
            ready = bracha_sent_ready.setdefault(message, False)

            if peer_id not in ids:
                ids.append(peer_id)
                if len(ids) >= ceil((n+t+1)/2) and not ready:
                    bracha_sent_ready[message] = True
                    unsafe_broadcast("ready", message)
                    ready_received(message, self.id)

        def ready_received(message, peer_id):
            # This is called when we receive a ready message. It
            # updates the ready count for the message. Depending on
            # the count, we may either stay in the same state or enter
            # the ready or delivered state.
            ids = bracha_ready.setdefault(message, [])
            ready = bracha_sent_ready.setdefault(message, False)
            delivered = bracha_delivered.setdefault(message, False)
            if peer_id not in ids:
                ids.append(peer_id)
                if len(ids) == t+1 and not ready:
                    bracha_sent_ready[message] = True
                    unsafe_broadcast("ready", message)
                    ready_received(message, self.id)

                elif len(ids) == 2*t+1 and not delivered:
                    bracha_delivered[message] = True
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


def create_runtime(id, players, threshold, options=None, runtime_class=Runtime):
    """Create a L{Runtime} and connect to the other players.

    This function should be used in normal programs instead of
    instantiating the Runtime directly. This function makes sure that
    the Runtime is correctly connected to the other players.

    The return value is a Deferred which will trigger when the runtime
    is ready. Add your protocol as a callback on this Deferred using
    code like this::

        def protocol(runtime):
            a, b, c = runtime.shamir_share([1, 2, 3], Zp, input)

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

if __name__ == "__main__":
    import doctest    #pragma NO COVER
    doctest.testmod() #pragma NO COVER
