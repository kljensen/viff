# Copyright 2007, 2008 VIFF Development Team.
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

"""Tests for viff.field."""

from viff.field import GF, GF256

from twisted.trial.unittest import TestCase
import operator

#: Declare doctests for Trial.
__doctests__ = ['viff.field']


class GFpElementTest(TestCase):
    """Tests for elements from a Zp field."""

    def setUp(self):
        """Initialize Zp to Z31."""
        self.field = GF(31)

    def test_field(self):
        """Test field attribute."""
        self.assertIdentical(self.field.field, self.field)
        self.assertIdentical(self.field(100).field, self.field)

    def _test_binary_operator(self, operation, a, b, expected):
        """Test C{operation} with and without coerced operands."""
        result = operation(self.field(a), self.field(b))
        self.assertEquals(result, self.field(expected))

        result = operation(self.field(a), b)
        self.assertEquals(result, self.field(expected))

        result = operation(a, self.field(b))
        self.assertEquals(result, self.field(expected))

    def test_add(self):
        """Test addition."""
        self._test_binary_operator(operator.add, 5, 0, 5)
        self._test_binary_operator(operator.add, 5, 3, 8)
        self._test_binary_operator(operator.add, 5, 30, 4)

    def test_sub(self):
        """Test subtraction."""
        self._test_binary_operator(operator.sub, 5, 0, 5)
        self._test_binary_operator(operator.sub, 5, 3, 2)
        self._test_binary_operator(operator.sub, 5, 10, 26)

    def test_mul(self):
        """Test multiplication."""
        self._test_binary_operator(operator.mul, 5, 0, 0)
        self._test_binary_operator(operator.mul, 5, 1, 5)
        self._test_binary_operator(operator.mul, 5, 4, 20)
        self._test_binary_operator(operator.mul, 5, 8, 9)

    def test_div(self):
        """Test division, including division by zero."""
        self.assertRaises(ZeroDivisionError, operator.div,
                          self.field(10), self.field(0))

        self.assertEquals(self.field(10) / self.field(10),
                          self.field(1))
        self.assertEquals(self.field(10) / self.field(9),
                          self.field(8))
        self.assertEquals(self.field(10) / self.field(5),
                          self.field(2))

        self.assertEquals(10 / self.field(5),
                          self.field(2))

    def test_invert(self):
        """Test inverse operation, including inverting zero."""
        self.assertRaises(ZeroDivisionError, lambda: ~self.field(0))
        self.assertEquals(~self.field(1), self.field(1))

    def test_neg(self):
        """Test negation."""
        self.assertEquals(-self.field(10), self.field(21))
        self.assertEquals(-self.field(10), self.field(-10))

    def test_sqrt(self):
        """Test extraction of square roots."""
        square = self.field(4)**2
        root = square.sqrt()
        self.assertEquals(root**2, square)

        square = self.field(5)**2
        root = square.sqrt()
        self.assertEquals(root**2, square)

        square = self.field(6)**2
        root = square.sqrt()
        self.assertEquals(root**2, square)

    def test_bit(self):
        """Test bit extraction."""
        a = self.field(14)
        self.assertEquals(a.bit(0), 0)
        self.assertEquals(a.bit(1), 1)
        self.assertEquals(a.bit(2), 1)
        self.assertEquals(a.bit(3), 1)
        self.assertEquals(a.bit(4), 0)
        self.assertEquals(a.bit(5), 0)
        self.assertEquals(a.bit(6), 0)
        self.assertEquals(a.bit(100), 0)

# TODO: figure out how to use the todo attribute correctly. Update
# this if and when __repr__ return the proper string
#    def test_repr(self):
#        self.assertEquals(repr(IntegerFieldElement(0)),
#                          "IntegerFieldElement(0)")
#        self.assertEquals(repr(IntegerFieldElement(1)),
#                          "IntegerFieldElement(1)")
#        self.assertEquals(repr(IntegerFieldElement(10)),
#                          "IntegerFieldElement(10)")

    def test_str(self):
        """Test string conversion."""
        self.assertEquals(str(self.field(0)), "{0}")
        self.assertEquals(str(self.field(1)), "{1}")
        self.assertEquals(str(self.field(10)), "{10}")


