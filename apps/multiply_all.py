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

import sys, time

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from pysmpc.field import IntegerFieldElement
from pysmpc.runtime import Runtime, Player, load_players

last_timestamp = time.time()
start = 0

def record_start():
    global start
    start = time.time()
    print "*" * 64
    print "Started"
    print

def total_time(x):
    now = time.time()
    print
    print "Total time used: %.3f sek" % (now-start)
    print "*" * 64
    return x

def timestamp(x):
    global last_timestamp
    now = time.time()
    print "Timestamp: %.2f, time since last: %.3f" % (now, now - last_timestamp)
    last_timestamp = now
    return x

def finish(x):
    reactor.stop()
    print "Stopped reactor"

def output(x, format="output: %s"):
    print format % x
    return x

id = int(sys.argv[1])
#input = IntegerFieldElement(int(sys.argv[2]), 9091)
input = IntegerFieldElement(42, 30916444023318367583)
count = int(sys.argv[3])
print "I am player %d and will input %s" % (id, input)

players = load_players("players.xml")

rt = Runtime(players, id, (len(players) -1)//2)

time.sleep(1)

#print "Runtime started. Press ENTER to continue..."
#sys.stdin.readline()

shares = []
for n in range(count):
    shares.extend(rt.share(input))

def run_test(_):
    print "Multiplying %d numbers" % len(shares)
    record_start()

    while len(shares) > 1:
        a = shares.pop(0)
        b = shares.pop(0)
        c = rt.mul(a,b)
        #c.addCallback(timestamp)
        shares.append(c)

    product = shares[0]
    product.addCallback(total_time)

    rt.open(product)

    product.addCallback(output, "result: %s")
    product.addCallback(finish)

dl = DeferredList(shares[:])
dl.addCallback(run_test)
    
print "#### Starting reactor ###"
reactor.run()
