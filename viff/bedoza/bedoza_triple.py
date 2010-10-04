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
import hashlib

from twisted.internet.defer import Deferred, gatherResults, succeed

from viff.runtime import Runtime, ShareList, gather_shares
from viff.field import FieldElement, GF
from viff.constants import TEXT
from viff.util import rand
from viff.bedoza.shares import BeDOZaShare, BeDOZaShareContents, PartialShare
from viff.bedoza.shares import PartialShareContents
from viff.bedoza.share_generators import ShareGenerator, PartialShareGenerator
from viff.bedoza.keylist import BeDOZaKeyList
from viff.bedoza.maclist import BeDOZaMACList
from viff.bedoza.add_macs import add_macs
from viff.bedoza.modified_paillier import ModifiedPaillier
from viff.bedoza.util import fast_pow
from viff.bedoza.util import _convolute
from viff.bedoza.share import generate_partial_share_contents

from viff.triple import Triple

# TODO: Use secure random instead!
from random import Random

try:
    import pypaillier
except ImportError:
    # The pypaillier module is not released yet, so we cannot expect
    # the import to work.
    print "Error: The pypaillier module or one of the used functions " \
        "are not available."


class TripleGenerator(object):

    def __init__(self, runtime, security_parameter, p, random):
        assert p > 1
        self.random = random
        # TODO: Generate Paillier cipher with N_i sufficiently larger than p
        self.runtime = runtime
        self.p = p
        self.Zp = GF(p)
        self.k = self._bit_length_of(p)
        self.security_parameter = security_parameter
        self.u_bound = 2**(self.security_parameter + 4 * self.k)

        paillier_random = Random(self.random.getrandbits(128))
        alpha_random = Random(self.random.getrandbits(128))
        self.paillier = ModifiedPaillier(runtime, paillier_random)
        
        # Debug output.
        #print "n_%d**2:%d" % (runtime.id, self.paillier.pubkey['n_square'])
        #print "n_%d:%d" % (runtime.id, self.paillier.pubkey['n'])
        #print "n_%d bitlength: %d" % \
        #    (runtime.id, self._bit_length_of(self.paillier.pubkey['n']))

        #self.Zp = GF(p)
        #self.Zn2 = GF(self.paillier.pubkey['n_square'])
        #self.alpha = self.Zp(self.random.randint(0, p - 1))
        self.alpha = alpha_random.randint(0, p - 1)
        self.n2 = runtime.players[runtime.id].pubkey['n_square']


    def generate_triples(self):
        """Generates triples for use in the BeDOZa protocol.

        Returns a deferred that will eventually yield a list
        containing *self.security_parameter* multiplicative
        triples. Each of these triples is an object of type
        viff.triple.Triple. The components of each triple t, e.g.

            t.a, t.b, and t.c,

        are each of type BeDOZaShare and guaranteed to satisfy the
        equation

            t.c = t.a * t.b.

        This method carries out the off-line work that is needed for
        the BeDOZa protocol to work.

        Data sent over the network is packaged in large hunks in order
        to optimize. TODO: Explain better.

        TODO: This method needs to have enough RAM to represent all n
        triples in memory at the same time. Is there a nice way to
        stream this, e.g. by using Python generators?

        """
        return self._generate_triples(self.security_parameter)


    def _generate_triples(self, number_of_triples):
        self.runtime.increment_pc()
        triples = self._generate_triple_candidates(2 * number_of_triples)
        return self._verify_triple_candidates(number_of_triples, triples)


    def _generate_triple_candidates(self, n):
        """Generates triple candidates for use in the BeDOZa protocol.

        Returns a deferred that will eventually yield a list of 3n
        shares of type viff.bedoza.shares.BeDOZaShare corresponding to
        n multiplicative tuples. The first n are the a's, then comes n
        b's followed by n c's.
        
        The triples are only candidates because consistency of the
        triples is only half-way guaranteed in the precense of active
        adversaries. More concretely, the triples returned by this
        method are guaranteed - even in the precense of an active
        adversary - to be of the right size. But they may not satisfy
        the equation

            c = a * b.

        """
        self.runtime.increment_pc()
        
        gen = PartialShareGenerator(self.Zp, self.runtime, self.random,
                                    self.paillier)
        partial_shares = []
        for _ in xrange(2 * n):
             partial_shares.append(
                 gen.generate_share(
                     self.random.randint(0, self.Zp.modulus - 1)))
        partial_shares_c = self._full_mul(partial_shares[0: n],
                                          partial_shares[n: 2 * n])
        full_shares = add_macs(self.runtime, self.Zp, self.u_bound, self.alpha,
                               self.random, self.paillier,
                               partial_shares + partial_shares_c)
        return full_shares  


    def _verify_triple_candidates(self, n, triple_candidates):
        """Verify remaining consistency of triple candidates.

        Takes as input a deferred list of 2n triple candidates as
        generated by _generate_triple_candidates(2 * n) and returns
        another deferred that will eventually yield a list of
        viff.triple.Triple objects that are guaranteed to be fully
        consistent. That is, the shares of the triples are guaranteed
        to be of the right size and for each triple, the shares are
        quaranteed to satisfy c = a * b.

        The technique implemented in this method is essentially that
        listed in Figure 5.5 in the progress report "LEGO and Other
        Cryptographic Constructions" by Claudio Orlandi.

        However, since we only implement a protocol that is secure in
        the Random Oracle Model and not the Common Reference String
        Model, we can safely skip step 2 of Figure 5.5 and instead
        generate r by having all players P_i broadcast a random
        element r_i and then have each player compute r as the hash of
        the sum of all r_i's.

        """
        assert n == len(triple_candidates) / 6

        def verify(v, a, b, c):
            if v.value != 0:
                raise Exception(
                    "TripleTest failed - The two triple candidates were "
                    "inconsistent.")
            return Triple(a, b, c)

        def prepare_verification(rs_serialized, results):
            # Repr/eval deserialization.
            rs = [eval(rss) for rss in rs_serialized]

            for i in xrange(n):
                a = triple_candidates[i]
                b = triple_candidates[i + 2 * n]
                c = triple_candidates[i + 4 * n]
                x = triple_candidates[i + n]
                y = triple_candidates[i + 3 * n]
                z = triple_candidates[i + 5 * n]

                # Hash all received random values to agree on a single
                # random value for each triple.
                hash = hashlib.sha1()
                for rp in rs:
                    hash.update(str(rp[i]))
                # TODO: We should use a secure random generator here.
                rand = Random(hash.digest())
                r = self.Zp(rand.randint(0, self.p - 1))

                l = self.runtime._cmul(r, x, self.Zp)
                m = self.runtime._cmul(r, y, self.Zp)
                k = self.runtime._cmul(r * r, z, self.Zp)
                v = c - self.runtime._basic_multiplication(a, b, l, m, k)
                v = self.runtime.open(v)
                self.runtime.schedule_callback(v, verify, a, b, c)
                v.addCallbacks(results[i].callback, results[i].errback)

        # TODO: Handle errors better.
        def err_handler(err):
            print err

        results = [Deferred() for _ in xrange(n)]

        ri = [self.random.randint(0, self.p - 1) for _ in xrange(n)]
        # TODO: We use repr/eval as simple marshalling. Should be
        # factored out and maybe optimized by using better compression
        # here.
        ris = self.runtime.broadcast(
            self.runtime.players.keys(), self.runtime.players.keys(), repr(ri))
        ris = gatherResults(ris)
        self.runtime.schedule_callback(ris, prepare_verification, results)     
        ris.addErrback(err_handler)
        
        # TODO: Which makes most sense?
        # 
        # 1) Compute each triple separately and return list of
        #    deferred triples, or
        #
        # 2) Compute triples as a batch and return single deferred
        #    that evaluates to list of triples.
        #
        
        return results


    def _bit_length_of(self, i):
        bit_length = 0
        while i:
            i >>= 1
            bit_length += 1
        return bit_length


    def _mul(self, inx, jnx, n, ais=None, cjs=None):
        """Multiply each of the field elements in *ais* with the
        corresponding encrypted elements in *cjs*.
        
        Returns a deferred which will yield a list of field elements.
        """
        CKIND = 1
 
        """The transmission_restraint_constant is the number of
        encrypted shares we can safely transmit in one call to
        sendData. The sendData method can only transmit up to
        65536 bytes.
        The constant has been imperically determined by running
        TripleGenerator.generate_triples.
        TODO: How can we allow a user of the runtime to adjust this
        constraint at a higher level of abstraction?

        """
        transmission_restraint_constant = 425

        number_of_packets = n / transmission_restraint_constant
        if n % transmission_restraint_constant != 0:
            number_of_packets += 1
        
        self.runtime.increment_pc()

        pc = tuple(self.runtime.program_counter)

        deferred = []
        zis = []
        if self.runtime.id == inx:
            Nj_square = self.paillier.get_modulus_square(jnx)
            all_cs = []
            for iny, (ai, cj) in enumerate(zip(ais, cjs)):
                if iny % transmission_restraint_constant == 0:
                    cs = []
                    all_cs.append(cs)
                u = rand.randint(0, self.u_bound)
                Ej_u = self.paillier.encrypt(u, jnx)
                cs.append( (fast_pow(cj, ai.value, Nj_square) * Ej_u) % Nj_square )
                zi = self.Zp(-u)
                zis.append(zi)
                
            for cs in all_cs:
                self.runtime.protocols[jnx].sendData(pc, CKIND, str(cs))

        if self.runtime.id == jnx:
            all_cs = []
            for _ in xrange(number_of_packets):
                cs = Deferred()
                self.runtime._expect_data(inx, CKIND, cs)
                all_cs.append(cs)
                
            def decrypt(all_cs, pc, zis):
                zjs = []
                cs = reduce(lambda x, y: x + eval(y), all_cs, [])
                for iny, c in enumerate(cs):
                    t = self.paillier.decrypt(c)
                    zj = self.Zp(t)
                    zjs.append(zj)
                if not zis == []:
                    return [x + y for x, y in zip(zis, zjs)]
                else:
                    return zjs 
            all_cs_d = gatherResults(all_cs)
            all_cs_d.addCallback(decrypt, pc, zis)
            deferred = all_cs_d
        else:
            zis_deferred = Deferred()
            zis_deferred.callback(zis)
            deferred = zis_deferred

        return deferred


    def _full_mul(self, a, b):
        """Multiply each of the PartialShares in the list *a* with the
        corresponding PartialShare in the list *b*.
        
        Returns a deferred which will yield a list of PartialShares.
        """
        self.runtime.increment_pc()
        
        def do_full_mul(shareContents, result_shares):
            """Share content belonging to ai, bi are at:
            shareContents[i], shareContents[len(shareContents) + i].
            """
            deferreds = []
            len_shares = len(shareContents)

            ais = [shareContent.value for shareContent in shareContents[0:len_shares/2]]
            bis = [shareContent.value for shareContent in shareContents[len_shares/2:]]
            
            b_enc_shares = []
            for inx in self.runtime.players:
                b_enc_shares.append([s.enc_shares[inx - 1]
                                     for s in shareContents[len_shares/2:]])

            values = len(ais) * [0]

            for inx in xrange(0, len(self.runtime.players)):
                for jnx in xrange(0, len(self.runtime.players)):
                    deferreds.append(self._mul(inx + 1,
                                               jnx + 1,
                                               len(ais),
                                               ais,
                                               b_enc_shares[jnx]))
            
            def compute_shares(zils, values, result_shares):
                for zil in zils:
                    for inx, zi in enumerate(zil):
                        values[inx] += zi

                return values
            
            d = gatherResults(deferreds)
            d.addCallback(compute_shares, values, result_shares)
            
            def callBackPartialShareContents(partialShareContents, result_shares):
                for v, s in zip(partialShareContents, result_shares):
                    s.callback(v)
                return None
            
            d.addCallback(lambda values: generate_partial_share_contents(
                    values, self.runtime, self.paillier))
            d.addCallback(callBackPartialShareContents, result_shares)
            return d
        result_shares = [PartialShare(self.runtime, self.Zp) for _ in a]
        self.runtime.schedule_callback(gatherResults(a + b),
                                       do_full_mul,
                                       result_shares)
        return result_shares


# TODO: Represent all numbers by GF objects, Zp, Zn, etc.
# E.g. paillier encrypt should return Zn^2 elms and decrypt should
# return Zp elements.
