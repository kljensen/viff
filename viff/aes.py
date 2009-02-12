# Copyright 2009 VIFF Development Team.
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

"""MPC implementation of AES (Rijndael)."""

__docformat__ = "restructuredtext"


import time

from viff.field import GF256
from viff.runtime import Share, gather_shares
from viff.matrix import Matrix


def bit_decompose(share, use_lin_comb=True):
    """Bit decomposition for GF256 shares."""

    assert isinstance(share, Share) and share.field == GF256, \
        "Parameter must be GF256 share."

    r_bits = [share.runtime.prss_share_random(GF256, binary=True) \
                  for i in range(8)]
    
    if (use_lin_comb):
        r = share.runtime.lin_comb([2 ** i for i in range(8)], r_bits)
    else:
        r = reduce(lambda x,y: x + y, 
                   [r_bits[i] * 2 ** i for i in range(8)])

    c = share.runtime.open(share + r)
    c_bits = [Share(share.runtime, GF256) for i in range(8)]
    
    def decompose(byte, bits):
        value = byte.value

        for i in range(8):
            c_bits[i].callback(GF256(value & 1))
            value >>= 1

    c.addCallback(decompose, c_bits)

    return [c_bits[i] + r_bits[i] for i in range(8)]


class AES:
    """AES instantiation:

    >>> aes = AES(runtime, 192)
    >>> cleartext = [Share(runtime, GF256, GF256(0)) for i in range(128/8)]
    >>> key = [runtime.prss_share_random(GF256) for i in range(192/8)]
    >>> ciphertext = aes.encrypt("abcdefghijklmnop", key)
    >>> ciphertext = aes.encrypt(cleartext, "keykeykeykeykeykeykeykey")
    >>> ciphertext = aes.encrypt(cleartext, key)

    In every case *ciphertext* will be a list of shares over GF256.
    """

    def __init__(self, runtime, key_size, block_size=128, 
                 use_exponentiation=False):
        """Initialize Rijndael.

        AES(runtime, key_size, block_size), whereas key size and block
        size must be given in bits. Block size defaults to 128."""

        assert key_size in [128, 192, 256], \
            "Key size must be 128, 192 or 256"
        assert block_size in [128, 192, 256], \
            "Block size be 128, 192 or 256"

        self.n_k = key_size / 32
        self.n_b = block_size / 32
        self.rounds = max(self.n_k, self.n_b) + 6
        self.runtime = runtime
        self.use_exponentiation = use_exponentiation

    # matrix for byte_sub, the last column is the translation vector
    A = Matrix([[1,0,0,0,1,1,1,1, 1],
                [1,1,0,0,0,1,1,1, 1],
                [1,1,1,0,0,0,1,1, 0],
                [1,1,1,1,0,0,0,1, 0],
                [1,1,1,1,1,0,0,0, 0],
                [0,1,1,1,1,1,0,0, 1],
                [0,0,1,1,1,1,1,0, 1],
                [0,0,0,1,1,1,1,1, 0]])

    def byte_sub(self, state, use_lin_comb=True):
        """ByteSub operation of Rijndael.

        The first argument should be a matrix consisting of elements
        of GF(2^8)."""

        def invert_by_masking(byte):
            bits = bit_decompose(byte)

            for j in range(len(bits)):
                bits[j].addCallback(lambda x: GF256(1) - x)
