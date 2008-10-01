# -*- coding: utf-8 -*-
#
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

"""VIFF runtime. This is where the virtual ideal functionality is
hiding! The runtime is responsible for sharing inputs, handling
communication, and running the calculations.

Each player participating in the protocol will instantiate a
:class:`Runtime` object and use it for the calculations.

The Runtime returns :class:`Share` objects for most operations, and
these can be added, subtracted, and multiplied as normal thanks to
overloaded arithmetic operators. The runtime will take care of
scheduling things correctly behind the scenes.
"""
from __future__ import division

__docformat__ = "restructuredtext"

import time
import marshal
from optparse import OptionParser, OptionGroup
from collections import deque

from viff import shamir
from viff.prss import prss, prss_lsb, prss_zero
from viff.field import GF256, FieldElement
from viff.util import wrapper, rand, profile

from twisted.internet import reactor
from twisted.internet.error import ConnectionDone, CannotListenError
from twisted.internet.defer import Deferred, DeferredList, gatherResults, succeed
from twisted.internet.defer import maybeDeferred
from twisted.internet.protocol import ReconnectingClientFactory, ServerFactory
from twisted.protocols.basic import Int16StringReceiver


class Share(Deferred):
    """A shared number.

    The :class:`Runtime` operates on shares, represented by this class.
    Shares are asynchronous in the sense that they promise to attain a
    value at some point in the future.

    Shares overload the arithmetic operations so that ``x = a + b``
    will create a new share *x*, which will eventually contain the
    sum of *a* and *b*. Each share is associated with a
    :class:`Runtime` and the arithmetic operations simply call back to
    that runtime.
    """

    def __init__(self, runtime, field, value=None):
        """Initialize a share.

        If an initial value is given, it will be passed to
        :meth:`callback` right away.
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

    def __eq__(self, other):
        """Equality testing."""
        return self.runtime.equal(self, other)

    def __neq__(self, other):
        """Negated equality testing."""
        return 1 - self.runtime.equal(self, other)


    def clone(self):
        """Clone a share.

        Works like :meth:`util.clone_deferred` except that it returns a new
        :class:`Share` instead of a :class:`Deferred`.
        """

        def split_result(result):
            clone.callback(result)
            return result
        clone = Share(self.runtime, self.field)
        self.addCallback(split_result)
        return clone


class ShareList(Share):
    """Create a share that waits on a number of other shares.

    Roughly modelled after the Twisted :class:`DeferredList`
    class. The advantage of this class is that it is a :class:`Share`
    (not just a :class:`Deferred`) and that it can be made to trigger
    when a certain threshold of the shares are ready. This example
    shows how the :meth:`pprint` callback is triggered when *a* and
    *c* are ready:

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

    The :meth:`pprint` function is called with a list of pairs. The first
    component of each pair is a boolean indicating if the callback or
    errback method was called on the corresponding :class:`Share`, and
    the second component is the value given to the callback/errback.

    If a threshold less than the full number of shares is used, some
    of the pairs may be missing and :const:`None` is used instead. In
    the example above the *b* share arrived later than *a* and *c*,
    and so the list contains a :const:`None` on its place.
    """
    def __init__(self, shares, threshold=None):
        """Initialize a share list.

        The list of shares must be non-empty and if a threshold is
        given, it must hold that ``0 < threshold <= len(shares)``. The
        default threshold is ``len(shares)``.
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

    Roughly modelled after the Twisted :meth:`gatherResults`
    function. It takes a list of shares and returns a new
    :class:`Share` which will be triggered with a list of values,
    namely the values from the initial shares:

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

    The :mod:`marshal` module is used for converting the data to bytes
    for the network and to convert back again to structured data.
    """

    def __init__(self):
        self.peer_id = None
        self.lost_connection = Deferred()
        #: Data expected to be received in the future.
        self.incoming_data = {}

    def connectionMade(self):
        self.sendString(str(self.factory.runtime.id))

    def connectionLost(self, reason):
        reason.trap(ConnectionDone)
        self.lost_connection.callback(self)

    def stringReceived(self, string):
        """Called when a share is received.

        The string received is unmarshalled into the program counter,
        and a data part. The data is passed the appropriate Deferred
        in :class:`self.incoming_data`.
        """
        if self.peer_id is None:
            # TODO: Handle ValueError if the string cannot be decoded.
            self.peer_id = int(string)
            try:
                cert = self.transport.getPeerCertificate()
            except AttributeError:
                cert = None
            if cert:
                # The player ID are stored in the serial number of the
                # certificate -- this makes it easy to check that the
                # player is who he claims to be.
                if cert.get_serial_number() != self.peer_id:
                    print "Peer %s claims to be %d, aborting!" \
                        % (cert.get_subject(), self.peer_id)
                    self.transport.loseConnection()
            self.factory.identify_peer(self)
        else:
            program_counter, data_type, data = marshal.loads(string)
            key = (program_counter, data_type)

            deq = self.incoming_data.setdefault(key, deque())
            if deq and isinstance(deq[0], Deferred):
                deferred = deq.popleft()
                if not deq:
                    del self.incoming_data[key]
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
        """
        self.sendData(program_counter, "share", share.value)

    def loseConnection(self):
        """Disconnect this protocol instance."""
        self.transport.loseConnection()


