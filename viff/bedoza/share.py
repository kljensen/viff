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

from twisted.internet.defer import gatherResults

from viff.bedoza.shares import PartialShareContents
from viff.bedoza.util import _convolute

def generate_partial_share_contents(field_elements, runtime, paillier):
    """Each party input a list of field elements *field_elements*.
    The value of the field elements are encrypted and the encrypted
    values are exchanged.

    Returns a deferred, which yields a list of PartialShareContents.  
    """
    
    runtime.increment_pc()

    N_squared_list = [paillier.get_modulus_square(player_id)
                      for player_id in runtime.players]

    list_of_enc_shares = []
    for field_element in field_elements:
        list_of_enc_shares.append(paillier.encrypt(field_element.value))
       
    list_of_enc_shares = runtime.broadcast(runtime.players.keys(), runtime.players.keys(),
                                           str(list_of_enc_shares))
    
    def create_partial_share(list_of_enc_shares, field_elements):
        list_of_enc_shares = [eval(x) for x in list_of_enc_shares]

        reordered_encrypted_shares = [[] for _ in list_of_enc_shares[0]]
        for enc_shares in list_of_enc_shares:
            for inx, enc_share in enumerate(enc_shares):
                reordered_encrypted_shares[inx].append(enc_share)

        partialShareContents = []
        for enc_shares, field_element in zip(reordered_encrypted_shares, field_elements):
            partialShareContents.append(PartialShareContents(field_element, enc_shares, N_squared_list))
        return partialShareContents

    d = gatherResults(list_of_enc_shares)
    runtime.schedule_callback(d, create_partial_share, field_elements)
    return d
        
