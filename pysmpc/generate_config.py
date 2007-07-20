#!/usr/bin/python

# Copyright 2007 Martin Geisler
#
# This file is part of PySMPC
#
# PySMPC is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PySMPC is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PySMPC in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

from __future__ import division

import sys
from configobj import ConfigObj
from optparse import OptionParser
from random import Random, SystemRandom
from pprint import pprint

from pysmpc.prss import generate_subsets
from pysmpc.runtime import Player


def s_str(subset):
    return " ".join(map(str, subset))


def s_unstr(str):
    return frozenset(map(int, str.split()))


def p_str(player):
    return "Player " + str(player)


def p_unstr(str):
    return int(str[7:])


def d_str(dealer):
    return "Dealer " + str(dealer)


def d_unstr(str):
    return int(str[7:])


# TODO: as noted in the Player constructor, one must set the field
# modulus before loading any config file. This weird requirement on
# the loading order should be changed.
def load_config(source):
    if isinstance(source, ConfigObj):
        config = source
    else:
        config = ConfigObj(source, file_error=True)
    players = {}

    for player in config:
        id = p_unstr(player)
        host = config[player]['host']
        port = int(config[player]['port'])

        if 'prss_keys' in config[player]:
            keys = {}
            for subset in config[player]['prss_keys']:
                keys[s_unstr(subset)] = config[player]['prss_keys'][subset]

            dealer_keys = {}
            for dealer in config[player]['prss_dealer_keys']:
                d = d_unstr(dealer)
                dealer_keys[d] = {}

                # TODO: rewrite with shorter lines
                for subset in config[player]['prss_dealer_keys'][dealer]:
                    dealer_keys[d][s_unstr(subset)] = config[player]['prss_dealer_keys'][dealer][subset]

            players[id] = Player(id, host, port, keys, dealer_keys)

            # ID of player for which this config file was made
            owner_id = id
        else:
            players[id] = Player(id, host, port)

    return owner_id, players


def generate_configs(n, t, addresses=None, prefix=None):
    players = frozenset(range(1, n+1))
    max_unqualified_subsets = generate_subsets(players, n-t)
    # TODO: rand = SystemRandom()
    rand = Random(0)

    def generate_key():
        # TODO: is a 40 byte hex string as good as a 20 byte binary
        # string when it is used for SHA1 hashing? It ought to be
        # since they contain the same entropy.

        # A SHA1 hash is 160 bit
        return hex(rand.randint(0, 2**160))

    configs = {}
    for p in players:
        config = ConfigObj(indent_type='  ')
        config.filename = "%s-%d.ini" % (prefix, p)
        config.initial_comment = ['PySMPC config file for Player %d' % p]
        config.final_comment = ['', 'End of config', '']
        configs[p] = config

    for p in players:
        if addresses is None:
            host, port = 'no-host', 0
        else:
            host, port = addresses[p-1]

        for player, config in configs.iteritems():
            config[p_str(p)] = dict(host=host, port=port)
            # Attaching an empty string as a comment will result in a newline
            # in the configuration file, making it slightly easier to read
            config.comments[p_str(p)] = ['']

            if player == p:
                # Prepare the config file for the keys
                config[p_str(p)]['prss_keys'] = {}
                config[p_str(p)]['prss_dealer_keys'] = {}

                for d in players:
                    config[p_str(p)]['prss_dealer_keys'][d_str(d)] = {}

    for subset in max_unqualified_subsets:
        key = generate_key()
        for player in subset:
            config = configs[player]
            config[p_str(player)]['prss_keys'][s_str(subset)] = key

    for dealer in players:
        d = d_str(dealer)
        for subset in max_unqualified_subsets:
            s = s_str(subset)
            key = generate_key()
            for player in (subset | set([dealer])):
                p = p_str(player)

                configs[player][p]['prss_dealer_keys'][d][s] = key

    return configs


if __name__ == "__main__":
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
