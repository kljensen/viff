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

"""MPC implementation of AES (Rijndael)."""

__docformat__ = "restructuredtext"


from viff.field import GF256
from viff.runtime import Share
from viff.matrix import Matrix


def bit_decompose(share):
    """Bit decomposition for GF256 shares."""

    assert isinstance(share, Share) and share.field == GF256, \
        "Parameter must be GF256 share."

    r_bits = [share.runtime.prss_share_random(GF256, binary=True) \
                  for i in range(8)]
    r = reduce(lambda x,y: x + y, [r_bits[i] * 2 ** i for i in range(8)])
    
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
    def __init__(self, runtime, key_size, block_size=128):
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

    def byte_sub(self, state):
        """ByteSub operation of Rijndael.

        The first argument should be a matrix consisting of elements
        of GF(2^8)."""

        for h in range(len(state)):
            row = state[h]
            
            for i in range(len(row)):
                byte = row[i]
                bits = bit_decompose(byte)

                for j in range(len(bits)):
                    bits[j] = 1 - bits[j]

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
                inverted_byte = c * r - b

                bits = bit_decompose(inverted_byte)

                A = Matrix([[1,0,0,0,1,1,1,1],
                            [1,1,0,0,0,1,1,1],
                            [1,1,1,0,0,0,1,1],
                            [1,1,1,1,0,0,0,1],
                            [1,1,1,1,1,0,0,0],
                            [0,1,1,1,1,1,0,0],
                            [0,0,1,1,1,1,1,0],
                            [0,0,0,1,1,1,1,1]])

                # caution: order is lsb first
                vector = A * Matrix(zip(bits)) + Matrix(zip([1,1,0,0,0,1,1,0]))
                bits = zip(*vector.rows)[0]

                row[i] = reduce(lambda x,y: x + y, 
                                [bits[j] * 2**j for j in range(len(bits))])

    def shift_row(self, state):
        """AES ShiftRow.

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

    def mix_column(self, state):
        """Rijndael MixColumn.

        Input should be a list of 4 rows."""

        assert len(state) == 4, "Wrong state size."

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

    def encrypt(self, cleartext, key):
        """Rijndael encryption.

        Cleartext and key should be either a string or a list of bytes 
        (possibly shared as elements of GF256)."""

        assert len(cleartext) == 4 * self.n_b, "Wrong length of cleartext."
        assert len(key) == 4 * self.n_k, "Wrong length of key."

        cleartext = self.preprocess(cleartext)
        key = self.preprocess(key)

        state = [cleartext[i::4] for i in xrange(4)]
        key = [key[4*i:4*i+4] for i in xrange(self.n_k)]

        expanded_key = self.key_expansion(key)

        self.add_round_key(state, expanded_key[0:self.n_b])

        for i in xrange(1, self.rounds):
            self.byte_sub(state)
            self.shift_row(state)
            self.mix_column(state)
            self.add_round_key(state, expanded_key[i*self.n_b:(i+1)*self.n_b])

        self.byte_sub(state)
        self.shift_row(state)
        self.add_round_key(state, expanded_key[self.rounds*self.n_b:])

        return [byte for word in zip(*state) for byte in word]
