#!/usr/bin/python

# Copyright 2009 VIFF Development Team.
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

# This program is a benchmark for the AES inversion.


import random
import time
from optparse import OptionParser

from twisted.internet import reactor

from viff.field import GF256
from viff.runtime import Runtime, create_runtime, gather_shares, Share
from viff.config import load_config

from viff.aes import AES


parser = OptionParser(usage="Usage: %prog [options] config_file")
parser.add_option("-e", "--exponentiation", action="store", type="int",
                  metavar="variant", 
                  help="Use exponentiation to invert bytes. "
                  "Default is the shortest sequential chain. "
                  "Possibilities:                             " +
                  "\n".join(["%d: %s                           " % 
                             (i, s) for (i, s) 
                             in enumerate(AES.exponentiation_variants)]))
parser.add_option("-m", "--masking", action="store_false", 
                  dest="exponentiation", 
                  help="Use masking to invert bytes.")
parser.set_defaults(exponentiation=1)
parser.add_option("-c", "--count", action="store", type="int",
                  help="Number of bytes to invert. Defaults to 100.")
parser.set_defaults(count=100)

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("You must specify a config file.")

id, players = load_config(args[0])

def invert(rt):
    aes = AES(rt, 192, use_exponentiation=options.exponentiation)
    bytes = [Share(rt, GF256, GF256(random.randint(0, 255)))
             for i in range(options.count)]

    start = time.time()

    done = gather_shares([aes.invert(byte) for byte in bytes])

    def finish(_):
        duration = time.time() - start
        print "Finished after %.3f s." % duration
        print "Time per inversion: %.3f ms" % (1000 * duration / options.count)
        rt.shutdown()

    done.addCallback(finish)

rt = create_runtime(id, players, 1, options)
rt.addCallback(invert)

reactor.run()
