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

# This file contains a simpel example of a VIFF program, which illustrates
# the basic features of VIFF. How to input values from the command line,
# from individual players in the program, add, multiply, and output values
# to all or some of the players.

# Inorder to run the program follow the three steps:
#
# Generate player configurations in the viff/apps directory using:
#   python generate-config-files.py localhost:4001 localhost:4002 localhost:4003
#
# Generate ssl certificates in the viff/apps directory using:
#   python generate-certificates.py
#
# Run the program using three different shells using the command:
#   python beginner.py player-x.ini 79
# where x is replaced by the player number

# Some useful imports.
import sys

import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from viff.field import GF
from viff.runtime import create_runtime
from viff.config import load_config
from viff.util import dprint, find_prime

# Load the configuration from the player configuration files.
id, players = load_config(sys.argv[1])

# Initialize the field we do arithmetic over.
Zp = GF(find_prime(2**64))

# Read input from the commandline.
input = int(sys.argv[2])

print "I am player %d and will input %s" % (id, input)


def protocol(runtime):
    print "-" * 64
    print "Program started"
    print

    # Each of the players [1, 2, 3] shares his input -- resulting in
    # three shares. The a share is the input from P1, b is from P2,
    # and c is from P3.
    a, b, c = runtime.input([1, 2, 3], Zp, input)

    # It is possible to make the players do different things by
    # branching on the players ID. In this case only P1 inputs a
    # number. The other two players must still participate in order to
    # get the hold of their share.
    if runtime.id == 1:
        s1 = runtime.input([1], Zp, 42)
    else:
        s1 = runtime.input([1], Zp, None)

    # Secure arithmetic works like normal.
    a = b + c
    b = c * s1

    # Outputting shares convert them from secret shared form into
    # cleartext. By default every player receives the cleartext.
    a = runtime.output(a)
    b = runtime.output(b)
    c = runtime.output(c)
    # Output s1 to player 2. The other players will receive None.
    s1 = runtime.output(s1, [2])

    dprint("### Output a to all: %s ###", a)
    dprint("### Output b to all: %s ###", b)
    dprint("### Output c to all: %s ###", c)

    # We only print the value of s1 for player 2, 
    # since only player 2 has the value of s1.
    if runtime.id == 2:
        dprint("### opened s1: %s ###", s1)
    
    # We wait for the evaluation of deferred a, b, c.
    runtime.wait_for(a, b, c)

def errorHandler(failure):
    print "Error: %s" % failure


# Create a runtime
pre_runtime = create_runtime(id, players, 1)
pre_runtime.addCallback(protocol)
# This error handler will enable debugging by capturing
# any exceptions and print them on Standard Out.
pre_runtime.addErrback(errorHandler)

print "#### Starting reactor ###"
reactor.run()
