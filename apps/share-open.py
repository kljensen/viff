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

from viff.field import GF256
from viff.runtime import create_runtime
from viff.config import load_config
from viff.util import dprint

id, players = load_config(sys.argv[1])
input = int(sys.argv[2])

print "I am player %d and will input %s" % (id, input)


def protocol(runtime):
    print "-" * 64
    print "Program started"
    print

    a, b, c = runtime.prss_share([1, 2, 3], GF256, input)

    a = runtime.open(a)
    b = runtime.open(b)
    c = runtime.open(c)

    dprint("### opened a: %s ###", a)
    dprint("### opened b: %s ###", b)
    dprint("### opened c: %s ###", c)

    runtime.wait_for(a, b, c)

pre_runtime = create_runtime(id, players, 1)
pre_runtime.addCallback(protocol)

print "#### Starting reactor ###"
reactor.run()
