# Copyright 2010 VIFF Development Team.
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

"""Triple generation for the BeDOZa protocol.
    TODO: Explain more.
"""

from twisted.internet.defer import Deferred, gatherResults, succeed

from viff.runtime import Runtime, Share, ShareList, gather_shares
from viff.field import FieldElement, GF
from viff.constants import TEXT
from viff.util import rand

from bedoza import BeDOZaKeyList, BeDOZaMACList, BeDOZaShare

# TODO: Use secure random instead!
from random import Random

from hash_broadcast import HashBroadcastMixin

try:
    import pypaillier
except ImportError:
    # The pypaillier module is not released yet, so we cannot expect
    # the import to work.
    print "Error: The pypaillier module or one of the used functions " \
        "are not available."

class Triple(object):
    def __init__(self, a, b, c):
        self.a, self.b, self.c = a, b, c
    def __str__(self):
        return "(%s,%s,%s)" % (self.a, self.b, self.c)


def _send(runtime, vals, serialize=str, deserialize=int):
    """Send vals[i] to player i + 1. Returns deferred list.

    Works as default for integers. If other stuff has to be
    sent, supply another serialization, deserialition.
    """
    runtime.increment_pc()
    
    pc = tuple(runtime.program_counter)
    for p in runtime.players:
        msg = serialize(vals[p - 1])
        runtime.protocols[p].sendData(pc, TEXT, msg)
    def err_handler(err):
        print err
    values = []
    for p in runtime.players:
        d = Deferred()
        d.addCallbacks(deserialize, err_handler)
        runtime._expect_data(p, TEXT, d)
        values.append(d)
    result = gatherResults(values)
    return result

def _convolute(runtime, val, serialize=str, deserialize=int):
    """As send, but sends the same val to all players."""
    return _send(runtime, [val] * runtime.num_players,
                 serialize=serialize, deserialize=deserialize)

def _convolute_gf_elm(runtime, gf_elm):
    return _convolute(runtime, gf_elm,
                      serialize=lambda x: str(x.value),
                      deserialize=lambda x: gf_elm.field(int(x)))

def _send_gf_elm(runtime, vals):
    return _send(runtime, vals, 
                 serialize=lambda x: str(x.value),
                 deserialize=lambda x: gf_elm.field(int(x)))


class PartialShareContents(object):
    """A BeDOZa share without macs, e.g. < a >.
    TODO: BeDOZaShare should extend this class?
    
    TODO: Should the partial share contain the public encrypted shares?
    TODO: It may be wrong to pass encrypted_shares to super constructor; 
      does it mean that the already public values get passed along on the
      network even though all players already posess them?
    """
    def __init__(self, value, enc_shares, N_squared_list):
        self.value = value
        self.enc_shares = enc_shares
        self.N_squared_list = N_squared_list

    def __str__(self):
        return "PartialShareContents(%d; %s; %s)" % (self.value, self.enc_shares, self.N_squared_list)

    def __add__(self, other):
        z = self.value + other.value
        z_enc_shares = []
        for x, y, N_squared in zip(self.enc_shares, other.enc_shares, self.N_squared_list):
            z_enc_shares.append((x * y) % N_squared)
        return PartialShareContents(z, z_enc_shares, self.N_squared_list)

# In VIFF, callbacks get the *contents* of a share as input. Hence, in order
# to get a PartialShare as input to callbacks, we need this extra level of
# wrapper indirection.
class PartialShare(Share):
    def __init__(self, runtime, value, enc_shares):
        N_squared_list = [ runtime.players[player_id].pubkey['n_square'] for player_id in runtime.players.keys()]
        partial_share_contents = PartialShareContents(value, enc_shares, N_squared_list)
        Share.__init__(self, runtime, value.field, partial_share_contents)



