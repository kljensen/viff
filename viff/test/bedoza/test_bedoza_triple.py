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

import sys
from exceptions import AssertionError

import operator

# We don't need secure random numbers for test purposes.
from random import Random

from twisted.internet.defer import gatherResults, Deferred, DeferredList

from viff.test.util import protocol
from viff.constants import TEXT
from viff.runtime import gather_shares, Share
from viff.config import generate_configs
from viff.field import FieldElement, GF
from viff.config import generate_configs

from viff.bedoza.bedoza import BeDOZaShare
from viff.bedoza.keylist import BeDOZaKeyList
from viff.bedoza.bedoza_triple import TripleGenerator, ModifiedPaillier
from viff.bedoza.shares import PartialShare, PartialShareContents
from viff.bedoza.util import _send, _convolute, _convolute_gf_elm
from viff.bedoza.add_macs import add_macs
from viff.bedoza.share_generators import ShareGenerator, PartialShareGenerator
from viff.bedoza.share import generate_partial_share_contents

from viff.test.bedoza.util import BeDOZaTestCase, skip_if_missing_packages
from viff.test.bedoza.util import TestShareGenerator


# Ok to use non-secure random generator in tests.
#from viff.util import rand
import random


class DataTransferTest(BeDOZaTestCase):

    @protocol
    def test_convolute_int(self, runtime):
        res = _convolute(runtime, runtime.id)
        def verify(result):
            self.assertEquals(runtime.players.keys(), result)
        runtime.schedule_callback(res, verify)
        return res

    @protocol
    def test_send(self, runtime):
        msg_send = [100 * p + runtime.id for p in runtime.players]
        msg_receive = [100 * runtime.id + p for p in runtime.players]
        res = _send(runtime, msg_send)
        def verify(result):
            self.assertEquals(msg_receive, result)
        runtime.schedule_callback(res, verify)
        return res
 
    @protocol
    def test_convolute_field_element(self, runtime):
        Zp = GF(17)
        res = _convolute_gf_elm(runtime, Zp(runtime.id))
        def verify(result):
            self.assertEquals(runtime.players.keys(), result)
        runtime.schedule_callback(res, verify)
        return res


class ModifiedPaillierTest(BeDOZaTestCase):

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_one(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(234838))
        val = 1
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_with_different_randomness_are_not_equal(self, runtime):
        random = Random(3423434)
        n = runtime.players[runtime.id].pubkey['n']
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))
        val = 47
        random_elm = random.randint(1, long(n))
        encrypted_val_1 = paillier.encrypt(val, random_elm=random_elm)
        encrypted_val_2 = paillier.encrypt(val, random_elm=random_elm)
        self.assertEquals(encrypted_val_1, encrypted_val_2)

    @protocol
    def test_modified_paillier_with_same_randomness_are_equal(self, runtime):
        random = Random(234333)
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))
        n = runtime.players[runtime.id].pubkey['n']
        val = 46
        random_elm_1 = random.randint(1, long(n))
        random_elm_2 = (random_elm_1 + 1) % n
        encrypted_val_1 = paillier.encrypt(val, random_elm=random_elm_1)
        encrypted_val_2 = paillier.encrypt(val, random_elm=random_elm_1)
        self.assertEquals(encrypted_val_1, encrypted_val_2)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_zero(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(338301))
        val = 0
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_minus_one(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(19623))
        val = -1
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_max_val(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(825604))
        n = runtime.players[runtime.id].pubkey['n']
        val = (n - 1) / 2
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_min_val(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(554424))
        n = runtime.players[runtime.id].pubkey['n']
        val = -(n - 1) / 2
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)
 
    @protocol
    def test_modified_paillier_can_decrypt_encrypted_positive(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(777737))
        val = 73423
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_encrypting_too_large_number_raises_exception(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(825604))
        n = runtime.players[runtime.id].pubkey['n']
        val = 1 + (n - 1) / 2
        self.assertRaises(AssertionError, paillier.encrypt, val)

    @protocol
    def test_encrypting_too_small_number_raises_exception(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(554424))
        n = runtime.players[runtime.id].pubkey['n']
        val = -(n - 1) / 2 - 1
        self.assertRaises(AssertionError, paillier.encrypt, val)

    @protocol
    def test_modified_paillier_can_encrypt_to_other(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(57503))
        msg = []
        for p in runtime.players:
            msg.append(paillier.encrypt(runtime.id, player_id=p))
        received = _send(runtime, msg)
        def verify(enc):
            plain = [paillier.decrypt(e) for e in enc]
            self.assertEquals(range(1, self.num_players + 1), plain)
        runtime.schedule_callback(received, verify)
        return received


