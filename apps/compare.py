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

from twisted.internet.defer import gatherResults

from pysmpc.field import GF, GF256
from pysmpc.runtime import Runtime
from pysmpc.config import load_config
from pysmpc.util import dprint

Zp = GF(30916444023318367583)

id, players = load_config(sys.argv[1])
try:
    count = int(sys.argv[2])
except IndexError:
    count = 10

rt = Runtime(players, id, 1)

bits = []
l = 7

rand = dict([(i, random.Random(i)) for i in players])

inputs = []
for i in range(count):
    input = dict([(j, rand[j].randint(0,pow(2,l))) for j in players])
    inputs.append(input)

# Fixed input for easier debugging
inputs.append({1: 20, 2: 25, 3: 0})

print "I am player %d, will compare %d numbers" % (id, len(inputs))

for input in inputs:
    x, y, z = rt.shamir_share(Zp(input[id]))
    bit = rt.open(rt.greater_than(x, y, Zp))
    bit.addCallback(lambda b: b == GF256(1))
    bit.addCallback(lambda b, x, y: "%3d >= %3d: %-5s (%s)" % (x, y, b, b == (x >= y)),
                    input[1], input[2])
    dprint("%s", bit)
    bits.append(bit)

results = gatherResults(bits)

rt.wait_for(results)
