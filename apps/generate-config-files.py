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

# This application is used to generate player configuration files. As
# an example, consider three players on hostnames foo, bar, and baz
# and that can be contacted on port number 5000. Generating
# configuration files for them is done by:
#
# % ./generate_config_files.py foo:5000 bar:5000 baz:5000
#
# If the players are on the same host (localhost), then use different
# port numbers for each player.
#
# Each player has his own configuration file. The players are numbered
# in the order listed, so the Player 1 is on the host foo and has the
# configuration file player-1.ini. Similarly for Player 2 and 3.
#
# Each file contains information about the other two players and keys
# used for pseudo-random secret sharing (PRSS). Because of the key
# material, the files should be distributed securely to the players.
#
# All example applications load a configuration file specified by a
# command line argument. For example, running the VIFF benchmark is
# done like this:
#
# On host baz:
# % ./benchmark.py player-3.ini
#
# On host bar:
# % ./benchmark.py player-2.ini
#
# On host foo:
# % ./benchmark.py player-1.ini
#
# It is currently necessary to start the players in reverse order
# (highest numbered first).

from __future__ import division
from optparse import OptionParser

from viff.config import generate_configs
from viff.paillierutil import ViffPaillier, NaClPaillier

try:
    import pypaillier
except ImportError:
    pypaillier = None

paillier_choices = ['viff']

if pypaillier:
    paillier_choices.append('nacl')

parser = OptionParser()
parser.add_option("-p", "--prefix",
                  help="output filename prefix")
parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
                  help="be verbose")
parser.add_option("-q", "--quiet", dest="verbose", action="store_false",
                  help="be quiet")
parser.add_option("-n", "--players", dest="n", type="int",
                  help="number of players")
parser.add_option("-k", "--keysize", type="int",
                  help="Specify the key-size for Paillier encryption")
parser.add_option("--paillier", type="choice", choices=paillier_choices,
                  help="the implementation of Paillier encryption")
parser.add_option("-t", "--threshold", dest="t", type="int",
                  help="threshold (it must hold that t < n/2)")
parser.add_option("--skip-prss", action="store_true",
                  help="do not generate PRSS keys")

parser.set_defaults(verbose=True, n=3, t=1, prefix='player', skip_prss=False,
                    keysize=1024, paillier='viff')

(options, args) = parser.parse_args()

if "nacl" == options.paillier:
    paillier = NaClPaillier(options.keysize)
else:
    paillier = ViffPaillier(options.keysize)

if len(args) != options.n:
    parser.error("must supply a hostname:port argument for each player")

addresses = [arg.split(':', 1) for arg in args]
configs = generate_configs(options.n, options.t, paillier, addresses,
                           options.prefix, options.skip_prss)

for config in configs.itervalues():
    config.write()
