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

import os
from random import Random

from twisted.internet import reactor
from twisted.internet.defer import gatherResults
from twisted.trial.unittest import TestCase
from twisted.protocols.loopback import loopbackAsync

from viff.field import GF, GF256
from viff.runtime import Runtime, Share
from viff.config import generate_configs, load_config
from viff import shamir

from viff.test.util import RuntimeTestCase

# TODO: find a way to specify the program for each player once and run
# it several times.

class RuntimeTest(RuntimeTestCase):

    def test_open(self):
        """
        Shamir share a value and open it.
        """
        input = self.Zp(42)
        a, b, c = shamir.share(input, 1, 3)

        a = Share(self.rt1, a[1])
        b = Share(self.rt2, b[1])
        c = Share(self.rt3, c[1])

        open_a = self.rt1.open(a)
        open_b = self.rt2.open(b)
        open_c = self.rt3.open(c)

        self.assertTrue(isinstance(open_a, Share))
        self.assertTrue(isinstance(open_b, Share))
        self.assertTrue(isinstance(open_c, Share))

        open_a.addCallback(self.assertEquals, input)
        open_b.addCallback(self.assertEquals, input)
        open_c.addCallback(self.assertEquals, input)

        return gatherResults([open_a, open_b, open_c])

    def test_open_deferred(self):
        """
        Shamir share a value and open it, but let some of the shares
        arrive "late" to the runtimes.
        """
        input = self.Zp(42)
        shares = shamir.share(input, 1, 3)
        
        a = Share(self.rt1)
        b = Share(self.rt2, shares[1][1])
        c = Share(self.rt3)

        a = self.rt1.open(a)
        b = self.rt2.open(b)
        c = self.rt3.open(c)

        a.addCallback(self.assertEquals, input)
        b.addCallback(self.assertEquals, input)
        c.addCallback(self.assertEquals, input)

        # TODO: This looks funny because shamir.share return a list of
        # (player-id, share) tuples. Maybe it should be changed so
        # that it simply returns a list of shares?
        a.callback(shares[0][1])
        c.callback(shares[2][1])

        return gatherResults([a, b, c])

    def test_open_no_mutate(self):
        """
        Shamir share a value and open it twice.
        """
        input = self.Zp(42)
        share_a, share_b, share_c = shamir.share(input, 1, 3)

        a = Share(self.rt1, share_a[1])
        b = Share(self.rt2, share_b[1])
        c = Share(self.rt3, share_c[1])

        # Open once
        open_a1 = self.rt1.open(a)
        open_b1 = self.rt2.open(b)
        open_c1 = self.rt3.open(c)

        # Test that a, b, and c remain unchanged
        a.addCallback(self.assertEquals, share_a[1])
        b.addCallback(self.assertEquals, share_b[1])
        c.addCallback(self.assertEquals, share_c[1])

        # Open twice
        open_a2 = self.rt1.open(a)
        open_b2 = self.rt2.open(b)
        open_c2 = self.rt3.open(c)

        # Test that we got the expected value in both openings
        open_a1.addCallback(self.assertEquals, input)
        open_b1.addCallback(self.assertEquals, input)
        open_c1.addCallback(self.assertEquals, input)

        open_a2.addCallback(self.assertEquals, input)
        open_b2.addCallback(self.assertEquals, input)
        open_c2.addCallback(self.assertEquals, input)

        return gatherResults([a, b, c,
                              open_a1, open_b1, open_c1,
                              open_a2, open_b2, open_c2])

    # TODO: factor out common code from test_add* and test_sub*.

    def test_add(self):
        share_a = Share(self.rt1)
        share_b = Share(self.rt1, self.Zp(200))

        share_c = share_a + share_b
        self.assertTrue(isinstance(share_c, Share),
                        "Type should be Share, but is %s" % share_c.__class__)

        share_c.addCallback(self.assertEquals, self.Zp(300))

        share_a.callback(self.Zp(100))
        return share_c

    def test_add_coerce(self):
        share_a = Share(self.rt1)
        share_b = self.Zp(200)
        share_c = share_a + share_b

        share_c.addCallback(self.assertEquals, self.Zp(300))
        share_a.callback(self.Zp(100))
        return share_c

    def test_sub(self):
        share_a = Share(self.rt1)
        share_b = Share(self.rt1, self.Zp(200))

        share_c = share_a - share_b
        self.assertTrue(isinstance(share_c, Share),
                        "Type should be Share, but is %s" % share_c.__class__)

        share_c.addCallback(self.assertEquals, self.Zp(300))
        share_a.callback(self.Zp(500))
        return share_c

    def test_sub_coerce(self):
        share_a = Share(self.rt1)
        share_b = self.Zp(200)
        share_c = share_a - share_b

        share_c.addCallback(self.assertEquals, self.Zp(300))
        share_a.callback(self.Zp(500))
        return share_c

    def test_mul(self):
        def second(sequence):
            return [x[1] for x in sequence]
        
        def recombine(shares):
            ids = map(self.Zp, range(1, len(shares) + 1))
            return shamir.recombine(zip(ids, shares))

        a1, a2, a3 = second(shamir.share(self.Zp(20), 1, 3))
        b1, b2, b3 = second(shamir.share(self.Zp(30), 1, 3))

        a1 = Share(self.rt1, a1)
        b1 = Share(self.rt1, b1)

        a2 = Share(self.rt2, a2)
        b2 = Share(self.rt2, b2)

        a3 = Share(self.rt3, a3)
        b3 = Share(self.rt3, b3)

        c1 = a1 * b1
        c2 = a2 * b2
        c3 = a3 * b3

        self.assertTrue(isinstance(c1, Share),
                        "Type should be Share, but is %s" % c1.__class__)
        self.assertTrue(isinstance(c2, Share),
                        "Type should be Share, but is %s" % c2.__class__)
        self.assertTrue(isinstance(c3, Share),
                        "Type should be Share, but is %s" % c3.__class__)

        res = gatherResults([c1, c2, c3])
        res.addCallback(recombine)
        res.addCallback(self.assertEquals, self.Zp(600))
        return res

    def test_xor(self):
        def second(sequence):
            return [x[1] for x in sequence]

        def recombine(shares, field):
            ids = map(field, range(1, len(shares) + 1))
            return shamir.recombine(zip(ids, shares))

        results = []
        for field in self.Zp, GF256:
            for a, b in (0, 0), (0, 1), (1, 0), (1, 1):
                a1, a2, a3 = second(shamir.share(field(a), 1, 3))
                b1, b2, b3 = second(shamir.share(field(b), 1, 3))

                a1 = Share(self.rt1, a1)
                b1 = Share(self.rt1, b1)
                a2 = Share(self.rt2, a2)
                b2 = Share(self.rt2, b2)
                a3 = Share(self.rt3, a3)
                b3 = Share(self.rt3, b3)
                
                if field is self.Zp:
                    res1 = self.rt1.xor_int(a1, b1)
                    res2 = self.rt2.xor_int(a2, b2)
                    res3 = self.rt3.xor_int(a3, b3)
                else:
                    res1 = self.rt1.xor_bit(a1, b1)
                    res2 = self.rt2.xor_bit(a2, b2)
                    res3 = self.rt3.xor_bit(a3, b3)
            
                res = gatherResults([res1, res2, res3])
                res.addCallback(recombine, field)
                res.addCallback(self.assertEquals, field(a ^ b))

                results.append(res)

        return gatherResults(results)

    def test_shamir_share(self):
        a = self.Zp(10)
        b = self.Zp(20)
        c = self.Zp(30)

        a1, b1, c1 = self.rt1.shamir_share(a)
        a2, b2, c2 = self.rt2.shamir_share(b)
        a3, b3, c3 = self.rt3.shamir_share(c)

        # Check a cross-section of the shares for correct type
        self.assertTrue(isinstance(a1, Share),
                        "Type should be Share, but is %s" % a1.__class__)
        self.assertTrue(isinstance(b2, Share),
                        "Type should be Share, but is %s" % b2.__class__)
        self.assertTrue(isinstance(c3, Share),
                        "Type should be Share, but is %s" % c3.__class__)

        def check_recombine(shares, value):
            ids = map(self.Zp, range(1, len(shares) + 1))
            self.assertEquals(shamir.recombine(zip(ids, shares)), value)

        a_shares = gatherResults([a1, a2, a3])
        a_shares.addCallback(check_recombine, a)

        b_shares = gatherResults([b1, b2, b3])
        b_shares.addCallback(check_recombine, b)

        c_shares = gatherResults([c1, c2, c3])
        c_shares.addCallback(check_recombine, c)

        a1 = self.rt1.open(a1)
        a2 = self.rt2.open(a2)
        a3 = self.rt3.open(a3)

        b1 = self.rt1.open(b1)
        b2 = self.rt2.open(b2)
        b3 = self.rt3.open(b3)

        c1 = self.rt1.open(c1)
        c2 = self.rt2.open(c2)
        c3 = self.rt3.open(c3)

        a1.addCallback(self.assertEquals, a)
        a2.addCallback(self.assertEquals, a)
        a3.addCallback(self.assertEquals, a)

        b1.addCallback(self.assertEquals, b)
        b2.addCallback(self.assertEquals, b)
        b3.addCallback(self.assertEquals, b)

        c1.addCallback(self.assertEquals, c)
        c2.addCallback(self.assertEquals, c)
        c3.addCallback(self.assertEquals, c)

        # TODO: ought to wait on connections.values() as well
        return gatherResults([a1, a2, a3, b1, b2, b3, c1, c2, c3])

    def test_prss_share_int(self):
        a = self.Zp(10)
        b = self.Zp(20)
        c = self.Zp(30)

        a1, b1, c1 = self.rt1.prss_share(a)
        a2, b2, c2 = self.rt2.prss_share(b)
        a3, b3, c3 = self.rt3.prss_share(c)
        
        # Check a cross-section of the shares for correct type
        self.assertTrue(isinstance(a1, Share),
                        "Type should be Share, but is %s" % a1.__class__)
        self.assertTrue(isinstance(b2, Share),
                        "Type should be Share, but is %s" % b2.__class__)
        self.assertTrue(isinstance(c3, Share),
                        "Type should be Share, but is %s" % c3.__class__)

        def check_recombine(shares, value):
            ids = map(self.Zp, range(1, len(shares) + 1))
            self.assertEquals(shamir.recombine(zip(ids, shares)), value)

        a_shares = gatherResults([a1, a2, a3])
        a_shares.addCallback(check_recombine, a)

        b_shares = gatherResults([b1, b2, b3])
        b_shares.addCallback(check_recombine, b)

        c_shares = gatherResults([c1, c2, c3])
        c_shares.addCallback(check_recombine, c)
        return gatherResults([a_shares, b_shares, c_shares])

    def test_prss_share_bit(self):
        a = GF256(10)
        b = GF256(20)
        c = GF256(30)

        a1, b1, c1 = self.rt1.prss_share(a)
        a2, b2, c2 = self.rt2.prss_share(b)
        a3, b3, c3 = self.rt3.prss_share(c)
        
        # Check a cross-section of the shares for correct type
        self.assertTrue(isinstance(a1, Share),
                        "Type should be Share, but is %s" % a1.__class__)
        self.assertTrue(isinstance(b2, Share),
                        "Type should be Share, but is %s" % b2.__class__)
        self.assertTrue(isinstance(c3, Share),
                        "Type should be Share, but is %s" % c3.__class__)

        def check_recombine(shares, value):
            ids = map(GF256, range(1, len(shares) + 1))
            self.assertEquals(shamir.recombine(zip(ids, shares)), value)

        a_shares = gatherResults([a1, a2, a3])
        a_shares.addCallback(check_recombine, a)

        b_shares = gatherResults([b1, b2, b3])
        b_shares.addCallback(check_recombine, b)

        c_shares = gatherResults([c1, c2, c3])
        c_shares.addCallback(check_recombine, c)
        return gatherResults([a_shares, b_shares, c_shares])

    def test_prss_share_random_bit(self):
        """
        Tests the sharing of a 0/1 GF256.
        """
        # TODO: how can we test if a sharing of a random GF256 element
        # is correct? Any three shares are "correct", so it seems that
        # the only thing we can test is that the three players gets
        # their shares. But this is also tested with the test below.
        a1 = self.rt1.prss_share_random(field=GF256, binary=True)
        a2 = self.rt2.prss_share_random(field=GF256, binary=True) 
        a3 = self.rt3.prss_share_random(field=GF256, binary=True)

        self.assertTrue(isinstance(a1, Share),
                        "Type should be Share, but is %s" % a1.__class__)
        self.assertTrue(isinstance(a2, Share),
                        "Type should be Share, but is %s" % a2.__class__)
        self.assertTrue(isinstance(a3, Share),
                        "Type should be Share, but is %s" % a3.__class__)
        
        def check_binary_recombine(shares):
            ids = map(GF256, range(1, len(shares) + 1))
            self.assertIn(shamir.recombine(zip(ids, shares)),
                          [GF256(0), GF256(1)])

        a_shares = gatherResults([a1, a2, a3])
        a_shares.addCallback(check_binary_recombine)
        return a_shares

    def test_prss_share_random_int(self):
        a1 = self.rt1.prss_share_random(field=self.Zp, binary=True)
        a2 = self.rt2.prss_share_random(field=self.Zp, binary=True)
        a3 = self.rt3.prss_share_random(field=self.Zp, binary=True)
        
        def check_binary_recombine(shares):
            ids = map(self.Zp, range(1, len(shares) + 1))
            self.assertIn(shamir.recombine(zip(ids, shares)),
                          [self.Zp(0), self.Zp(1)])

        a_shares = gatherResults([a1, a2, a3])
        a_shares.addCallback(check_binary_recombine)
        return a_shares

    def test_convert_bit_share(self):
        # TODO: test conversion from GF256 to Zp and between Zp and Zq
        # fields.
        def second(sequence):
            return [x[1] for x in sequence]

        int_0_shares = second(shamir.share(self.Zp(0), 1, 3))
        int_1_shares = second(shamir.share(self.Zp(1), 1, 3))

        res_0_1 = self.rt1.convert_bit_share(int_0_shares[0], self.Zp, GF256)
        res_0_2 = self.rt2.convert_bit_share(int_0_shares[1], self.Zp, GF256)
        res_0_3 = self.rt3.convert_bit_share(int_0_shares[2], self.Zp, GF256)

        res_1_1 = self.rt1.convert_bit_share(int_1_shares[0], self.Zp, GF256)
        res_1_2 = self.rt2.convert_bit_share(int_1_shares[1], self.Zp, GF256)
        res_1_3 = self.rt3.convert_bit_share(int_1_shares[2], self.Zp, GF256)

        def check_recombine(shares, value):
            ids = map(GF256, range(1, len(shares) + 1))
            self.assertEquals(shamir.recombine(zip(ids, shares)), value)
        
        res_0 = gatherResults([res_0_1, res_0_2, res_0_3])
        res_0.addCallback(check_recombine, GF256(0))

        res_1 = gatherResults([res_1_1, res_1_2, res_1_3])
        res_1.addCallback(check_recombine, GF256(1))
        return gatherResults([res_0, res_1])

    def test_greater_than(self):
        a = self.Zp(10)
        b = self.Zp(20)
        c = self.Zp(30)

        a1, b1, c1 = self.rt1.shamir_share(a)
        a2, b2, c2 = self.rt2.shamir_share(b)
        a3, b3, c3 = self.rt3.shamir_share(c)

        res_ab1 = self.rt1.greater_than(a1, b1, self.Zp)
        res_ab2 = self.rt2.greater_than(a2, b2, self.Zp)
        res_ab3 = self.rt3.greater_than(a3, b3, self.Zp)

        res_ab1 = self.rt1.open(res_ab1)
        res_ab2 = self.rt2.open(res_ab2)
        res_ab3 = self.rt3.open(res_ab3)

        res_ab1.addCallback(self.assertEquals, GF256(False))
        res_ab2.addCallback(self.assertEquals, GF256(False))
        res_ab3.addCallback(self.assertEquals, GF256(False))

        return gatherResults([a1, a2, a3, b1, b2, b3, c1, c2, c3,
                              res_ab1, res_ab2, res_ab3])

    def test_greater_thanII(self):
        a = self.Zp(10)
        b = self.Zp(20)
        c = self.Zp(30)

        a1, b1, c1 = self.rt1.shamir_share(a)
        a2, b2, c2 = self.rt2.shamir_share(b)
        a3, b3, c3 = self.rt3.shamir_share(c)

        res_ab1 = self.rt1.greater_thanII(a1, b1, self.Zp)
        res_ab2 = self.rt2.greater_thanII(a2, b2, self.Zp)
        res_ab3 = self.rt3.greater_thanII(a3, b3, self.Zp)

        res_ab1 = self.rt1.open(res_ab1)
        res_ab2 = self.rt2.open(res_ab2)
        res_ab3 = self.rt3.open(res_ab3)

        res_ab1.addCallback(self.assertEquals, self.Zp(False))
        res_ab2.addCallback(self.assertEquals, self.Zp(False))
        res_ab3.addCallback(self.assertEquals, self.Zp(False))

        return gatherResults([a1, a2, a3, b1, b2, b3, c1, c2, c3,
                              res_ab1, res_ab2, res_ab3])

