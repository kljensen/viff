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

        AES(runtime, key_size, block_size), whereas keys ize and block
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
        of GF(2^8) or shares thereof with 4 rows and block_size / 32
        elements."""

        assert len(state) == 4, "State must have 4 rows."
        assert len(state[0]) == self.n_b, "State must have block_size / 32 columns"

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

                r = self.runtime.prss_share_random(GF256)
                c = self.runtime.open((byte + b) * r)
                
                c.addCallback(lambda c: ~c)
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
        if self.n_b in [4,6]:
            offsets = [0, 1, 2, 3]
        else:
            offsets = [0, 1, 3, 4]

        for i, row in enumerate(state):
            for j in range(offsets[i]):
                row.append(row.pop(0))

    