#                bits[j] = 1 - bits[j]

            while(len(bits) > 1):
                bits.append(bits.pop() * bits.pop())

            # b == 1 if byte is 0, b == 0 else
            b = bits[0]

            r = Share(self.runtime, GF256)
            c = Share(self.runtime, GF256)

            def get_masked_byte(c_opened, r_related, c, r, byte):
                if (c_opened == 0):
                    r_trial = self.runtime.prss_share_random(GF256)
                    c_trial = self.runtime.open((byte + b) * r_trial)
                    c_trial.addCallback(get_masked_byte, r_trial,
                                        c, r, byte)
                else:
                    r_related.addCallback(r.callback)
                    c.callback(~c_opened)

            get_masked_byte(0, None, c, r, byte)

            # necessary to avoid communication in multiplication
            # was: return c * r - b
            result = gather_shares([c, r, b])
            result.addCallback(lambda (c, r, b): c * r - b)
            return result

        def invert_by_exponentiation(byte):
            byte_2 = byte * byte
            byte_3 = byte_2 * byte
            byte_6 = byte_3 * byte_3
            byte_12 = byte_6 * byte_6
            byte_15 = byte_12 * byte_3
            byte_30 = byte_15 * byte_15
            byte_60 = byte_30 * byte_30
            byte_63 = byte_60 * byte_3
            byte_126 = byte_63 * byte_63
            byte_252 = byte_126 * byte_126
            byte_254 = byte_252 * byte_2
            return byte_254

        if (self.use_exponentiation):
            invert = invert_by_exponentiation
        else:
            invert = invert_by_masking

        for h in range(len(state)):
            row = state[h]
            
            for i in range(len(row)):
                bits = bit_decompose(invert(row[i]))

                # include the translation in the matrix multiplication
                # (see definition of AES.A)
                bits.append(GF256(1))

                if (use_lin_comb):
                    bits = [self.runtime.lin_comb(AES.A.rows[j], bits) 
                            for j in range(len(bits) - 1)]
                    row[i] = self.runtime.lin_comb(
                        [2**j for j in range(len(bits))], bits)
                else:
                    # caution: order is lsb first
                    vector = AES.A * Matrix(zip(bits))
                    bits = zip(*vector.rows)[0]
                    row[i] = reduce(lambda x,y: x + y, 
                                    [bits[j] * 2**j for j in range(len(bits))])

    def shift_row(self, state):
        """Rijndael ShiftRow.

        State should be a list of 4 rows."""

        assert len(state) == 4, "Wrong state size."

        if self.n_b in [4,6]:
            offsets = [0, 1, 2, 3]
        else:
            offsets = [0, 1, 3, 4]

        for i, row in enumerate(state):
            for j in range(offsets[i]):
                row.append(row.pop(0))

    # matrix for mix_column
    C = [[2, 3, 1, 1],
         [1, 2, 3, 1],
         [1, 1, 2, 3],
         [3, 1, 1, 2]]

    for row in C:
        for i in xrange(len(row)):
            row[i] = GF256(row[i])

    C = Matrix(C)

    def mix_column(self, state, use_lin_comb=True):
        """Rijndael MixColumn.

        Input should be a list of 4 rows."""

        assert len(state) == 4, "Wrong state size."

        if (use_lin_comb):
            columns = zip(*state)

            for i, row in enumerate(state):
                row[:] = [self.runtime.lin_comb(AES.C.rows[i], column)
                          for column in columns]
        else:
            state[:] = (AES.C * Matrix(state)).rows

    def add_round_key(self, state, round_key):
        """Rijndael AddRoundKey.

        State should be a list of 4 rows and round_key a list of
        4-byte columns (words)."""

        assert len(round_key) == self.n_b, "Wrong key size."
        assert len(round_key[0]) == 4, "Key must consist of 4-byte words."

        state[:] = (Matrix(state) + Matrix(zip(*round_key))).rows

    def key_expansion(self, key):
        """Rijndael key expansion.

        Input and output are lists of 4-byte columns (words)."""

        assert len(key) == self.n_k, "Wrong key size."
        assert len(key[0]) == 4, "Key must consist of 4-byte words."

        expanded_key = list(key)

        for i in xrange(self.n_k, self.n_b * (self.rounds + 1)):
            temp = list(expanded_key[i - 1])

            if (i % self.n_k == 0):
                temp.append(temp.pop(0))
                self.byte_sub([temp])
                temp[0] += GF256(2) ** (i / self.n_k - 1)
            elif (self.n_k > 6 and i % self.n_k == 4):
                self.byte_sub([temp])

            new_word = []

            for j in xrange(4):
                new_word.append(expanded_key[i - self.n_k][j] + temp[j])

            expanded_key.append(new_word)

        return expanded_key

    def preprocess(self, input):
        if (isinstance(input, str)):
            return [Share(self.runtime, GF256, GF256(ord(c))) 
                    for c in input]
        else:
            for byte in input:
                assert byte.field == GF256, \
                    "Input must be a list of GF256 elements " \
                    "or of shares thereof."
            return input

    def encrypt(self, cleartext, key, benchmark=False):
        """Rijndael encryption.

        Cleartext and key should be either a string or a list of bytes 
        (possibly shared as elements of GF256)."""

        start = time.time()

        assert len(cleartext) == 4 * self.n_b, "Wrong length of cleartext."
        assert len(key) == 4 * self.n_k, "Wrong length of key."

        cleartext = self.preprocess(cleartext)
        key = self.preprocess(key)

        state = [cleartext[i::4] for i in xrange(4)]
        key = [key[4*i:4*i+4] for i in xrange(self.n_k)]

        if (benchmark):
            global preparation, communication
            preparation = 0
            communication = 0

            def progress(x, i, start_round):
                time_diff = time.time() - start_round
                global communication
                communication += time_diff
                print "Round %2d: %f, %f" % \
                    (i, time_diff, time.time() - start)
                return x

            def prep_progress(i, start_round):
                time_diff = time.time() - start_round
                global preparation
                preparation += time_diff
                print "Round %2d preparation: %f, %f" % \
                    (i, time_diff, time.time() - start)
        else:
            progress = lambda x, i, start_round: x
            prep_progress = lambda i, start_round: None

        expanded_key = self.key_expansion(key)

        self.add_round_key(state, expanded_key[0:self.n_b])

        prep_progress(0, start)

        def get_trigger(state):
            return state[3][self.n_b-1]

        def get_last(state):
            return state[3][self.n_b-1]

        def round(_, state, i):
            start_round = time.time()
            
            self.byte_sub(state)
            self.shift_row(state)
            self.mix_column(state)
            self.add_round_key(state, expanded_key[i*self.n_b:(i+1)*self.n_b])

            get_last(state).addCallback(progress, i, time.time())

            if (i < self.rounds - 1):
                get_trigger(state).addCallback(round, state, i + 1)
            else:
                get_trigger(state).addCallback(final_round, state)

            prep_progress(i, start_round)

            return _

        def final_round(_, state):
            start_round = time.time()

            self.byte_sub(state)
            self.shift_row(state)
            self.add_round_key(state, expanded_key[self.rounds*self.n_b:])

            get_last(state).addCallback(progress, self.rounds, time.time())

            get_trigger(state).addCallback(finish, state)

            prep_progress(self.rounds, start_round)

            return _

        def finish(_, state):
            actual_result = [byte for word in zip(*state) for byte in word]

            for a, b in zip(actual_result, result):
                a.addCallback(b.callback)

            if (benchmark):
                print "Total preparation time: %f" % preparation
                print "Total communication time: %f" % communication

            return _

        round(None, state, 1)

        result = [Share(self.runtime, GF256) for i in xrange(4 * self.n_b)]
        return result
