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

from pysmpc.field import GF
from pysmpc.runtime import Runtime
from pysmpc.config import load_config
from pysmpc.util import dprint

id, players = load_config(sys.argv[1])
Zp = GF(int(sys.argv[2]))
input = Zp(int(sys.argv[3]))

print "I am player %d and will input %s" % (id, input)

rt = Runtime(players, id, 1)

print "-" * 64
print "Program started"
print

a, b, c = rt.shamir_share(input)

a = rt.open(a)
b = rt.open(b)
c = rt.open(c)

dprint("### opened a: %s ###", a)
dprint("### opened b: %s ###", b)
dprint("### opened c: %s ###", c)

rt.wait_for(a,b,c)
