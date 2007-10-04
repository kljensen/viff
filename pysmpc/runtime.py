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

"""PySMPC runtime.

The runtime is responsible for sharing inputs, handling communication,
and running the calculations.
"""

import marshal
import socket

from pysmpc import shamir
from pysmpc.prss import prss
from pysmpc.field import GF, GF256, FieldElement
from pysmpc.util import rand, dprint

from twisted.internet import defer, reactor
from twisted.internet.defer import Deferred, DeferredList, gatherResults
from twisted.internet.protocol import ClientFactory, ServerFactory
from twisted.protocols.basic import Int16StringReceiver


_indent = 0
_trace_counters = {}

def trace(func):
    """Trace function entry and exit."""
    def wrapper(*args, **kwargs):
        """
        Wrapper.
        """
        global _indent
        count = _trace_counters.setdefault(func.func_name, 1)
        try:
            print "%s-> Entering: %s (%d)" % ("  " * _indent,
                                              func.func_name, count)
            _indent += 1
            _trace_counters[func.func_name] += 1
            return func(*args, **kwargs)
        finally:
            _indent -= 1
            print "%s<- Exiting:  %s (%d)" % ("  " * _indent,
                                              func.func_name, count)
    return wrapper

def println(format="", *args):
    """Print a line indented according to the stack depth."""
    if len(args) > 0:
        format = format % args

    print "%s %s" % ("  " * _indent, format)


class ShareExchanger(Int16StringReceiver):
    """Send and receive shares."""

    #@trace
    def __init__(self, id):
        self.id = id
        
    #@trace
    def stringReceived(self, string):
        program_counter, modulus, value = marshal.loads(string)

        share = GF(modulus)(value)
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
        """Send a share."""
        #println("Sending to id=%d: program_counter=%s, share=%s",
        #        self.id, program_counter, share)

        data = (program_counter, share.modulus, share.value)
        self.sendString(marshal.dumps(data))
        return self

    def loseConnection(self):
        """Disconnect this protocol instance."""
        self.transport.loseConnection()
        # TODO: this ought to be the last callback and so it might not
        # be necessary to pass self on?
        return self

class ShareExchangerFactory(ServerFactory, ClientFactory):
    """Factory for creating ShareExchanger protocols."""

    #@trace
    def __init__(self, incoming_shares, port_player_mapping, protocols):
        println("ShareExchangerFactory: %s", port_player_mapping)

        self.incoming_shares = incoming_shares
        self.port_player_mapping = port_player_mapping
        self.protocols = protocols

    #@trace
    def buildProtocol(self, addr):
        """Build and return a new protocol for communicating with addr."""
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

 
#@trace
def inc_pc(program_counter):
    """Increment a program counter."""
    return program_counter[:-1] + (program_counter[-1]+1,)

#@trace
def sub_pc(program_counter):
    """Generate a sub-counter from a program counter."""
    return program_counter + (1,)