class GF256Test(TestCase):
    """Tests for elements from the GF256 field."""

    def test_construct(self):
        """Test overflows in constructor."""
        self.assertEquals(GF256(256), GF256(0))
        self.assertEquals(GF256(257), GF256(1))

    def test_field(self):
        """Test field attribute."""
        self.assertIdentical(GF256.field, GF256)
        self.assertIdentical(GF256(10).field, GF256)

    def _test_binary_operator(self, operation, a, b, expected):
        """Test C{operation} with and without coerced operands."""
        result = operation(GF256(a), GF256(b))
        self.assertEquals(result, GF256(expected))

        result = operation(GF256(a), b)
        self.assertEquals(result, GF256(expected))

        result = operation(a, GF256(b))
        self.assertEquals(result, GF256(expected))

    def test_add(self):
        """Test addition."""
        self._test_binary_operator(operator.add, 0, 0, 0)
        self._test_binary_operator(operator.add, 1, 1, 0)
        self._test_binary_operator(operator.add, 100, 100, 0)
        self._test_binary_operator(operator.add, 0, 1, 1)
        self._test_binary_operator(operator.add, 1, 2, 3)

        a = GF256(10)
        a += GF256(10)
        self.assertEquals(a, GF256(0))

    def test_sub(self):
        """Test subtraction."""
        self._test_binary_operator(operator.sub, 0, 0, 0)
        self._test_binary_operator(operator.sub, 1, 1, 0)
        self._test_binary_operator(operator.sub, 100, 100, 0)
        self._test_binary_operator(operator.sub, 0, 1, 1)
        self._test_binary_operator(operator.sub, 1, 2, 3)

    def test_xor(self):
        """Test exclusive-or."""
        self._test_binary_operator(operator.xor, 0, 0, 0)
        self._test_binary_operator(operator.xor, 0, 1, 1)
        self._test_binary_operator(operator.xor, 1, 0, 1)
        self._test_binary_operator(operator.xor, 1, 1, 0)

    def test_mul(self):
        """Test multiplication."""
        self._test_binary_operator(operator.mul, 0, 47, 0)
        self._test_binary_operator(operator.mul, 2, 3, 6)
        self._test_binary_operator(operator.mul, 16, 32, 54)

    def test_div(self):
        """Test division, including division by zero."""
        self.assertRaises(ZeroDivisionError, lambda: GF256(10) / GF256(0))

        self.assertEquals(GF256(10) / GF256(10), GF256(1))
        self.assertEquals(GF256(10) / GF256(9), GF256(208))
        self.assertEquals(GF256(10) / GF256(5), GF256(2))

        self.assertEquals(10 / GF256(5), GF256(2))

    def test_pow(self):
        """Test exponentiation."""
        self.assertEquals(GF256(3)**3, GF256(3) * GF256(3) * GF256(3))
        self.assertEquals(GF256(27)**100, GF256(27)**50 * GF256(27)**50)

    def test_invert(self):
        """Test inverse operation, including inverting zero."""
        self.assertRaises(ZeroDivisionError, lambda: ~GF256(0))
        self.assertEquals(~GF256(1), GF256(1))

    def test_neg(self):
        """Test negation."""
        self.assertEquals(-GF256(0), GF256(0))
        self.assertEquals(-GF256(10), GF256(10))
        self.assertEquals(-GF256(100), GF256(100))

#    def test_repr(self):
#        self.assertEquals(repr(GF256(0)), "GF256(0)")
#        self.assertEquals(repr(GF256(1)), "GF256(1)")
#        self.assertEquals(repr(GF256(10)), "GF256(10)")

    def test_str(self):
        """Test string conversion."""
        self.assertEquals(str(GF256(0)), "[0]")
        self.assertEquals(str(GF256(1)), "[1]")
        self.assertEquals(str(GF256(10)), "[10]")
