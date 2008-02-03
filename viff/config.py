# Copyright 2007, 2008 VIFF Development Team.
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

"""Functions for loading and saving player configurations.

Each player participating in a protocol execution must know some
information about the other players, namely their hostname and port
number. The player also needs to know something about itself, namely
the keys used for pseudo-random secret sharing (PRSS).

The L{Player} class encapsulates this information. Generating a player
configuration is done using the L{generate_configs} function. The
C{apps/generate_config_files.py} script uses that function to generate
a player config and save it in a number of .ini files. Such a .ini
file can be loaded with the L{load_config} function.
"""

from configobj import ConfigObj

from viff.prss import generate_subsets, PRF
from viff.util import rand

class Player:
    """Wrapper for information about a player in the protocol."""

    def __init__(self, id, host, port, keys=None, dealer_keys=None):
        """Initialize a player."""
        self.id = id
        self.host = host
        self.port = port
        self.keys = keys
        self.dealer_keys = dealer_keys

    # TODO: the PRFs ought to be cached
    def prfs(self, modulus):
        """Retrieve PRSS PRFs.

        The pseudo-random functions are used when this player is part
        of a pseudo-random secret sharing for sharing an element
        random to all players.

        @return: mapping from player subsets to L{PRF} instances.
        @returntype: L{dict} from L{frozenset} to L{PRF} instances.
        """
        prfs = {}
        for subset, key in self.keys.iteritems():
            prfs[subset] = PRF(key, modulus)
        return prfs

    # TODO: the PRFs ought to be cached
    def dealer_prfs(self, modulus):
        """Retrieve dealer PRSS PRFs.

        The pseudo-random functions are used when this player is the
        dealer in a pseudo-random secret sharing.

        @return: mapping from player subsets to L{PRF} instances.
        @returntype: L{dict} from L{frozenset} to L{PRF} instances.
        """
        dealers = {}
        for dealer, keys in self.dealer_keys.iteritems():
            prfs = {}
            for subset, key in keys.iteritems():
                prfs[subset] = PRF(key, modulus)
                dealers[dealer] = prfs
        return dealers

    def __repr__(self):
        """Simple string representation of the player."""
        return "<Player %d: %s:%d>" % (self.id, self.host, self.port)

def load_config(source):
    """Load a player configuration file.

    Configuration files are simple INI-files containing information
    (hostname and port number) about the other players in the
    protocol.

    One of the players own the config file and for this player
    additional information on PRSS keys is available.

    @return: owner ID and a mapping of player IDs to players.
    @returntype: C{int}, C{dict} from C{int} to L{Player} instances.
    """
    def s_unstr(str):
        """Convert a string to a subset ID."""
        return frozenset(map(int, str.split()))

    def p_unstr(str):
        """Convert a string to a player ID."""
        return int(str[7:])

    def d_unstr(str):
        """Convert a string to a dealer ID."""
        return int(str[7:])
    
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
    """Generate player configurations.

    The configurations are returned as C{ConfigObj}s and can be saved
    to disk if desired.

    @param n: number of players.
    @param t: threshold.
    @param addresses: list of (host, port) pairs.
    @param prefix: filename prefix.

    @return: mapping from player id to player configuration.
    @returntype: C{dict} from C{int} to C{ConfigObj}.
    """    
    players = frozenset(range(1, n+1))
    max_unqualified_subsets = generate_subsets(players, n-t)

    def generate_key():
        # TODO: is a 40 byte hex string as good as a 20 byte binary
        # string when it is used for SHA1 hashing? It ought to be
        # since they contain the same entropy.

        # A SHA1 hash is 160 bit
        return hex(rand.randint(0, 2**160))

    def s_str(subset):
        """Convert a subset to a string."""
        return " ".join(map(str, subset))

    def p_str(player):
        """Convert a player ID to a string."""
        return "Player " + str(player)

    def d_str(dealer):
        """Convert a dealer ID to a string."""
        return "Dealer " + str(dealer)

    configs = {}
    for p in players:
        config = ConfigObj(indent_type='  ')
        config.filename = "%s-%d.ini" % (prefix, p)
        config.initial_comment = ['VIFF config file for Player %d' % p]
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