def partial_share(random, runtime, Zp, val, paillier=None):
    if not paillier:
        paillier_random = Random(random.getrandbits(128))
        paillier = ModifiedPaillier(runtime, paillier_random)
    share_random = Random(random.getrandbits(128))
    gen = PartialShareGenerator(Zp, runtime, share_random, paillier)
    return gen.generate_share(Zp(val))


class PartialShareGeneratorTest(BeDOZaTestCase):
 
    @protocol
    def test_shares_have_correct_type(self, runtime):
        Zp = GF(23)
        share = partial_share(Random(23499), runtime, Zp, 7)
        def test(share):
            self.assertEquals(Zp, share.value.field)
        runtime.schedule_callback(share, test)
        return share
 
    @protocol
    def test_shares_are_additive(self, runtime):
        secret = 7
        share = partial_share(Random(34993), runtime, GF(23), secret)
        def convolute(share):
            values = _convolute_gf_elm(runtime, share.value)
            def test_sum(vals):
                self.assertEquals(secret, sum(vals))
            runtime.schedule_callback(values, test_sum)
        runtime.schedule_callback(share, convolute)
        return share

    @protocol
    def test_encrypted_shares_decrypt_correctly(self, runtime):
        random = Random(3423993)
        modulus = 17
        secret = 7
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))
        share = partial_share(Random(random.getrandbits(128)), runtime, GF(modulus), secret, paillier=paillier)
        def decrypt(share):
            decrypted_share = paillier.decrypt(share.enc_shares[runtime.id - 1])
            decrypted_shares = _convolute(runtime, decrypted_share)
            def test_sum(vals):
                self.assertEquals(secret, sum(vals) % modulus)
            runtime.schedule_callback(decrypted_shares, test_sum)
        runtime.schedule_callback(share, decrypt)
        return share

class ShareGeneratorTest(BeDOZaTestCase):

    @protocol
    def test_encrypted_real_share_open_correctly(self, runtime):
        random = Random(3423993)
        modulus = 17
        Zp = GF(modulus)
        bits_in_p = 5
        u_bound = 2**(4 * bits_in_p)
        alpha = 15
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))

        share_random = Random(random.getrandbits(128))
        gen = ShareGenerator(Zp, runtime, share_random, paillier, u_bound, alpha)
        share = gen.generate_share(7)
        def check(v):
            self.assertEquals(7, v)
        r = runtime.open(share)
        runtime.schedule_callback(r, check)
        return r

    @protocol
    def test_encrypted_random_real_shares_open_correctly(self, runtime):
        random = Random(3423993)
        modulus = 17
        Zp = GF(modulus)
        bits_in_p = 5
        u_bound = 2**(4 * bits_in_p)
        alpha = 15
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))

        share_random = Random(random.getrandbits(128))
        gen = TestShareGenerator(Zp, runtime, share_random, paillier, u_bound, alpha)
        shares = gen.generate_random_shares(7)
        expected_result = [9,16,7,12,3,5,6]
        results = []
        for inx, share in enumerate(shares):
            def check(v, expected_result):
                self.assertEquals(expected_result, v)
            r = runtime.open(share)
            results.append(r)
            runtime.schedule_callback(r, check, expected_result[inx])
        return gather_shares(results)

class AddMacsTest(BeDOZaTestCase): 

    timeout = 10

    @protocol
    def test_add_macs_produces_correct_sharing(self, runtime):
        # TODO: Here we use the open method of the BeDOZa runtime in
        # order to verify the macs of the generated full share. In
        # order to be more unit testish, this test should use its own
        # way of verifying these.
        p = 17
        Zp = GF(p)
        secret = 6
        random = Random(283883)
        paillier_random = Random(random.getrandbits(128))
        paillier = ModifiedPaillier(runtime, random)

        add_macs_random = Random(random.getrandbits(128))

        shares_random = Random(random.getrandbits(128))
        shares = []
        shares.append(partial_share(shares_random, runtime, Zp, secret, paillier=paillier))
        shares.append(partial_share(shares_random, runtime, Zp, secret + 1, paillier=paillier))
        shares.append(partial_share(shares_random, runtime, Zp, secret + 2, paillier=paillier))
        shares.append(partial_share(shares_random, runtime, Zp, secret + 3, paillier=paillier))

        bits_in_p = 5
        u_bound = 2**(4 * bits_in_p)
        alpha = 15

        zs = add_macs(runtime, Zp, u_bound, alpha,
                      add_macs_random, paillier, shares)
        def verify(open_shares):
            inx = secret
            for open_share in open_shares:
                self.assertEquals(inx, open_share.value)
                inx += 1

        opened_shares = []
        for s in zs:
            opened_shares.append(runtime.open(s))
        d = gather_shares(opened_shares)
        d.addCallback(verify)
        return d

        
