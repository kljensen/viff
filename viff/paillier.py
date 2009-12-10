# Copyright 2008 VIFF Development Team.
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

"""Paillier crypto system and two-party runtime.

The :class:`PaillierRuntime` is a special two-player runtime based on
the homomorphic Paillier crypto system.

From the paper "Public-Key Cryptosystems Based on Composite Degree
Residuosity Classes" by Pascal Paillier in EUROCRYPT 1999, 223-238.
"""

from twisted.internet.defer import Deferred, gatherResults
import gmpy

from viff.runtime import Runtime, Share, gather_shares
from viff.constants import PAILLIER
from viff.util import rand, find_random_prime

def L(u, n):
    return (u-1)/n

def generate_keys(bit_length):
    # Make an RSA modulus n.
    p = find_random_prime(bit_length/2)
    while True:
        q = find_random_prime(bit_length/2)
        if p<>q: break

    n = p*q
    nsq = n*n

    # Calculate Carmichael's function.
    lm = gmpy.lcm(p-1, q-1)

    # Generate a generator g in B.
    while True:
        g = rand.randint(1, long(nsq))
        if gmpy.gcd(L(pow(g, lm, nsq), n), n) == 1: break

    return {'n':n, 'g': g}, {'n': n, 'g': g, 'lm': lm}

def encrypt(m, pubkey):
    r = rand.randint(1, long(pubkey['n']))
    return encrypt_r(m, r, pubkey)

def encrypt_r(m, r, pubkey):
    n = pubkey['n']
    g = pubkey['g']
    nsq = n*n
    return (pow(g, m, nsq)*pow(r, n, nsq)) % nsq

#: Cache for ciphertext-independent factors.
_decrypt_factors = {}

def decrypt(c, seckey):
    c = long(c)
    n = seckey['n']
    g = seckey['g']
    lm = seckey['lm']
    numer = L(pow(c, lm, n*n), n)
    key = (n, g, lm)
    try:
        factor = _decrypt_factors[key]
    except KeyError:
        denom = L(pow(g, lm, n*n), n)
        factor = gmpy.invert(denom, n)
        _decrypt_factors[key] = factor
    return (numer * factor) % n


class PaillierRuntime(Runtime):
    """Two-player runtime based on the Paillier crypto system."""

    def add_player(self, player, protocol):
        Runtime.add_player(self, player, protocol)
        if player.id == self.id:
            self.player = player
        else:
            self.peer = player

    def prss_share_random(self, field):
        """Generate a share of a uniformly random element."""
        prfs = self.players[self.id].prfs(field.modulus)
        # There can only be one PRF in the dictionary.
        prf = prfs.values()[0]
        share = field(prf(tuple(self.program_counter)))
        return Share(self, field, share)

    def input(self, inputters, field, number=None):
        """Input *number* to the computation.

        The input is shared using the :meth:`share` method.
        """
        return self.share(inputters, field, number)

    def share(self, inputters, field, number=None):
        """Share *number* additively."""
        assert number is None or self.id in inputters

        results = []
        for peer_id in inputters:
            # Unique program counter per input.
            self.increment_pc()

            if peer_id == self.id:
                a = field(rand.randint(0, field.modulus - 1))
                b = number - a

                results.append(Share(self, a.field, a))
                pc = tuple(self.program_counter)
                self.protocols[self.peer.id].sendShare(pc, b)
            else:
                share = self._expect_share(peer_id, field)
                results.append(share)

        # Unpack a singleton list.
        if len(results) == 1:
            return results[0]
        else:
            return results

    def output(self, share, receivers=None):
        return self.open(share, receivers)

    def open(self, share, receivers=None):
        """Open *share* to *receivers* (defaults to both players)."""

        def exchange(a):
            pc = tuple(self.program_counter)
            self.protocols[self.peer.id].sendShare(pc, a)
            result = self._expect_share(self.peer.id, share.field)
            result.addCallback(lambda b: a + b)
            return result

        result = share.clone()
        self.schedule_callback(result, exchange)
        return result

    def add(self, share_a, share_b):
        """Addition of shares.

        Communication cost: none.
        """
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            share_b = Share(self, field, share_b)

        result = gather_shares([share_a, share_b])
        result.addCallback(lambda (a, b): a + b)
        return result

    def mul(self, share_a, share_b):
        """Multiplication of shares."""
        field = getattr(share_a, "field", getattr(share_b, "field", None))

        k = self.options.security_parameter
        n = min(self.player.pubkey['n'], self.peer.pubkey['n'])
        assert field.modulus**2 + 2**k < n, \
            "Need bigger Paillier keys to multiply."

        if not isinstance(share_a, Share):
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            share_b = Share(self, field, share_b)

        def finish_mul((a, b)):
            pc = tuple(self.program_counter)
            send_data = self.protocols[self.peer.id].sendData

            if hash(pc) % 2 == self.id:
                # We play the role of P1.
                a1, b1 = a, b
                enc_a1 = encrypt(a1.value, self.player.pubkey)
                enc_b1 = encrypt(b1.value, self.player.pubkey)
                send_data(pc, PAILLIER, str(enc_a1))
                send_data(pc, PAILLIER, str(enc_b1))

                enc_c1 = Share(self, field)
                self._expect_data(self.peer.id, PAILLIER, enc_c1)
                c1 = enc_c1.addCallback(decrypt, self.player.seckey)
                c1.addCallback(lambda c: long(c) + a1 * b1)
                return c1
            else:
                # We play the role of P2.
                a2, b2 = a, b
                enc_a1 = Deferred()
                self._expect_data(self.peer.id, PAILLIER, enc_a1)
                enc_a1.addCallback(long)
                enc_b1 = Deferred()
                self._expect_data(self.peer.id, PAILLIER, enc_b1)
                enc_b1.addCallback(long)

                nsq = self.peer.pubkey['n']**2
                # Calculate a1 * b2 and b1 * a2 inside the encryption.
                enc_a1_b2 = enc_a1.addCallback(pow, b2.value, nsq)
                enc_b1_a2 = enc_b1.addCallback(pow, a2.value, nsq)

                # Chose and encrypt r.
                r = rand.randint(0, 2 * field.modulus**2 + 2**k)
                enc_r = encrypt(r, self.peer.pubkey)

                c1 = gatherResults([enc_a1_b2, enc_b1_a2])
                c1.addCallback(lambda (a,b): a * b * enc_r)
                c1.addCallback(lambda c: send_data(pc, PAILLIER, str(c)))

                c2 = a2 * b2 - r
                return Share(self, field, c2)

        result = gather_shares([share_a, share_b])
        result.addCallback(finish_mul)
        return result
