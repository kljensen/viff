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

"""This program does a secret division between two secret shared
values. It is of course mostly meaningless for this example (you can
compute the inputs from your own value and the output).

The program can be run as follows for each player (min 3) where 24 is
the number we would like to divide (by):

$ python division.py player-X.ini 24

Only the numbers of player 1 and player 2 are actually used, but
more players are necessary for the security.
"""

from optparse import OptionParser
from twisted.internet import reactor

from viff.field import GF
from viff.runtime import BasicRuntime, create_runtime, make_runtime_class
from viff.comparison import ComparisonToft07Mixin
from viff.config import load_config
from viff.util import find_prime, dprint


def bits_to_val(bits):
    return sum([2**i * b for (i, b) in enumerate(reversed(bits))])


def divide(x, y, l):
    """Returns a share of of ``x/y`` (rounded down).

       Precondition:  ``2**l * y < x.field.modulus``.

       If ``y == 0`` return ``(2**(l+1) - 1)``.

       The division is done by making a comparison for every
       i with ``(2**i)*y`` and *x*.
       Protocol by Sigurd Meldgaard.

       Communication cost: *l* rounds of comparison.

       Also works for simple integers:
       >>>divide(3, 3, 2)
       1
       >>>divide(50, 10, 10)
       5
       """
    bits = []
    for i in range(l, -1, -1):
        t = 2**i * y
        cmp = t <= x
        bits.append(cmp)
        x = x - t * cmp
    return bits_to_val(bits)


def main():
     # Parse command line arguments.
    parser = OptionParser(usage=__doc__)

    parser.add_option("--modulus",
                     help="lower limit for modulus (can be an expression)")

    parser.set_defaults(modulus=2**65)

    BasicRuntime.add_options(parser)

    options, args = parser.parse_args()
    if len(args)==2:
        number = int(args[1])
    else:
        number = None

    if len(args) == 0:
        parser.error("you must specify a config file")

    Zp = GF(find_prime(options.modulus, blum=True))

    # Load configuration file.
    id, players = load_config(args[0])

    runtime_class = make_runtime_class(mixins=[ComparisonToft07Mixin])
    pre_runtime = create_runtime(id, players, 1, options, runtime_class)

    def run(runtime):
        print "Connected."

        # Players 1 and 2 are doing a sharing over the field Zp.
        # Our input is number (none for other players).
        if runtime.id == 3:
            print "I have no number"
        else:
            print "My number: %d." % number
        (x, y) = runtime.shamir_share([1, 2], Zp, number)

        # Do the secret computation.
        result = divide(x, y, 10) # 10 bits for the result.

        # Now open the result so we can see it.
        dprint("The two numbers divided are: %s", runtime.open(result))

        result.addCallback(lambda _: runtime.shutdown())

    pre_runtime.addCallback(run)

    # Start the Twisted event loop.
    reactor.run()

if __name__ == "__main__":
    main()