#    @protocol
#    def test_add_macs_preserves_value_of_sharing(self, runtime):
#        partial_share = self._generate_partial_share_of(42)
#        full_share = TripleGenerator()._add_macs(partial_share)
#        secret = self._open_sharing(full_share)
#        self.assertEquals(42, secret)
#        return partial_share
#    #test_add_macs_preserves_value_of_sharing.skip = "nyi"
#        
#    @protocol
#    def test_add_macs_preserves_value_of_zero_sharing(self, runtime):
#        partial_share = self._generate_partial_share_of(0)
#        full_share = TripleGenerator()._add_macs(partial_share)
#        secret = self._open_sharing(full_share)
#        self.assertEquals(0, secret)
#        return partial_share
#    #test_add_macs_preserves_value_of_zero_sharing.skip = "nyi"
# 

class TripleTest(BeDOZaTestCase): 

    timeout = 25

    @protocol
    def test_generate_triples_generates_correct_single_triple(self, runtime):
        p = 17
        Zp = GF(p)
        random = Random(574566 + runtime.id)        
        triple_generator = TripleGenerator(runtime, self.security_parameter, p, random)
        triples = triple_generator._generate_triples(1)

        def check((a, b, c)):
            self.assertEquals(c, a * b)

        def open(triple):
            d1 = runtime.open(triple.a)
            d2 = runtime.open(triple.b)
            d3 = runtime.open(triple.c)
            d = gatherResults([d1, d2, d3])
            runtime.schedule_callback(d, check)
            return d

        for triple in triples:
            runtime.schedule_callback(triple, open)
        return gatherResults(triples)

    @protocol
    def test_generate_triples_generates_correct_triples(self, runtime):
        p = 17

        Zp = GF(p)
      
        random = Random(574566 + runtime.id)        
        triple_generator = TripleGenerator(runtime, self.security_parameter, p, random)

        triples = triple_generator._generate_triples(10)

        def check((a, b, c)):
            self.assertEquals(c, a * b)

        def open(triple):
            d1 = runtime.open(triple.a)
            d2 = runtime.open(triple.b)
            d3 = runtime.open(triple.c)
            d = gatherResults([d1, d2, d3])
            runtime.schedule_callback(d, check)
            return d

        for triple in triples:
            runtime.schedule_callback(triple, open)
        return gatherResults(triples)

    @protocol
    def test_generate_triple_candidates_generates_correct_triples(self, runtime):
        p = 17

        Zp = GF(p)
       
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, self.security_parameter, p, random)

        triples = triple_generator._generate_triple_candidates(5)
        def verify(triples):
            for inx in xrange(len(triples) // 3):
                self.assertEquals(triples[10 + inx], triples[inx] * triples[5 + inx])
        opened_shares = []
        for s in triples:
            opened_shares.append(runtime.open(s))
        d = gather_shares(opened_shares)
        d.addCallback(verify)
        return d

class MulTest(BeDOZaTestCase): 

    timeout = 10
        
    @protocol
    def test_mul_computes_correct_result(self, runtime):
        p = 17
       
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, 32, p, random)

        Zp = GF(p)

        ais = [Zp(6), Zp(6), Zp(6), Zp(6)]
        b2 = Zp(7)
        cs = []
        for ai in ais:
            cs.append(triple_generator.paillier.encrypt(b2.value, 2))      

        n = len(ais)
        
        if runtime.id == 1:
            r1 = triple_generator._mul(1, 2, n, ais, cs)
            def check1(shares):
                for share in shares:
                    pc = tuple(runtime.program_counter)
                    runtime.protocols[2].sendData(pc, TEXT, str(share.value))
                return True
            r1.addCallback(check1)
            return r1
        else:
            r1 = triple_generator._mul(1, 2, n)
            def check(shares):
                deferreds = []
                for share in shares:
                    if runtime.id == 2:
                        def check_additivity(zi, zj):
                            self.assertEquals((Zp(long(zi)) + zj).value, 8)
                            return None
                        d = Deferred()
                        d.addCallback(check_additivity, share.value)
                        runtime._expect_data(1, TEXT, d)
                        deferreds.append(d)
                    else:
                        self.assertEquals(share.value, 0)
                return gatherResults(deferreds)
            r1.addCallback(check)
            return r1

    @protocol
    def test_mul_same_player_inputs_and_receives(self, runtime):
        p = 17
      
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, self.security_parameter, p, random)

        Zp = GF(p)

        ais = [Zp(6), Zp(6), Zp(6), Zp(6)]
        b2 = Zp(7)
        cs = []
        for ai in ais:
            cs.append(triple_generator.paillier.encrypt(b2.value, 2))

        n = len(ais)
        
        r1 = triple_generator._mul(2, 2, n, ais, cs)
        def check(shares):
            for share in shares:
                if runtime.id == 2:
                    self.assertEquals(share.value, 8)
            return True
            
        r1.addCallback(check)
        return r1


