#!/usr/bin/python

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

import sys, time, random
from optparse import OptionParser

from twisted.internet import reactor
from twisted.internet.defer import gatherResults, succeed

from gmpy import mpz

from viff import shamir
from viff.field import GF
from viff.runtime import Runtime
from viff.config import load_config

def output(x, format="output: %s"):
    print format % x
    return x

last_timestamp = time.time()
def timestamp():
    global last_timestamp
    now = time.time()
    print "Delta: %8.3f ms" % (1000*(now-last_timestamp))
    last_timestamp = now

parser = OptionParser()
parser.add_option("-m", "--modulus",
                  help="lower limit for modulus (can be an expression)")
parser.add_option("-c", "--count", type="int",
                  help="number of bids")
parser.add_option("-v", "--verbose", action="store_true",
                  help="verbose output after each iteration")
parser.add_option("-q", "--quiet", action="store_false",
                  help="little output after each iteration")
parser.add_option("-l", "--length", type="int",
                  help="bit length of input numbers")

parser.set_defaults(modulus="30916444023318367583",
                    verbose=False, length=32, count=4000)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")


modulus = eval(options.modulus, {}, {})

if modulus < 0:
    parser.error("modulus is negative: %d" % modulus)

prime = mpz(modulus-1).next_prime()
while prime % 4 == 1:
    prime = prime.next_prime()

if str(prime) != options.modulus:
    print "Using %d as modulus" % prime
    if prime != modulus:
        print "Adjusted from %d" % modulus


Zp = GF(long(prime))
id, players = load_config(args[0])

print "I am player %d" % id

l = options.length
t = (len(players) -1)//2
n = len(players)

rt = Runtime(players, id, t)

# Shares of seller and buyer bids. Assume that each bidder and seller
# has secret shared the bids and encrypted them for each player. These
# have then been read, decrypted and summed up...

random.seed(0)

# Generate random bids -- we could generate numbers up to 2**l, but
# restricting them to only two digits use less space in the output.
B = [random.randint(1, 2**l) for _ in range(options.count)]
S = [random.randint(1, 2**l) for _ in range(options.count)]

# Make the bids monotone.
B.sort(reverse=True)
S.sort()

seller_bids = [shamir.share(Zp(x), t, n)[id-1][1] for x in S]
buyer_bids  = [shamir.share(Zp(x), t, n)[id-1][1] for x in B]


def debug(low, mid, high):
    string = ["  " for _ in range(high+1)]
    string[low] = " |"
    string[mid] = " ^"
    string[high] = " |"

    print "B: " + " ".join(["%2d" % b for b in B])
    print "S: " + " ".join(["%2d" % s for s in S])
    print "   " + " ".join(["%2d" % x for x in range(len(B)+1)])
    print "   " + " ".join(string)


def branch(result, low, mid, high):
    print "low: %d, high: %d, last result: %s" % (low, high, result)
    timestamp()

    if result == 1:
        low = mid
    else:
        high = mid

    if low+1 < high:
        mid = (low + high)//2
        if options.verbose:
            debug(low, mid, high)
        result = rt.open(rt.greater_than(buyer_bids[mid], seller_bids[mid], Zp))
        result.addCallback(output, str(B[mid]) + " >= " + str(S[mid]) + ": %s")
        result.addCallback(branch, low, mid, high)
        return result
    else:
        if options.verbose:
            debug(low,mid,high)
        return low

def auction():
    result = branch(0, 0, len(seller_bids), 0)

    def check_result(result):
        expected = max([i for i, (b,s) in enumerate(zip(B,S)) if b > s])
        if result == expected:
            print "Result: %d (correct)" % result
        else:
            print "Result: %d (incorrect, expected %d)" % (result, expected)

    result.addCallback(check_result)
    result.addCallback(lambda _: reactor.stop())

reactor.callLater(0, auction)
reactor.run()
