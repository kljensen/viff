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

"""
PySMPC runtime.

The runtime is responsible for sharing inputs, handling communication,
and running the calculations.
"""

import marshal
import socket
#from pprint import pformat, pprint
# TODO: use SystemRandom instead (runs out of entropy?)
from random import Random

from pysmpc import shamir
from pysmpc.prss import prss, PRF
from pysmpc.field import FieldElement, IntegerFieldElement, GF256Element, GMPIntegerFieldElement

from twisted.internet import defer, reactor
from twisted.internet.defer import Deferred, DeferredList, gatherResults
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol
from twisted.protocols.basic import Int16StringReceiver

# TODO: move this to another file, probably together with the
# configuration loading/saving machinery.
class Player:
    """
    Wrapper for information about a player in the protocol.
    """

    def __init__(self, id, host, port, keys=None, dealer_keys=None):
        self.id = id
        self.host = host
        self.port = port

        if keys is not None:
            self.prfs = {}

            # TODO: using the modulus here requires that it has been
            # set previously! Since players are constructed when a
            # config file is loaded, one must set the modulus before
            # loading any config files.
            for modulus in 2, GF256Element.modulus, IntegerFieldElement.modulus:
                prfs = {}
                for subset, key in keys.iteritems():
                    prfs[subset] = PRF(key, modulus)
                self.prfs[modulus] = prfs

        if dealer_keys is not None:
            self.dealer_prfs = {}

            for modulus in GF256Element.modulus, IntegerFieldElement.modulus:
                dealers = {}
                for dealer in dealer_keys:
                    prfs = {}
                    for subset, key in dealer_keys[dealer].iteritems():
                        prfs[subset] = PRF(key, modulus)
                    dealers[dealer] = prfs
                self.dealer_prfs[modulus] = dealers
                    
                    
    def __repr__(self):
        return "<Player %d: %s:%d>" % (self.id, self.host, self.port)

def output(arg, format="output: %s"):
    """
    Callback used for printing values while still passing them along
    to the next callback the processing chain.
    """
    print format % arg
    return arg


indent = 0

_trace_counters = {}

def trace(func):
    """
    Decorator which will make print function entry and exit.
    """
    def wrapper(*args, **kwargs):
        """
        Wrapper.
        """
        global indent
        count = _trace_counters.setdefault(func.func_name, 1)
        try:
            print "%s-> Entering: %s (%d)" % ("  " * indent, func.func_name, count)
            indent += 1
            _trace_counters[func.func_name] += 1
            return func(*args, **kwargs)
        finally:
            indent -= 1
            print "%s<- Exiting:  %s (%d)" % ("  " * indent, func.func_name, count)
    
    return wrapper

def println(format="", *args):
    """
    Print an indented line.
    """
    if len(args) > 0:
        format = format % args

    print "%s %s" % ("  " * indent, format)

def dump_incoming_shares(shares):
    """
    Debug dump of the incomming shares.
    """
    print "Incoming shares:"
    shares = list(shares.iteritems())
    shares.sort()
    for key, value in shares:
        print "  %s -> %s" % (key, value)
        #if len(value.callbacks) > 0:
        #    print "  %d callbacks:" % len(value.callbacks)
        #    for callback in value.callbacks:
        #        print "    %s" % (callback[0], )

    print


class ShareExchanger(Int16StringReceiver):
    """
    The protocol responsible for exchanging shares.
    """

    #@trace
    def __init__(self, id):
        self.id = id
        vals = [IntegerFieldElement, GMPIntegerFieldElement, GF256Element]
        keys = range(len(vals))
        self.class_to_type = dict(zip(vals, keys))
        self.type_to_class = dict(zip(keys, vals))
        
    #@trace
    def stringReceived(self, string):
        program_counter, share_type, value = marshal.loads(string)
        share = self.type_to_class[share_type].unmarshal(value)
        key = (program_counter, self.id)

        shares = self.factory.incoming_shares
        try:
            reactor.callLater(0, shares.pop(key).callback, share)
        except KeyError:
            shares[key] = defer.succeed(share)

        # TODO: marshal.loads can raise EOFError, ValueError, and
        # TypeError. They should be handled somehow.

    #@trace
    def sendShare(self, program_counter, share):
        """
        Send a share.
        """
        #println("Sending to id=%d: program_counter=%s, share=%s",
        #        self.id, program_counter, share)

        # TODO: find a nicer way to communicate the type of the share.
        data = (program_counter,
                self.class_to_type[type(share)],
                share.marshal())
        self.sendString(marshal.dumps(data))
        return self


    def loseConnection(self):
        """
        Disconnect this protocol instance.
        """
        self.transport.loseConnection()
        # TODO: this ought to be the last callback and so it might not
        # be necessary to pass self on?
        return self

