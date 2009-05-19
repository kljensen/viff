#!/usr/bin/python

# Copyright 2008, 2009 VIFF Development Team.
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

from optparse import OptionParser
import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from viff.field import GF
from viff.runtime import create_runtime, Runtime
from viff.config import load_config

parser = OptionParser("%prog config input")
Runtime.add_options(parser)
(options, args) = parser.parse_args()

if len(args) != 2:
    parser.error("please supply a config file and an integer")

Zp = GF(1031)

id, players = load_config(args[0])
input = int(args[1])

def protocol(rt):

    def got_result(result):
        print "Product:", result
        rt.shutdown()

    x, y, z = rt.shamir_share([1, 2, 3], Zp, input)
    product = x * y * z
    opened_product = rt.open(product)
    opened_product.addCallback(got_result)

pre_runtime = create_runtime(id, players, 1)
pre_runtime.addCallback(protocol)

reactor.run()
