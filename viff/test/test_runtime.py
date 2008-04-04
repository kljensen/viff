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

"""Tests for viff.runtime.

Each method in Runtime is tested using a small protocol in
L{RuntimeTest}. If the environment variable STRESS is defined (to any
value) additional multiplication and comparison stress testing is
performed by L{StressTest}.
"""

import os
from random import Random
import operator

from twisted.internet.defer import gatherResults

from viff.field import GF256
from viff.runtime import Share
from viff.comparison import Toft05Runtime
from viff.test.util import RuntimeTestCase, BinaryOperatorTestCase, protocol


__doctests__ = ['viff.runtime']


class AddTest(BinaryOperatorTestCase, RuntimeTestCase):
    operator = operator.add


class SubTest(BinaryOperatorTestCase, RuntimeTestCase):
    operator = operator.sub


class MulTest(BinaryOperatorTestCase, RuntimeTestCase):
    operator = operator.mul


class XorTest(BinaryOperatorTestCase, RuntimeTestCase):
    a = 0
    b = 1
    operator = operator.xor


class RuntimeTest(RuntimeTestCase):
    """Test L{viff.runtime.Runtime}."""

    @protocol
    def test_mul_no_resharing_int(self, runtime):
        """Verify that local multiplications really are local."""
        a = Share(runtime, self.Zp, self.Zp(2))
        b = 3
        c = a * b

        # We setup a list which can be mutated from the mutate
        # callback below:
        c_value = [None]
        def mutate(value):
            c_value[0] = value

        # We now add the callback to c and expect it to be called
        # immediatedly since c should have a value right away. This is
        # a slight hack: There is nothing in the Deferred abstraction
        # that says that callbacks will be called immediatedly.
        c.addCallback(mutate)
        self.assertEquals(c_value[0], 6)

    @protocol
    def test_mul_no_resharing_field_element(self, runtime):
        """Verify that local multiplications really are local.

        This test uses a Zp element instead of a plain integer.
        """
        a = Share(runtime, self.Zp, self.Zp(2))
        b = self.Zp(3)
        c = a * b

        c_value = [None]
        def mutate(value):
            c_value[0] = value

        c.addCallback(mutate)
        self.assertEquals(c_value[0], 6)

    @protocol
    def test_xor(self, runtime):
        """Test exclusive-or.

        All possible combination of 0/1 are tried for both a Zp field
        and GF256.
        """
        results = []
        for field in self.Zp, GF256:
            for a, b in (0, 0), (0, 1), (1, 0), (1, 1):
                # Share a and b with a pseudo-Shamir sharing. The
                # addition is done with field elements because we need
                # the special GF256 addition here when field is GF256.
                share_a = Share(runtime, field, field(a) + runtime.id)
                share_b = Share(runtime, field, field(b) + runtime.id)

                share_c = share_a ^ share_b

                opened_c = runtime.open(share_c)
                opened_c.addCallback(self.assertEquals, field(a ^ b))
                results.append(opened_c)
        return gatherResults(results)

    @protocol
    def test_shamir_share(self, runtime):
        """Test symmetric Shamir sharing.

        Every player participates in the sharing.
        """
        a, b, c = runtime.shamir_share([1, 2, 3], self.Zp, 42 + runtime.id)

        self.assert_type(a, Share)
        self.assert_type(b, Share)
        self.assert_type(c, Share)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gatherResults([opened_a, opened_b, opened_c])

    @protocol
    def test_shamir_share_asymmetric(self, runtime):
        """Test asymmetric Shamir sharing."""
        # Share a single input -- the result should be a Share and not
        # a singleton list.
        if runtime.id == 2:
            b = runtime.shamir_share([2], self.Zp, 42 + runtime.id)
        else:
            b = runtime.shamir_share([2], self.Zp)

        # Share two inputs, but do it in "backwards" order.
        if runtime.id == 1 or runtime.id == 3:
            c, a = runtime.shamir_share([3, 1], self.Zp, 42 + runtime.id)
        else:
            c, a = runtime.shamir_share([3, 1], self.Zp)

        self.assert_type(a, Share)
        self.assert_type(b, Share)
        self.assert_type(c, Share)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gatherResults([opened_a, opened_b, opened_c])


