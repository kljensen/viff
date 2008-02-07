#!/usr/bin/python

# Copyright 2007, 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
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

import time, signal
from optparse import OptionParser

from twisted.internet import reactor
from twisted.internet.defer import DeferredList, gatherResults

#from twisted.internet import defer
#defer.setDebugging(True)

from viff.field import GF
from viff.runtime import Runtime, create_runtime
from viff.config import load_config
from viff.util import rand, find_prime


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

# To avoid having leaving the ports in boring TIME_WAIT state, we must
# shut the reactor down cleanly if killed.
signal.signal(2, finish)

parser = OptionParser()
parser.add_option("-m", "--modulus",
                  help="lower limit for modulus (can be an expression)")
parser.add_option("-c", "--count", type="int",
                  help="number of comparisons")

parser.set_defaults(modulus="30916444023318367583",
                    count=100)

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")

id, players = load_config(args[0])

Zp = GF(find_prime(options.modulus, blum=True))

# TODO: better q-prime...must depend on prime
qprime = 3001
Zq = GF(long(qprime))
#Zq = Zp

count = options.count
print "I am player %d, will compare %d numbers" % (id, count)

def protocol(rt):
    print "Testing online requirements for comparisonII"
    l = rt.options.bit_length
    k = rt.options.security_parameter
    assert prime > 2**(l+k)

    print "l = %d" % l
    print "k = %d" % k

    shares = []
    for n in range(2*count//len(players) + 1):
        input = rand.randint(0, 2**l - 1)
        shares.extend(rt.shamir_share([1, 2, 3], Zp, input))
    # We want to measure the time for count comparisons, so we need
    # 2*count input numbers.
    shares = shares[:2*count]

    preproc = []
    pseudoPreproc = []
    for i in range(count):
        thisPreproc = rt.greater_than_equalII_preproc(Zp, smallField = Zq)
        preproc.append(thisPreproc)
        pseudoPreproc += thisPreproc[2:-1]
        pseudoPreproc += thisPreproc[-1]

        # print status as we go along
        # TODO: why does this not work?
        def printDonePreproc(_, i):
            print "Done preprocessing %d" % i
            return _
        tmp = DeferredList(thisPreproc[2:-1])
        tmp.addCallback(printDonePreproc, i)

    def run_test(_):
        print "Preprocessing done..."
        print "Making %d comparisons" % count
        record_start()

        bits = []
        while len(shares) > 1:
            a = shares.pop(0)
            b = shares.pop(0)
            c = rt.greater_than_equalII_online(a, b, preproc.pop(), Zp)
            bits.append(c)

        stop = DeferredList(bits)
        stop.addCallback(record_stop)
        stop.addCallback(finish)

        # TODO: it would be nice it the results were checked
        # automatically, but it needs to be done without adding
        # overhead to the benchmark.


    # We want to wait until all numbers have been shared and
    # preprocessing has been performed
    dl = gatherResults(shares + pseudoPreproc)
    dl.addCallback(run_test)

pre_runtime = create_runtime(id, players, (len(players) -1)//2, options)
pre_runtime.addCallback(protocol)
    
print "#### Starting reactor ###"
reactor.run()