class ModifiedPaillier(object):
    """A slight modification of the Paillier cryptosystem.

    This modification has plaintext space [-(n-1)/ ; (n-1)/2] rather
    than the usual Z_n where n is the Paillier modulus.

    See Ivan's paper, beginning of section 6.
    """

    def __init__(self, runtime, random):
        self.runtime = runtime;
        self.random = random

    def _f(self, x, n):
        if x >= 0:
            return x
        else:
            return n + x

    def _f_inverse(self, y, n):
        if 0 <= y <= (n + 1) / 2:
            return y
        else:
            return y - n

    def encrypt(self, value, player_id=None):
        """Encrypt using public key of player player_id.

        Defaults to own public key.
        """
        assert isinstance(value, int) or isinstance(value, long), \
            "paillier: encrypts only integers and longs, got %s" % value.__class__
        if not player_id:
            player_id = self.runtime.id
        n = self.runtime.players[player_id].pubkey['n']
        min = -(n - 1) / 2 + 1
        max = (n + 1) / 2
        assert min <= value <= max, \
            "paillier: plaintext %d outside legal range [-(n-1)/2+1 ; (n+1)/2] = " \
            "[%d ; %d]"  % (value, min, max)
        pubkey = self.runtime.players[player_id].pubkey
        randomness = self.random.randint(1, long(n))
        return pypaillier.encrypt_r(self._f(value, n), randomness, pubkey)

    def decrypt(self, enc_value):
        """Decrypt using own private key."""
        assert isinstance(enc_value, int) or isinstance(enc_value, long), \
            "paillier decrypts only longs, got %s" % enc_value.__class__
        n = self.runtime.players[self.runtime.id].pubkey['n']
        n_square = self.runtime.players[self.runtime.id].pubkey['n_square']
        assert 0 <= enc_value < n_square, \
            "paillier: ciphertext %d not in range [0 ; n^2] = [0 ; %d]" \
            % (enc_value, n_square)
        seckey = self.runtime.players[self.runtime.id].seckey
        return self._f_inverse(pypaillier.decrypt(enc_value, seckey), n)

    def get_modulus(self, player_id):
        return self.runtime.players[player_id].pubkey['n']

    def get_modulus_square(self, player_id):
        return self.runtime.players[player_id].pubkey['n_square']

