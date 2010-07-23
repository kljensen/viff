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

from viff.runtime import Share

from viff.bedoza.keylist import BeDOZaKeyList
from viff.bedoza.maclist import BeDOZaMACList

class PartialShareContents(object):
    """A BeDOZa share without macs, e.g. < a >.
    TODO: BeDOZaShare should extend this class?
    
    TODO: Should the partial share contain the public encrypted shares?
    TODO: It may be wrong to pass encrypted_shares to super constructor; 
      does it mean that the already public values get passed along on the
      network even though all players already posess them?
    """
    def __init__(self, value, enc_shares, N_squared_list):
        self.value = value
        self.enc_shares = enc_shares
        self.N_squared_list = N_squared_list

    def __str__(self):
        return "PartialShareContents(%d; %s; %s)" % (self.value, self.enc_shares, self.N_squared_list)

    def __add__(self, other):
        z = self.value + other.value
        z_enc_shares = []
        for x, y, N_squared in zip(self.enc_shares, other.enc_shares, self.N_squared_list):
            z_enc_shares.append((x * y) % N_squared)
        return PartialShareContents(z, z_enc_shares, self.N_squared_list)


# In VIFF, callbacks get the *contents* of a share as input. Hence, in order
# to get a PartialShare as input to callbacks, we need this extra level of
# wrapper indirection.
class PartialShare(Share):
    def __init__(self, runtime, field, value=None, enc_shares=None):
        if value == None and enc_shares == None:
            Share.__init__(self, runtime, field)
        else:
            N_squared_list = [ runtime.players[player_id].pubkey['n_square'] for player_id in runtime.players.keys()]
            partial_share_contents = PartialShareContents(value, enc_shares, N_squared_list)
            Share.__init__(self, runtime, field, partial_share_contents)


class BeDOZaShareContents(object):

    def __init__(self, value, keyList, macs):
        self.value = value
        self.keyList = keyList
        self.macs = macs

    def get_value(self):
        return self.value

    def get_keys(self):
        return self.keyList

    def get_macs(self):
        return self.macs

    def get_mac(self, inx):
        return self.macs.get_mac(inx)

    def __add__(self, other):
        zi = self.value + other.value
        zks = self.keyList + other.keyList
        zms = self.macs + other.macs
        return BeDOZaShareContents(zi, zks, zms)

    def __sub__(self, other):
        zi = self.value - other.value
        zks = self.keyList - other.keyList
        zms = self.macs - other.macs
        return BeDOZaShareContents(zi, zks, zms)

    def add_public(self, c, my_id):
        if my_id == 1:
            self.value = self.value + c
        self.keyList.set_key(0, self.keyList.get_key(0) - self.keyList.alpha * c)
        return self
    
    def sub_public(self, c, my_id):
        if my_id == 1:
            self.value = self.value - c
        self.keyList.set_key(0, self.keyList.get_key(0) + self.keyList.alpha * c)
        return self

    def cmul(self, c):
        zi = c * self.value
        zks = self.keyList.cmul(c)
        zms = self.macs.cmul(c)
        return BeDOZaShareContents(zi, zks, zms)

    def __str__(self):
        return "(%s, %s, %s)" % (str(self.value), str(self.keyList), str(self.macs))
    
class BeDOZaShare(Share):
    """A share in the BeDOZa runtime.

    A share in the BeDOZa runtime is a pair ``(x_i, authentication_codes)`` of:

    - A share of a number, ``x_i``
    - A list of authentication_codes, ``authentication_codes``

    The :class:`Runtime` operates on shares, represented by this class.
    Shares are asynchronous in the sense that they promise to attain a
    value at some point in the future.

    Shares overload the arithmetic operations so that ``x = a + b``
    will create a new share *x*, which will eventually contain the
    sum of *a* and *b*. Each share is associated with a
    :class:`Runtime` and the arithmetic operations simply call back to
    that runtime.
    """

    def __init__(self, runtime, field, value=None, keyList=None, authentication_codes=None):
        if value == None and keyList == None and authentication_codes == None:
            Share.__init__(self, runtime, field)
        else:
            Share.__init__(self, runtime, field, BeDOZaShareContents(value, keyList, authentication_codes))
