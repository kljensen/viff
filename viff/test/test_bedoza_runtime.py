# Copyright 2010 VIFF Development Team.
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

import sys

# We don't need secure random numbers for test purposes.
from random import Random

from twisted.internet.defer import gatherResults, DeferredList

from viff.test.util import RuntimeTestCase, protocol
from viff.runtime import gather_shares, Share
from viff.config import generate_configs
from viff.bedoza.bedoza import BeDOZaRuntime
from viff.bedoza.shares import BeDOZaShare, BeDOZaShareContents
from viff.bedoza.keylist import BeDOZaKeyList
from viff.bedoza.maclist import BeDOZaMACList
from viff.field import FieldElement, GF
from viff.util import rand
from viff.bedoza.modified_paillier import ModifiedPaillier
from viff.bedoza.share_generators import ShareGenerator
from viff.bedoza.bedoza_triple import TripleGenerator

# The PyPaillier and commitment packages are not standard parts of VIFF so we
# skip them instead of letting them fail if the packages are not available. 
try:
    import pypaillier
except ImportError:
    pypaillier = None

# HACK: The paillier keys that are available as standard in VIFF tests
# are not suited for use with pypaillier. Hence, we use NaClPaillier
# to generate test keys. This confusion will disappear when pypaillier
# replaces the current Python-based paillier implementation.
from viff.paillierutil import NaClPaillier

# HACK^2: Currently, the NaClPaillier hack only works when triple is
# imported. It should ideally work without the triple package.
try:
    import tripple
except ImportError:
    tripple = None