class TripleGenerator(object):

    def __init__(self, runtime, p, random):
        assert p > 1
        self.random = random
        # TODO: Generate Paillier cipher with N_i sufficiently larger than p
        self.runtime = runtime
        self.p = p
        self.Zp = GF(p)
        self.k = self._bit_length_of(p)
        self.u_bound = 2**(4 * self.k)

        paillier_random = Random(self.random.getrandbits(128))
        alpha_random = Random(self.random.getrandbits(128))
        self.paillier = ModifiedPaillier(runtime, paillier_random)
        
        # Debug output.
        #print "n_%d**2:%d" % (runtime.id, self.paillier.pubkey['n_square'])
        #print "n_%d:%d" % (runtime.id, self.paillier.pubkey['n'])
        #print "n_%d bitlength: %d" % (runtime.id, self._bit_length_of(self.paillier.pubkey['n']))

        #self.Zp = GF(p)
        #self.Zn2 = GF(self.paillier.pubkey['n_square'])
        #self.alpha = self.Zp(self.random.randint(0, p - 1))
        self.alpha = alpha_random.randint(0, p - 1)
        self.n2 = runtime.players[runtime.id].pubkey['n_square']

    def _bit_length_of(self, i):
        bit_length = 0
        while i:
            i >>= 1
            bit_length += 1
        return bit_length

    def generate_triples(self, n):
        """Generates and returns a set of n triples.
        
        Data sent over the network is packaged in large hunks in order
        to optimize. TODO: Explain better.

        TODO: This method needs to have enough RAM to represent all n
        triples in memory at the same time. Is there a nice way to
        stream this, e.g. by using Python generators?
        """
        triples = self._generate_passive_triples(n)
        # TODO: Do some ZK stuff.

    def _generate_passive_triples(self, n):
        """Generates and returns a set of n passive tuples.
        
        E.g. where consistency is only guaranteed if all players follow the
        protool.
        """
        pass
    
    def _add_macs(self, partial_shares):
        """Adds macs to the set of PartialBeDOZaShares.
        
        Returns a tuple with a single element that is a list of full
        shares, e.g. including macs.  (the full shares are deferreds
        of type BeDOZaShare.)

        TODO: We have to return the list in a tuple due to some
        Twisted thing.
        """        
        # TODO: Would be nice with a class ShareContents like the class
        # PartialShareContents used here.
        
        self.runtime.increment_pc() # Huh!?

        mac_keys = []

        # TODO: Currently only support for one share.
        i = 0

        c_list = []
        for j in range(self.runtime.num_players):
            # TODO: This is probably not the fastes way to generate
            # the betas.
            beta = self.random.randint(0, 2**(4 * self.k))
            # TODO: Outcommented until mod paillier works for negative numbers.
            #if rand.choice([True, False]):
            #    beta = -beta
            enc_beta = self.paillier.encrypt(beta, player_id=j+1)
            c_j = partial_shares[i].enc_shares[j]
            n2 = self.runtime.players[j + 1].pubkey['n_square']
            c = (pow(c_j, self.alpha, n2) * enc_beta) % n2
            c_list.append(c)
            mac_keys.append(self.Zp(beta))
        received_cs = _send(self.runtime, c_list)

        def finish_sharing(recevied_cs):
            mac_key_list = BeDOZaKeyList(self.alpha, mac_keys)
            decrypted_cs = [self.Zp(self.paillier.decrypt(c)) for c in received_cs.result]
            mac_msg_list = BeDOZaMACList(decrypted_cs)
            # Twisted HACK: Need to pack share into tuple.
            return BeDOZaShare(self.runtime,
                               partial_shares[i].value.field,
                               partial_shares[i].value,
                               mac_key_list,
                               mac_msg_list),

        self.runtime.schedule_callback(received_cs, finish_sharing)
        return [received_cs]

        # for player i:
        #     receive c from player i and set 
        #         m^i=Decrypt(c)
    
    def _mul(self, inx, jnx, ai=None, cj=None):
        CKIND = 1
        DiKIND = 2
        DjKIND = 3
        
        self.runtime.increment_pc()

        pc = tuple(self.runtime.program_counter)
            
        deferreds = []
        if self.runtime.id == inx:
            u = rand.randint(0, self.u_bound)
            Ej_u = self.paillier.encrypt(u, jnx)
            Nj_square = self.paillier.get_modulus_square(jnx)
            c = (pow(cj, ai.value, Nj_square) * Ej_u) % Nj_square
            self.runtime.protocols[jnx].sendData(pc, CKIND, str(c))
            zi = self.Zp(-u)
            di = self.paillier.encrypt(zi.value, inx)
            for player_id in self.runtime.players:
                self.runtime.protocols[player_id].sendData(pc, DiKIND, str(di))
            zi_deferred = Deferred()
            zi_deferred.callback(zi)
            deferreds.append(zi_deferred)

        if self.runtime.id == jnx:
            c = Deferred()
            self.runtime._expect_data(inx, CKIND, c)
            def decrypt(c, pc):
                t = self.paillier.decrypt(long(c))
                zj = self.Zp(t)
                dj = self.paillier.encrypt(zj.value, jnx)
                for player_id in self.runtime.players:
                    self.runtime.protocols[player_id].sendData(pc, DjKIND, str(dj))
                return zj 
            c.addCallback(decrypt, pc)
            deferreds.append(c)

        di = Deferred()
        self.runtime._expect_data(inx, DiKIND, di)
        dj = Deferred()
        self.runtime._expect_data(jnx, DjKIND, dj)

        deferreds.append(di)
        deferreds.append(dj)
        r = gatherResults(deferreds)
        def wrap(ls, inx, jnx):
            value = reduce(lambda x, y: x + y, [self.Zp(0)] + ls[0:-2])
            n_square_i = self.paillier.get_modulus_square(inx)
            n_square_j = self.paillier.get_modulus_square(jnx)
            enc_shares = len(self.runtime.players) * [1]
            enc_shares[inx - 1] = (enc_shares[inx - 1] * long(ls[-2])) % n_square_i
            enc_shares[jnx - 1] = (enc_shares[jnx - 1] * long(ls[-1])) % n_square_j
            N_squared_list = [self.paillier.get_modulus_square(player_id) for player_id in self.runtime.players]
            return PartialShareContents(value, enc_shares, N_squared_list)
        r.addCallback(wrap, inx, jnx)
        return r

    def _full_mul(self, a, b):
        self.runtime.increment_pc()
        
        def do_full_mul((contents_a, contents_b)):
            deferreds = []
            for inx in xrange(0, len(self.runtime.players)):
                for jnx in xrange(0, len(self.runtime.players)):
                    deferreds.append(self._mul(inx + 1, jnx + 1, contents_a.value, contents_b.enc_shares[jnx]))
            def compute_share(partialShares):
                partialShareContents = reduce(lambda x, y: x + y, partialShares)
                pid = self.runtime.id
                share = partialShareContents.enc_shares[pid - 1]
                share = self.paillier.decrypt(share)
                share = self.Zp(share)
                return PartialShare(self.runtime, partialShareContents.value, partialShareContents.enc_shares)
            d = gatherResults(deferreds)
            d.addCallback(compute_share)
            return d
        s = gatherResults([a, b])
        self.runtime.schedule_callback(s, do_full_mul)
        return s


# TODO: Represent all numbers by GF objects, Zp, Zn, etc.
# E.g. paillier encrypt should return Zn^2 elms and decrypt should
# return Zp elements.
