#!/usr/bin/python

# Copyright 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
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

# This is an implementation of the example program (Figure 6) used by
# Janus Dam Nielsen and Michael I. Schwartzbach in their paper "A
# Domain-Specific Programming Language for Secure Multiparty
# Computation" presented at the PLAS '07 conference. The program
# evaluates a polynomial securely and reveals the sign of the result.

from time import time

from optparse import OptionParser
from twisted.internet import reactor

from viff.field import GF
from viff.runtime import Runtime, create_runtime
from viff.comparison import Toft07Runtime
from viff.config import load_config
from viff.util import find_prime

# We start by defining the protocol.
def eval_poly(runtime):
    print "Starting protocol"
    start_time = time()

    modulus = find_prime(2**65, blum=True)
    Zp = GF(modulus)

    # In this example we just let Player 1 share the input values.
    if runtime.id == 1:
        x = runtime.shamir_share([1], Zp, 17)
        a = runtime.shamir_share([1], Zp, 42)
        b = runtime.shamir_share([1], Zp, -5)
        c = runtime.shamir_share([1], Zp, 87)
    else:
        x = runtime.shamir_share([1], Zp)
        a = runtime.shamir_share([1], Zp)
        b = runtime.shamir_share([1], Zp)
        c = runtime.shamir_share([1], Zp)

    # Evaluate the polynomial.
    p = a * (x * x) + b * x + c

    sign = (p < 0) * -1 + (p > 0) * 1
    output = runtime.open(sign)
    output.addCallback(done, start_time, runtime)

def done(sign, start_time, runtime):
    print "Sign: %s" % sign
    print "Time taken: %.2f sec" % (time() - start_time)
    runtime.shutdown()

# Parse command line arguments.
parser = OptionParser()
Runtime.add_options(parser)
options, args = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")
else:
    id, players = load_config(args[0])

# Create a deferred Runtime and ask it to run our protocol when ready.
pre_runtime = create_runtime(id, players, 1, options, Toft07Runtime)
pre_runtime.addCallback(eval_poly)

# Start the Twisted event loop.
reactor.run()
