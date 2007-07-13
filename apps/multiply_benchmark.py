#!/usr/bin/python

# Copyright 2007 Martin Geisler
#
# This file is part of PySMPC
#
# PySMPC is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PySMPC is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PySMPC in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

import sys, time, signal
from optparse import OptionParser

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from gmpy import mpz
from pysmpc.field import GMPIntegerFieldElement, IntegerFieldElement
from pysmpc.runtime import Runtime
from pysmpc.generate_config import load_config


last_timestamp = time.time()
start = 0

def record_start():
    global start
    start = time.time()
    print "*" * 64
    print "Started"

def record_stop(x):
    stop = time.time()
    print
    print "Total time used: %.3f sec" % (stop-start)
    print "Time per multiplication: %.3f ms" % (1000*float(stop-start) / count)
    print "*" * 64
    return x

def timestamp(x):
    global last_timestamp
    now = time.time()
    print "Delta: %8.3f ms" % (1000*(now-last_timestamp))
    last_timestamp = now
    return x

def finish(*x):
    reactor.stop()
    print "Stopped reactor"

def output(x, format="output: %s"):
    print format % x
    return x

# To avoid having leaving the ports in boring TIME_WAIT state, we must
# shut the reactor down cleanly if killed.
signal.signal(2, finish)


parser = OptionParser()
parser.add_option("-m", "--modulus",
                  help="lower limit for modulus (can be an expression)")
parser.add_option("--gmp", action="store_true", help="use GMP")
parser.add_option("-i", "--input", type="int", help="input number")
parser.add_option("-c", "--count", type="int", help="number of multiplications")

parser.set_defaults(modulus="30916444023318367583",
                    gmp=False, input=42, count=100)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")

id, players = load_config(sys.argv[1])

modulus = eval(options.modulus, {}, {})

if modulus < 0:
    parser.error("modulus is negative: %d" % modulus)

prime = long(mpz(modulus-1).next_prime())

if str(prime) != options.modulus:
    print "Using %d as modulus" % prime
    if prime != modulus:
        print "Adjusted from %d" % modulus

if options.gmp:
    print "Using GMP"
    Field = GMPIntegerFieldElement
    Field.modulus = mpz(prime)
else:
    print "Not using GMP"
    Field = IntegerFieldElement
    Field.modulus = int(prime) # Convert long to int if possible,
                               # leave as long if not.

input = Field(options.input)
count = options.count
print "I am player %d, will multiply %d numbers" % (id, count)

rt = Runtime(players, id, (len(players) -1)//2)

shares = []
for n in range(count//len(players) + 1):
    shares.extend(rt.shamir_share(input))

shares = shares[:count]

def run_test(_):
    print "Multiplying %d numbers" % count
    record_start()

    while len(shares) > 1:
        a = shares.pop(0)
        b = shares.pop(0)
        c = rt.mul(a,b)
        #c.addCallback(timestamp)
        shares.append(c)

    product = shares[0]
    product.addCallback(record_stop)

    rt.open(product)
    def check(result, expected):
        if result.value == expected:
            print "Result: %s (correct)" % result
        else:
            print "Result: %s (incorrect, expected %d)" % (result, expected)
    product.addCallback(check, pow(42, count, Field.modulus))
    product.addCallback(finish)

# We want to wait until all numbers have been shared
dl = DeferredList(shares)
dl.addCallback(run_test)
    
print "#### Starting reactor ###"
reactor.run()
