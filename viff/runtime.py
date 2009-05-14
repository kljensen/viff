# -*- coding: utf-8 -*-
#
# Copyright 2007, 2008, 2009 VIFF Development Team.
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
import struct
from optparse import OptionParser, OptionGroup
from collections import deque

from viff.field import GF256, FieldElement
from viff.util import wrapper, rand, deep_wait, track_memory_usage

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.error import ConnectionDone, CannotListenError
from twisted.internet.defer import Deferred, DeferredList, gatherResults, succeed
from twisted.internet.defer import maybeDeferred
from twisted.internet.protocol import ReconnectingClientFactory, ServerFactory
from twisted.protocols.basic import Int16StringReceiver

# Constants used by ShareExchanger.
SHARE    = 0
ECHO     = 1
READY    = 2
SEND     = 3
PAILLIER = 4


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
        return self.runtime.add(self, other)

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
        return self.runtime.mul(self, other)

    def __pow__(self, exponent):
        """Exponentation to known integer exponents."""
        return self.runtime.pow(self, exponent)

    def __xor__(self, other):
        """Exclusive-or."""
        return self.runtime.xor(self, other)

    def __rxor__(self, other):
        """Exclusive-or (reflected argument version)."""
        return self.runtime.xor(self, other)

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
    """

    def __init__(self):
        self.peer_id = None
        self.lost_connection = Deferred()
        #: Data expected to be received in the future.
        self.incoming_data = {}
        self.waiting_deferreds = {}

    def connectionMade(self):
        self.sendString(str(self.factory.runtime.id))

    def connectionLost(self, reason):
        reason.trap(ConnectionDone)
        self.lost_connection.callback(self)

    def stringReceived(self, string):
        """Called when a share is received.

        The string received is unpacked into the program counter, and
        a data part. The data is passed the appropriate Deferred in
        :class:`self.incoming_data`.
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
            try:
                pc_size, data_size, data_type = struct.unpack("!HHB", string[:5])
                fmt = "!%dI%ds" % (pc_size, data_size)
                unpacked = struct.unpack(fmt, string[5:])

                program_counter = unpacked[:pc_size]
                data = unpacked[-1]

                key = (program_counter, data_type)

                if key in self.waiting_deferreds:
                    deq = self.waiting_deferreds[key]
                    deferred = deq.popleft()
                    if not deq:
                        del self.waiting_deferreds[key]
                    deferred.callback(data)
                else:
                    deq = self.incoming_data.setdefault(key, deque())
                    deq.append(data)
            except struct.error, e:
                self.factory.runtime.abort(self, e)

    def sendData(self, program_counter, data_type, data):
        """Send data to the peer.

        The *program_counter* is a tuple of unsigned integers, the
        *data_type* is an unsigned byte and *data* is a string.

        The data is encoded as follows::

          +---------+-----------+-----------+--------+--------------+
          | pc_size | data_size | data_type |   pc   |     data     |
          +---------+-----------+-----------+--------+--------------+
            2 bytes   2 bytes      1 byte     varies      varies

        The program counter takes up ``4 * pc_size`` bytes, the data
        takes up ``data_size`` bytes.
        """
        pc_size = len(program_counter)
        data_size = len(data)
        fmt = "!HHB%dI%ds" % (pc_size, data_size)
        t = (pc_size, data_size, data_type) + program_counter + (data,)
        self.sendString(struct.pack(fmt, *t))

    def sendShare(self, program_counter, share):
        """Send a share.

        The program counter and the share are converted to bytes and
        sent to the peer.
        """
        self.sendData(program_counter, SHARE, hex(share.value))

    def loseConnection(self):
        """Disconnect this protocol instance."""
        self.transport.loseConnection()


class ShareExchangerFactory(ReconnectingClientFactory, ServerFactory):
    """Factory for creating ShareExchanger protocols."""

    protocol = ShareExchanger
    maxDelay = 3
    factor = 1.234567 # About half of the Twisted default

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
    :attr:`Runtime._pool`, and if that fails it falls back to the
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