class BeDOZaBasicCommandsTest(RuntimeTestCase):
    """Test for basic commands."""

    # Number of players.
    num_players = 3

    timeout = 3

    runtime_class = BeDOZaRuntime

    # TODO: During test, we would like generation of Paillier keys to
    # be deterministic. How do we obtain that?
    def generate_configs(self, *args):
        # In production, paillier keys should be something like 2000
        # bit. For test purposes, it is ok to use small keys.
        # TODO: paillier freezes if key size is too small, e.g. 13.
        return generate_configs(paillier=NaClPaillier(250), *args)

    def setUp(self):
        RuntimeTestCase.setUp(self)
        self.Zp = GF(17)
        bits_in_p = 5
        self.u_bound = 2**(4 * bits_in_p)
        self.alpha = 15

    @protocol
    def test_plus(self, runtime):
        """Test addition of two numbers."""

        Zp = self.Zp
       
        x = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(3), Zp(4), Zp(1)]), BeDOZaMACList([Zp(2), Zp(74), Zp(23), Zp(2)]))
        y = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(5), Zp(2), Zp(7)]), BeDOZaMACList([Zp(2), Zp(74), Zp(23), Zp(2)]))
        z = runtime._plus((x, y), Zp)
        self.assertEquals(z.get_value(), Zp(4))
        self.assertEquals(z.get_keys(), BeDOZaKeyList(Zp(23), [Zp(8), Zp(6), Zp(8)]))
        self.assertEquals(z.get_macs(), BeDOZaMACList([Zp(4), Zp(148), Zp(46), Zp(4)]))

    @protocol
    def test_sum(self, runtime):
        """Test addition of two numbers."""       

        def check(v):
            self.assertEquals(v, 0)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(8)
        y2 = gen.generate_share(9)
        z2 = runtime.add(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_plus(self, runtime):
        """Test addition of two numbers."""

        def check(v):
            self.assertEquals(v, 11)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(2)
        y2 = gen.generate_share(9)
        z2 = x2 + y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_constant_right(self, runtime):
        """Test addition of secret shared number and a public number."""

        y1 = 7

        def check(v):
            self.assertEquals(v, 15)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(8)
        z2 = x2 + y1
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sum_constant_left(self, runtime):
        """Test addition of a public number and secret shared number."""

        y1 = 7

        def check(v):
            self.assertEquals(v, 15)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(8)
        z2 = y1 + x2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_minus(self, runtime):
        """Test subtraction of two numbers."""

        Zp = self.Zp
       
        x = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(5), Zp(4), Zp(7)]), BeDOZaMACList([Zp(2), Zp(75), Zp(23), Zp(2)]))
        y = BeDOZaShareContents(Zp(2), BeDOZaKeyList(Zp(23), [Zp(3), Zp(2), Zp(1)]), BeDOZaMACList([Zp(2), Zp(74), Zp(23), Zp(2)]))
        z = runtime._minus((x, y), Zp)
        self.assertEquals(z.get_value(), Zp(0))
        self.assertEquals(z.get_keys(), BeDOZaKeyList(Zp(23), [Zp(2), Zp(2), Zp(6)]))
        self.assertEquals(z.get_macs(), BeDOZaMACList([Zp(0), Zp(1), Zp(0), Zp(0)]))

    @protocol
    def test_sub(self, runtime):
        """Test subtraction of two numbers."""

        def check(v):
            self.assertEquals(v, 1)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(9)
        y2 = gen.generate_share(8)
        z2 = runtime.sub(x2, y2)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_minus(self, runtime):
        """Test subtraction of two numbers."""

        def check(v):
            self.assertEquals(v, 1)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(9)
        y2 = gen.generate_share(8)
        z2 = x2 - y2
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_constant_right(self, runtime):
        """Test subtraction of secret shared number and a public number."""

        y = 4

        def check(v):
            self.assertEquals(v, 4)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(8)
        z2 = x2 - y
        d = runtime.open(x2)
        d.addCallback(check)
        return d

    @protocol
    def test_sub_constant_left(self, runtime):
        """Test subtraction of a public number and secret shared number."""

        y = 8

        def check(v):
            self.assertEquals(v, 3)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(5)
        z2 = y - x2
        d = runtime.open(x2)
        d.addCallback(check)
        return d

    @protocol
    def test_constant_multiplication_constant_left(self, runtime):
        """Test multiplication of two numbers."""

        x1 = 6
        y1 = 7

        def check(v):
            self.assertEquals(v, self.Zp(x1 * y1))

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(x1)

        z2 = runtime._cmul(self.Zp(y1), x2, self.Zp)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_constant_multiplication_constant_right(self, runtime):
        """Test multiplication of two numbers."""

        x1 = 6
        y1 = 7

        def check(v):
            self.assertEquals(v, self.Zp(x1 * y1))

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x2 = gen.generate_share(x1)

        z2 = runtime._cmul(x2, self.Zp(y1), self.Zp)
        d = runtime.open(z2)
        d.addCallback(check)
        return d

    @protocol
    def test_get_triple(self, runtime):
        """Test generation of a triple."""

        def check((a, b, c)):
            self.assertEquals(c, a * b)

        def open(triple):
            d1 = runtime.open(triple.a)
            d2 = runtime.open(triple.b)
            d3 = runtime.open(triple.c)
            d = gather_shares([d1, d2, d3])
            d.addCallback(check)
            return d

        random = Random(3423993)
        gen = TripleGenerator(runtime, self.Zp.modulus, random)
        [triple] = gen.generate_triples(1)
        triple.addCallback(open)
        return triple

    @protocol
    def test_basic_multiply(self, runtime):
        """Test multiplication of two numbers."""

        x1 = 6
        y1 = 6

        def check(v):
            self.assertEquals(v, self.Zp(x1 * y1))

        def do_stuff(triple, alpha):
            random = Random(3423993)
            share_random = Random(random.getrandbits(128))
        
            paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
            gen = ShareGenerator(self.Zp, runtime, share_random,
                                 paillier, self.u_bound, alpha)
        
            x2 = gen.generate_share(x1)
            y2 = gen.generate_share(y1)
            z2 = runtime._basic_multiplication(x2, y2,
                                               triple.a,
                                               triple.b,
                                               triple.c)
            d = runtime.open(z2)
            d.addCallback(check)
            return d

        gen = TripleGenerator(runtime, self.Zp.modulus, Random(3423993))
        alpha = gen.alpha
        [triple] = gen.generate_triples(1)
        runtime.schedule_callback(triple, do_stuff, alpha)
        return triple

    # @protocol
    # def test_mul_mul(self, runtime):
    #     """Test multiplication of two numbers."""

    #     x1 = 6
    #     y1 = 6

    #     def check(v):
    #         self.assertEquals(v, self.Zp(x1 * y1))

    #     gen = TripleGenerator(runtime, self.Zp.modulus, Random(3423993))
    #     alpha = gen.alpha
    #     runtime.triples = gen.generate_triples(1)
        

    #     random = Random(3423993)
    #     share_random = Random(random.getrandbits(128))
    #     paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
    #     gen = ShareGenerator(self.Zp, runtime, share_random,
    #                          paillier, self.u_bound, self.alpha)
        
    #     x2 = gen.generate_share(x1)
    #     y2 = gen.generate_share(y1)
        
    #     z2 = x2 * y2
    #     d = runtime.open(z2)
    #     d.addCallback(check)
    #     return d
    
    @protocol
    def test_basic_multiply_constant_right(self, runtime):
        """Test multiplication of two numbers."""

        x1 = 6
        y1 = 6

        def check(v):
            self.assertEquals(v, self.Zp(x1 * y1))

        def do_stuff(triple, alpha):
            random = Random(3423993)
            share_random = Random(random.getrandbits(128))
        
            paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
            gen = ShareGenerator(self.Zp, runtime, share_random,
                                 paillier, self.u_bound, alpha)
        
            x2 = gen.generate_share(x1)
            y2 = gen.generate_share(y1)
            z2 = runtime._basic_multiplication(x2, self.Zp(y1),
                                               triple.a,
                                               triple.b,
                                               triple.c)
            d = runtime.open(z2)
            d.addCallback(check)
            return d

        gen = TripleGenerator(runtime, self.Zp.modulus, Random(3423993))
        alpha = gen.alpha
        [triple] = gen.generate_triples(1)
        runtime.schedule_callback(triple, do_stuff, alpha)
        return triple

    @protocol
    def test_basic_multiply_constant_left(self, runtime):
        """Test multiplication of two numbers."""

        x1 = 6
        y1 = 6

        def check(v):
            self.assertEquals(v, self.Zp(x1 * y1))

        def do_stuff(triple, alpha):
            random = Random(3423993)
            share_random = Random(random.getrandbits(128))
        
            paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
            gen = ShareGenerator(self.Zp, runtime, share_random,
                                 paillier, self.u_bound, alpha)
        
            x2 = gen.generate_share(x1)
            y2 = gen.generate_share(y1)
            z2 = runtime._basic_multiplication(self.Zp(x1), y2,
                                               triple.a,
                                               triple.b,
                                               triple.c)
            d = runtime.open(z2)
            d.addCallback(check)
            return d

        gen = TripleGenerator(runtime, self.Zp.modulus, Random(3423993))
        alpha = gen.alpha
        [triple] = gen.generate_triples(1)
        runtime.schedule_callback(triple, do_stuff, alpha)
        return triple

    @protocol
    def test_open_multiple_secret_share(self, runtime):
        """Test sharing and open of a number."""

        def check(ls):
            for v in ls:
                self.assertEquals(v, 6)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x = gen.generate_share(6)
        y = gen.generate_share(6)
        d = runtime.open_multiple_values([x, y])
        d.addCallback(check)
        return d

    @protocol
    def test_open_two_secret_share(self, runtime):
        """Test sharing and open of a number."""

        def check((a, b)):
            self.assertEquals(a, 6)
            self.assertEquals(b, 6)

        random = Random(3423993)
        share_random = Random(random.getrandbits(128))
        
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))          
        gen = ShareGenerator(self.Zp, runtime, share_random,
                             paillier, self.u_bound, self.alpha)
        
        x = gen.generate_share(6)
        y = gen.generate_share(6)
        d = runtime.open_two_values(x, y)
        d.addCallback(check)
        return d
    
