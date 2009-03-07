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

# This example shows how to use multi-party AES encryption.


import time
from optparse import OptionParser

from twisted.internet import reactor

from viff.field import GF256
from viff.runtime import Runtime, create_runtime, gather_shares
from viff.config import load_config

from viff.aes import AES


parser = OptionParser(usage="Usage: %prog [options] config_file")
parser.add_option("-e", "--exponentiation", action="store_true",
                  help="Use exponentiation to invert bytes (default).")
parser.add_option("-m", "--masking", action="store_false",
                  dest="exponentiation",
                  help="Use masking to invert bytes.")
parser.set_defaults(exponentiation=True)

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("You must specify a config file.")

id, players = load_config(args[0])

def encrypt(_, rt, key):
    start = time.time()
    print "Started at %f." % start

    aes = AES(rt, 192, use_exponentiation=options.exponentiation)
    ciphertext = aes.encrypt("a" * 16, key, True)

    opened_ciphertext = [rt.open(c) for c in ciphertext]

    def fin(ciphertext):
        print "Finished after %f sec." % (time.time() - start)
        print "Ciphertext:", [hex(c.value) for c in ciphertext]
        rt.shutdown()

    g = gather_shares(opened_ciphertext)
    g.addCallback(fin)

def share_key(rt):
    key =  []

    for i in range(24):
        inputter = i % 3 + 1
        if (inputter == id):
            key.append(rt.input([inputter], GF256, ord("b")))
        else:
            key.append(rt.input([inputter], GF256))

    s = rt.synchronize()
    s.addCallback(encrypt, rt, key)

rt = create_runtime(id, players, 1, options)
rt.addCallback(share_key)

reactor.run()
