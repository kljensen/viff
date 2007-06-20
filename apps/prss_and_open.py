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

from twisted.internet.defer import gatherResults

from pysmpc.field import IntegerFieldElement, GF256Element
from pysmpc.runtime import Runtime
from pysmpc.generate_config import load_config

def output(x, format="output: %s"):
    print (("-"*64) + "\n" + format + "\n" + ("-"*64)) % x
    return x

id, players = load_config(sys.argv[1])
print "I am player %d" % id

IntegerFieldElement.modulus = 31

rt = Runtime(players, id, (len(players) -1)//2)

elems = []
bits = []

for _ in range(10):
    #x = rt.share_random_bit()
    #rt.open(x)
    #elems.append(x)
    
    y = rt.share_random_int(binary=True)
    rt.open(y)
    bits.append(y)

#wait_elems = gatherResults(elems)
#wait_elems.addCallback(output, "elems: %s")

wait_bits = gatherResults(bits)
wait_bits.addCallback(output, "bits: %s")

rt.wait_for(wait_bits)