class ShareExchangerFactory(ServerFactory, ClientFactory):
    """
    Factory for creating ShareExchanger protocols.
    """

    #@trace
    def __init__(self, incoming_shares, port_player_mapping, protocols):
        println("ShareExchangerFactory: %s", port_player_mapping)

        self.incoming_shares = incoming_shares
        self.port_player_mapping = port_player_mapping
        self.protocols = protocols

    #@trace
    def buildProtocol(self, addr):
        """
        Build a new protocol for communicating with addr.
        """
        port = addr.port - (addr.port % 100)
        # Resolving the hostname into an IP address is a blocking
        # operation, but this is acceptable since buildProtocol is
        # only called when the runtime is initialized.
        ip = socket.gethostbyname(addr.host)

        id = self.port_player_mapping[(ip, port)]
        println("Peer id: %s", id)
        
        p = ShareExchanger(id)
        p.factory = self

        reactor.callLater(0, self.protocols[id].callback, p)
        return p

 
########################################

class Runtime:
    """
    The PySMPC runtime.

    Each party in the protocol must instantiate an object from this
    class and use it for all calculations.
    """

    #@trace
    def __init__(self, players, id, threshold):
        self.players = players
        self.id = id
        self.threshold = threshold

        self.program_counter = 0

        # Dictionary mapping (program_counter, player_id) to Deferreds
        # yielding shares.
        self.incoming_shares = {}

        # List of Deferreds yielding protocols
        self.protocols = dict((id, Deferred()) for id, p in players.iteritems())
        self.protocols[self.id].callback("Unused")
        # Now try connecting...
        self.connect()

    def connect(self):
        # Resolving the hostname into an IP address is a blocking
        # operation, but this is acceptable since it is only done when
        # the runtime is initialized.
        ip_addresses = [socket.gethostbyname(p.host) for p in self.players.values()]

        mapping = dict()
        for ip, (id, p) in zip(ip_addresses, self.players.iteritems()):
            mapping[(ip, p.port)] = id

        factory = ShareExchangerFactory(self.incoming_shares, mapping,
                                        self.protocols)

        reactor.listenTCP(self.players[self.id].port, factory)

        for id, player in self.players.iteritems():
            if id > self.id:
                bind_port = self.players[self.id].port + id
                println("Will connect to %s from port %d", player, bind_port)
                reactor.connectTCP(player.host, player.port, factory,
                                   bindAddress=(self.players[self.id].host,
                                                bind_port))

        println("Initialized Runtime with %d players, threshold %d",
                len(self.players), self.threshold)

    def shutdown(self):
        """
        Callback used for shutting down the runtime gracefully.
        """
        println("Initiating shutdown sequence.")
        for _, protocol in self.protocols.iteritems():
            protocol.addCallback(lambda p: p.loseConnection())
        println("Waiting 1 second")
        reactor.callLater(1, reactor.stop)

    def wait_for(self, *vars):
        """
        Start the runtime and wait for the variables given. The
        runtime is shut down when all variables are calculated.
        """
        dl = DeferredList(vars)
        dl.addCallback(lambda _: self.shutdown())

        reactor.run()
        println("Reactor stopped")

    #@trace
    def init_pc(self, program_counter):
        """
        Initialize a program counter.
        """
        if program_counter is None:
            self.program_counter += 1
            program_counter = (self.program_counter,)
        return program_counter

    #@trace
    def inc_pc(self, program_counter):
        """
        Increment a program counter.
        """
        program_counter = program_counter[:-1] + (program_counter[-1]+1,)
        #println("**** Inc PC: %s ****", program_counter)
        return program_counter
 
    #@trace
    def sub_pc(self, program_counter):
        """
        Generate a sub-counter from a program counter.
        """
        program_counter = program_counter + (1,)
        #println("****** Sub PC: %s ******", program_counter)
        return program_counter

    #@trace
    def open(self, sharing, threshold=None, program_counter=None):
        """
        Open a share. Returns nothing, the share given is mutated.

        Communication cost: n broadcasts.
        """
        assert isinstance(sharing, Deferred)
        program_counter = self.init_pc(program_counter)
        if threshold is None:
            threshold = self.threshold

        def broadcast(share):
            """
            Broadcast share to all players.
            """
            assert isinstance(share, FieldElement)

            deferreds = []
            for id in self.players:
                d = self.exchange_shares(program_counter, id, share)
                d.addCallback(lambda s, id: (s.field(id), s), id)
                deferreds.append(d)

            # TODO: This list ought to trigger as soon as more than
            # threshold shares has been received.
            return self._recombine(deferreds, threshold)

        sharing.addCallback(broadcast)
        # TODO: should open() return a new deferred?
        
    #@trace
    def add(self, share_a, share_b):
        """
        Addition of shares.

        Communication cost: none.
        """
        if not isinstance(share_a, Deferred):
            share_a = defer.succeed(share_a)
        if not isinstance(share_b, Deferred):
            share_b = defer.succeed(share_b)

        result = gatherResults([share_a, share_b])
        result.addCallback(lambda (a, b): a + b)
        return result

    #@trace
    def sub(self, share_a, share_b):
        """
        Subtraction of shares.

        Communication cost: none.
        """
        if not isinstance(share_a, Deferred):
            share_a = defer.succeed(share_a)
        if not isinstance(share_b, Deferred):
            share_b = defer.succeed(share_b)

        result = gatherResults([share_a, share_b])
        result.addCallback(lambda (a, b): a - b)
        return result

    #@trace
    def mul(self, share_a, share_b, program_counter=None):
        """
        Multiplication of shares.

        Communication cost: 1 Shamir sharing.
        """
        # TODO:  mul accept FieldElements and do quick local
        # multiplication in that case. If two FieldElements are given,
        # return a FieldElement.
        program_counter = self.init_pc(program_counter)

        if not isinstance(share_a, Deferred):
            share_a = defer.succeed(share_a)
        if not isinstance(share_b, Deferred):
            share_b = defer.succeed(share_b)

        result = gatherResults([share_a, share_b])
        result.addCallback(lambda (a, b): a * b)
        result.addCallback(self._shamir_share, self.sub_pc(program_counter))
        result.addCallback(self._recombine, threshold=2*self.threshold)
        return result
    
    #@trace
    def xor_int(self, share_a, share_b, program_counter=None):
        """
        Exclusive-or of integer sharings.
        
        Communication cost: 1 multiplication.
        """
        if not isinstance(share_a, Deferred):
            share_a = defer.succeed(share_a)
        if not isinstance(share_b, Deferred):
            share_b = defer.succeed(share_b)

        program_counter = self.init_pc(program_counter)
        share_c = self.mul(share_a, share_b, self.sub_pc(program_counter))
        result = gatherResults([share_a, share_b, share_c])
        result.addCallback(lambda (a, b, c): a + b - 2*c)
        return result

    xor_bit = add

    def _share_random(self, prfs, id, field, key):
        """
        Do a PRSS using pseudo-random numbers from the field given.
        """
        return prss(len(self.players), self.threshold, id, field, prfs, key)

    def _share_known(self, element, field, program_counter):
        # The shares for which we have all the keys.
        all_shares = []
        
        # Shares we calculate from doing PRSS with the other players.
        tmp_shares = {}

        dealer_prfs = self.players[self.id].dealer_prfs[field.modulus]

        # TODO: Stop calculating shares for all_shares at
        # self.threshold+1 since that is all we need to do the Shamir
        # recombine below.
        for player in self.players:
            # TODO: when player == self.id, the two calls to
            # _share_random are the same.
            share = self._share_random(dealer_prfs[self.id], player,
                                       field, program_counter)
            all_shares.append((field(player), share))

            tmp_shares[player] = self._share_random(dealer_prfs[player],
                                                    self.id,
                                                    field, program_counter)

        # We can now calculate what was shared and derive the
        # correction factor.
        shared = shamir.recombine(all_shares[:self.threshold+1])
        correction = element - shared

        result = []
        for player in self.players:
            # TODO: more efficient broadcast?
            d = self.exchange_shares(program_counter, player, correction)
            # We have to add our own share to the correction factor
            # received.
            d.addCallback(lambda c, s: s + c, tmp_shares[player])
            result.append(d)

        return result


    def share_int(self, integer, program_counter=None):
        """Share an integer.

        Communication cost: 1 broadcast."""
        assert isinstance(integer, IntegerFieldElement)
        program_counter = self.init_pc(program_counter)

        return self._share_known(integer, IntegerFieldElement, program_counter)


    def share_bit(self, bit, program_counter=None):
        """Share a bit.

        Communication cost: 1 broadcast."""
        assert isinstance(bit, GF256Element)
        program_counter = self.init_pc(program_counter)

        return self._share_known(bit, GF256Element, program_counter)


    #@trace
    def share_random_int(self, binary=False, program_counter=None):
        """
        Generate integer shares of a uniformly random number
        IntegerFieldElement. No player learns the value of the
        integer.

        Communication cost: none if binary=False, 1 open otherwise.
        """
        program_counter = self.init_pc(program_counter)
        prfs = self.players[self.id].prfs[IntegerFieldElement.modulus]
        share = self._share_random(prfs, self.id, IntegerFieldElement,
                                   program_counter)

        if not binary:
            return defer.succeed(share)

        result = self.mul(share, share)

        program_counter = self.sub_pc(program_counter)
        # Open the square and compute a square-root
        self.open(result, 2*self.threshold, program_counter)

        def finish(square, share, binary, program_counter):
            if square == 0:
                # We were unlucky, try again...
                return self.share_random_int(binary, self.sub_pc(program_counter))
            else:
                # We can finish the calculation
                root = square.sqrt()
                # When the root is computed, we divide the share and
                # convert the resulting -1/1 share into a 0/1 share.
                two = IntegerFieldElement(2)
                return defer.succeed((share/root + 1) / two)

        result.addCallback(finish, share, binary, program_counter)
        return result
        
    #@trace
    def share_random_bit(self, binary=False, program_counter=None):
        """
        Generate shares of a uniformly random GF256Element, or a 0/1
        element if binary is True. No player learns the value of the
        element.

        Communication cost: none.
        """
        program_counter = self.init_pc(program_counter)

        if binary:
            modulus = 2
        else:
            modulus = GF256Element.modulus
        prfs = self.players[self.id].prfs[modulus]
        share = self._share_random(prfs, self.id, GF256Element, program_counter)
        return defer.succeed(share)

    def _shamir_share(self, number, program_counter):
        """
        Share a FieldElement using Shamir sharing.

        Returns a list of (id, share) pairs.
        """
        shares = shamir.share(number, self.threshold, len(self.players))
        #println("Shares of %s: %s", number, shares)
        
        result = []
        for other_id, share in shares:
            d = self.exchange_shares(program_counter, other_id.value, share)
            d.addCallback(lambda share, id: (id, share), other_id)
            result.append(d)

        return result

    #@trace
    def shamir_share(self, number, program_counter=None):
        """
        Share an IntegerFieldElement using Shamir sharing.

        Returns a list of shares.

        Communication cost: n elements transmitted.
        """
        assert isinstance(number, FieldElement)
        program_counter = self.init_pc(program_counter)

        def split(pair):
            pair.addCallback(lambda (_, share): share)

        result = self._shamir_share(number, program_counter)
        map(split, result)
        return result

    def bit_to_int(self, b_share, program_counter=None):
        """
        Converts a GF256Element sharing of a bit to a
        IntegerFieldElement sharing of the same bit.
        """
        # TODO: This ought to be the reverse of int_to_bit, but it is
        # not needed right now.
        pass

    #@trace
    def int_to_bit(self, i_share, program_counter=None):
        """
        Converts an IntegerFieldElement sharing of a bit to a
        GF256Element sharing of the same bit.
        """
        program_counter = self.init_pc(program_counter)

        # TODO: temporary seed for consistant testing
        bit = Random(0).randint(0, 1)

        program_counter = self.sub_pc(program_counter)
        bit_shares = self.share_bit(GF256Element(bit), program_counter)

        program_counter = self.inc_pc(program_counter)
        int_shares = self.share_int(IntegerFieldElement(bit), program_counter)

        tmp = i_share
        for int_share in int_shares:
            tmp = self.xor_int(tmp, int_share)

        # We open the tmp variable and convert the value to a bit
        # sharing.
        program_counter = self.inc_pc(program_counter)
        self.open(tmp, program_counter=program_counter)
        tmp.addCallback(lambda i: GF256Element(i.value))
        
        for bit_share in bit_shares:
            tmp = self.xor_bit(tmp, bit_share)

        return tmp

    #@trace
    def greater_than(self, share_a, share_b, program_counter=None):
        """
        Computes share_a >= share_b, where share_a and share_b are
        IntegerFieldElements. The result is aGF256Element share.
        """
        program_counter = self.init_pc(program_counter)

        # TODO: get these from a configuration file or similar
        l = 32 # bit-length of input numbers
        m = l + 2
        t = m + 1

        # Preprocessing begin

        # TODO: why must these relations hold?
        assert 2**(l+1) + 2**t < IntegerFieldElement.modulus, "2^(l+1) + 2^t < p must hold"
        assert len(self.players) + 2 < 2**l

        int_bits = []
        program_counter = self.sub_pc(program_counter)
        for _ in range(m):
            program_counter = self.inc_pc(program_counter)
            int_bits.append(self.share_random_int(True, program_counter))

        # We must use int_bits without adding callbacks to the bits --
        # having int_b wait on them ensures this.

        def bits_to_int(bits):
            """
            Converts a list of bits to an integer.
            """
            return sum([2**i * b for (i, b) in enumerate(bits)])

        int_b = gatherResults(int_bits)
        int_b.addCallback(bits_to_int)

        bit_bits = []
        for b in int_bits:
            program_counter = self.inc_pc(program_counter)
            # TODO: this changes int_bits! It should be okay since
            # int_bits is not used any further, but still...
            bit_bits.append(self.int_to_bit(b, program_counter))

        # Preprocessing done

        a = self.add(self.sub(share_a, share_b), 2**l)
        T = self.add(self.sub(2**t, int_b), a)
        program_counter = self.inc_pc(program_counter)
        self.open(T, program_counter=program_counter)

        #@trace
        def calculate(results, program_counter):
            """
            Finish the calculation.
            """
            T = results[0]
            bit_bits = results[1:]

            vec = [(GF256Element(0), GF256Element(0))]

            # Calculate the vector, using only the first l bits
            for i, bi in enumerate(bit_bits[:l]):
                Ti = GF256Element(T.bit(i))
                ci = self.xor_bit(bi, Ti)
                vec.append((ci, Ti))

            #@trace
            def diamond((top_a, bot_a), (top_b, bot_b), program_counter):
                """
                The "diamond-operator" where

                (x, X) `diamond` (0, Y) = (0, Y)
                (x, X) `diamond` (1, Y) = (x, X)
                """
                program_counter = self.sub_pc(program_counter)
                top = self.mul(top_a, top_b, program_counter)
                #   = x * y
                program_counter = self.inc_pc(program_counter)
                bot = self.xor_bit(self.mul(top_b, self.xor_bit(bot_a, bot_b),
                                            program_counter), bot_b)
                #   = (y * (X ^ Y)) ^ Y

                return (top, bot)

            while len(vec) > 1:
                tmp = []
                while len(vec) > 1:
                    program_counter = self.inc_pc(program_counter)
                    tmp.append(diamond(vec.pop(0), vec.pop(0), program_counter))
                if len(vec) == 1:
                    tmp.append(vec[0])
                vec = tmp

            return self.xor_bit(GF256Element(T.bit(l)),
                                self.xor_bit(bit_bits[l], vec[0][1]))

        result = gatherResults([T] + bit_bits)
        program_counter = self.inc_pc(program_counter)
        result.addCallback(calculate, program_counter)
        return result
        

    ########################################################################
    ########################################################################


    #@trace
    def exchange_shares(self, program_counter, id, share):
        """
        Exchange shares with another player.

        We send the player our share and record a Deferred which will
        trigger when the share from the other side arrives.
        """
        assert isinstance(share, FieldElement)
        #println("exchange_shares sending: program_counter=%s, id=%d, share=%s",
        #        program_counter, id, share)

        if id == self.id:
            return defer.succeed(share)
        else:
            key = (program_counter, id)
            if key not in self.incoming_shares:
                self.incoming_shares[key] = Deferred()

            # Send the share to the other side
            self.protocols[id].addCallback(ShareExchanger.sendShare,
                                           program_counter, share)
            return self.incoming_shares[key]

    def _recombine(self, shares, threshold):
        """
        Shamir recombine a list of deferreds which must yield
        (id,share) pairs.
        """
        assert len(shares) > threshold
        result = gatherResults(shares[:threshold+1])
        result.addCallback(shamir.recombine)
        return result
