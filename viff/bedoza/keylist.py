# Copyright 2010 VIFF Development Team.
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

class BeDOZaKeyList(object):
    """A list of keys, one for each player.

    We assume that the key for player *i* is stored in
    location *i - 1* in the *keys* list given as argument to the constructor.
    """

    def __init__(self, alpha, keys):
        self.alpha = alpha
        self.keys = keys

    def get_key(self, player_id):
        return self.keys[player_id]

    def set_key(self, player_id, v):
        self.keys[player_id] = v

    def cmul(self, c):
        return BeDOZaKeyList(self.alpha, map(lambda k: c * k, self.keys))

    def __add__(self, other):
        """Addition."""
        assert self.alpha == other.alpha
        keys = []
        for k1, k2 in zip(self.keys, other.keys):
            keys.append(k1 + k2)
        return BeDOZaKeyList(self.alpha, keys)

    def __sub__(self, other):
        """Subtraction."""
        assert self.alpha == other.alpha
        keys = []
        for k1, k2 in zip(self.keys, other.keys):
            keys.append(k1 - k2)
        return BeDOZaKeyList(self.alpha, keys)

    def __eq__(self, other):
        return self.alpha == other.alpha and self.keys == other.keys

    def __str__(self):
        return "(%s, %s)" % (self.alpha, str(self.keys))

    def __repr__(self):
        return str(self)

