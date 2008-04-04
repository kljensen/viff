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

#: Declare doctests for Trial.
__doctests__ = ['viff.matrix']

from viff.field import GF
from viff.matrix import Matrix, hyper
from viff.prss import generate_subsets
from twisted.trial.unittest import TestCase


class MatrixTest(TestCase):
    """Matrix tests."""

    def is_hyper(self, mat):
        """Checks if a square matrix is hyper-invertible.

        @param mat: A square matrix.
        @return: True if the matrix is hyper-invertible, otherwise False.
        """
        n = len(mat.rows)
        for size in range(1, n+1):
            subsets = generate_subsets(frozenset(range(n)), size)
            for rows in subsets:
                for columns in subsets:
                    sub = Matrix([[mat[r, c] for r in rows] for c in columns])
                    if sub.determinant() == 0:
                        return False
        return True

    def test_hyper(self):
        """Checks that a generated matrix is hyper-invertible."""
        Zp = GF(47)
        for i in range(1, 6):
            m = hyper(i, Zp)
            self.assertTrue(self.is_hyper(m))

    def test_not_hyper(self):
        """Check a non-hyper-invertible matrix."""
        Zp = GF(11)
        # This is an invertible matrix, but it is not hyper-invertible
        # since none of the three the upper 2x2 matrices are
        # invertible.
        m = Matrix([[Zp(2), Zp(3), Zp(4)],
                    [Zp(4), Zp(6), Zp(9)],
                    [Zp(3), Zp(5), Zp(8)]])
        self.assertFalse(self.is_hyper(m))
