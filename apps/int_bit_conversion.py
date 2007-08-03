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

from pysmpc.field import GF, GF256Element
from pysmpc.runtime import Runtime
from pysmpc.config import load_config

def output(x, format="output: %s"):
    print format % x
    return x

id, players = load_config(sys.argv[1])
print "I am player %d" % id

rt = Runtime(players, id, (len(players) -1)//2)

Zp = GF(11)

a, b, c = rt.prss_share(Zp(0))
x, y, z = rt.prss_share(Zp(1))

a_b = rt.int_to_bit(a, Zp)
b_b = rt.int_to_bit(b, Zp)
c_b = rt.int_to_bit(c, Zp)

x_b = rt.int_to_bit(x, Zp)
y_b = rt.int_to_bit(y, Zp)
z_b = rt.int_to_bit(z, Zp)

rt.open(a_b)
rt.open(b_b)
rt.open(c_b)

rt.open(x_b)
rt.open(y_b)
rt.open(z_b)

def check(result, variable, expected):
    if result == expected:
        print "%s: %s (correct)" % (variable, result)
    else:
        print "%s: %s (incorrect, expected %d)" % (variable, result, expected)

a_b.addCallback(check, "a_b", GF256Element(0))
b_b.addCallback(check, "b_b", GF256Element(0))
c_b.addCallback(check, "c_b", GF256Element(0))

x_b.addCallback(check, "x_b", GF256Element(1))
y_b.addCallback(check, "y_b", GF256Element(1))
z_b.addCallback(check, "z_b", GF256Element(1))

rt.wait_for(a_b, b_b, c_b, x_b, y_b, z_b)
