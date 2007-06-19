

from pysmpc.field import IntegerFieldElement, GF256Element

from twisted.trial.unittest import TestCase, FailTest
import operator

# This will make Trial run the doctests too, in addition to the tests
# defined below.
__doctests__ = ['pysmpc.field']


class IntegerFieldElementTestCase(TestCase):

    def setUp(self):
        IntegerFieldElement.modulus = 31

    def test_construct(self):
        IntegerFieldElement.modulus = None
        self.assertRaises(ValueError, lambda: IntegerFieldElement(0))

    def _test_binary_operator(self, operation, a, b, expected):
        result = operation(IntegerFieldElement(a), IntegerFieldElement(b))
        self.assertEquals(result, IntegerFieldElement(expected))

        result = operation(IntegerFieldElement(a), b)
        self.assertEquals(result, IntegerFieldElement(expected))

        result = operation(a, IntegerFieldElement(b))
        self.assertEquals(result, IntegerFieldElement(expected))

    def test_add(self):
        self._test_binary_operator(operator.add, 5, 0, 5)
        self._test_binary_operator(operator.add, 5, 3, 8)
        self._test_binary_operator(operator.add, 5, 30, 4)

    def test_sub(self):
        self._test_binary_operator(operator.sub, 5, 0, 5)
        self._test_binary_operator(operator.sub, 5, 3, 2)
        self._test_binary_operator(operator.sub, 5, 10, 26)

    def test_mul(self):
        self._test_binary_operator(operator.mul, 5, 0, 0)
        self._test_binary_operator(operator.mul, 5, 1, 5)
        self._test_binary_operator(operator.mul, 5, 4, 20)
        self._test_binary_operator(operator.mul, 5, 8, 9)

    def test_div(self):
        self.assertRaises(ZeroDivisionError,
                          lambda: IntegerFieldElement(10) / IntegerFieldElement(0))

        self.assertEquals(IntegerFieldElement(10) / IntegerFieldElement(10),
                          IntegerFieldElement(1))
        self.assertEquals(IntegerFieldElement(10) / IntegerFieldElement(9),
                          IntegerFieldElement(8))
        self.assertEquals(IntegerFieldElement(10) / IntegerFieldElement(5),
                          IntegerFieldElement(2))

        self.assertEquals(10 / IntegerFieldElement(5),
                          IntegerFieldElement(2))

    def test_invert(self):
        self.assertRaises(ZeroDivisionError, lambda: ~IntegerFieldElement(0))
        self.assertEquals(~IntegerFieldElement(1), IntegerFieldElement(1))

    def test_neg(self):
        self.assertEquals(-IntegerFieldElement(10), IntegerFieldElement(21))
        self.assertEquals(-IntegerFieldElement(10), IntegerFieldElement(-10))

    def test_sqrt(self):
        square = IntegerFieldElement(4)**2
        root = square.sqrt()
        self.assertEquals(root**2, square)
        
        square = IntegerFieldElement(5)**2
        root = square.sqrt()
        self.assertEquals(root**2, square)
        
        square = IntegerFieldElement(6)**2
        root = square.sqrt()
        self.assertEquals(root**2, square)

    def test_bit(self):
        a = IntegerFieldElement(14)
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
#        self.assertEquals(repr(IntegerFieldElement(0)), "IntegerFieldElement(0)")
#        self.assertEquals(repr(IntegerFieldElement(1)), "IntegerFieldElement(1)")
#        self.assertEquals(repr(IntegerFieldElement(10)), "IntegerFieldElement(10)")
#    test_repr.todo = (FailTest, "'{0}' != 'IntegerFieldElement(0)'")

    def test_str(self):
        self.assertEquals(str(IntegerFieldElement(0)), "{0}")
        self.assertEquals(str(IntegerFieldElement(1)), "{1}")
        self.assertEquals(str(IntegerFieldElement(10)), "{10}")



class GF256ElementTestCase(TestCase):

    def test_construct(self):
        self.assertEquals(GF256Element(256), GF256Element(0))
        self.assertEquals(GF256Element(257), GF256Element(1))

    def _test_binary_operator(self, operation, a, b, expected):
        result = operation(GF256Element(a), GF256Element(b))
        self.assertEquals(result, GF256Element(expected))

        result = operation(GF256Element(a), b)
        self.assertEquals(result, GF256Element(expected))

        result = operation(a, GF256Element(b))
        self.assertEquals(result, GF256Element(expected))

    def test_add(self):
        self._test_binary_operator(operator.add, 0, 0, 0)
        self._test_binary_operator(operator.add, 1, 1, 0)
        self._test_binary_operator(operator.add, 100, 100, 0)
        self._test_binary_operator(operator.add, 0, 1, 1)
        self._test_binary_operator(operator.add, 1, 2, 3)

        a = GF256Element(10)
        a += GF256Element(10)
        self.assertEquals(a, GF256Element(0))

    def test_sub(self):
        self._test_binary_operator(operator.sub, 0, 0, 0)
        self._test_binary_operator(operator.sub, 1, 1, 0)
        self._test_binary_operator(operator.sub, 100, 100, 0)
        self._test_binary_operator(operator.sub, 0, 1, 1)
        self._test_binary_operator(operator.sub, 1, 2, 3)

    def test_mul(self):
        self._test_binary_operator(operator.mul, 0, 47, 0)
        self._test_binary_operator(operator.mul, 2, 3, 6)
        self._test_binary_operator(operator.mul, 16, 32, 54)

    def test_div(self):
        self.assertRaises(ZeroDivisionError,
                          lambda: GF256Element(10) / GF256Element(0))

        self.assertEquals(GF256Element(10) / GF256Element(10), GF256Element(1))
        self.assertEquals(GF256Element(10) / GF256Element(9), GF256Element(208))
        self.assertEquals(GF256Element(10) / GF256Element(5), GF256Element(2))

        self.assertEquals(10 / GF256Element(5), GF256Element(2))

    def test_pow(self):
        self.assertEquals(GF256Element(3)**3,
                          GF256Element(3)*GF256Element(3)*GF256Element(3))
        self.assertEquals(GF256Element(27)**100,
                          GF256Element(27)**50 * GF256Element(27)**50)

    def test_invert(self):
        self.assertRaises(ZeroDivisionError, lambda: ~GF256Element(0))
        self.assertEquals(~GF256Element(1), GF256Element(1))

    def test_neg(self):
        self.assertEquals(-GF256Element(0), GF256Element(0))
        self.assertEquals(-GF256Element(10), GF256Element(10))
        self.assertEquals(-GF256Element(100), GF256Element(100))

#    def test_repr(self):
#        self.assertEquals(repr(GF256Element(0)), "GF256Element(0)")
#        self.assertEquals(repr(GF256Element(1)), "GF256Element(1)")
#        self.assertEquals(repr(GF256Element(10)), "GF256Element(10)")

    def test_str(self):
        self.assertEquals(str(GF256Element(0)), "[0]")
        self.assertEquals(str(GF256Element(1)), "[1]")
        self.assertEquals(str(GF256Element(10)), "[10]")

