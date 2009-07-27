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
from twisted.internet.defer import gatherResults

from viff.field import GF
from viff.runtime import create_runtime
from viff.config import load_config
from viff.util import dprint

id, players = load_config(sys.argv[1])
print "I am player %d" % id

Z31 = GF(31)


def protocol(rt):
    elements = [rt.open(rt.prss_share_random(Z31)) for _ in range(10)]
    result = gatherResults(elements)
    dprint("bits: %s", result)

    rt.wait_for(result)

pre_runtime = create_runtime(id, players, (len(players) -1)//2)
pre_runtime.addCallback(protocol)

reactor.run()
