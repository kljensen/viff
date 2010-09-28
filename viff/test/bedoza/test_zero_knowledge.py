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
from viff.bedoza.modified_paillier import ModifiedPaillier
from viff.bedoza.zero_knowledge import ZKProof
from viff.bedoza.util import rand_int_signed

from viff.test.util import protocol
from viff.test.bedoza.util import BeDOZaTestCase, skip_if_missing_packages


class RuntimeStub(object):
    def __init__(self, players=[1, 2, 3], id=1):
        self.players = players
        self.id = id

class BeDOZaZeroKnowledgeTest(BeDOZaTestCase):

    num_players = 3

    def test_zk_matrix_entries_are_correct(self):
        s, k, prover_id = 5, 1, 1
        c = [None] * s
        zk = ZKProof(s, prover_id, k, RuntimeStub(), c)
        zk.e = [1, 0, 0, 1, 1]
        for i in range(zk.s):
            for j in range(zk.m):
                if j >= i and j < i + zk.s:
                    self.assertEquals(zk.e[j - i], zk._E(j, i))
                else:
                    self.assertEquals(0, zk._E(j, i))

    def test_vec_pow_is_correct(self):
        s, prover_id, k, Zn = 5, 1, 0, GF(17)
        c = [None] * s
        y = [Zn(i) for i in range(1, 6)]
        zk = ZKProof(s, prover_id, k, RuntimeStub(), c)
        zk.e = [1, 0, 1, 1, 0]
        y_pow_E = zk._vec_pow_E(y)
        self.assertEquals([Zn(v) for v in [1, 2, 3, 8, 13, 12, 3, 5, 1]],
                          y_pow_E)

    def test_vec_pow_is_correct_2(self):
        s, k, Zn, prover_id = 3, 0, GF(17), 1
        c = [None] * s
        y = [Zn(i) for i in [1, 7, 2]]
        zk = ZKProof(s, prover_id, k, RuntimeStub(), c)
        zk.e = [0, 1, 1]
        y_pow_E = zk._vec_pow_E(y)
        self.assertEquals([Zn(v) for v in [1, 1, 7, 14, 2]], y_pow_E)

    def test_vec_mul_E_is_correct(self):
        s, prover_id, k, Zn = 5, 1, 0, GF(17)
        c = [None] * s
        y = [Zn(i) for i in range(1, 6)]
        zk = ZKProof(s, prover_id, k, RuntimeStub(), c)
        zk.e = [1, 0, 1, 1, 0]
        x = [1, 2, 0, 1, 0]
        x_mul_E = zk._vec_mul_E(x)
        self.assertEquals([v for v in [1, 2, 1, 4, 2, 1, 1, 0, 0]], x_mul_E)

    def test_vec_mul_E_is_correct_2(self):
        s, k, prover_id = 3, 0, 1
        c = [None] * s
        zk = ZKProof(s, prover_id, k, RuntimeStub(), c)
        zk.e = [0, 1, 1]
        x = [2, -3, 0]
        x_mul_E = zk._vec_mul_E(x)
        self.assertEquals([v for v in [0, 2, -1, -3, 0]], x_mul_E)

    @protocol
    def test_broadcast(self, runtime):
        s, k, prover_id = 0, 2, 1
        c = []
        zk = ZKProof(s, prover_id, k, runtime, c)
        res = zk._broadcast([5, 6, 7])
        def verify(res):
            self.assertEquals(eval(res), [5, 6, 7])
        runtime.schedule_callback(res, verify)
        return res

    def test_extract_bits(self):
        s, k, prover_id = 5, 1, 1
        c = [None] * s
        runtime = RuntimeStub()
        zk = ZKProof(s, prover_id, k, runtime, c)
        self.assertEquals([], zk._extract_bits('test', 0))
        self.assertEquals([0], zk._extract_bits('test', 1))
        self.assertEquals([0, 1], zk._extract_bits('test', 2))
        self.assertEquals([0, 1, 1, 1, 0, 1, 0], zk._extract_bits('test', 7))
        self.assertEquals([0, 1, 1, 1, 0, 1, 0, 0], zk._extract_bits('test', 8))
        self.assertEquals([0, 1, 1, 1, 0, 1, 0, 0, 0], zk._extract_bits('test', 9))
        self.assertEquals([0, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 1], zk._extract_bits('test', 14))

    def test_generate_e_generates_e_of_right_length(self):
        s, prover_id, k = 9, 1, 0
        c = [1, 1, 0, 0, 1, 0, 1, 0, 1]
        zk = ZKProof(s, prover_id, k, RuntimeStub(), c)
        zk.d = [1, 0, 0, 1, 1, 0, 1, 1, 1]
        zk._generate_e()
        self.assertEquals(s, len(zk.e))

    def test_generate_e_is_deterministic(self):
        s, prover_id, k = 9, 1, 0
        c = [1, 1, 0, 0, 1, 0, 1, 0, 1]
        zk = ZKProof(s, prover_id, k, RuntimeStub(), c)
        zk.d = [1, 0, 0, 1, 1, 0, 1, 1, 1]
        zk._generate_e()
        e1 = zk.e
        zk._generate_e()
        self.assertEquals(e1, zk.e)

    @protocol
    def test_generate_Z_and_W_is_correct(self, runtime):
        s, prover_id, k = 3, 1, 0
        c = [None] * s
        zk = ZKProof(s, prover_id, k, runtime, c)
        zk.u = [1, -2, 0, 6, -3]
        zk.v = [3, 5, 2, 1, 7]
        zk.x = [2, -3, 0]
        zk.r = [1, 7, 2]
        zk.e = [0, 1, 1]
        zk._generate_Z_and_W()
        self.assertEquals([1, 0, -1, 3, -3], zk.Z)
        self.assertEquals([3, 5, 14, 14, 14], zk.W)


    def _generate_test_ciphertexts(self, random, runtime, k, s, prover_id):
        paillier = ModifiedPaillier(runtime, random)
        xs, rs, cs = [], [], []
        for i in range(s):
            x = rand_int_signed(random, 2**k)
            r, c = paillier.encrypt_r(x, player_id=prover_id)
            xs.append(x)
            rs.append(r)
            cs.append(c)
        return xs, rs, cs

    @protocol
    def test_succeeding_proof(self, runtime):
        seed = 2348838
        k, s, prover_id = 5, 3, 1
        player_random = Random(seed + runtime.id)
        shared_random = Random(seed)
        paillier = ModifiedPaillier(runtime, Random(player_random.getrandbits(128)))
        x, r, c = self._generate_test_ciphertexts(shared_random, runtime, k, s, prover_id)
        #print "Player", runtime.id, " x =", x
        #print "Player", runtime.id, " r =", r
        #print "Player", runtime.id, " c =", c
        if runtime.id == prover_id: 
            zk = ZKProof(s, prover_id, k, runtime, c, paillier=paillier, random=player_random, x=x, r=r)
        else:
            zk = ZKProof(s, prover_id, k, runtime, c, paillier=paillier, random=player_random)

        deferred_proof = zk.start()
        def verify(result):
            self.assertTrue(result)
        runtime.schedule_callback(deferred_proof, verify)
        return deferred_proof

# TODO: Test succeeding proof.
# TODO: Test failing proof.

skip_if_missing_packages(BeDOZaZeroKnowledgeTest)