if 'STRESS' in os.environ:

    class StressTest(RuntimeTestCase):

        def _mul_stress_test(self, count):
            a, b, c = 17, 42, 111

            a1, b1, c1 = self.rt1.shamir_share(self.Zp(a))
            a2, b2, c2 = self.rt2.shamir_share(self.Zp(b))
            a3, b3, c3 = self.rt3.shamir_share(self.Zp(c))

            x, y, z = 1, 1, 1

            for _ in range(count):
                x = a1 * b1 * c1 * x
                y = a2 * b2 * c2 * y
                z = a3 * b3 * c3 * z

            x = self.rt1.open(x)
            y = self.rt2.open(y)
            z = self.rt3.open(z)

            result = self.Zp((a * b * c)**count)

            x.addCallback(self.assertEquals, result)
            y.addCallback(self.assertEquals, result)
            z.addCallback(self.assertEquals, result)

            return gatherResults([x, y, z])

        def test_mul_100(self):
            return self._mul_stress_test(100)

        def test_mul_200(self):
            return self._mul_stress_test(200)
        
        def test_mul_400(self):
            return self._mul_stress_test(400)
        
        def test_mul_800(self):
            return self._mul_stress_test(800)
        

        def _compare_stress_test(self, count):
            """
            This test repeatedly shares and compares random inputs.
            """
            # Random generators
            rand = {1: Random(count + 1),
                    2: Random(count + 2),
                    3: Random(count + 3)}
            results = []

            for _ in range(count):
                a = rand[1].randint(0, pow(2, self.rt1.options.bit_length))
                b = rand[2].randint(0, pow(2, self.rt2.options.bit_length))
                c = rand[3].randint(0, pow(2, self.rt3.options.bit_length))

                a1, b1, c1 = self.rt1.shamir_share(self.Zp(a))
                a2, b2, c2 = self.rt2.shamir_share(self.Zp(b))
                a3, b3, c3 = self.rt3.shamir_share(self.Zp(c))

                # Do all six possible comparisons between a, b, and c
                results1 = [self.rt1.greater_than(a1, b1, self.Zp),
                            self.rt1.greater_than(b1, a1, self.Zp),
                            self.rt1.greater_than(a1, c1, self.Zp),
                            self.rt1.greater_than(c1, a1, self.Zp),
                            self.rt1.greater_than(b1, c1, self.Zp),
                            self.rt1.greater_than(c1, b1, self.Zp)]

                results2 = [self.rt2.greater_than(a2, b2, self.Zp),
                            self.rt2.greater_than(b2, a2, self.Zp),
                            self.rt2.greater_than(a2, c2, self.Zp),
                            self.rt2.greater_than(c2, a2, self.Zp),
                            self.rt2.greater_than(b2, c2, self.Zp),
                            self.rt2.greater_than(c2, b2, self.Zp)]

                results3 = [self.rt3.greater_than(a3, b3, self.Zp),
                            self.rt3.greater_than(b3, a3, self.Zp),
                            self.rt3.greater_than(a3, c3, self.Zp),
                            self.rt3.greater_than(c3, a3, self.Zp),
                            self.rt3.greater_than(b3, c3, self.Zp),
                            self.rt3.greater_than(c3, b3, self.Zp)]

                # Open all results
                results1 = map(self.rt1.open, results1)
                results2 = map(self.rt2.open, results2)
                results3 = map(self.rt3.open, results3)

                expected = map(GF256, [a >= b, b >= a,
                                       a >= c, c >= a,
                                       b >= c, c >= b])

                result1 = gatherResults(results1)
                result2 = gatherResults(results2)
                result3 = gatherResults(results3)

                result1.addCallback(self.assertEquals, expected)
                result2.addCallback(self.assertEquals, expected)
                result3.addCallback(self.assertEquals, expected)

                results.extend([result1, result2, result3])

            return gatherResults(results)

        def test_compare_1(self):
            return self._compare_stress_test(1)

        def test_compare_2(self):
            return self._compare_stress_test(2)
        
        def test_compare_4(self):
            return self._compare_stress_test(4)
        
        def test_compare_8(self):
            return self._compare_stress_test(8)