class Runtime:
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
        group.add_option("--track-memory", action="store_true",
                         help="Track memory usage over time.")

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
                            profile=False,
                            track_memory=False)

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
        print "Synchronizing shutdown...",

        def close_connections(_):
            print "done."
            print "Closing connections...",
            results = [maybeDeferred(self.port.stopListening)]
            for protocol in self.protocols.itervalues():
                results.append(protocol.lost_connection)
                protocol.loseConnection()
            return DeferredList(results)

        def stop_reactor(_):
            print "done."
            print "Stopping reactor...",
            reactor.stop()
            print "done."

        sync = self.synchronize()
        sync.addCallback(close_connections)
        sync.addCallback(stop_reactor)
        return sync

    def abort(self, protocol, exc):
        """Abort the execution due to an exception.

        The *protocol* received bad data which resulted in *exc* being
        raised when unpacking.
        """
        print "*** bad data from Player %d: %s" % (protocol.peer_id, exc)
        print "*** aborting!"
        for p in self.protocols.itervalues():
            p.loseConnection()
        reactor.stop()
        print "*** all protocols disconnected"

    def wait_for(self, *vars):
        """Make the runtime wait for the variables given.

        The runtime is shut down when all variables are calculated.
        """
        dl = DeferredList(vars)
        self.schedule_callback(dl, lambda _: self.shutdown())

    @increment_pc
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
        saved_pc = self.program_counter[:]

        @wrapper(func)
        def callback_wrapper(*args, **kwargs):
            """Wrapper for a callback which ensures a correct PC."""
            try:
                current_pc = self.program_counter[:]
                self.program_counter[:] = saved_pc
                return func(*args, **kwargs)
            finally:
                self.program_counter[:] = current_pc

        return deferred.addCallback(callback_wrapper, *args, **kwargs)

    @increment_pc
    def synchronize(self):
        """Introduce a synchronization point.

        Returns a :class:`Deferred` which will trigger if and when all
        other players have made their calls to :meth:`synchronize`. By
        adding callbacks to the returned :class:`Deferred`, one can
        divide a protocol execution into disjoint phases.
        """
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

        if key in self.protocols[peer_id].incoming_data:
            # We have already received some data from the other side.
            deq = self.protocols[peer_id].incoming_data[key]
            data = deq.popleft()
            if not deq:
                del self.protocols[peer_id].incoming_data[key]
            deferred.callback(data)
        else:
            # We have not yet received anything from the other side.
            deq = self.protocols[peer_id].waiting_deferreds.setdefault(key, deque())
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
        share.addCallback(lambda value: field(long(value, 16)))
        self._expect_data(peer_id, SHARE, share)
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

        - The Deferred must yield a list of the promised length.

        - The list contains the actual data. This data can be either a
          Deferred or a tuple of Deferreds.

        The :meth:`ActiveRuntime.generate_triples` method is an
        example of a method fulfilling this interface.
        """

        def update(results, program_counters):
            # We concatenate the sub-lists in results.
            results = sum(results, [])

            # The pool must map program counters to Deferreds to
            # present a uniform interface for the functions we
            # pre-process.
            results = map(succeed, results)

            # Update the pool with pairs of program counter and data.
            self._pool.update(zip(program_counters, results))

            # Return a Deferred that waits on the individual results.
            # This is important to make it possible for the players to
            # avoid starting before the pre-processing is complete.
            return deep_wait(results)

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

    def input(self, inputters, field, number=None):
        """Input *number* to the computation.

        The players listed in *inputters* must provide an input
        number, everybody will receive a list with :class:`Share`
        objects, one from each *inputter*. If only a single player is
        listed in *inputters*, then a :class:`Share` is given back
        directly.
        """
        raise NotImplemented("Override this abstract method in a subclass.")

    def output(self, share, receivers=None):
        """Open *share* to *receivers* (defaults to all players).

        Returns a :class:`Share` to players with IDs in *receivers*
        and :const:`None` to the remaining players.
        """
        raise NotImplemented("Override this abstract method in a subclass.")

    def add(self, share_a, share_b):
        """Secure addition.
        
        At least one of the arguments must be a :class:`Share`, the
        other can be a :class:`FieldElement` or a (possible long)
        Python integer."""
        raise NotImplemented("Override this abstract method in a subclass.")

    def mul(self, share_a, share_b):
        """Secure multiplication.
        
        At least one of the arguments must be a :class:`Share`, the
        other can be a :class:`FieldElement` or a (possible long)
        Python integer."""
        raise NotImplemented("Override this abstract method in a subclass.")


def make_runtime_class(runtime_class=None, mixins=None):
    """Creates a new runtime class with *runtime_class* as a base
    class mixing in the *mixins*. By default
    :class:`viff.passive.PassiveRuntime` will be used.
    """
    if runtime_class is None:
        # The import is put here because of circular depencencies
        # between viff.runtime and viff.passive.
        from viff.passive import PassiveRuntime
        runtime_class = PassiveRuntime
    if mixins is None:
        return runtime_class
    else:
        # We must include at least one new-style class in bases. We
        # include it last to avoid overriding __init__ from the other
        # base classes.
        bases = (runtime_class,) + tuple(mixins) + (object,)
        return type("ExtendedRuntime", bases, {})

def create_runtime(id, players, threshold, options=None, runtime_class=None):
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
    if options and options.track_memory:
        lc = LoopingCall(track_memory_usage)
        # Five times per second seems like a fair value. Besides, the
        # kernel will track the peak memory usage for us anyway.
        lc.start(0.2)
        reactor.addSystemEventTrigger("after", "shutdown", track_memory_usage)

    if runtime_class is None:
        # The import is put here because of circular depencencies
        # between viff.runtime and viff.passive.
        from viff.passive import PassiveRuntime
        runtime_class = PassiveRuntime

    if options and options.profile:
        # To collect profiling information we monkey patch reactor.run
        # to do the collecting. It would be nicer to simply start the
        # profiler here and stop it upon shutdown, but this triggers
        # http://bugs.python.org/issue1375 since the start and stop
        # calls are in different stack frames.
        import cProfile
        prof = cProfile.Profile()
        old_run = reactor.run
        def new_run(*args, **kwargs):
            print "Starting reactor with profiling"
            prof.runcall(old_run, *args, **kwargs)

            import pstats
            stats = pstats.Stats(prof)
            print
            stats.strip_dirs()
            stats.sort_stats("time", "calls")
            stats.print_stats(40)
            stats.dump_stats("player-%d.pstats" % id)
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
                try:
                    ctx.use_certificate_file('player-%d.cert' % id)
                    ctx.use_privatekey_file('player-%d.key' % id)
                    ctx.check_privatekey()
                    ctx.load_verify_locations('ca.cert')
                    ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
                                   lambda conn, cert, errnum, depth, ok: ok)
                    self.ctx = ctx
                except SSL.Error, e:
                    print "SSL errors - did you forget to generate certificates?"
                    for (lib, func, reason) in e.args[0]:
                        print "* %s in %s: %s" % (func, lib, reason)
                    raise SystemExit("Stopping program")

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
