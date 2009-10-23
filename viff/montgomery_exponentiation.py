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


def sizeinbits(a):
    acc = 0
    while a != 0:
        acc += 1
        a = a >> 1
    return acc


def calc_r(n):
    """Compute r."""
    n_size = sizeinbits(n)
    r = 2**(n_size+1)

    while gcd(r, n) != 1:
        r = r << 1
		
    return r


def calc_r_r_inv(n):
    """Compute r and r inverse."""
    assert (n % 2) == 1, "n must be odd."
    n_size = sizeinbits(n)
    r = 2**(n_size+1)

    while gcd(r, n) != 1:
        r = r << 1
		
    return r, inversemod(r, n)


def calc_np(n, r):
    """Compute n'."""
    assert (n % 2) == 1, "n must be odd."
    n_prime = inversemod(n, r)
    return r - n_prime 


def inversemod(a, n):
    g, x, y = xgcd(a, n)
    if g != 1:
        raise ZeroDivisionError, (a,n)
    assert g == 1, "a must be coprime to n."
    return x%n


def gcd(a, b):                                       
    if a < 0:  a = -a
    if b < 0:  b = -b
    if a == 0: return b
    if b == 0: return a
    while b != 0: 
        (a, b) = (b, a%b)
    return a


def xgcd(a, b):
    if a == 0 and b == 0: return (0, 0, 1)
    if a == 0: return (abs(b), 0, b/abs(b))
    if b == 0: return (abs(a), a/abs(a), 0)
    x_sign = 1; y_sign = 1
    if a < 0: a = -a; x_sign = -1
    if b < 0: b = -b; y_sign = -1
    x = 1; y = 0; r = 0; s = 1
    while b != 0:
        (c, q) = (a%b, a/b)
        (a, b, r, s, x, y) = (b, c, x-q*r, y-q*s, r, s)
    return (a, x*x_sign, y*y_sign)


def montgomery_exponentiation_reduction(a, r , n ):
    return (a * r) % n


def montgomery_product(a, b, n_prime, size_of_r, r, n):
    t = a * b 
    m = (t * n_prime) & r -1
    u = (t + m * n ) >> size_of_r - 1
    if u >= n:
        return u -n 
    return u


def montgomery_exponentiation(a, x, n, n_prime, r):
    ah = (a * r) % n 
    xh = r % n 
    x_s = sizeinbits(x) - 1
    px = 2**x_s
    size_of_r = sizeinbits(r)
    while px != 0:
        t = xh * xh 
        m = (t * n_prime) & r -1
        u = (t + m * n ) >> size_of_r - 1
        if u >= n:
            xh = u - n 
        else:
            xh = u
        if (px & x) > 0:
            t = ah * xh 
            m = (t * n_prime) & r - 1
            u = (t + m * n ) >> size_of_r - 1
            if u >= n:
                xh =  u -n 
            else:
                xh = u
	px = px >> 1

    m = (xh * n_prime) & r - 1
    u = (xh + m * n ) >> size_of_r - 1
    if u >= n:
        return u - n 
    return u

def montgomery_exponentiation2(a, x, n, n_prime,  r):
    ah = (a * r) % n 
    xh = r % n 
    x_s = sizeinbits(x) - 1
    px = 2**x_s
    size_of_r = sizeinbits(r)
    while px != 0:
        xh = montgomery_product(xh, xh, n_prime, size_of_r, r, n)
        if (px & x) > 0:
            xh = montgomery_product(ah, xh, n_prime, size_of_r, r, n)
	px = px >> 1

    x  = montgomery_product(xh, 1, n_prime, size_of_r, r, n)
    return x




# n = 2328734783
# r, r_inv = calc_r(n)
# n_prime = calc_np(n, r) 

if __name__ ==  '__main__':
    n = 2328734783
    r, r_inv = calc_r_r_inv(n)
    n_prime = calc_np(n, r) 
    a = 2987
    x = 1093874
    print montgomery_exponentiation(a, x, n, n_prime, r)
    print pow(a, x, n)
    print a**x % n