class ShareExchangerFactory(ReconnectingClientFactory, ServerFactory):
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

    def clientConnectionLost(self, connector, reason):
        reason.trap(ConnectionDone)


def increment_pc(method):
    """Make *method* automatically increment the program counter.

    Adding this decorator to a :class:`Runtime` method will ensure
    that the program counter is incremented correctly when entering
    the method.
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
    first tries to get the data needed from
    :attr:`BasicRuntime._pool`, and if that fails it falls back to the
    original method.

    The *generator* method is only used to record where the data
    should be generated from, the method is not actually called. This
    must be the name of the method (a string) and not the method
    itself.
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
        group.add_option("--no-ssl", action="store_false", dest="ssl",
                         help="Disable the use of secure SSL connections.")
        group.add_option("--ssl", action="store_true",
                         help=("Enable the use of secure SSL connections "
                               "(if the OpenSSL bindings are available)."))
        group.add_option("--deferred-debug", action="store_true",
                         help="Enable extra debug output for deferreds.")
        group.add_option("--profile", action="store_true",
                         help="Collect and print profiling information.")

        try:
            # Using __import__ since we do not use the module, we are
            # only interested in the side-effect.
            __import__('OpenSSL')
            have_openssl = True
        except ImportError:
            have_openssl = False

        parser.set_defaults(bit_length=32,
                            security_parameter=30,
                            ssl=have_openssl,
                            deferred_debug=False,
                            profile=False)

    def __init__(self, player, threshold, options=None):
        """Initialize runtime.

        Initialized a runtime owned by the given, the threshold, and
        optionally a set of options. The runtime has no network
        connections and knows of no other players -- the
        :func:`create_runtime` function should be used instead to
        create a usable runtime.
        """
        assert threshold > 0, "Must use a positive threshold."
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
        self.program_counter = [0]

        #: Connections to the other players.
        #:
        #: Mapping from from Player ID to :class:`ShareExchanger`
        #: objects.
        self.protocols = {}

        #: Number of known players.
        #:
        #: Equal to ``len(self.players)``, but storing it here is more
        #: direct.
        self.num_players = 0

        #: Information on players.
        #:
        #: Mapping from Player ID to :class:`Player` objects.
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
        print "Synchronizing shutdown... ",

        def close_connections(_):
            print "done."
            print "Closing connections... ",
            results = [maybeDeferred(self.port.stopListening)]
            for protocol in self.protocols.itervalues():
                results.append(protocol.lost_connection)
                protocol.loseConnection()
            return DeferredList(results)

        def stop_reactor(_):
            print "done."
            print "Stopping reactor... ",
            reactor.stop()
            print "done."

        sync = self.synchronize()
        sync.addCallback(close_connections)
        sync.addCallback(stop_reactor)
        return sync

    def wait_for(self, *vars):
        """Make the runtime wait for the variables given.

        The runtime is shut down when all variables are calculated.
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
        :meth:`addCallback`.
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
            if not deq:
                del self.protocols[peer_id].incoming_data[key]
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

        The *program* specifies which methods to call and with which
        arguments. The generator methods called must adhere to the
        following interface:

        - They must return a ``(int, Deferred)`` tuple where the
          ``int`` tells us how many items of pre-processed data the
          :class:`Deferred` will yield.

        - The Deferred must yield a list of the promissed length.

        - The list contains the actual data. This data can be either a
          Deferred or a tuple of Deferreds.

        The :meth:`ActiveRuntime.generate_triples` method is an
        example of a method fulfilling this interface.
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

    The runtime is used for sharing values (:meth:`shamir_share` or
    :meth:`prss_share`) into :class:`Share` object and opening such
    shares (:meth:`open`) again. Calculations on shares is normally
    done through overloaded arithmetic operations, but it is also
    possible to call :meth:`add`, :meth:`mul`, etc. directly if one
    prefers.

    Each player in the protocol uses a :class:`Runtime` object. To
    create an instance and connect it correctly with the other
    players, please use the :func:`create_runtime` function instead of
    instantiating a Runtime directly. The :func:`create_runtime`
    function will take care of setting up network connections and
    return a :class:`Deferred` which triggers with the
    :class:`Runtime` object when it is ready.
    """

    def __init__(self, player, threshold, options=None):
        """Initialize runtime."""
        BasicRuntime.__init__(self, player, threshold, options)

    @increment_pc
    def open(self, share, receivers=None, threshold=None):
        """Open a secret sharing.

        The *receivers* are the players that will eventually obtain
        the opened result. The default is to let everybody know the
        result. By default the :attr:`threshold` + 1 shares are
        reconstructed, but *threshold* can be used to override this.

        Communication cost: every player sends one share to each
        receiving player.
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

    @profile
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

    @profile
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
        subset of players specified in *inputters*. Each inputter
        provides an integer. The result is a list of shares, one for
        each inputter.

        The protocol uses the pseudo-random secret sharing technique
        described in the paper "Share Conversion, Pseudorandom
        Secret-Sharing and Applications to Secure Computation" by
        Ronald Cramer, Ivan Damgård, and Yuval Ishai in Proc. of TCC
        2005, LNCS 3378. `Download
        <http://www.cs.technion.ac.il/~yuvali/pubs/CDI05.ps>`__

        Communication cost: Each inputter does one broadcast.
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
    def prss_share_zero(self, field):
        """Generate shares of the zero element from the field given.

        Communication cost: none.
        """
        # Key used for PRSS.
        prss_key = tuple(self.program_counter)
        prfs = self.players[self.id].prfs(field.modulus)
        zero_share = prss_zero(self.num_players, self.threshold, self.id,
                               field, prfs, prss_key)
        return Share(self, field, zero_share)

    @increment_pc
    def prss_double_share(self, field):
        """Make a double-sharing using PRSS.

        The pair of shares will have degree t and 2t where t is the
        default threshold for the runtime.
        """
        r_t = self.prss_share_random(field)
        z_2t = self.prss_share_zero(field)
        return (r_t, r_t + z_2t)

    @increment_pc
    def prss_share_bit_double(self, field):
        """Share a random bit over *field* and GF256.

        The protocol is described in "Efficient Conversion of
        Secret-shared Values Between Different Fields" by Ivan Damgård
        and Rune Thorbek available as `Cryptology ePrint Archive,
        Report 2008/221 <http://eprint.iacr.org/2008/221>`__.
        """
        n = self.num_players
        k = self.options.security_parameter
        prfs = self.players[self.id].prfs(2**k)
        prss_key = tuple(self.program_counter)

        b_p = self.prss_share_random(field, binary=True)
        r_p, r_lsb = prss_lsb(n, self.id, field, prfs, prss_key)

        b = self.open(b_p + r_p)
        # Extract least significant bit and change field to GF256.
        b.addCallback(lambda i: GF256(i.value & 1))
        b.field = GF256

        # Use r_lsb to flip b as needed.
        return (b_p, b ^ r_lsb)

    @increment_pc
    def prss_shamir_share_bit_double(self, field):
        """Shamir share a random bit over *field* and GF256."""
        n = self.num_players
        k = self.options.security_parameter
        prfs = self.players[self.id].prfs(2**k)
        prss_key = tuple(self.program_counter)
        inputters = range(1, self.num_players + 1)

        ri = rand.randint(0, 2**k - 1)
        ri_p = self.shamir_share(inputters, field, ri)
        ri_lsb = self.shamir_share(inputters, GF256, ri & 1)

        r_p = reduce(self.add, ri_p)
        r_lsb = reduce(self.add, ri_lsb)

        b_p = self.prss_share_random(field, binary=True)
        b = self.open(b_p + r_p)
        # Extract least significant bit and change field to GF256.
        b.addCallback(lambda i: GF256(i.value & 1))
        b.field = GF256

        # Use r_lsb to flip b as needed.
        return (b_p, b ^ r_lsb)

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
        """Secret share *number* over *field* using Shamir's method.

        The number is shared using polynomial of degree *threshold*
        (defaults to :attr:`threshold`). Returns a list of shares
        unless there is only one inputter in which case the
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

def make_runtime_class(runtime_class=Runtime, mixins=None):
    """Creates a new runtime class with *runtime_class* as a base
    class mixing in the *mixins*.
    """
    if mixins is None:
        return runtime_class
    else:
        # We must include at least one new-style class in bases. We
        # include it last to avoid overriding __init__ from the other
        # base classes.
        bases = (runtime_class,) + tuple(mixins) + (object,)
        return type("ExtendedRuntime", bases, {})

def create_runtime(id, players, threshold, options=None, runtime_class=Runtime):
    """Create a :class:`Runtime` and connect to the other players.

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
    if options and options.profile:
        # To collect profiling information we monkey patch reactor.run
        # to do the collecting. It would be nicer to simply start the
        # profiler here and stop it upon shutdown, but this triggers
        # http://bugs.python.org/issue1375 since the start and stop
        # calls are in different stack frames.
        import hotshot
        prof = hotshot.Profile("viff-%d.prof" % id)
        old_run = reactor.run
        def new_run(*args, **kwargs):
            print "Starting reactor with profiling"
            prof.runcall(old_run, *args, **kwargs)

            import sys
            import hotshot.stats
            print "Loading profiling statistics...",
            sys.stdout.flush()
            stats = hotshot.stats.load("viff-%d.prof" % id)
            print "done."
            print
            stats.strip_dirs()
            stats.sort_stats("time", "calls")
            stats.print_stats(40)
        reactor.run = new_run

    # This will yield a Runtime when all protocols are connected.
    result = Deferred()

    # Create a runtime that knows about no other players than itself.
    # It will eventually be returned in result when the factory has
    # determined that all needed protocols are ready.
    runtime = runtime_class(players[id], threshold, options)
    factory = ShareExchangerFactory(runtime, players, result)

    if options and options.ssl:
        print "Using SSL"
        from twisted.internet.ssl import ContextFactory
        from OpenSSL import SSL

        class SSLContextFactory(ContextFactory):
            def __init__(self, id):
                """Create new SSL context factory for *id*."""
                self.id = id
                ctx = SSL.Context(SSL.SSLv3_METHOD)
                # TODO: Make the file names configurable.
                ctx.use_certificate_file('player-%d.cert' % id)
                ctx.use_privatekey_file('player-%d.key' % id)
                ctx.check_privatekey()

                ctx.load_verify_locations('ca.cert')
                ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
                               lambda conn, cert, errnum, depth, ok: ok)
                self.ctx = ctx

            def getContext(self):
                return self.ctx

        ctx_factory = SSLContextFactory(id)
        listen = lambda port: reactor.listenSSL(port, factory, ctx_factory)
        connect = lambda host, port: reactor.connectSSL(host, port, factory, ctx_factory)
    else:
        print "Not using SSL"
        listen = lambda port: reactor.listenTCP(port, factory)
        connect = lambda host, port: reactor.connectTCP(host, port, factory)

    port = players[id].port
    runtime.port = None
    delay = 2
    while runtime.port is None:
        # We keep trying to listen on the port, but with an
        # exponentially increasing delay between each attempt.
        try:
            runtime.port = listen(port)
        except CannotListenError, e:
            delay *= 1 + rand.random()
            print "Error listening on port %d: %s" % (port, e.socketError[1])
            print "Will try again in %d seconds" % delay
            time.sleep(delay)
    print "Listening on port %d" % port

    for peer_id, player in players.iteritems():
        if peer_id > id:
            print "Will connect to %s" % player
            connect(player.host, player.port)

    return result

if __name__ == "__main__":
    import doctest    #pragma NO COVER
    doctest.testmod() #pragma NO COVER
