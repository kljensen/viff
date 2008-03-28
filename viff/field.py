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

"""Modeling of Galois (finite) fields.

The GF function creates classes which implements Galois (finite)
fields of prime order whereas the GF256 class implements the the
GF(2^8) field with characteristic 2.

All fields work the same: instantiate an object from a field to get
hold of an element of that field. Elements implement the normal
arithmetic one would expect: addition, multiplication, etc.

Defining a field:

>>> Zp = GF(19)

Defining field elements:

>>> x = Zp(10)
>>> y = Zp(15)

Addition and subtraction (with modulo reduction):

>>> x + y
{6}
>>> x - y
{14}

Exponentiation:

>>> x**3
{12}

Square roots can be found for elements based on GF fields with a Blum
prime modulus (see L{GF} for more information):

>>> x.sqrt()
{3}

Field elements from different fields cannot be mixed, you will get a
type error if you try:

>>> Zq = GF(17)
>>> z = Zq(2)
>>> x + z
Traceback (most recent call last):
    ...
TypeError: unsupported operand type(s) for +: 'GFElement' and 'GFElement'

The reason for the slightly confusing error message is that C{x} and
C{z} are instances of two I{different} classes called C{GFElement}.
"""

from gmpy import mpz


class FieldElement(object):
    """Common base class for elements."""


#: Logarithm table.
#:
#: Maps a value M{x} to M{log3(x)}. See L{_generate_tables}.
_log_table = {}
#: Exponentiation table.
#:
#: Maps a value M{y} to M{3^y}. See L{_generate_tables}.
_exp_table = {}
#: Inversion table.
#:
#: Maps a value M{x} to M{x^-1}. See L{_generate_tables}.
_inv_table = {}


