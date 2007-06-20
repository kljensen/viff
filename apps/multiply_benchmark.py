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

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from gmpy import mpz
from pysmpc.field import GMPIntegerFieldElement as Field
from pysmpc.runtime import Runtime
from pysmpc.generate_config import load_config


last_timestamp = time.time()
start = 0

def record_start():
    global start
    start = time.time()
    print "*" * 64
    print "Started"
    print

def record_stop(x):
    stop = time.time()
    print
    print "Total time used: %.3f sec" % (stop-start)
    print "Time for 100 multiplications: %.3f ms" % (100000*float(stop-start) / count)
    print "*" * 64
    return x

def timestamp(x):
    global last_timestamp
    now = time.time()
    print "Timestamp: %.2f, time since last: %.3f" % (now, now - last_timestamp)
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


id, players = load_config(sys.argv[1])
big = mpz(2) ** 1000 - 1000
Field.modulus = big.next_prime()
#Field.modulus = 13407807929942597099574024998205846127479365820592393377723561443721764030073546976801874298166903427690031858186486050853753882811946569946433649006084171L
input = Field(42)
count = int(sys.argv[2])
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
    product.addCallback(output, "result: %s")
    product.addCallback(finish)

# We want to wait until all numbers have been shared
dl = DeferredList(shares[:])
dl.addCallback(run_test)
    
print "#### Starting reactor ###"
reactor.run()
