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

import struct

from twisted.internet.defer import gatherResults
from viff.runtime import Share

from viff.bedoza.util import _send
from viff.bedoza.keylist import BeDOZaKeyList
from viff.bedoza.maclist import BeDOZaMACList

from viff.bedoza.shares import BeDOZaShare, BeDOZaShareContents


def add_macs(runtime, field, u_bound, alpha, random, paillier, partial_shares):
    """Adds macs to the set of PartialBeDOZaShares.
        
    Returns a deferred which yields a list of full shares, e.g.
    including macs.  (the full shares are deferreds of type
    BeDOZaShare.)
    """        
    # TODO: Would be nice with a class ShareContents like the class
    # PartialShareContents used here.
        
    runtime.increment_pc() # Huh!?

    def do_add_macs(partial_share_contents, result_shares):
        """The transmission_restraint_constant is the number of
        encrypted shares we can safely transmit in one call to
        sendData. The sendData method can only transmit up to
        65536 bytes.
        The constant has been imperically determined by running
        TripleGenerator.generate_triples.
        TODO: How can we allow a user of the runtime to adjust this
        constraint at a higher level of abstraction?
        """
        transmission_restraint_constant = 50
        
        num_players = runtime.num_players

        list_of_player_to_enc_shares_lists = []
        
        player_to_mac_keys = [ [] for x in runtime.players]
        player_to_enc_shares = [ [] for x in runtime.players]
        for inx, partial_share_content in enumerate(partial_share_contents):
            if inx % transmission_restraint_constant == 0:
                player_to_enc_shares = [ [] for x in runtime.players]
                list_of_player_to_enc_shares_lists.append(player_to_enc_shares)
            for j in xrange(num_players):
                # TODO: This is probably not the fastes way to generate
                # the betas.
                beta = random.randint(0, u_bound)
                if random.choice([True, False]):
                    beta = -beta
                enc_beta = paillier.encrypt(beta, player_id = j + 1)
                c_j = partial_share_content.enc_shares[ j ]
                n2 = paillier.get_modulus_square( j + 1 )
                c = (pow(c_j, alpha, n2) * enc_beta) % n2
                player_to_enc_shares[j].append(c)
                player_to_mac_keys[j].append(field(beta))

        received_cs = []
        for ls in list_of_player_to_enc_shares_lists:
            received_cs.append(_send(runtime, ls, deserialize=eval))

        def merge(received_cs):
            r = [ [] for x in xrange(len(received_cs[0]))]
            for ls in received_cs:
                for inx, xs in enumerate(ls):
                    r[inx] += xs
            return r

        def finish_sharing(recevied_cs, partial_share_contents,
                           lists_of_mac_keys, result_shares):
            recevied_cs = merge(recevied_cs)
            shares = []               
            for inx in xrange(0, len(partial_share_contents)):
                mac_keys = []
                decrypted_cs = []
                for c_list, mkeys in zip(recevied_cs,
                                         lists_of_mac_keys):
                    decrypted_cs.append(field(paillier.decrypt(c_list[inx])))
                    mac_keys.append(mkeys[inx])
                partial_share = partial_share_contents[inx]
                mac_key_list = BeDOZaKeyList(alpha, mac_keys)

                mac_msg_list = BeDOZaMACList(decrypted_cs)
                result_shares[inx].callback(
                    BeDOZaShareContents(partial_share.value, mac_key_list,
                                        mac_msg_list))
            return shares

        runtime.schedule_callback(gatherResults(received_cs),
                                  finish_sharing,
                                  partial_share_contents,
                                  player_to_mac_keys,
                                  result_shares)
        return received_cs

    result_shares = [Share(runtime, field)
                     for x in xrange(len(partial_shares))]
    runtime.schedule_callback(gatherResults(partial_shares),
                              do_add_macs,
                              result_shares)
    return result_shares
