
from pysmpc.field import IntegerFieldElement, GF256Element

from twisted.trial.unittest import TestCase
import operator

class IntegerFieldElementTestCase(TestCase):

    def setUp(self):
        IntegerFieldElement.modulus = 31

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
