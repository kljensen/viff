# Copyright 2007, 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

"""Tests for viff.prss."""

from viff.prss import generate_subsets

from twisted.trial.unittest import TestCase

#: Declare doctests for Trial.
__doctests__ = ['viff.prss']


class PRSSTestCase(TestCase):

    def test_generate_subsets(self):
        """Test subset generation.

        All possible subsets of all possible sizes are generated and
        it is verified that they have the correct size and that they
        can be combined to yield the original set.
        """

        def binom(n, k):
            """Binomial coefficient."""

            def fac(n):
                """Factorial."""
                if n > 1:
                    return n * fac(n-1)
                else:
                    return 1

            return fac(n) // (fac(k) * fac(n-k))

        # Maximum size of sets to test. The running time grows quite
        # rapidly, so this should not be too big.
        max_size = 6

        for size in range(max_size):
            set = frozenset(range(size))

            for sub_size in range(max_size):
                subsets = generate_subsets(set, sub_size)

                if sub_size > size:
                    self.assertEquals(len(subsets), 0)
                else:
                    self.assertEquals(len(subsets), binom(len(set), sub_size))

                    union = reduce(lambda a, b: a | b, subsets)
                    if sub_size == 0:
                        self.assertEquals(frozenset([]), union)
                    else:
                        self.assertEquals(set, union)