class Runtime:
    """The PySMPC runtime.

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
        self.protocols = dict((id, Deferred())
                              for id, p in players.iteritems())
        self.protocols[self.id].callback("Unused")
        # Now try connecting...
        self.connect()

    def connect(self):
        # Resolving the hostname into an IP address is a blocking
        # operation, but this is acceptable since it is only done when
        # the runtime is initialized.
        ip_addresses = [socket.gethostbyname(p.host)
                        for p in self.players.values()]

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
        """Shutdown the runtime.

        All connections are closed and the runtime cannot be used
        again after this has been called.
        """
        println("Initiating shutdown sequence.")
        for protocol in self.protocols.itervalues():
            protocol.addCallback(lambda p: p.loseConnection())
        println("Waiting 1 second")
        reactor.callLater(1, reactor.stop)

    def wait_for(self, *vars):
        """Start the runtime and wait for the variables given.

        The runtime is shut down when all variables are calculated.
        """
        dl = DeferredList(vars)
        dl.addCallback(lambda _: self.shutdown())
        reactor.run()
        println("Reactor stopped")

    #@trace
    def init_pc(self, program_counter):
        """Initialize a program counter."""
        if program_counter is None:
            self.program_counter += 1
            program_counter = (self.program_counter,)
        return program_counter

    #@trace
    def open(self, sharing, threshold=None, program_counter=None):
        """Open a share. Returns nothing, the share given is mutated.

        Communication cost: n broadcasts.
        """
        assert isinstance(sharing, Deferred)
        program_counter = self.init_pc(program_counter)
        if threshold is None:
            threshold = self.threshold

        def broadcast(share):
            """Broadcast share to all players."""
            assert isinstance(share, FieldElement)
            deferreds = []
            for id in self.players:
                d = self._exchange_shares(program_counter, id, share)
                d.addCallback(lambda s, id: (s.field(id), s), id)
                deferreds.append(d)

            # TODO: This list ought to trigger as soon as more than
            # threshold shares has been received.
            return self._recombine(deferreds, threshold)

        sharing.addCallback(broadcast)
        # TODO: should open() return a new deferred?
        
    #@trace
    def add(self, share_a, share_b):
        """Addition of shares.

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
        """Subtraction of shares.

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
        """Multiplication of shares.

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
        result.addCallback(self._shamir_share, sub_pc(program_counter))
        result.addCallback(self._recombine, threshold=2*self.threshold)
        return result
    
    #@trace
    def xor_int(self, share_a, share_b, program_counter=None):
        """Exclusive-or of integer sharings.
        
        Communication cost: 1 multiplication.
        """
        if not isinstance(share_a, Deferred):
            share_a = defer.succeed(share_a)
        if not isinstance(share_b, Deferred):
            share_b = defer.succeed(share_b)

        program_counter = self.init_pc(program_counter)
        share_c = self.mul(share_a, share_b, sub_pc(program_counter))
        result = gatherResults([share_a, share_b, share_c])
        result.addCallback(lambda (a, b, c): a + b - 2*c)
        return result

    xor_bit = add

    def prss_share(self, element, program_counter=None):
        """PRSS share a field element.

        Communication cost: 1 broadcast.
        """
        assert isinstance(element, FieldElement)
        program_counter = self.init_pc(program_counter)
        field = type(element)
        n = len(self.players)

        # The shares for which we have all the keys.
        all_shares = []
        
        # Shares we calculate from doing PRSS with the other players.
        tmp_shares = {}

        dealer_prfs = self.players[self.id].dealer_prfs(field.modulus)

        # TODO: Stop calculating shares for all_shares at
        # self.threshold+1 since that is all we need to do the Shamir
        # recombine below.
        for player in self.players:
            # TODO: when player == self.id, the two calls to prss are
            # the same.
            share = prss(n, player, field, dealer_prfs[self.id],
                         program_counter)
            all_shares.append((field(player), share))
            tmp_shares[player] = prss(n, self.id, field, dealer_prfs[player],
                                      program_counter)

        # We can now calculate what was shared and derive the
        # correction factor.
        shared = shamir.recombine(all_shares[:self.threshold+1])
        correction = element - shared

        result = []
        for player in self.players:
            # TODO: more efficient broadcast?
            d = self._exchange_shares(program_counter, player, correction)
            # We have to add our own share to the correction factor
            # received.
            d.addCallback(lambda c, s: s + c, tmp_shares[player])
            result.append(d)
        return result

    def prss_share_random(self, field, binary=False, program_counter=None):
        """Generate shares of a uniformly random element from the field given.

        If binary is True, a 0/1 element is generated. No player
        learns the value of the element.

        Communication cost: none if binary=False, 1 open otherwise.
        """
        program_counter = self.init_pc(program_counter)

        if field is GF256 and binary:
            modulus = 2
        else:
            modulus = field.modulus

        prfs = self.players[self.id].prfs(modulus)
        share = prss(len(self.players), self.id, field, prfs, program_counter)

        if field is GF256 or not binary:
            return defer.succeed(share)

        result = self.mul(share, share)

        program_counter = sub_pc(program_counter)
        # Open the square and compute a square-root
        self.open(result, 2*self.threshold, program_counter)

        def finish(square, share, binary, program_counter):
            if square == 0:
                # We were unlucky, try again...
                return self.prss_share_random(field, binary,
                                              sub_pc(program_counter))
            else:
                # We can finish the calculation
                root = square.sqrt()
                # When the root is computed, we divide the share and
                # convert the resulting -1/1 share into a 0/1 share.
                two = field(2)
                return defer.succeed((share/root + 1) / two)

        result.addCallback(finish, share, binary, program_counter)
        return result

    def _shamir_share(self, number, program_counter):
        """Share a FieldElement using Shamir sharing.

        Returns a list of (id, share) pairs.
        """
        shares = shamir.share(number, self.threshold, len(self.players))
        #println("Shares of %s: %s", number, shares)
        
        result = []
        for other_id, share in shares:
            d = self._exchange_shares(program_counter, other_id.value, share)
            d.addCallback(lambda share, id: (id, share), other_id)
            result.append(d)

        return result

    #@trace
    def shamir_share(self, number, program_counter=None):
        """Share a field element using Shamir sharing.

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

    #@trace
    def convert_bit_share(self, share, src_field, dst_field,
                          program_counter=None):
        """Convert a 0/1 share from src_field into dst_field."""
        program_counter = self.init_pc(program_counter)
        bit = rand.randint(0, 1)

        program_counter = sub_pc(program_counter)
        dst_shares = self.prss_share(dst_field(bit), program_counter)

        program_counter = inc_pc(program_counter)
        src_shares = self.prss_share(src_field(bit), program_counter)

        # TODO: merge xor_int and xor_bit into an xor method and move
        # this decission there.
        if src_field is GF256:
            xor = self.xor_bit
        else:
            xor = self.xor_int
        
        # TODO: Using a parallel reduce here seems to be slower than
        # using the built-in reduce.
        tmp = reduce(xor, src_shares, share)

        # We open tmp and convert the value into a field element from
        # the dst_field.
        program_counter = inc_pc(program_counter)
        self.open(tmp, program_counter=program_counter)
        tmp.addCallback(lambda i: dst_field(i.value))
        
        if dst_field is GF256:
            xor = self.xor_bit
        else:
            xor = self.xor_int

        return reduce(xor, dst_shares, tmp)

    #@trace
    def convert_bit_share_II(self, share, src_field, dst_field,
                          program_counter=None, k=None):
        """Convert a 0/1 share from src_field into dst_field."""

        program_counter = self.init_pc(program_counter)
        program_counter = sub_pc(program_counter)


        #TODO: don't do log like this...
        def log(x):
            result = 0
            while x > 1:
                result +=1
                x /= 2
            return result+1 # Error for powers of two...
            

        if k==None:
            k = 30
        l = k + log(dst_field.modulus)
        # TODO assert field sizes are OK...




        this_mask = rand.randint(0, (2**l) -1)

        # Share large random values in the big field and reduced ones in the small...
        program_counter = inc_pc(program_counter)
        src_shares = self.prss_share(src_field(this_mask), program_counter)
        program_counter = inc_pc(program_counter)
        dst_shares = self.prss_share(dst_field(this_mask), program_counter)


        tmp = reduce(self.add, src_shares, share)

        # We open tmp and convert the value into a field element from
        # the dst_field.
        program_counter = inc_pc(program_counter)
        self.open(tmp, program_counter=program_counter)

        tmp.addCallback(lambda i: dst_field(i.value))

        full_mask = reduce(self.add, dst_shares)

        return self.sub(tmp, full_mask)


    #@trace
    def greater_than(self, share_a, share_b, field, program_counter=None):
        """Compute share_a >= share_b.

        Both arguments must be from the field given. The result is a
        GF256 share.
        """
        program_counter = self.init_pc(program_counter)

        # TODO: get these from a configuration file or similar
        l = 32 # bit-length of input numbers
        m = l + 2
        t = m + 1

        # Preprocessing begin

        assert 2**(l+1) + 2**t < field.modulus, "2^(l+1) + 2^t < p must hold"
        assert len(self.players) + 2 < 2**l

        int_bits = []
        program_counter = sub_pc(program_counter)
        for _ in range(m):
            program_counter = inc_pc(program_counter)
            int_bits.append(self.prss_share_random(field, True,
                                                   program_counter))

        # We must use int_bits without adding callbacks to the bits --
        # having int_b wait on them ensures this.

        def bits_to_int(bits):
            """Converts a list of bits to an integer."""
            return sum([2**i * b for (i, b) in enumerate(bits)])

        int_b = gatherResults(int_bits)
        int_b.addCallback(bits_to_int)

        bit_bits = []
        for b in int_bits:
            program_counter = inc_pc(program_counter)
            # TODO: this changes int_bits! It should be okay since
            # int_bits is not used any further, but still...
            bit_bits.append(self.convert_bit_share(b, field, GF256,
                                                   program_counter))

        # Preprocessing done

        a = self.add(self.sub(share_a, share_b), 2**l)
        T = self.add(self.sub(2**t, int_b), a)
        program_counter = inc_pc(program_counter)
        self.open(T, program_counter=program_counter)

        #@trace
        def calculate(results, program_counter):
            """Finish the calculation."""
            T = results[0]
            bit_bits = results[1:]

            vec = [(GF256(0), GF256(0))]

            # Calculate the vector, using only the first l bits
            for i, bi in enumerate(bit_bits[:l]):
                Ti = GF256(T.bit(i))
                ci = self.xor_bit(bi, Ti)
                vec.append((ci, Ti))

            #@trace
            def diamond((top_a, bot_a), (top_b, bot_b), program_counter):
                """The "diamond-operator".

                Defined by

                (x, X) `diamond` (0, Y) = (0, Y)
                (x, X) `diamond` (1, Y) = (x, X)
                """
                program_counter = sub_pc(program_counter)
                top = self.mul(top_a, top_b, program_counter)
                #   = x * y
                program_counter = inc_pc(program_counter)
                bot = self.xor_bit(self.mul(top_b, self.xor_bit(bot_a, bot_b),
                                            program_counter), bot_b)
                #   = (y * (X ^ Y)) ^ Y

                return (top, bot)

            # Reduce using the diamond operator. We want to do as much
            # as possible in parallel while being careful not to
            # switch the order of elements since the diamond operator
            # is non-commutative.
            while len(vec) > 1:
                tmp = []
                while len(vec) > 1:
                    program_counter = inc_pc(program_counter)
                    tmp.append(diamond(vec.pop(0), vec.pop(0), program_counter))
                if len(vec) == 1:
                    tmp.append(vec[0])
                vec = tmp

            return self.xor_bit(GF256(T.bit(l)),
                                self.xor_bit(bit_bits[l], vec[0][1]))

        result = gatherResults([T] + bit_bits)
        program_counter = inc_pc(program_counter)
        result.addCallback(calculate, program_counter)
        return result
        
    ########################################################################
    ########################################################################


    #@trace
    def greater_thanII_preproc(self, field, smallField=None,
                               program_counter=None, l=None, k=None):
        """Preprocessing for greater_thanII."""
        program_counter = self.init_pc(program_counter)
        program_counter = sub_pc(program_counter)

        if smallField is None:
            smallField = field
        if l is None:
            l = 32
        if k is None:
            k = 30
        # l++ for technical reasons
        # need an extra bit to avoid troubles with equal inputs
        l += 1

        # TODO: verify asserts are correct...
        assert field.modulus > 2**(l+2) + 2**(l+k), "Field too small"
        assert smallField.modulus > 3 + 3*l, "smallField too small"


        # TODO: do not generate all bits, only $l$ of them
        # could perhaps do PRSS over smaller subset?
        r_bitsField = []
        for _ in range(l+k):
            program_counter = inc_pc(program_counter)
            r_bitsField.append(self.prss_share_random(field, True, program_counter))

        # TODO: compute r_full from r_modl and top bits, not from scratch
        r_full = field(0)
        for (i,b) in enumerate(r_bitsField):
            program_counter = inc_pc(program_counter)
            r_full = self.add(r_full,
                              self.mul(b, field(2**i),
                                       program_counter=program_counter))

        r_bitsField = r_bitsField[:l]
        r_modl = field(0)
        for (i,b) in enumerate(r_bitsField):
            program_counter = inc_pc(program_counter)
            r_modl = self.add(r_modl,
                              self.mul(b, field(2**i),
                                       program_counter=program_counter))
            

        # Transfer bits to smallField
        if field is smallField:
            r_bits = r_bitsField
        else:
            r_bits = []
            for bit in r_bitsField:
                program_counter = inc_pc(program_counter)
                r_bits.append(self.convert_bit_share_II(bit, field, smallField,
                                                        program_counter=program_counter))

        program_counter = inc_pc(program_counter)
        s_bit = self.prss_share_random(field, binary=True,
                                       program_counter=program_counter)

        program_counter = inc_pc(program_counter)
        s_bitSmallField = self.convert_bit_share_II(s_bit, field, smallField,
                                                    program_counter=program_counter)
        program_counter = inc_pc(program_counter)
        s_sign = self.add(smallField(1),
                          self.mul(s_bitSmallField, smallField(-2),
                                   program_counter=program_counter))


        # m: uniformly random -- should be non-zero, however, this
        # happens with negligible probability
        # TODO: small field, no longer negligible probability of zero -- update
        program_counter = inc_pc(program_counter)
        mask = self.prss_share_random(smallField, False, program_counter)

        program_counter = inc_pc(program_counter)
        mask_2 = self.prss_share_random(smallField, False, program_counter)
        program_counter = inc_pc(program_counter)
        mask_OK = self.mul(mask, mask_2, program_counter = program_counter)
        program_counter = inc_pc(program_counter)
        self.open(mask_OK, program_counter=program_counter)
        dprint("Mask_OK: %s", mask_OK)
        


        return field, smallField, s_bit, s_sign, mask, r_full, r_modl, r_bits
        
        

        ##################################################
        # Preprocessing done
        ##################################################
        

    #@trace
    def greater_thanII_online(self, share_a, share_b, preproc, field,
                              program_counter=None, l=None):
        """Compute share_a >= share_b.
        Result is shared.
        """
        program_counter = self.init_pc(program_counter)
        program_counter = sub_pc(program_counter)

        if l == None:
            l = 32

        # increment l as a, b are increased
        l +=1
        # a = 2a+1; b= 2b // ensures inputs not equal
        program_counter = inc_pc(program_counter)
        share_a = self.add(self.mul(field(2),
                                    share_a,
                                    program_counter=program_counter),
                           field(1))
        program_counter = inc_pc(program_counter)
        share_b = self.mul(field(2), share_b, program_counter=program_counter)

        
        ##################################################
        # Unpack preprocessing
        ##################################################
        #TODO: assert fields are the same...
        field, smallField, s_bit, s_sign, mask, r_full, r_modl, r_bits = preproc
        assert l == len(r_bits), "preprocessing does not match " \
            "online parameters"

        ##################################################
        # Begin online computation
        ##################################################
        # c = 2**l + a - b + r
        z = self.add(self.sub(share_a, share_b), field(2**l))
        c = self.add(r_full, z)


        program_counter = inc_pc(program_counter)
        self.open(c, program_counter=program_counter)


        #@trace
        def calculate(c, program_counter):
            """Finish the calculation."""
            c_bits = [smallField(c.bit(i)) for i in range(l)]

            sumXORs = [0]*l
            # sumXORs[i] = sumXORs[i+1] + r_bits[i+1] + c_(i+1) - 2*r_bits[i+1]*c_(i+1)
            for i in range(l-2, -1, -1):
                # sumXORs[i] = \sum_{j=i+1}^{l-1} r_j\oplus c_j
                program_counter = inc_pc(program_counter)
                sumXORs[i] = self.add(sumXORs[i+1],
                                      self.xor_int(r_bits[i+1], c_bits[i+1],
                                                   program_counter=program_counter))
            E_tilde = []
            for i in range(len(r_bits)):
                ## s + rBit[i] - cBit[i] + 3 * sumXors[i];
                program_counter = inc_pc(program_counter)
                e_i = self.add(s_sign,
                               self.sub(r_bits[i], c_bits[i]))
                e_i = self.add(e_i,
                               self.mul(smallField(3),sumXORs[i],
                                        program_counter=program_counter))
                E_tilde.append(e_i)
            E_tilde.append(mask) # Hack: will mult e_i and mask...

            while len(E_tilde) > 1:
                program_counter = inc_pc(program_counter)
                # TODO: pop() ought to be preferred? No: it takes the
                # just appended and thus works liniarly... try with
                # two lists instead, pop(0) is quadratic if it moves
                # elements.
                E_tilde.append(self.mul(E_tilde.pop(0),
                                        E_tilde.pop(0),
                                        program_counter=program_counter))

            program_counter = inc_pc(program_counter)
            self.open(E_tilde[0], program_counter=program_counter)
            E_tilde[0].addCallback(lambda bit: field(bit.value != 0))
            non_zero = E_tilde[0]


            # UF == underflow
            program_counter = inc_pc(program_counter)
            UF = self.xor_int(non_zero, s_bit, program_counter=program_counter)

            # conclude the computation -- compute final bit and map to 0/1
            # return  2^(-l) * (z - (c%2**l - r%2**l + UF*2**l))
            #
            c_mod2l = field(c.value % 2**l)
            program_counter = inc_pc(program_counter)
            result = self.add(self.sub(c_mod2l, r_modl),
                              self.mul(UF, field(2**l), program_counter))
            result = self.sub(z, result)
            program_counter = inc_pc(program_counter)
            result = self.mul(result, ~(field(2**l)), program_counter)
            return result
        # END calculate

        program_counter = inc_pc(program_counter)                                    
        c.addCallback(calculate, program_counter)
        return c
#         result = gatherResults([c])
#         program_counter = inc_pc(program_counter)
#         result.addCallback(calculate, program_counter)
#         return result




    



    #@trace
    def greater_thanII(self, share_a, share_b, field,
                       program_counter=None, l=None):
        """Compute share_a >= share_b.

        Both arguments must be of type field. The result is a
        field share.
        """

        program_counter = self.init_pc(program_counter)
        program_counter = sub_pc(program_counter)

        # TODO: get these from a configuration file or similar
        k = 30 # security parameter
        if l is None:
            l = 32 # bit-length of input numbers

        program_counter = inc_pc(program_counter)
        preproc = self.greater_thanII_preproc(field, l=l, k=k,
                                              program_counter=program_counter)
        program_counter = inc_pc(program_counter)
        return self.greater_thanII_online(share_a, share_b, preproc, field,
                                          program_counter=program_counter, l=l)

    ########################################################################
    ########################################################################

    #@trace
    def _exchange_shares(self, program_counter, id, share):
        """Exchange shares with another player.

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
        """Shamir recombine a list of deferred (id,share) pairs."""
        assert len(shares) > threshold
        result = gatherResults(shares[:threshold+1])
        result.addCallback(shamir.recombine)
        return result