class ShareTest(BeDOZaTestCase):

    timeout = 10

    @protocol
    def test_share_protocol_single(self, runtime):
        p, k = 17, 5
        Zp = GF(p)
        random = Random(3455433 + runtime.id)
        elms = [Zp(runtime.id)]
        paillier_random = Random(random.getrandbits(128))
        zk_random = Random(random.getrandbits(128))
        paillier = ModifiedPaillier(runtime, paillier_random)
        partial_shares = generate_partial_share_contents(
            elms, runtime, paillier, k, zk_random)

        def decrypt(share_contents):
            self.assertEquals(1, len(share_contents))
            decrypted_share = paillier.decrypt(
                share_contents[0].enc_shares[runtime.id - 1])
            decrypted_shares = _convolute(runtime, decrypted_share)
            def test_sum(vals):
                self.assertEquals([Zp(e) for e in [1, 2, 3]], vals)
            runtime.schedule_callback(decrypted_shares, test_sum)

        runtime.schedule_callback(partial_shares, decrypt)
        return partial_shares

    @protocol
    def test_share_protocol_multi(self, runtime):
        p, k = 17, 5
        Zp = GF(p)
        random = Random(345453 + runtime.id)
        elms = [Zp(runtime.id), Zp(runtime.id * 3)]
        paillier_random = Random(random.getrandbits(128))
        zk_random = Random(random.getrandbits(128))
        paillier = ModifiedPaillier(runtime, paillier_random)
        partial_shares = generate_partial_share_contents(
            elms, runtime, paillier, k, zk_random)

        def decrypt(share_contents):
            self.assertEquals(2, len(share_contents))
            decrypted_shares = [paillier.decrypt(
                    share_contents[i].enc_shares[runtime.id - 1])
                                for i in range(2)]
            decrypted_shares = [_convolute(runtime, decrypted_shares[i])
                                for i in range(2)]
            def test_sum(vals, should_be):
                self.assertEquals([Zp(e) for e in should_be], vals)
            runtime.schedule_callback(
                decrypted_shares[0], test_sum, [1, 2, 3])
            runtime.schedule_callback(
                decrypted_shares[1], test_sum, [3, 6, 9])

        runtime.schedule_callback(partial_shares, decrypt)
        return partial_shares


class FullMulTest(BeDOZaTestCase): 

    timeout = 10
        
    @protocol
    def test_fullmul_computes_the_correct_result(self, runtime):
        p = 17

        Zp = GF(p)
        
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, self.security_parameter, p, random)

        paillier = triple_generator.paillier
        
        share_as = []
        share_bs = []      
        share_as.append(partial_share(random, runtime, GF(p), 6, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 7, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 5, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 4, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 2, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 3, paillier=paillier))


        share_zs = triple_generator._full_mul(share_as, share_bs)
        def check(shares):
            def test_sum(ls):
                self.assertEquals(8, Zp(sum(ls[0])))
                self.assertEquals(3, Zp(sum(ls[1])))
                self.assertEquals(6, Zp(sum(ls[2])))
            values = []
            for share in shares:
                value = _convolute(runtime, share.value.value)
                values.append(value)
            d = gatherResults(values)
            runtime.schedule_callback(d, test_sum)
            return d
            
        d = gatherResults(share_zs)
        d.addCallback(check)
        return d

    @protocol
    def test_fullmul_encrypted_values_are_the_same_as_the_share(self, runtime):
        p = 17

        Zp = GF(p)
        
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, self.security_parameter, p, random)

        paillier = triple_generator.paillier

        share_as = []
        share_bs = []      
        share_as.append(partial_share(random, runtime, GF(p), 6, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 7, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 5, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 4, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 2, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 3, paillier=paillier))

        share_zs = triple_generator._full_mul(share_as, share_bs)
        def check(shares):
            all_enc_shares = []
            for share in shares:
                def test_enc(enc_shares, value):
                    all_the_same, zi_enc = reduce(lambda x, y: (x[0] and x[1] == y, y), enc_shares, (True, enc_shares[0]))
                    zi_enc = triple_generator.paillier.decrypt(zi_enc)
                    self.assertEquals(value, Zp(zi_enc))
                    return True
                for inx, enc_share in enumerate(share.enc_shares):
                    d = _convolute(runtime, enc_share)
                    if runtime.id == inx + 1:
                        d.addCallback(test_enc, share.value)
                all_enc_shares.append(d)
            return gatherResults(all_enc_shares)
        
        d = gatherResults(share_zs)
        d.addCallback(check)
        return d
        

skip_if_missing_packages(
    ShareTest,
    ModifiedPaillierTest,
    PartialShareGeneratorTest,
    TripleTest,
    DataTransferTest,
    MulTest,
    FullMulTest,
    ShareGeneratorTest,
    AddMacsTest)
