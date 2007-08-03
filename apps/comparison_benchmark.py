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

import time, signal, random
from optparse import OptionParser

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from gmpy import mpz
from pysmpc.field import GF
from pysmpc.runtime import Runtime
from pysmpc.config import load_config


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
    print "Time per comparison: %.3f ms" % (1000*float(stop-start) / count)
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
parser.add_option("-c", "--count", type="int", help="number of comparisons")

parser.set_defaults(modulus="30916444023318367583", count=100)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")

id, players = load_config(args[0])

modulus = eval(options.modulus, {}, {})

if modulus < 0:
    parser.error("modulus is negative: %d" % modulus)

prime = mpz(modulus-1).next_prime()
while prime % 4 != 3:
    prime = prime.next_prime()

if str(prime) != options.modulus:
    print "Using %s as modulus" % prime
    if prime != modulus:
        print "Adjusted from %d" % modulus

Zp = GF(long(prime))

count = options.count
print "I am player %d, will compare %d numbers" % (id, count)

rt = Runtime(players, id, (len(players) -1)//2)

l = 32 # TODO: needs to be taken from the runtime or a config file.

shares = []
for n in range(2*count//len(players) + 1):
    input = Zp(random.randint(0, 2**l))
    shares.extend(rt.shamir_share(input))
# We want to measure the time for count comparisons, so we need
# 2*count input numbers.
shares = shares[:2*count]

def run_test(_):
    print "Making %d comparisons" % count
    record_start()

    bits = []
    while len(shares) > 1:
        a = shares.pop(0)
        b = shares.pop(0)
        c = rt.greater_than(a,b, Zp)
        #c.addCallback(timestamp)
        bits.append(c)

    stop = DeferredList(bits)
    stop.addCallback(record_stop)
    stop.addCallback(finish)

    # TODO: it would be nice it the results were checked
    # automatically, but it needs to be done without adding overhead
    # to the benchmark.

# We want to wait until all numbers have been shared
dl = DeferredList(shares)
dl.addCallback(run_test)
    
print "#### Starting reactor ###"
reactor.run()
