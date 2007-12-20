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

# This example benchmarks multiplications. All input numbers are
# multiplied in parallel down to a single number. This builds a
# multiplication tree like this for calculating a * b * c * d * e * f:
#
#          *
#         / \
#        /   \
#       *     \
#      / \     \
#     /   \     \
#    *     *     *
#   / \   / \   / \
#  a   b c   d e   f
#
# So the multiplications do not run entirely in parallel: within a
# layer the multiplications run in parallel, but each layer has to
# wait on the layers below it.
#
# To multiply x numbers the players:
#
# * Share x random numbers.
#
# * Wait until all shares have arrived, then start the clock.
#
# * Multiply in the tree-like fashion.
#
# * Stop the clock and report the time taken.
#
# This means that the time reported excludes the time used for the
# initial sharing of input values and the time it would take to
# reconstruct the output value.

import time, signal
from optparse import OptionParser

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from gmpy import mpz
from viff.field import GF
from viff.runtime import Runtime, create_runtime
from viff.config import load_config

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

parser = OptionParser()
parser.add_option("-m", "--modulus",
                  help="lower limit for modulus (can be an expression)")
parser.add_option("-i", "--input", type="int",
                  help="input number")
parser.add_option("-c", "--count", type="int",
                  help="number of multiplications")

parser.set_defaults(modulus="30916444023318367583", input=42, count=100)

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")

id, players = load_config(args[0])

modulus = eval(options.modulus, {}, {})

if modulus < 0:
    parser.error("modulus is negative: %d" % modulus)

prime = long(mpz(modulus-1).next_prime())

if str(prime) != options.modulus:
    print "Using %d as modulus" % prime
    if prime != modulus:
        print "Adjusted from %d" % modulus

Zp = GF(prime)

input = Zp(options.input)
count = options.count
print "I am player %d, will multiply %d numbers" % (id, count)

def protocol(rt):
    shares = []
    for n in range(count//len(players) + 1):
        shares.extend(rt.shamir_share(input))

    def run_test(_):
        print "Multiplying %d numbers" % count
        record_start()

        while len(shares) > 1:
            a = shares.pop(0)
            b = shares.pop(0)
            c = a * b
            #c.addCallback(timestamp)
            shares.append(c)

        product = shares[0]
        product.addCallback(record_stop)

        result = rt.open(product)
        result.addCallback(check, pow(42, count, Zp.modulus))

        def check(result, expected):
            if result.value == expected:
                print "Result: %s (correct)" % result
            else:
                print "Result: %s (incorrect, expected %d)" % (result, expected)

        def finish(_):
            rt.shutdown()
            print "Stopped reactor"

        result.addCallback(finish)

    shares = shares[:count]
    # We want to wait until all numbers have been shared
    dl = DeferredList(shares)
    dl.addCallback(run_test)

pre_runtime = create_runtime(id, players, (len(players) -1)//2, options)
pre_runtime.addCallback(protocol)

print "#### Starting reactor ###"
reactor.run()
