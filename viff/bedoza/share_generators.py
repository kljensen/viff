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

from viff.bedoza.shares import BeDOZaShare, BeDOZaShareContents, PartialShare
from viff.bedoza.shares import PartialShareContents
from viff.bedoza.util import _convolute
from viff.bedoza.add_macs import add_macs

class PartialShareGenerator(object):

    def __init__(self, Zp, runtime, random, paillier):
        self.paillier = paillier
        self.Zp = Zp
        self.runtime = runtime
        self.random = random

    def generate_share(self, value):
        self.runtime.increment_pc()
        
        # TODO: Exclusive?
        r = [self.Zp(self.random.randint(0, self.Zp.modulus - 1))
             for _ in range(self.runtime.num_players - 1)]
        if self.runtime.id == 1:
            share = value - sum(r)
        else:
            share = r[self.runtime.id - 2]
        enc_share = self.paillier.encrypt(share.value)
        enc_shares = _convolute(self.runtime, enc_share)
        def create_partial_share(enc_shares, share):
            return PartialShare(self.runtime, self.Zp, share, enc_shares)
        self.runtime.schedule_callback(enc_shares, create_partial_share, share)
        return enc_shares

    def generate_random_shares(self, n):
        self.runtime.increment_pc()
        N_squared_list = [self.runtime.players[player_id].pubkey['n_square']
                          for player_id in self.runtime.players]
        shares = [PartialShare(self.runtime, self.Zp) for _ in xrange(n)]
        for inx in xrange(n):
            r = self.random.randint(0, self.Zp.modulus - 1)
            ri = self.Zp(r)
            enc_share = self.paillier.encrypt(ri.value)
            enc_shares = _convolute(self.runtime, enc_share)
            def create_partial_share(enc_shares, ri, s, N_squared_list):
                s.callback(PartialShareContents(ri, enc_shares,
                                                N_squared_list))
            self.runtime.schedule_callback(enc_shares,
                                           create_partial_share,
                                           ri,
                                           shares[inx],
                                           N_squared_list)
        return shares

class ShareGenerator(PartialShareGenerator):

    def __init__(self, Zp, runtime, random, paillier, u_bound, alpha):
        self.u_bound = u_bound
        self.alpha = alpha
        PartialShareGenerator.__init__(self, Zp, runtime, random, paillier)

    def generate_share(self, value):
        self.runtime.increment_pc()
        partial_share = PartialShareGenerator.generate_share(self, value)
        full_share = add_macs(self.runtime, self.Zp, self.u_bound, self.alpha,
                             self.random, self.paillier, [partial_share])
        return full_share[0]
    
    def generate_random_shares(self, n):
        self.runtime.increment_pc()
        partial_shares = PartialShareGenerator.generate_random_shares(self, n)
        return add_macs(self.runtime, self.Zp, self.u_bound, self.alpha,
                        self.random, self.paillier, partial_shares)
