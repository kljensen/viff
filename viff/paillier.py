# Copyright 2008 VIFF Development Team.
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

import gmpy

from viff.util import rand, find_random_prime

def L(u, n):
    return (u-1)/n

def generate_keys(bit_length):
    # Make an RSA modulus n.
    p = find_random_prime(bit_length/2)
    while True:
        q = find_random_prime(bit_length/2)
        if p<>q: break

    n = p*q
    nsq = n*n

    # Calculate Carmichael's function.
    lm = gmpy.lcm(p-1, q-1)

    # Generate a generator g in B.
    while True:
        g = rand.randint(1, long(nsq))
        if gmpy.gcd(L(pow(g, lm, nsq), n), n) == 1: break

    return (n, g), (n, g, lm)

def encrypt(m, (n, g)):
    r = rand.randint(1, long(n))
    nsq = n*n
    return (pow(g, m, nsq)*pow(r, n, nsq)) % nsq

def decrypt(c, (n, g, lm)):
    numer = L(pow(c, lm, n*n), n)
    denom = L(pow(g, lm, n*n), n)
    return (numer*gmpy.invert(denom, n)) % n
