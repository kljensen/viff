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

import sys, time, random

from twisted.internet import reactor
from twisted.internet.defer import gatherResults, succeed

from pysmpc import shamir
from pysmpc.field import IntegerFieldElement as F
from pysmpc.runtime import Runtime
from pysmpc.generate_config import load_config

def output(x, format="output: %s"):
    print format % x
    return x

F.modulus = 2039
# Bit length of input values to greater_than.
l = 7

id, players = load_config(sys.argv[1])
print "I am player %d" % id

t = 1
n = len(players)

rt = Runtime(players, id, t)

# Shares of seller and buyer bids. Assume that each bidder and seller
# has secret shared the bids and encrypted them for each player. These
# have then been read, decrypted and summed up...

B = [30, 28, 25, 18, 15, 10]
S = [ 5, 15, 20, 22, 23, 25]

seller_bids = [shamir.share(F(x), t, n)[id-1][1] for x in S]
buyer_bids  = [shamir.share(F(x), t, n)[id-1][1] for x in B]


print "B:", buyer_bids
print "S:", seller_bids

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

    if result == 1:
        low = mid
    else:
        high = mid

    if low+1 < high:
        mid = (low + high)//2
        debug(low, mid, high)
        result = rt.greater_than(buyer_bids[mid], seller_bids[mid])
        rt.open(result)
        result.addCallback(output, str(B[mid]) + " >= " + str(S[mid]) + ": %s")
        result.addCallback(branch, low, mid, high)
        return result
    else:
        debug(low,mid,high)
        return low

def auction():
    result = branch(0, 0, len(seller_bids), 0)
    result.addCallback(output, "result: %s")
    result.addCallback(lambda _: reactor.stop())

reactor.callLater(0, auction)
reactor.run()
