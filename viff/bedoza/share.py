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

from gmpy import mpz

from twisted.internet.defer import gatherResults

from viff.bedoza.zero_knowledge import ZKProof
from viff.bedoza.shares import PartialShareContents

def generate_partial_share_contents(field_elements, runtime, paillier, k, random):
    """Protocol for generating partial shares.

    This protocol corresponds to the "Share" protocol in the document
    "A new On- and Off-line Phase for MPC".

    Each party inputs a list of field elements *field_elements*. The
    values of the field elements are encrypted, the encrypted values
    are exchanged, and for each player, a zero-knowledge proof is
    carried out, proving that each player knows the plaintexts
    corresponding to the ciphertexts, he broadcasts, and that the
    plaintexts are of limited size.

    Returns a deferred, which yields a list of PartialShareContents.

    """    
    # TODO: We should assert that len(field_elements) == s.

    # TODO: The gatherResults is used several times in this method in
    # a way that prevents maximal asynchronicity. E.g. all players
    # wait until all zero-knowledge proofs are completed before they
    # start constructing partial shares. However, the callback for a
    # particular partial share could be triggered as soon as the
    # players have completed the zk proof for that share.

    runtime.increment_pc()

    N_squared_list = [paillier.get_modulus_square(player_id)
                      for player_id in runtime.players]

    list_of_enc_shares = []
    list_of_random_elements = []
    for field_element in field_elements:
        r, e = paillier.encrypt_r(field_element.value)
        list_of_enc_shares.append(e)
        list_of_random_elements.append(r)
       
    list_of_enc_shares = runtime.broadcast(
        runtime.players.keys(), runtime.players.keys(),
        str(list_of_enc_shares))

    def construct_partial_shares(zk_results, list_of_enc_shares, field_elements):
        if False in zk_results:
            raise Exception("Zero-knowledge proof failed")
        reordered_encrypted_shares = [[] for _ in list_of_enc_shares[0]]
        for enc_shares in list_of_enc_shares:
            for inx, enc_share in enumerate(enc_shares):
                reordered_encrypted_shares[inx].append(enc_share)
        partial_share_contents = []
        for enc_shares, field_element \
                in zip(reordered_encrypted_shares, field_elements):
            partial_share_contents.append(PartialShareContents(
                    field_element, enc_shares, N_squared_list))
        return partial_share_contents

    def do_zk_proofs(list_of_enc_shares, field_elements):
        zk_results = []
        list_of_enc_shares = [eval(x) for x in list_of_enc_shares]

        # We expect all players to broadcast the same number of
        # encrypted shares.
        assert all([len(enc_shares) == len(list_of_enc_shares[0]) 
                    for enc_shares in list_of_enc_shares])

        for i in range(runtime.num_players):
            x, r = None, None
            if runtime.id == i + 1:
                x, r = [mpz(e.value) 
                        for e in field_elements], list_of_random_elements
            zk_proof = ZKProof(
                len(field_elements), i + 1, k, runtime, list_of_enc_shares[i],
                random=random, x=x, r=r, paillier=paillier)
            zk_result = zk_proof.start()
            zk_results.append(zk_result)
        d = gatherResults(zk_results)
        runtime.schedule_callback(
            d, construct_partial_shares, list_of_enc_shares, field_elements)
        return d

    d = gatherResults(list_of_enc_shares)
    runtime.schedule_callback(d, do_zk_proofs, field_elements)
    return d