def _generate_tables():
    """Generate tables with logarithms, antilogarithms (exponentials)
    and inverses.

    This updates the L{_log_table}, L{_exp_table}, and L{_inv_table}
    fields. The generator used is 0x03.

    Code adapted from U{http://www.samiam.org/galois.html}.
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

    modulus = 256 #: GF(2^8) modulus, always 256.

    def __init__(self, value):
        """Initialize new element.

        The value given is modulo reduced so the following holds:

        >>> GF256(1) == GF256(257)
        True
        """
        self.value = value % self.modulus

    def __add__(self, other):
        """Add this and another GF256 element.

        >>> GF256(0x01) + GF256(0x01)
        [0]
        >>> GF256(0x01) + GF256(0x02)
        [3]

        Adding integers works too, the other operand is coerced into a
        GF256 element automatically:

        >>> GF256(0x01) + 1
        [0]
        """
        if not isinstance(other, (GF256, int, long)):
            # This occurs with code like 'a + b' where b is a Share.
            # In that case we must return NotImplemented to signal
            # that b.__radd__(a) should be run instead. The Share will
            # then schedule things correctly.
            return NotImplemented
        if isinstance(other, GF256):
            other = other.value
        return GF256(self.value ^ other)

    #: Add this and another GF256 element (reflected argument version).
    __radd__ = __add__

    #: Subtract this and another GF256 element.
    #:
    #: Addition is its own inverse in GF(2^8) and so this is the same
    #: as L{__add__}.
    __sub__ = __add__
    #: Subtract this and another GF256 element (reflected argument version).
    __rsub__ = __sub__

    #: Exclusive-or.
    #:
    #: This is just addition for GF256 elements.
    __xor__ = __add__

    #: Exclusive-or (reflected argument version).
    __rxor__ = __xor__

    def __mul__(self, other):
        """Multiply this and another GF256.

        >>> GF256(0) * GF256(47)
        [0]
        >>> GF256(2) * GF256(3)
        [6]
        >>> GF256(16) * GF256(32)
        [54]
        """
        if not isinstance(other, (GF256, int, long)):
            return NotImplemented
        if isinstance(other, GF256):
            other = other.value
        if self.value == 0 or other == 0:
            return GF256(0)
        else:
            log_product = (_log_table[self.value] + _log_table[other]) % 255
            return GF256(_exp_table[log_product])


    #: Multiply this and another GF256 element (reflected argument version).
    __rmul__ = __mul__

    def __pow__(self, exponent):
        """Exponentiation."""
        result = GF256(1)
        for _ in range(exponent):
            result *= self
        return result

    def __div__(self, other):
        """Division.

        @param other: right-hand side.
        @type other: GF256 element
        """
        return self * ~other

    __truediv__ = __div__

    def __rdiv__(self, other):
        """Division (reflected argument version).

        @param other: the left-hand side.
        @type other: integer
        """
        return GF256(other) / self

    __rtruediv__ = __rdiv__

    def __neg__(self):
        """Negation."""
        return self

    def __invert__(self):
        """Invertion.

        @raise ZeroDivisionError: if trying to inverse the zero
        element.
        """
        if self.value == 0:
            raise ZeroDivisionError("Cannot invert zero")
        return GF256(_inv_table[self.value])

    def __repr__(self):
        return "[%d]" % self.value
        #return "GF256(%d)" % self.value

    def __str__(self):
        return "[%d]" % self.value

    def __eq__(self, other):
        """Equality testing.

        Testing for equality with integers works as expected:

        >>> GF256(10) == 10
        True
        """
        if isinstance(other, GF256):
            other = other.value
        return self.value == other

    def __hash__(self):
        """Hash value."""
        return hash((self.field, self.value))

    def __nonzero__(self):
        """Truth value testing.

        Returns False if this element is zero, True otherwise. This
        allows GF256 elements to be used directly in Boolean formula:

        >>> bool(GF256(0))
        False
        >>> bool(GF256(1))
        True
        >>> x = GF256(1)
        >>> not x
        False
        """
        return self.value != 0

# We provide the class here to make the construction of new elements
# easy in a polymorphic context.
GF256.field = GF256


#: Cached fields.
#:
#: Calls to GF with identical modulus must return the same class
#: (field), so we cache them here. The cache is seeded with the
#: GF256 class which is always defined.
_field_cache = {256: GF256}


def GF(modulus):
    """Generate a Galois (finite) field with the given modulus.

    The modulus must be a prime:

    >>> Z23 = GF(23) # works
    >>> Z10 = GF(10) # not a prime
    Traceback (most recent call last):
        ...
    ValueError: 10 is not a prime

    A modulus of 256 is special since it returns the GF(2^8) field
    even though 256 is no prime:

    >>> GF256 = GF(256)
    >>> print GF256(1)
    [1]

    Please note, that if you wish to calculate square roots, the
    modulus must be a Blum prime (congruent to 3 mod 4):

    >>> Z17 = GF(17) # 17 % 4 == 1, so 17 is no Blum prime
    >>> x = Z17(10)
    >>> x.sqrt()
    Traceback (most recent call last):
        ...
    AssertionError: Cannot compute square root of {10} with modulus 17
    """
    if modulus in _field_cache:
        return _field_cache[modulus]

    if not mpz(modulus).is_prime():
        raise ValueError("%d is not a prime" % modulus)

    # Define a new class representing the field. This class will be
    # returned at the end of the function.
    class GFElement(FieldElement):

        def __init__(self, value):
            self.value = value % self.modulus

        def __add__(self, other):
            """Addition."""
            if not isinstance(other, (GFElement, int, long)):
                return NotImplemented
            try:
                # We can do a quick test using 'is' here since
                # there will only be one class representing this
                # field.
                assert self.field is other.field, "Fields must be identical"
                return GFElement(self.value + other.value)
            except AttributeError:
                return GFElement(self.value + other)

        __radd__ = __add__

        def __sub__(self, other):
            """Subtraction."""
            if not isinstance(other, (GFElement, int, long)):
                return NotImplemented
            try:
                assert self.field is other.field, "Fields must be identical"
                return GFElement(self.value - other.value)
            except AttributeError:
                return GFElement(self.value - other)

        def __rsub__(self, other):
            """Subtraction (reflected argument version)."""
            return GFElement(other - self.value)

        def __mul__(self, other):
            """Multiplication."""
            if not isinstance(other, (GFElement, int, long)):
                return NotImplemented
            try:
                assert self.field is other.field, "Fields must be identical"
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
                raise ZeroDivisionError("Cannot invert zero")

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
                assert self.field is other.field, "Fields must be identical"
                return self * ~other
            except AttributeError:
                return self * ~GFElement(other)

        __truediv__ = __div__

        def __rdiv__(self, other):
            """Division (reflected argument version)."""
            return GFElement(other) / self

        __rtruediv__ = __rdiv__

        def sqrt(self):
            """Square root.

            No attempt is made the to return the positive square root.

            Computing square roots is only possible when the modulus
            is a Blum prime (congruent to 3 mod 4).
            """
            assert self.modulus % 4 == 3, "Cannot compute square " \
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
                assert self.field is other.field, "Fields must be identical"
                return self.value == other.value
            except AttributeError:
                return self.value == other

        def __cmp__(self, other):
            """Comparison."""
            try:
                assert self.field is other.field, "Fields must be identical"
                return cmp(self.value, other.value)
            except AttributeError:
                return cmp(self.value, other)

        def __hash__(self):
            """Hash value."""
            return hash((self.field, self.value))

        def __nonzero__(self):
            """Truth value testing.

            Returns False if this element is zero, True otherwise.
            This allows GF elements to be used directly in Boolean
            formula:

            >>> bool(GF256(0))
            False
            >>> bool(GF256(1))
            True
            >>> x = GF256(1)
            >>> not x
            False
            """
            return self.value != 0

    GFElement.modulus = modulus
    GFElement.field = GFElement

    _field_cache[modulus] = GFElement
    return GFElement


if __name__ == "__main__":
    import doctest    #pragma NO COVER
    doctest.testmod() #pragma NO COVER
