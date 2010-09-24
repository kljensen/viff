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
     
    def _verify_input(self, value, player_id):
        assert isinstance(value, int) or isinstance(value, long), \
            "paillier: encrypts only integers and longs, got %s" % \
                value.__class__

    def encrypt_with_randomness(self, value, randomness, player_id=None):
        """Encrypt using public key of player player_id using the
        given randomness.

        Defaults to own public key.

        """
        self._verify_input(value, player_id)
        if not player_id:
            player_id = self.runtime.id
        n = self.runtime.players[player_id].pubkey['n']
        min = -(n - 1) / 2
        max = (n - 1) / 2
        assert min <= value <= max, \
            "paillier: plaintext %d outside legal range [-(n-1)/2 " \
            "; (n-1)/2] = [%d ; %d]"  % (value, min, max)
        pubkey = self.runtime.players[player_id].pubkey
        return randomness, pypaillier.encrypt_r(self._f(value, n), randomness, pubkey) 

    def encrypt_r(self, value, player_id=None):
       """As encrypt_with_randomness, but generates its own randomness."""
       self._verify_input(value, player_id)
       if not player_id:
           player_id = self.runtime.id
       n = self.runtime.players[player_id].pubkey['n']
       randomness = self.random.randint(1, long(n))
       return self.encrypt_with_randomness(value, randomness, player_id=player_id)


    def encrypt(self, value, player_id=None):
        """As encrypt_r, but doesn't return randomness used, only
        encrypted value."""
        return self.encrypt_r(value, player_id=player_id)[1]


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
