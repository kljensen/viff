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

from gmpy import gcd

try:
    import pypaillier
except ImportError:
    # The pypaillier module is not released yet, so we cannot expect
    # the import to work.
    print "Error: The pypaillier module or one of the used functions " \
        "are not available."

class ModifiedPaillier(object):
    """A slight modification of the Paillier cryptosystem.

    This modification has plaintext space [-(n-1)/2 ; (n-1)/2] rather
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
        if 0 <= y <= (n - 1) / 2:
            return y
        else:
            return y - n


    def encrypt_r(self, value, player_id=None, random_elm=None):
        """Encryption of the given value.
        
        If player_id is given, encrypts using public key of that
        player, otherwise just use public key of the player itself.
        
        The encryption requires some randomness in the form of an
        element in Zn*. If random_elm is given, it is used as random
        element. Otherwise, a random element is generated using the
        pseudo-random generator given when the ModifiedPaillier object
        was constructed.
        """
        assert isinstance(value, int) or isinstance(value, long), \
            "paillier: encrypts only integers and longs, got %s" % \
                value.__class__
        if not player_id:
            player_id = self.runtime.id
        n = self.runtime.players[player_id].pubkey['n']
        min = -(n - 1) / 2
        max = (n - 1) / 2
        assert min <= value <= max, \
            "paillier: plaintext %d outside legal range [-(n-1)/2 " \
            "; (n-1)/2] = [%d ; %d]"  % (value, min, max)

        # Here we verify that random_elm is either None or in Zn*. But
        # for realistical parameters, we can save time by not doing
        # this, since for large n = pq, it is extremely unlikely that
        # a random element in Zn is not also a member of Zn*.
        if random_elm == None:
            while True:
                random_elm = self.random.randint(1, long(n))
                if gcd(random_elm, n) == 1:
                    break
        elif not gcd(random_elm, n) == 1:
            raise Exception("Random element must be an element in Zn*")

        pubkey = self.runtime.players[player_id].pubkey
        return random_elm, pypaillier.encrypt_r(
            self._f(value, n), random_elm, pubkey)


    def encrypt(self, value, player_id=None, random_elm=None):
        """Encryption of the given value.

        As encrypt_r, but doesn't return randomness used, only
        encrypted value.
        """
        return self.encrypt_r(value, player_id=player_id,
                              random_elm=random_elm)[1]


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
