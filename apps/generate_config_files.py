#!/usr/bin/python

# Copyright 2007 Martin Geisler
#
# This file is part of VIFF
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

from __future__ import division
from optparse import OptionParser

from viff.config import generate_configs

parser = OptionParser()
parser.add_option("-p", "--prefix",
                  help="output filename prefix")
parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
                  help="be verbose")
parser.add_option("-q", "--quiet", dest="verbose", action="store_false",
                  help="be quiet")
parser.add_option("-n", "--players", dest="n", type="int",
                  help="number of players")
parser.add_option("-t", "--threshold", dest="t", type="int",
                  help="threshold (it must hold that t < n/2)")

parser.set_defaults(verbose=True, n=3, t=1, prefix='player')

(options, args) = parser.parse_args()

if not options.t < options.n/2:
    parser.error("must have t < n/2")

if len(args) != options.n:
    parser.error("must supply a hostname:port argument for each player")

addresses = [arg.split(':', 1) for arg in args]
configs = generate_configs(options.n, options.t, addresses, options.prefix)

for config in configs.itervalues():
    config.write()
