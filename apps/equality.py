#!/usr/bin/python

# Copyright 2008 VIFF Development Team.
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
#

"""This program is a very simple example of a VIFF program which shows
the secret equality testing of two numbers.

The program can be run as follows for each player (min 3) where 24 is
the number we would like to compare:

$ python equality.py player-X.ini -n 24

Only the numbers of player 1 and player 2 are actually compared, but
more players are necessary for the security.
"""

from optparse import OptionParser
from twisted.internet import reactor

from viff.field import GF
from viff.runtime import Runtime, create_runtime, make_runtime_class
from viff.config import load_config
from viff.util import find_prime
from viff.equality import ProbabilisticEqualityMixin


class Protocol:

    def __init__(self, runtime):
        print "Connected."
        self.rt = runtime

        # Is our player id among the two first?
        if runtime.id <= 2:
            print "My number: %d." % options.number
            # Players 1 and two are doing a sharing over the field ZP
            # our input is options number
            (x, y) = runtime.shamir_share([1, 2], Zp, options.number)
        else:
            print "I do not have a number."
            (x, y) = runtime.shamir_share([1, 2], Zp, None)

        # Do the secret computation
        result = (x == y)

        # Now open the result so that we can see it
        result = runtime.open(result)

        def finish(eq):
            print
            if eq:
                print "The two numbers where equal!"
            else:
                print "The two numbers where different! (with high probability)"
            print

        # When the values for the opening arrive, we can call the
        # finish function, followed by the shutdown method.
        result.addCallback(finish)
        result.addCallback(lambda _: runtime.shutdown())


# Parse command line arguments.
parser = OptionParser(usage=__doc__)

parser.add_option("--modulus",
                 help="lower limit for modulus (can be an expression)")
parser.add_option("-n", "--number", type="int",
                 help="number to compare")

parser.set_defaults(modulus=2**65, number=None)

Runtime.add_options(parser)

options, args = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")

Zp = GF(find_prime(options.modulus, blum=True))

# Load configuration file.
id, players = load_config(args[0])

runtime_class = make_runtime_class(mixins=[ProbabilisticEqualityMixin])
pre_runtime = create_runtime(id, players, 1, options, runtime_class)
pre_runtime.addCallback(Protocol)

# Start the Twisted event loop.
reactor.run()
