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


# We don't need secure random numbers for test purposes.
from random import Random

from viff.field import GF
from viff.runtime import gather_shares

from viff.bedoza.bedoza_triple import ModifiedPaillier
from viff.bedoza.util import _convolute, _convolute_gf_elm

from viff.test.util import protocol
from viff.test.bedoza.util import BeDOZaTestCase, skip_if_missing_packages
from viff.test.bedoza.util import TestShareGenerator, TestPartialShareGenerator


class TestPartialShareGeneratorTest(BeDOZaTestCase):
 
    def _partial_share(self, random, runtime, Zp, val, paillier=None):
        if not paillier:
            paillier_random = Random(random.getrandbits(128))
            paillier = ModifiedPaillier(runtime, paillier_random)
        share_random = Random(random.getrandbits(128))
        gen = TestPartialShareGenerator(Zp, runtime, share_random, paillier)
        return gen.generate_share(Zp(val))

    def _partial_random_shares(self, random, runtime, Zp, n, paillier=None):
        if not paillier:
            paillier_random = Random(random.getrandbits(128))
            paillier = ModifiedPaillier(runtime, paillier_random)
        share_random = Random(random.getrandbits(128))
        gen = TestPartialShareGenerator(Zp, runtime, share_random, paillier)
        return gen.generate_random_shares(n)

    @protocol
    def test_shares_have_correct_type(self, runtime):
        Zp = GF(23)
        share = self._partial_share(Random(23499), runtime, Zp, 7)
        def test(share):
            self.assertEquals(Zp, share.value.field)
        runtime.schedule_callback(share, test)
        return share
 
    @protocol
    def test_shares_are_additive(self, runtime):
        secret = 7
        share = self._partial_share(Random(34993), runtime, GF(23), secret)
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
        share = self._partial_share(Random(random.getrandbits(128)), runtime,
                                    GF(modulus), secret, paillier=paillier)
        def decrypt(share):
            decrypted_share = paillier.decrypt(share.enc_shares[runtime.id - 1])
            decrypted_shares = _convolute(runtime, decrypted_share)
            def test_sum(vals):
                self.assertEquals(secret, sum(vals) % modulus)
            runtime.schedule_callback(decrypted_shares, test_sum)
        runtime.schedule_callback(share, decrypt)
        return share

    @protocol
    def test_random_shares_have_correct_type(self, runtime):
        Zp = GF(23)
        shares = self._partial_random_shares(Random(23499), runtime, Zp, 7)
        for share in shares:
            def test(share):
                self.assertEquals(Zp, share.value.field)
            runtime.schedule_callback(share, test)
            
        return shares
 
    @protocol
    def test_encrypted_random_shares_decrypt_correctly(self, runtime):
        random = Random(3423993)
        modulus = 17
        Zp = GF(modulus)
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))
        shares = self._partial_random_shares(random, runtime, Zp, 7, paillier=paillier)
        expected_result = [9,16,7,12,3,5,6]
        for inx, share in enumerate(shares):
            def decrypt(share, expected_result):
                decrypted_share = paillier.decrypt(share.enc_shares[runtime.id - 1])
                decrypted_shares = _convolute(runtime, decrypted_share)
                def test_sum(vals, expected_result):
                    v = Zp(sum(vals))
                    self.assertEquals(expected_result, v)
                runtime.schedule_callback(decrypted_shares, test_sum, expected_result)
            runtime.schedule_callback(share, decrypt, expected_result[inx])
            
        return shares

class TestShareGeneratorTest(BeDOZaTestCase):

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
        gen = TestShareGenerator(Zp, runtime, share_random, paillier, u_bound, alpha)
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


skip_if_missing_packages(
    TestPartialShareGeneratorTest,
    TestShareGeneratorTest)
