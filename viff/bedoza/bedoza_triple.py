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

import itertools

from twisted.internet.defer import Deferred, gatherResults, succeed

from viff.runtime import Runtime, Share, ShareList, gather_shares
from viff.field import FieldElement, GF
from viff.constants import TEXT
from viff.util import rand
from viff.bedoza.shares import BeDOZaShare, BeDOZaShareContents, PartialShare, PartialShareContents
from viff.bedoza.share_generators import PartialShareGenerator, ShareGenerator
from viff.bedoza.keylist import BeDOZaKeyList
from viff.bedoza.maclist import BeDOZaMACList
from viff.bedoza.util import _send, _convolute
from viff.bedoza.add_macs import add_macs
from viff.bedoza.modified_paillier import ModifiedPaillier

# TODO: Use secure random instead!
from random import Random

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

        self.runtime.increment_pc()
        
        def check(v, a, b, c):
            if v.value != 0:
                raise Exception("TripleTest failed - The two triples were inconsistent.")
            return (a, b, c)
        
        def compute_value(r, a, b, c, x, y, z):
            l = self.runtime._cmul(r, x, self.Zp)
            m = self.runtime._cmul(r, y, self.Zp)
            k = self.runtime._cmul(r*r, z, self.Zp)
            v = c - self.runtime._basic_multiplication(a, b, l, m, k)
            v = self.runtime.open(v)
            v.addCallback(check, a, b, c)
            return v

        gen = ShareGenerator(self.Zp, self.runtime, self.random, self.paillier, self.u_bound, self.alpha)
        
        random_shares = gen.generate_random_shares(n)

        results = [Deferred() for _ in xrange(n)]
        
        triples = self._generate_passive_triples(2 * n)

        for inx in xrange(n):
            a = triples[inx]
            b = triples[inx + 2 * n]
            c = triples[inx + 4 * n]
            x = triples[inx + n]
            y = triples[inx + 3 * n]
            z = triples[inx + 5 * n]
            r = self.runtime.open(random_shares[inx])
            self.runtime.schedule_callback(r, compute_value, a, b, c, x, y, z)
            r.chainDeferred(results[inx])
        return results
          
        # TODO: Do some ZK stuff.

    def _generate_passive_triples(self, n):
        """Generates and returns a list of 3n shares corresponding to
        n passive tuples. The first n are the a's, then comes n b's
        followed by n c's.
        
        Consistency is only guaranteed if all players follow the protool.
        """

        self.runtime.increment_pc()
        
        gen = PartialShareGenerator(self.Zp, self.runtime, self.random, self.paillier)
        partial_shares = []
        for _ in xrange(2 * n):
             partial_shares.append(gen.generate_share(self.random.randint(0, self.Zp.modulus - 1)))


        partial_shares_c = self._full_mul(partial_shares[0:n], partial_shares[n:2*n])

        full_shares = add_macs(self.runtime, self.Zp, self.u_bound, self.alpha, self.random, self.paillier, partial_shares + partial_shares_c)

        return full_shares  

        # for player i:
        #     receive c from player i and set 
        #         m^i=Decrypt(c)
    
    def _mul(self, inx, jnx, ais=None, cjs=None):
        """Multiply each of the field elements in *ais* with the
        corresponding encrypted elements in *cjs*.
        
        Returns a deferred which will yield a list of PartialShareContents.
        """
        CKIND = 1
        DiKIND = 2
        DjKIND = 3
        
        self.runtime.increment_pc()

        pc = tuple(self.runtime.program_counter)

        deferreds = []
        zis = []
        if self.runtime.id == inx:
            Nj_square = self.paillier.get_modulus_square(jnx)
            cs = []
            dis = []
            for ai, cj in zip(ais, cjs):
                u = rand.randint(0, self.u_bound)
                Ej_u = self.paillier.encrypt(u, jnx)
                cs.append( (pow(cj, ai.value, Nj_square) * Ej_u) % Nj_square )
                zi = self.Zp(-u)
                zis.append(zi)
                dis.append(self.paillier.encrypt(zi.value, inx))
            self.runtime.protocols[jnx].sendData(pc, CKIND, str(cs))

            for player_id in self.runtime.players:
                self.runtime.protocols[player_id].sendData(pc, DiKIND, str(dis))

        if self.runtime.id == jnx:
            cs = Deferred()
            self.runtime._expect_data(inx, CKIND, cs)
            def decrypt(cs, pc, zis):
                zjs = []
                djs = []
                for c in eval(cs):
                    t = self.paillier.decrypt(c)
                    zj = self.Zp(t)
                    zjs.append(zj)
                    djs.append(self.paillier.encrypt(zj.value, jnx))
                for player_id in self.runtime.players:
                    self.runtime.protocols[player_id].sendData(pc, DjKIND, str(djs))
                if not zis == []:
                    return [x + y for x, y in zip(zis, zjs)]
                else:
                    return zjs 
            cs.addCallback(decrypt, pc, zis)
            deferreds.append(cs)
        else:
            zis_deferred = Deferred()
            zis_deferred.callback(zis)
            deferreds.append(zis_deferred)

        dis = Deferred()
        self.runtime._expect_data(inx, DiKIND, dis)
        djs = Deferred()
        self.runtime._expect_data(jnx, DjKIND, djs)

        deferreds.append(dis)
        deferreds.append(djs)
        r = gatherResults(deferreds)
        def wrap((values, dis, djs), inx, jnx):
            dis = eval(dis)
            djs = eval(djs)
            n_square_i = self.paillier.get_modulus_square(inx)
            n_square_j = self.paillier.get_modulus_square(jnx)
            N_squared_list = [self.paillier.get_modulus_square(player_id) for player_id in self.runtime.players]
            ps = []
            for v, di, dj in itertools.izip_longest(values, dis, djs, fillvalue=self.Zp(0)):
                value = v 
                enc_shares = len(self.runtime.players) * [1]
                enc_shares[inx - 1] = (enc_shares[inx - 1] * di) % n_square_i
                enc_shares[jnx - 1] = (enc_shares[jnx - 1] * dj) % n_square_j
                ps.append(PartialShareContents(value, enc_shares, N_squared_list))
            return ps
        r.addCallback(wrap, inx, jnx)
        return r

    def _full_mul(self, a, b):
        """Multiply each of the PartialShares in the list *a* with the
        corresponding PartialShare in the list *b*.
        
        Returns a deferred which will yield a list of PartialShares.
        """
        self.runtime.increment_pc()
        
        def do_full_mul(shares, result_shares):
            """Share content belonging to ai, bi are at:
            shares[i], shares[len(shares) + i].
            """
            deferreds = []
            len_shares = len(shares)
            a_values = [s.value for s in shares[0:len_shares/2]]
            b_enc_shares = []
            for inx in self.runtime.players:              
                b_enc_shares.append([s.enc_shares[inx - 1] for s in shares[len_shares/2:]])
            for inx in xrange(0, len(self.runtime.players)):
                for jnx in xrange(0, len(self.runtime.players)):
                    deferreds.append(self._mul(inx + 1,
                                               jnx + 1,
                                               a_values,
                                               b_enc_shares[jnx]))
                        
            def compute_shares(partialShareContents, len_shares, result_shares):
                num_players = len(self.runtime.players)
                pcs = len(partialShareContents[0]) * [None]
                for ps in partialShareContents:
                    for inx in xrange(0, len(ps)):
                        if pcs[inx] == None:
                            pcs[inx] = ps[inx]
                        else:
                            pcs[inx] += ps[inx]
                for p, s in zip(pcs, result_shares):
                    s.callback(p)
                return None
            d = gatherResults(deferreds)
            d.addCallback(compute_shares, len_shares, result_shares)
            return d
        result_shares = [Share(self.runtime, self.Zp) for x in a]
        self.runtime.schedule_callback(gatherResults(a + b),
                                       do_full_mul,
                                       result_shares)
        return result_shares


# TODO: Represent all numbers by GF objects, Zp, Zn, etc.
# E.g. paillier encrypt should return Zn^2 elms and decrypt should
# return Zp elements.
