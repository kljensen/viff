# Copyright 2007 Martin Geisler
#
# This file is part of VIFF
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

"""Modeling of fields.

The GF function creates Galois fields (finite fields) whereas the
GF256 class models elements from the GF(2^8) field.
"""

from gmpy import mpz

class FieldElement(object):
    """Common base class for elements."""


_log_table = {}
_exp_table = {}
_inv_table = {}

def _generate_tables():
    """Generate tables with logarithms, exponentials and inverses.

    Code adapted from http://www.samiam.org/galois.html.
    """
    a = 1
    for c in range(255):
        a &= 0xff
        _exp_table[c] = a
        d = a & 0x80
        a <<= 1
        if d == 0x80:
            a ^= 0x1b
        a ^= _exp_table[c]
        _log_table[_exp_table[c]] = c
    _exp_table[255] = _exp_table[0]
    _log_table[0] = 0

    #_inv_table[0] = 0
    for c in range(1, 255):
        _inv_table[c] = _exp_table[255 - _log_table[c]]

_generate_tables()

# The class name is slightly wrong since the class instances cannot be
# said to be represent a field. Instead they represent instances of
# GF256 elements. But the shorter name is better, though, in the
# common case where one talks about the class as a field.
class GF256(FieldElement):
    """Models an element of the GF(2^8) field."""

    modulus = 256

    def __init__(self, value):
        self.value = value % self.modulus

    def field(self, value):
        return GF256(value)

    def __add__(self, other):
        """Add this and another GF256.

        >>> GF256(0x01) + GF256(0x01)
        [0]
        >>> GF256(0x01) + GF256(0x02)
        [3]

        Adding integers works too, the other operand is coerced into a
        GF256 element automatically:

        >>> GF256(0x01) + 1
        [0]
        """
        if isinstance(other, GF256):
            other = other.value
        return GF256(self.value ^ other)

    __radd__ = __add__
    __sub__ = __add__
    __rsub__ = __sub__

    def __mul__(self, other):
        """Multiply this and another GF256.

        >>> GF256(0) * GF256(47)
        [0]
        >>> GF256(2) * GF256(3)
        [6]
        >>> GF256(16) * GF256(32)
        [54]
        """
        if isinstance(other, GF256):
            other = other.value
        if self.value == 0 or other == 0:
            return GF256(0)
        else:
            log_product = (_log_table[self.value] + _log_table[other]) % 255
            return GF256(_exp_table[log_product])

    __rmul__ = __mul__

    def __pow__(self, exponent):
        result = GF256(1)
        for _ in range(exponent):
            result *= self
        return result

    def __div__(self, other):
        return self * ~other

    def __rdiv__(self, other):
        return GF256(other) / self

    def __neg__(self):
        return self

    def __invert__(self):
        if self.value == 0:
            raise ZeroDivisionError, "Cannot invert zero"
        return GF256(_inv_table[self.value])

    def __repr__(self):
        return "[%d]" % self.value
        #return "GF256(%d)" % self.value

    def __str__(self):
        return "[%d]" % self.value

    def __eq__(self, other):
        if isinstance(other, GF256):
            other = other.value
        return self.value == other


# Calls to GF with identical modulus must return the same class
# (field), so we cache them here. The cache is seeded with the
# GF256 class which is always defined.
_field_cache = {256: GF256}

