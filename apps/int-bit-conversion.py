#!/usr/bin/env python

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

import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from viff.field import GF, GF256
from viff.runtime import create_runtime
from viff.comparison import Toft05Runtime
from viff.config import load_config

id, players = load_config(sys.argv[1])
print "I am player %d" % id


def protocol(rt):
    print "Starting protocol"
    Zp = GF(11)
    a, b, c = rt.prss_share([1, 2, 3], Zp, 0)
    x, y, z = rt.prss_share([1, 2, 3], Zp, 1)

    a_b = rt.open(rt.convert_bit_share(a, GF256))
    b_b = rt.open(rt.convert_bit_share(b, GF256))
    c_b = rt.open(rt.convert_bit_share(c, GF256))

    x_b = rt.open(rt.convert_bit_share(x, GF256))
    y_b = rt.open(rt.convert_bit_share(y, GF256))
    z_b = rt.open(rt.convert_bit_share(z, GF256))

    def check(result, variable, expected):
        if result == expected:
            print "%s: %s (correct)" % (variable, result)
        else:
            print "%s: %s (incorrect, expected %d)" \
                % (variable, result, expected)

    a_b.addCallback(check, "a_b", GF256(0))
    b_b.addCallback(check, "b_b", GF256(0))
    c_b.addCallback(check, "c_b", GF256(0))

    x_b.addCallback(check, "x_b", GF256(1))
    y_b.addCallback(check, "y_b", GF256(1))
    z_b.addCallback(check, "z_b", GF256(1))

    rt.wait_for(a_b, b_b, c_b, x_b, y_b, z_b)

pre_runtime = create_runtime(id, players, (len(players) -1)//2,
                             runtime_class=Toft05Runtime)
pre_runtime.addCallback(protocol)

reactor.run()
