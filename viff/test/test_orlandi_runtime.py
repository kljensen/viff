# Copyright 2009 VIFF Development Team.
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

from twisted.internet.defer import gatherResults, DeferredList

from viff.test.util import RuntimeTestCase, protocol, BinaryOperatorTestCase
from viff.runtime import Share, gather_shares
try:
    from viff.orlandi import OrlandiRuntime, OrlandiShare
    import commitment
except ImportError:
    commitment = None
    OrlandiRuntime = None
    OrlandiShare = None

from viff.field import FieldElement, GF
from viff.passive import PassiveRuntime

from viff.util import rand


def _get_triple(runtime, field):
    n = field(0)
    Ca = commitment.commit(6, 0, 0)
    a = OrlandiShare(runtime, field, field(2), (n, n), Ca)
    Cb = commitment.commit(12, 0, 0)
    b = OrlandiShare(runtime, field, field(4), (n, n), Cb)
    Cc = commitment.commit(72, 0, 0)
    c = OrlandiShare(runtime, field, field(24), (n, n), Cc)
    return (a, b, c)


class OrlandiBasicCommandsTest(RuntimeTestCase):
    """Test for basic commands."""

    # Number of players.
    num_players = 3

    runtime_class = OrlandiRuntime

    @protocol
    def test_secret_share(self, runtime):
        """Test sharing of random numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check((xi, (rho1, rho2), Cr)):
            # Check that we got the expected number of shares.
            self.assert_type(xi, FieldElement)
            self.assert_type(rho1, FieldElement)
            self.assert_type(rho2, FieldElement)
            self.assert_type(Cr, commitment.Commitment)

        if 1 == runtime.id:
            share = runtime.secret_share([1], self.Zp, 42)
        else:
            share = runtime.secret_share([1], self.Zp)
        share.addCallback(check)
        return share

    @protocol
    def test_open_secret_share(self, runtime):
        """Test sharing and open of a number."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 42)

        if 1 == runtime.id:
            x = runtime.secret_share([1], self.Zp, 42)
        else:
            x = runtime.secret_share([1], self.Zp)
        d = runtime.open(x)
        d.addCallback(check)
        return d

    @protocol
    def test_random_share(self, runtime):
        """Test creation of a random shared number."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(True, True)

        x = runtime.random_share(self.Zp)
        d = runtime.open(x)
        d.addCallback(check)
        return d

    @protocol
    def test_sum(self, runtime):
        """Test addition of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 + y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = runtime.add(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_plus(self, runtime):
        """Test addition of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 + y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = x2 + y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_constant(self, runtime):
        """Test addition of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 + y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        z2 = x2 + y1
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub(self, runtime):
        """Test subtration of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 - y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = runtime.sub(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_minus(self, runtime):
        """Test subtration of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 - y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        if 3 == runtime.id:
            y2 = runtime.secret_share([3], self.Zp, y1)
        else:
            y2 = runtime.secret_share([3], self.Zp)

        z2 = x2 - y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_constant(self, runtime):
        """Test subtration of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 - y1)

        if 1 == runtime.id:
            x2 = runtime.secret_share([1], self.Zp, x1)
        else:
            x2 = runtime.secret_share([1], self.Zp)

        z2 = x2 - y1
        d = runtime.open(z2)
        d.addCallback(check)
        return d


class OrlandiAdvancedCommandsTest(RuntimeTestCase):
    """Test for advanced commands."""

    # Number of players.
    num_players = 3

    runtime_class = OrlandiRuntime

    timeout = 800

    @protocol
    def test_shift(self, runtime):
        """Test addition of the shift command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 42)

        x = runtime.shift([2], self.Zp, 42)
        d = runtime.open(x)
        d.addCallback(check)
        return d

    @protocol
    def test_shift_two_inputters(self, runtime):
        """Test addition of the shift command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 42)

        x, y = runtime.shift([1,3], self.Zp, 42)
        d1 = runtime.open(x)
        d1.addCallback(check)
        d2 = runtime.open(y)
        d2.addCallback(check)
        return DeferredList([d1, d2])

    @protocol
    def test_shift_two_consequtive_inputters(self, runtime):
        """Test addition of the shift command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def r1(ls):
            x, y = ls
            self.assertEquals(runtime.program_counter, [4])

        x = runtime.shift([1], self.Zp, 42)
        y = runtime.shift([2], self.Zp, 42)
        r = gather_shares([x, y])
        r.addCallback(r1)
        return r

    @protocol
    def test_shift_two_consequtive_inputters2(self, runtime):
        """Test addition of the shift command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(v):
            self.assertEquals(v, 42)

        def r1((x, y)):
            self.assertEquals(x, 42)
            self.assertEquals(y, 42)

        x = runtime.shift([1], self.Zp, 42)
        y = runtime.shift([2], self.Zp, 42)
        r = gather_shares([runtime.open(x), runtime.open(y)])
        r.addCallback(r1)
        return r

    @protocol
    def test_input(self, runtime):
        """Test of many uses of the input command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        count = 9

        a_shares = []
        b_shares = []
        for i in range(count):
            inputter = (i % len(runtime.players)) + 1
            if inputter == runtime.id:
                a = rand.randint(0, self.Zp.modulus)
                b = rand.randint(0, self.Zp.modulus)
            else:
                a, b = None, None
            a_shares.append(runtime.input([inputter], self.Zp, a))
            b_shares.append(runtime.input([inputter], self.Zp, b))
        shares_ready = gather_shares(a_shares + b_shares)
        return shares_ready

    @protocol
    def test_basic_multiply(self, runtime):
        """Test multiplication of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.shift([2], self.Zp, x1)
        y2 = runtime.shift([3], self.Zp, y1)

        a, b, c = _get_triple(self, self.Zp)
        z2 = runtime._basic_multiplication(x2, y2, a, b, c)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_mul_mul(self, runtime):
        """Test multiplication of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.shift([2], self.Zp, x1)
        y2 = runtime.shift([3], self.Zp, y1)

        z2 = x2 * y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_basic_multiply_constant_right(self, runtime):
        """Test multiplication of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.shift([1], self.Zp, x1)

        a, b, c = _get_triple(self, self.Zp)
        z2 = runtime._basic_multiplication(x2, self.Zp(y1), a, b, c)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_basic_multiply_constant_left(self, runtime):
        """Test multiplication of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.shift([1], self.Zp, x1)

        a, b, c = _get_triple(self, self.Zp)
        z2 = runtime._basic_multiplication(self.Zp(y1), x2, a, b, c)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_constant_multiplication_constant_left(self, runtime):
        """Test multiplication of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.shift([1], self.Zp, x1)

        z2 = runtime._cmul(self.Zp(y1), x2, self.Zp)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_constant_multiplication_constant_right(self, runtime):
        """Test multiplication of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.shift([1], self.Zp, x1)

        z2 = runtime._cmul(x2, self.Zp(y1), self.Zp)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_constant_multiplication_constant_None(self, runtime):
        """Test multiplication of two numbers."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        x2 = runtime.shift([1], self.Zp, x1)
        y2 = runtime.shift([1], self.Zp, y1)

    @protocol
    def test_sum_poly(self, runtime):
        """Test implementation of sum_poly."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        f = []
        f.append((self.Zp(7), (self.Zp(7), self.Zp(7)), self.Zp(7)))
        f.append((self.Zp(9), (self.Zp(9), self.Zp(9)), self.Zp(9)))
        f.append((self.Zp(13), (self.Zp(13), self.Zp(13)), self.Zp(13)))

        x, (rho1, rho2), Cx = runtime.sum_poly(1, f)
        self.assertEquals(x, 29)
        self.assertEquals(rho1, 29)
        self.assertEquals(rho2, 29)
        self.assertEquals(Cx, 29)
        return x

    @protocol
    def test_sum_poly(self, runtime):
        """Test implementation of sum_poly."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        Cf1 = commitment.commit(21, 21, 21)
        Cf2 = commitment.commit(27, 27, 27)
        Cf3 = commitment.commit(39, 39, 39)

        f = []
        f.append((self.Zp(7), (self.Zp(7), self.Zp(7)), Cf1))
        f.append((self.Zp(9), (self.Zp(9), self.Zp(9)), Cf2))
        f.append((self.Zp(13), (self.Zp(13), self.Zp(13)), Cf3))

        x, (rho1, rho2), Cx = runtime.sum_poly(3, f)
        self.assertEquals(x, 453)
        self.assertEquals(rho1, 453)
        self.assertEquals(rho2, 453)
        self.assertEquals(Cx, Cf1**3 * Cf2**9 * Cf3**27)
        return x

    @protocol
    def test_delta(self, runtime):
        """Test implementation of compute_delta."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        delta = runtime.compute_delta(3)
        self.assertEquals(delta[0], 7)
        self.assertEquals(delta[1], -21)
        self.assertEquals(delta[2], 35)
        self.assertEquals(delta[3], -35)
        self.assertEquals(delta[4], 21)
        self.assertEquals(delta[5], -7)
        self.assertEquals(delta[6], 1)

        return delta

    @protocol
    def test_leak_mul(self, runtime):
        """Test leaktolerant multiplication of two numbers."""
        commitment.set_reference_string(long(2), long(6))

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        x1 = 42
        y1 = 7

        runtime.d = 2

        def check(v):
            self.assertEquals(v, x1 * y1)

        x2 = runtime.shift([1], self.Zp, x1)
        y2 = runtime.shift([2], self.Zp, y1)

        c, sls = runtime.random_triple(self.Zp, 2*runtime.d + 1)

        def cont(M):
            z2 = runtime.leak_tolerant_mul(x2, y2, M)
            d = runtime.open(z2)
            d.addCallback(check)
            return d
        sls.addCallbacks(cont, runtime.error_handler)
        return sls

        z2 = runtime._cmul(y2, x2, self.Zp)
        self.assertEquals(z2, None)
        return z2

