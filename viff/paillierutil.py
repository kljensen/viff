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

from viff import paillier

try:
    import pypaillier
except ImportError:
    pypaillier = None

try:
    import tripple

except ImportError:
    tripple = None


class Paillier:

    def __init__(self, keysize):
        self.keysize = keysize
        self.type = 'Unknown'

    def generate_keys(self):
        pass


class ViffPaillier:

    def __init__(self, keysize):
        self.keysize = keysize
        self.type = 'viff'

    def generate_keys(self):
        return paillier.generate_keys(self.keysize)

class NaClPaillier:

    def __init__(self, keysize):
        self.keysize = keysize
        self.type = 'nacl'

    def generate_keys(self):
        return pypaillier.generate_keys(self.keysize)  

def deserializ_seckey(str):
    d = {}
    for k, v in str.items():
        d[k] = long(v)
    return d

def deserializ_pubkey(paillier_type, str):
        pubkey = {}
        for k, v in str.items():
            pubkey[k] = long(v)
        if paillier_type == "nacl":
            g1 = pypaillier.encrypt_r(1, 1, pubkey)
            pubkey['fixed_base'] = tripple.init(g1, pubkey['n_square'])            
        return pubkey



