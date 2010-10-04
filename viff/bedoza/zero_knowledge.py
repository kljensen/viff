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

from gmpy import mpz, digits

import hashlib

from viff.runtime import gatherResults
from viff.bedoza.util import rand_int_signed

class ZKProof(object):
    """Zero-knowledge protocol used as part of the Share protocol.

    In this proof, a player (the player with id prover_id) inputs s
    ciphertexts c[i] = E(x[j], r[j]), for i = 1, ..., s, created using
    the modified Paillier cipher and proves to the other players that
    he knows the plaintexts x[j] and that the x[i]'s are of limited
    size, e.g. that abs(x[i]) <= 2**k.
    """
    
    def __init__(self, s, prover_id, k, runtime, c, random=None, paillier=None, x=None, r=None):
        """
        random: a random source (e.g. viff.util.Random)

        All players must submit the same vector c, but only the player
        with id prover_id should submit the corresponding x and r, e.g. where
        c_i = E_i(x_i, r_i).
        """
        assert len(c) == s
        assert prover_id in runtime.players
        if x != None:
            for xi in x:
                assert abs(xi) <= 2**k
        self.x = x
        self.r = r
        self.s = s
        self.m = 2 * s - 1
        self.prover_id = prover_id
        self.k = k
        self.runtime = runtime
        self.c = c
        self.paillier = paillier
        self.random = random
        self.prover_n = mpz(self.runtime.players[self.prover_id].pubkey['n'])

        # TODO: Use the n**2 already in the pubkey.
        self.prover_n2 = self.prover_n**2

    def start(self):
        """Executes this zero-knowledge proof.

        Returns a deferred evaluating to True if the proof succeeds
        and False otherwise. The proof succeeds if the verifiers,
        e.g. all players except the player with prover_id are able to
        verify that each number inside the encryptions c are
        numerically at most 2**(s + 2k).

        The result also evaluates to True or False as above for the
        proving player, even though this is not needed.
        """
        if self.runtime.id == self.prover_id:
            self._generate_proof()
        deferred_proof = self._get_proof_broadcasted_by_prover()
        self.runtime.schedule_callback(deferred_proof, self._verify_proof)
        return deferred_proof

    def _generate_proof(self):
        self._generate_u_v_and_d()
        self._generate_e()
        self._generate_Z_and_W()

    def _verify_proof(self, serialized_proof):
        # The prover don't need to prove to himself.
        if self.runtime.id == self.prover_id:
            return True
        self._deserialize_proof(serialized_proof)
        self._generate_e()
        temp = self._vec_pow_E(self.c, self.prover_n2)
        S = self._vec_mul(self.d, temp, self.prover_n2)
        T = [mpz(self.paillier.encrypt(int(self.Z[j]), player_id=self.prover_id, random_elm=int(self.W[j])))
             for j in range(self.m)]
        for j in xrange(self.m):
            # TODO: Return false if S[j] != T[j].
            if S[j] != T[j]:
                # TODO: Proof failed, return false!
                pass
            if abs(self.Z[j]) > 2**(2 * self.k):
                # TODO: Proof failed, return false!
                pass

        # TODO: Fix zero-knowledge proof!!!
        return True
        

    def _generate_u_v_and_d(self):
        self.u, self.v, self.d = [], [], []
        for i in range(self.m):
            ui = rand_int_signed(self.random, 2**(2 * self.k))
            vi, di = self.paillier.encrypt_r(ui)
            assert abs(ui) <= 2**(2 * self.k)
            self.u.append(mpz(ui))
            self.v.append(mpz(vi))
            self.d.append(mpz(di))

    def _generate_Z_and_W(self):
        self.Z = self._vec_add(self.u, self._vec_mul_E(self.x))
        self.W = self._vec_mul(self.v, self._vec_pow_E(self.r, self.prover_n2), self.prover_n2)

    def _get_proof_broadcasted_by_prover(self):
        serialized_proof = None
        if self.runtime.id == self.prover_id:
            # TODO: Should we somehow compress message for improved
            # performance?
            serialized_proof = self._serialize_proof()
        deferred_proof = self._broadcast(serialized_proof)
        return deferred_proof

    def _serialize_proof(self):
        return repr([self.d, self.Z, self.W])

    def _deserialize_proof(self, serialized_proof):
        # We remove quotes before evaluation in order to get a list.
        proof = eval(serialized_proof[1:-1])
        self.d = proof[0]
        self.Z = proof[1]
        self.W = proof[2]

    def _extract_bits(self, string, no_of_bits):
        """Returns list of first no_of_bits from the given string."""
        word_size = 8 # No of bits in char.
        assert no_of_bits <= word_size * len(string), "Not enough bits"
        res = []
        if no_of_bits == 0:
            return res
        no_of_chars = 1 + no_of_bits / word_size
        for c in string[:no_of_chars]:
            _digits = [int(v) for v in digits(ord(c), 2).zfill(word_size)]
            if len(res) + word_size >= no_of_bits:
                return res + _digits[:no_of_bits - len(res)]
            res += _digits
        return [mpz(b) for b in res]


    def _generate_e(self):
        """Generating an s-bit challenge e by the Fiat-Shamir heuristic.
        
        In other security models, generating the challenge requires
        interaction.
       
        The challenge is a list of 0's and 1's of length s.
        """
        # This can be easily fixed by using the hash as seed for a
        # secure prng.
        assert self.s <= 160, "Error: Algorithm only supports s <= 160"
        assert hasattr(self, 'c')
        assert hasattr(self, 'd')
        h = hashlib.sha1()
        for c, d in zip(self.c, self.d):
            h.update(repr(c))
            h.update(repr(d))
        hash = h.digest()
        self.e = self._extract_bits(hash, self.s)

    def _broadcast(self, values):
        msg = repr(values) if self.prover_id == self.runtime.id else None
        return self.runtime.broadcast(
            [self.prover_id], self.runtime.players.keys(), message=msg)

    def _err_handler(self, err):
        print err
        return err # raise or what?

    def _E(self, row, col):
        """Computes the value of the entry in the matrix E at the given row
        and column.
        
        The first column of E consists of the bits of e followed by 0's;
        The next column has one zero, then the bits of e, followed by 0's,
        etc.
        """
        if row >= col and row < col + self.s:
            return self.e[row - col]
        else:
            return 0

    def _vec_add(self, x, y):
        return [x + y for x, y in zip(x,y)]

    def _vec_mul_E(self, x):
        """Takes an s x 1 vector x and returns the m x 1 vector xE."""
        # TODO: This could probably be optimized since we know the
        # structure of E.
        res = []
        for j in xrange(self.m):
            t = 0
            for i in xrange(self.s):
                t = t + x[i] * self._E(j, i)
            res.append(t)
        return res
    
    def _vec_mul(self, x, y, n):
        return [(x * y) % n for x, y in zip(x,y)]

    def _vec_pow_E(self, y, n):
        """Computes and returns the m := 2s-1 length vector y**E."""
        assert self.s == len(y), \
            "not same length: %d != %d" % (self.s, len(y))
        res = [mpz(1)] * self.m
        for j in range(self.m):
            for i in range(self.s):
                if self._E(j, i) == mpz(1):
                    # TODO: Should we reduce modulo n each time?
                    res[j] = (res[j] * y[i]) % n
        return res