def GF(modulus):
    """Generate a Galois (finite) field with the given modulus.

    The modulus must be a Blum prime.

    >>> Z23 = GF(23) # works
    >>> Z10 = GF(10) # not a prime
    Traceback (most recent call last):
        ...
    ValueError: 10 is not a prime

    #>>> Z17 = GF(17) # not a Blum prime
    #Traceback (most recent call last):
    #    ...
    #ValueError: 17 is not a Blum prime

    A modulus of 256 is special since it returns the GF(2^8) field
    even though 256 is no prime:

    >>> GF256 = GF(256)
    >>> print GF256(1)
    [1]
    """
    if modulus in _field_cache:
        return _field_cache[modulus]

    if not mpz(modulus).is_prime():
        raise ValueError, "%d is not a prime" % modulus

    # TODO: to Blum or not to Blum, that is the question...
    #if not modulus % 4 == 3:
    #    raise ValueError, "%d is not a Blum prime" % modulus

    # Define a new class representing the field. This class will be
    # returned at the end of the function.
    class GFElement(FieldElement):
        def __init__(self, value):
            self.value = value % self.modulus

        def __add__(self, other):
            """Addition."""
            try:
                # We can do a quick test using 'is' here since
                # there will only be one class representing this
                # field.
                assert self.field is other.field
                return GFElement(self.value + other.value)
            except AttributeError:
                return GFElement(self.value + other)

        __radd__ = __add__

        def __sub__(self, other):
            """Subtraction."""
            try:
                assert self.field is other.field
                return GFElement(self.value - other.value)
            except AttributeError:
                return GFElement(self.value - other)

        def __rsub__(self, other):
            """Subtraction (reflected argument version)."""
            return GFElement(other - self.value)

        def __mul__(self, other):
            """Multiplication."""
            try:
                assert self.field is other.field
                return GFElement(self.value * other.value)
            except AttributeError:
                return GFElement(self.value * other)

        __rmul__ = __mul__

        def __pow__(self, exponent):
            """Exponentiation."""
            return GFElement(pow(self.value, exponent, self.modulus))

        def __neg__(self):
            """Negation."""
            return GFElement(-self.value)

        def __invert__(self):
            """Inversion.

            Note that zero cannot be inverted, trying to do so
            will raise a ZeroDivisionError.
            """
            if self.value == 0:
                raise ZeroDivisionError, "Cannot invert zero"

            def extended_gcd(a, b):
                """The extended Euclidean algorithm."""
                x = 0
                lastx = 1
                y = 1
                lasty = 0
                while b != 0:
                    quotient = a // b
                    a, b = b, a % b
                    x, lastx = lastx - quotient*x, x
                    y, lasty = lasty - quotient*y, y
                return (lastx, lasty, a)

            inverse = extended_gcd(self.value, self.modulus)[0]
            return GFElement(inverse)

        def __div__(self, other):
            """Division."""
            try:
                assert self.field is other.field
                return self * ~other
            except AttributeError:
                return self * ~GFElement(other)

        def __rdiv__(self, other):
            """Division (reflected argument version)."""
            return GFElement(other) / self

        def sqrt(self):
            """Square root.

            No attempt is made the to return the positive square
            root.
            """
            assert self.modulus % 4 == 3, "Cannot conpute square " \
                   "root of %s with modulus %s" % (self, self.modulus)

            # Because we assert that the modulus is a Blum prime
            # (congruent to 3 mod 4), there will be no reminder in the
            # division below.
            root = pow(self.value, (self.modulus+1)//4, self.modulus)
            return GFElement(root)

        def bit(self, index):
            """Extract a bit (index is counted from zero)."""
            return (self.value >> index) & 1

        def __repr__(self):
            return "{%d}" % self.value
            #return "GFElement(%d)" % self.value

        def __str__(self):
            """Informal string representation.

            This is simply the value enclosed in curly braces.
            """
            return "{%d}" % self.value

        def __eq__(self, other):
            """Equality test."""
            try:
                assert self.field is other.field
                return self.value == other.value
            except AttributeError:
                return self.value == other

        def __cmp__(self, other):
            """Comparison."""
            try:
                assert self.field is other.field
                return cmp(self.value, other.value)
            except AttributeError:
                return cmp(self.value, other)

        def __hash__(self):
            """Hash value."""
            return hash((self.field, self.value))

    GFElement.modulus = modulus
    GFElement.field = GFElement

    _field_cache[modulus] = GFElement
    return GFElement


if __name__ == "__main__":
    import doctest
    doctest.testmod()
