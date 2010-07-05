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

"""Full threshold actively secure runtime."""

from twisted.internet.defer import Deferred, gatherResults, succeed

from viff.runtime import Runtime, Share, ShareList

from hash_broadcast import HashBroadcastMixin

class BeDOZaException(Exception):
    pass

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

    def __init__(self, runtime, field, value=None, authentication_codes=None):
        self.share = value
        self.authentication_codes = authentication_codes
        Share.__init__(self, runtime, field, (value, authentication_codes))

class RandomShareGenerator:

    def authentication_codes(self, alpha, betas, v):
        auth_codes = []
        for beta in betas:
            auth_codes.append(alpha*v + beta)
        return auth_codes

    def generate_random_shares(self, field, number_of_shares):
        alpha = self.get_keys()[0]
        shares = []
        for i in xrange(0, number_of_shares):
            if self.id == 1:
                betas = map(lambda (alpha, betas): betas[0], self.keys.values())
                v = field(1)
                auth_codes= self.authentication_codes(alpha, betas, v)
                shares.append(BeDOZaShare(self, field, v, auth_codes))
            if self.id == 2:
                betas = map(lambda (alpha, betas): betas[1], self.keys.values())
                v = field(2)
                auth_codes= self.authentication_codes(alpha, betas, v)
                shares.append(BeDOZaShare(self, field, v, auth_codes))
            if self.id == 3:
                betas = map(lambda (alpha, betas): betas[2], self.keys.values())
                v = field(3)
                auth_codes= self.authentication_codes(alpha, betas, v)
                shares.append(BeDOZaShare(self, field, v, auth_codes))
        return shares

class KeyLoader:

    def load_keys(self, field):
        alpha = field(2)
        return {1: (alpha, [field(1), field(2), field(3)]),
                2: (alpha, [field(4), field(5), field(6)]),
                3: (alpha, [field(7), field(8), field(9)])}

class BeDOZaRuntime(Runtime, HashBroadcastMixin, KeyLoader, RandomShareGenerator):
    """The BeDOZa runtime.

    The runtime is used for sharing values (:meth:`secret_share` or
    :meth:`shift`) into :class:`BeDOZaShare` object and opening such
    shares (:meth:`open`) again. Calculations on shares is normally
    done through overloaded arithmetic operations, but it is also
    possible to call :meth:`add`, :meth:`mul`, etc. directly if one
    prefers.

    Each player in the protocol uses a :class:`~viff.runtime.Runtime`
    object. To create an instance and connect it correctly with the
    other players, please use the :func:`~viff.runtime.create_runtime`
    function instead of instantiating a Runtime directly. The
    :func:`~viff.runtime.create_runtime` function will take care of
    setting up network connections and return a :class:`Deferred`
    which triggers with the :class:`~viff.runtime.Runtime` object when
    it is ready.
    """

    def __init__(self, player, threshold=None, options=None):
        """Initialize runtime."""
        Runtime.__init__(self, player, threshold, options)
        self.threshold = self.num_players - 1
        self.random_share_number = 100
        self.random_shares = []
 
    def MAC(self, alpha, beta, v):
         return alpha*v + beta

    def random_share(self, field):
        """Retrieve a previously generated random share in the field, field.

        If no more shares are left, generate self.random_share_number new ones.
        """
        self.keys = self.load_keys(field)
        if len(self.random_shares) == 0:
            self.random_shares = self.generate_random_shares(field, self.random_share_number)

        return self.random_shares.pop()

    def output(self, share, receivers=None):
        return self.open(share, receivers)

    def open(self, share, receivers=None):
        """Share reconstruction.
 
        Every partyi broadcasts a share pair ``(x_i', rho_x,i')``.

        The parties compute the sums ``x'``, ``rho_x'`` and check
        ``Com_ck(x',rho_x') = C_x``.

        If yes, return ``x = x'``, else else return :const:`None`.
        """
        assert isinstance(share, Share)
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()

        field = share.field

        self.increment_pc()

        def recombine_value(shares_codes):
            isOK = True
            n = len(self.players)
            alpha = self.get_keys()[0]
            keys = self.get_keys()[1]
            x = 0
            for inx in xrange(0, n):
                xi = shares_codes[inx]
                mi = shares_codes[n + inx]
                beta = keys[inx]
                x += xi
                isOK = isOK and mi == self.MAC(alpha, beta, xi)
            if not isOK:
                raise BeDOZaException("Wrong commitment for value %s." % x)
            return x

        def exchange((xi, codes), receivers):
            # Send share to all receivers.
            pc = tuple(self.program_counter)
            for other_id in receivers:
                self.protocols[other_id].sendShare(pc, xi)
                self.protocols[other_id].sendShare(pc, codes[other_id - 1])

            if self.id in receivers:
                num_players = len(self.players.keys())
                values = num_players * [None]
                codes = num_players * [None]
                for inx, other_id in enumerate(self.players.keys()):
                    values[inx] =  self._expect_share(other_id, field)
                    codes[inx] = self._expect_share(other_id, field)
                result = gatherResults(values + codes)
                result.addCallbacks(recombine_value, self.error_handler)
                return result

        result = share.clone()
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def get_keys(self):
        if self.id == 1:
            return self.keys[1]
        if self.id == 2:
            return self.keys[2]
        if self.id == 3:
            return self.keys[3]