class ConvertBitShareTest(RuntimeTestCase):
    runtime_class = Toft05Runtime

    @protocol
    def test_convert_bit_share(self, runtime):
        """Test conversion 0/1 element conversion from Zp to GF256."""
        # TODO: test conversion from GF256 to Zp and between Zp and Zq
        # fields.
        results = []
        for value in 0, 1:
            share = Share(runtime, self.Zp, self.Zp(value))
            converted = runtime.convert_bit_share(share, GF256)
            self.assertEquals(converted.field, GF256)
            opened = runtime.open(converted)
            opened.addCallback(self.assertEquals, GF256(value))
            results.append(opened)
        return gatherResults(results)


if 'STRESS' in os.environ:

    class StressTest(RuntimeTestCase):
        """Multiplication and comparison stress test.

        These tests are only executed if the environment variable
        C{STRESS} is defined.
        """

        def _mul_stress_test(self, runtime, count):
            """Execute a number of multiplication rounds.

            Three numbers are multiplied in each round.
            """
            a, b, c = runtime.shamir_share([1, 2, 3], self.Zp, 42 + runtime.id)

            product = 1

            for _ in range(count):
                product *= a * b * c

            opened = runtime.open(product)
            result = self.Zp(((42 + 1) * (42 + 2) * (42 + 3))**count)

            opened.addCallback(self.assertEquals, result)
            return opened

        @protocol
        def test_mul_100(self, runtime):
            """Test 100 multiplication rounds."""
            return self._mul_stress_test(runtime, 100)

        @protocol
        def test_mul_200(self, runtime):
            """Test 200 multiplication rounds."""
            return self._mul_stress_test(runtime, 200)

        @protocol
        def test_mul_400(self, runtime):
            """Test 400 multiplication rounds."""
            return self._mul_stress_test(runtime, 400)

        @protocol
        def test_mul_800(self, runtime):
            """Test 800 multiplication rounds."""
            return self._mul_stress_test(runtime, 800)

        def _compare_stress_test(self, runtime, count):
            """Repeatedly share and compare random numbers.

            Three random numbers are generated and compared in all six
            possible ways.
            """
            # Random generators
            rand = Random(count)
            results = []
            max = 2**runtime.options.bit_length

            for _ in range(count):
                inputs = {1: rand.randint(0, max),
                          2: rand.randint(0, max),
                          3: rand.randint(0, max)}
                a, b, c = runtime.shamir_share([1, 2, 3], self.Zp,
                                               inputs[runtime.id])

                result_shares = [a >= b, b >= a, a >= c,
                                 c >= a, b >= c, c >= b]

                # Open all results
                opened_results = map(runtime.open, result_shares)

                expected = map(GF256, [inputs[1] >= inputs[2],
                                       inputs[2] >= inputs[1],
                                       inputs[1] >= inputs[3],
                                       inputs[3] >= inputs[1],
                                       inputs[2] >= inputs[3],
                                       inputs[3] >= inputs[2]])

                result = gatherResults(opened_results)
                result.addCallback(self.assertEquals, expected)
                results.append(result)

            return gatherResults(results)

        @protocol
        def test_compare_1(self, runtime):
            """Test 1 comparison round."""
            return self._compare_stress_test(runtime, 1)

        @protocol
        def test_compare_2(self, runtime):
            """Test 2 comparison rounds."""
            return self._compare_stress_test(runtime, 2)

        @protocol
        def test_compare_4(self, runtime):
            """Test 4 comparison rounds."""
            return self._compare_stress_test(runtime, 4)

        @protocol
        def test_compare_8(self, runtime):
            """Test 8 comparison rounds."""
            return self._compare_stress_test(runtime, 8)
