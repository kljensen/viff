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

import sys

from viff.field import GF
from viff.runtime import Runtime
from viff.generate_config import load_config

id, players = load_config(sys.argv[1])

Zp = GF(1031)
Zq = GF(2039)

base = 1000
input1 = base - id
input2 = base + id

print "I am player %d, will share %d and %d " % (id, input1, input2)

rt = Runtime(players, id, 1)

a, b, c = rt.shamir_share(Zp(input1))
x, y, z = rt.shamir_share(Zq(input2))

d = rt.open(rt.mul(rt.mul(a,b), c))
w = rt.open(rt.mul(rt.mul(x,y), z))

def check(result, field, expected):
    if result == expected:
        print "%s: %s (correct)" % (field, result)
    else:
        print "%s: %s (incorrect, expected %d)" % (field, result, expected)

d.addCallback(check, "Zp", Zp(base-1) * Zp(base-2) * Zp(base-3))
w.addCallback(check, "Zq", Zq(base+1) * Zq(base+2) * Zq(base+3))

rt.wait_for(d, w)
