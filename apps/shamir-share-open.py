#!/usr/bin/python

# Copyright 2007, 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License (LGPL) as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General
# Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with VIFF. If not, see <http://www.gnu.org/licenses/>.

import sys

from twisted.internet import reactor

from viff.field import GF
from viff.runtime import create_runtime
from viff.config import load_config
from viff.util import dprint

id, players = load_config(sys.argv[1])
Zp = GF(int(sys.argv[2]))
input = int(sys.argv[3])

print "I am player %d and will input %s" % (id, input)


def protocol(rt):
    print "-" * 64
    print "Program started"
    print

    a, b, c = rt.shamir_share([1, 2, 3], Zp, input)

    a = rt.open(a)
    b = rt.open(b)
    c = rt.open(c)

    dprint("### opened a: %s ###", a)
    dprint("### opened b: %s ###", b)
    dprint("### opened c: %s ###", c)

    rt.wait_for(a, b, c)


pre_runtime = create_runtime(id, players, 1)
pre_runtime.addCallback(protocol)

reactor.run()