class TripleGenTest(RuntimeTestCase):
    """Test for generation of triples."""

    # Number of players.
    num_players = 3

    runtime_class = OrlandiRuntime

    timeout = 1600

    @protocol
    def test_tripleGen(self, runtime):
        """Test the triple_gen command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check((a, b, c)):
            self.assertEquals(c, a * b)

        def open((a, b, c, _)):
            d1 = runtime.open(a)
            d2 = runtime.open(b)
            d3 = runtime.open(c)
            d = gatherResults([d1, d2, d3])
            d.addCallback(check)
            return d
        d = runtime.triple_gen(self.Zp)
        d.addCallbacks(open, runtime.error_handler)
        return d

    @protocol
    def test_tripleGen2(self, runtime):
        """Test the triple_gen command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check((a, b, c, dx, dy, dz)):
            self.assertEquals(c, a * b)
            self.assertEquals(dz, dx * dy)

        def open(((a, b, c, control), (x, y, z, _))):
            d1 = runtime.open(a)
            d2 = runtime.open(b)
            d3 = runtime.open(c)
            dx = runtime.open(x)
            dy = runtime.open(y)
            dz = runtime.open(z)
            d = gatherResults([d1, d2, d3, dx, dy, dz])
            d.addCallback(check)
            return d
        t1 = runtime.triple_gen(self.Zp)
        t2 = runtime.triple_gen(self.Zp)
        d = gatherResults([t1, t2])
        d.addCallbacks(open, runtime.error_handler)
        return d

    @protocol
    def test_tripleTest(self, runtime):
        """Test the triple_test command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check((a, b, c)):
            self.assertEquals(c, a * b)

        def open((a, b, c, _)):
            d1 = runtime.open(a)
            d2 = runtime.open(b)
            d3 = runtime.open(c)
            d = gatherResults([d1, d2, d3])
            d.addCallback(check)
            return d
        d = runtime.triple_test(self.Zp)
        d.addCallbacks(open, runtime.error_handler)
        return d

    @protocol
    def test_random_triple(self, runtime):
        """Test the triple_combiner command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(ls):
            for x in xrange(len(ls) // 3):
                a = ls[x * 3]
                b = ls[x * 3 + 1]
                c = ls[x * 3 + 2]
                self.assertEquals(c, a * b)

        def open(ls):
            ds = []
            for (a, b, c) in ls:
                d1 = runtime.open(a)
                d2 = runtime.open(b)
                d3 = runtime.open(c)
                ds.append(d1)
                ds.append(d2)
                ds.append(d3)

            d = gatherResults(ds)
            d.addCallback(check)
            return d
        c, d = runtime.random_triple(self.Zp, 1)
        d.addCallbacks(open, runtime.error_handler)
        return d

    @protocol
    def test_random_triple3_parallel(self, runtime):
        """Test the triple_combiner command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(ls):
            for x in xrange(len(ls) // 3):
                a = ls[x * 3]
                b = ls[x * 3 + 1]
                c = ls[x * 3 + 2]
                self.assertEquals(c, a * b)

        def open(ls):
            ds = []
            for [(a, b, c)] in ls:
                d1 = runtime.open(a)
                d2 = runtime.open(b)
                d3 = runtime.open(c)
                ds.append(d1)
                ds.append(d2)
                ds.append(d3)

            d = gatherResults(ds)
            d.addCallback(check)
            return d
        ac, a = runtime.random_triple(self.Zp, 1)
        bc, b = runtime.random_triple(self.Zp, 1)
        cc, c = runtime.random_triple(self.Zp, 1)
        d = gather_shares([a, b, c])
        d.addCallbacks(open, runtime.error_handler)
        return d

    @protocol
    def test_random_triple_parallel(self, runtime):
        """Test the triple_combiner command."""

        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(ls):
            for x in xrange(len(ls) // 3):
                a = ls[x * 3]
                b = ls[x * 3 + 1]
                c = ls[x * 3 + 2]
                self.assertEquals(c, a * b)

        def open(ls):
            ds = []
            for [(a, b, c)] in ls:
                d1 = runtime.open(a)
                d2 = runtime.open(b)
                d3 = runtime.open(c)
                ds.append(d1)
                ds.append(d2)
                ds.append(d3)

            d = gatherResults(ds)
            d.addCallback(check)
            return d

        a_shares = []
        b_shares = []
        c_shares = []

        def cont(x):
            while a_shares and b_shares:
                a = a_shares.pop()
                b = b_shares.pop()
                c_shares.append(runtime.mul(a, b))
            done = gather_shares(c_shares)
            return done

        count = 5

        for i in range(count):
            inputter = (i % len(runtime.players)) + 1
            if inputter == runtime.id:
                a = rand.randint(0, self.Zp.modulus)
                b = rand.randint(0, self.Zp.modulus)
            else:
                a, b = None, None
            a_shares.append(runtime.input([inputter], self.Zp, a))
            b_shares.append(runtime.input([inputter], self.Zp, b))
        shares_ready = gather_shares(a_shares + b_shares)

        runtime.schedule_callback(shares_ready, cont)
        return shares_ready

if not commitment:
    OrlandiAdvancedCommandsTest.skip = "Skipped due to missing commitment module."
    OrlandiBasicCommandsTest.skip = "Skipped due to missing commitment module."
    TripleGenTest.skip = "Skipped due to missing commitment module."
