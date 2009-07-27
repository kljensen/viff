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

# This example is a tribute to the original example of secure
# multi-party computation by Yao in 1982. In his example two
# millionaires meet in the street and they want to securely compare
# their fortunes. They want to do so without revealing how much they
# own to each other. This problem would be easy to solve if both
# millionaires trust a common third party, but we want to solve it
# without access to a third party.
#
# In this example the protocol is run between three millionaires and
# uses a protocol for secure integer comparison by Toft from 2005.
#
# Give a player configuration file as a command line argument or run
# the example with '--help' for help with the command line options.

from optparse import OptionParser
import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from viff.field import GF
from viff.runtime import create_runtime, gather_shares
from viff.comparison import Toft05Runtime
from viff.config import load_config
from viff.util import rand, find_prime

# We start by defining the protocol, it will be started at the bottom
# of the file.

class Protocol:

    def __init__(self, runtime):
        # Save the Runtime for later use
        self.runtime = runtime

        # This is the value we will use in the protocol.
        self.millions = rand.randint(1, 200)
        print "I am Millionaire %d and I am worth %d millions." \
            % (runtime.id, self.millions)

        # For the comparison protocol to work, we need a field modulus
        # bigger than 2**(l+1) + 2**(l+k+1), where the bit length of
        # the input numbers is l and k is the security parameter.
        # Further more, the prime must be a Blum prime (a prime p such
        # that p % 4 == 3 holds). The find_prime function lets us find
        # a suitable prime.
        l = runtime.options.bit_length
        k = runtime.options.security_parameter
        Zp = GF(find_prime(2**(l + 1) + 2**(l + k + 1), blum=True))

        # We must secret share our input with the other parties. They
        # will do the same and we end up with three variables
        m1, m2, m3 = runtime.shamir_share([1, 2, 3], Zp, self.millions)

        # Now that everybody has secret shared their inputs we can
        # compare them. We compare the worth of the first millionaire
        # with the two others, and compare those two millionaires with
        # each other.
        m1_ge_m2 = m1 >= m2
        m1_ge_m3 = m1 >= m3
        m2_ge_m3 = m2 >= m3

        # The results are secret shared, so we must open them before
        # we can do anything usefull with them.
        open_m1_ge_m2 = runtime.open(m1_ge_m2)
        open_m1_ge_m3 = runtime.open(m1_ge_m3)
        open_m2_ge_m3 = runtime.open(m2_ge_m3)

        # We will now gather the results and call the
        # self.results_ready method when they have all been received.
        results = gather_shares([open_m1_ge_m2, open_m1_ge_m3, open_m2_ge_m3])
        results.addCallback(self.results_ready)

        # We can add more callbacks to the callback chain in results.
        # These are called in sequence when self.results_ready is
        # finished. The first callback acts like a barrier and makes
        # all players wait on each other.
        #
        # The callbacks are always called with an argument equal to
        # the return value of the preceeding callback. We do not need
        # the argument (which is None since self.results_ready does
        # not return anything), so we throw it away using a lambda
        # expressions which ignores its first argument.
        runtime.schedule_callback(results, lambda _: runtime.synchronize())
        # The next callback shuts the runtime down, killing the
        # connections between the players.
        runtime.schedule_callback(results, lambda _: runtime.shutdown())

    def results_ready(self, results):
        # Since this method is called as a callback above, the results
        # variable will contain actual field elements, not just
        # Shares. That makes it very easy to work on them.

        # Let us start by unpacking the list.
        m1_ge_m2 = results[0]
        m1_ge_m3 = results[1]
        m2_ge_m3 = results[2]

        # We can establish the correct order of Millionaires 2 and 3.
        if m2_ge_m3:
            comparison = [3, 2]
        else:
            comparison = [2, 3]

        # We only have to insert Millionaire 1 in the correct spot.
        if m1_ge_m2 and m1_ge_m3:
            # Millionaire 1 is largest.
            comparison = comparison + [1]
        elif not m1_ge_m2 and not m1_ge_m3:
            # Millionaire 1 is smallest.
            comparison = [1] + comparison
        else:
            # Millionaire 1 is between the others.
            comparison = [comparison[0], 1, comparison[1]]

        print "From poorest to richest:"
        for id in comparison:
            if id == self.runtime.id:
                print "  Millionaire %d (%d millions)" % (id, self.millions)
            else:
                print "  Millionaire %d" % id

# Parse command line arguments.
parser = OptionParser()
Toft05Runtime.add_options(parser)
options, args = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")
else:
    id, players = load_config(args[0])

# Create a deferred Runtime and ask it to run our protocol when ready.
pre_runtime = create_runtime(id, players, 1, options, Toft05Runtime)
pre_runtime.addCallback(Protocol)

# Start the Twisted event loop.
reactor.run()
