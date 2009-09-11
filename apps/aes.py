#!/usr/bin/env python

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
from pprint import pformat

import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from viff.field import GF256
from viff.runtime import Runtime, create_runtime, gather_shares
from viff.config import load_config

from viff.aes import AES


parser = OptionParser(usage="Usage: %prog [options] config_file")
parser.add_option("-K", "--keylength", action="store", type="int",
                  help="Key length: 128, 192, or 256. Defaults to 128.")
parser.set_defaults(keylength=128)
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
parser.add_option("-o", "--at-once", action="store_true",help="Prepare "
                  "the whole computation at once instead of round-wise.")
parser.add_option("-c", "--count", action="store", type="int",
                  help="Number of blocks to encrypt. Defaults to 1.")
parser.set_defaults(count=1)
parser.add_option("-a", "--active", action="store_true", help="Use actively "
                  "secure runtime. Default is only passive security.")
parser.add_option("-p", "--preproc", action="store_true", help="Use "
                  "preprocessing. Default is no preprocessing.")

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("You must specify a config file.")

id, players = load_config(args[0])

def encrypt(_, rt, key):
    start = time.time()
    print "Started at %f." % start

    aes = AES(rt, options.keylength, use_exponentiation=options.exponentiation)

    ciphertext = []

    for i in range(options.count):
        ciphertext += aes.encrypt("a" * 16, key, True,
                                  prepare_at_once=options.at_once)

    opened_ciphertext = [rt.open(c) for c in ciphertext]

    def fin(ciphertext):
        print "Finished after %f sec." % (time.time() - start)
        print "Ciphertext:", [hex(c.value) for c in ciphertext]

        if rt._needed_data and options.preproc:
            print "Missing pre-processed data:"
            for (func, args), pcs in rt._needed_data.iteritems():
                print "* %s%s:" % (func, args)
                print "  " + pformat(pcs).replace("\n", "\n  ")

        if rt._pool:
            print "Unused pre-processed data:"
            pcs = rt._pool.keys()
            pcs.sort()
            print "  " + pformat(pcs).replace("\n", "\n  ")

        rt.shutdown()

    g = gather_shares(opened_ciphertext)
    rt.schedule_complex_callback(g, fin)

def share_key(rt):
    key =  []

    for i in range(options.keylength / 8):
        inputter = i % 3 + 1
        if (inputter == id):
            key.append(rt.input([inputter], GF256, ord("b")))
        else:
            key.append(rt.input([inputter], GF256))

    s = rt.synchronize()
    rt.schedule_complex_callback(s, encrypt, rt, key)

def preprocess(rt):
    if options.active:
        start = time.time()

        if options.exponentiation is False:
            max = 301
            js = [3 + i * 15 + j for i in range(20) for j in range(7) + [8]]
        elif options.exponentiation == 0:
            max = 321
            js = [2 + i * 16 + j for i in range(20) for j in range(13)]
        elif options.exponentiation == 1 or options.exponentiation == 2:
            max = 261
            js = [1 + i * 13 + j for i in range(20) for j in range(11)]
        elif options.exponentiation == 3:
            max = 301
            js = [1 + i * 15 + j for i in range(20) for j in range(13)]

        pcs = [(2, 18, k) +  (max,) * i + (j, 1, 0)
               for k in range(1, options.count + 1)
               for i in range(10)
               for j in js]

        preproc = rt.preprocess({("generate_triples", (GF256,)): pcs})

        def fin(_):
            print "Finished preprocessing after %f sec." % (time.time() - start)
            return rt

        preproc.addCallback(fin)
        rt.schedule_complex_callback(preproc, share_key)

if options.active:
    from viff.active import ActiveRuntime
    runtime_class = ActiveRuntime
else:
    from viff.passive import PassiveRuntime
    runtime_class = PassiveRuntime

rt = create_runtime(id, players, 1, options, runtime_class)

if options.preproc:
    rt.addCallback(preprocess)
else:
    rt.addCallback(share_key)

reactor.run()
