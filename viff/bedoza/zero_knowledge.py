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


class ZKProof(object):
    """Protocol proving that a player's plaintexts are of limited size.
    
    This is a zero-knowledge protocol in which player player_id inputs s
    ciphertexts c[i] = E(x[j], r[j]), i = 1, ..., s, created using the
    modified Paillier cipher and proves to the other players that the x[i]'s
    are of limited size, e.g. that abs(x[i]) <= 2**k.
    
    Zn is the plaintext field of player player_id's modified Paillier cipher.
    
    While player player_id must input the ciphertexts, the other players
    should call the method with c = None.
    
    """
    
    def __init__(self, player_id, Zn, c=None):
        self.player_id = player_id
        self.Zn = Zn
        self.c = c
        self.e = None

    def start():
        
        pass

    def _set_e(self, e):
        self.e = e
        self.s = len(e)
        self.m = 2 * len(e) - 1

    def _generate_challenge(self):
        # TODO: Implement.
        self.e = [0, 0, 1, 0, 1]
        self.s = len(e)
        self.m = 2 * len(e) - 1


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

    def vec_add(self, x, y):
        return [xi + yi for x, y in zip(x,y)]
    
    def vec_mul(self, x, y):
        return [xi * yi for x, y in zip(x,y)]

    def vec_pow_E(self, y):
        """Computes and returns the m := 2s-1 length vector y**E."""
        assert self.s == len(y), \
            "not same length: %d != %d" % (self.s, len(y))
        res = [self.Zn(1)] * self.m
        for j in range(2 * self.s - 1):
            for i in range(self.s):
                if self._E(j, i) == 1:
                    res[j] *= y[i]
        return res
