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

from viff.runtime import Runtime, Share, ShareList, gather_shares
from viff.field import FieldElement

from viff.simplearithmetic import SimpleArithmetic

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

    def __init__(self, runtime, field, value=None, keyList=None, authentication_codes=None):
        self.share = value
        self.keyList = keyList
        self.authentication_codes = authentication_codes
        Share.__init__(self, runtime, field, (value, keyList, authentication_codes))

class BeDOZaKeyList(object):

    def __init__(self, alpha, keys):
        self.alpha = alpha
        self.keys = keys

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
    
class BeDOZaMessageList(object):

    def __init__(self, auth_codes):
        self.auth_codes = auth_codes

    def __add__(self, other):
        """Addition."""
        auth_codes = []
        for c1, c2 in zip(self.auth_codes, other.auth_codes):
            auth_codes.append(c1 + c2)
        return BeDOZaMessageList(auth_codes)

    def __sub__(self, other):
        """Subtraction."""
        auth_codes = []
        for c1, c2 in zip(self.auth_codes, other.auth_codes):
            auth_codes.append(c1 - c2)
        return BeDOZaMessageList(auth_codes)

    def __eq__(self, other):
        return self.auth_codes == other.auth_codes

    def __str__(self):
        return str(self.auth_codes)

    def __repr__(self):
        return str(self)
    
class RandomShareGenerator:

    def generate_random_shares(self, field, number_of_shares):
        shares = []
        for i in xrange(0, number_of_shares):
            if self.id == 1:
                v = field(1)
                shares.append(self.generate_share(field, v))
            if self.id == 2:
                v = field(2)
                shares.append(self.generate_share(field, v))
            if self.id == 3:
                v = field(3)
                shares.append(self.generate_share(field, v))
        return shares

    def generate_share(self, field, value):
        auth_codes = self.generate_auth_codes(self.id, value)
        my_keys = self.generate_keys()
        return BeDOZaShare(self, field, value, my_keys, auth_codes)

    def generate_auth_codes(self, playerId, value):
        keys = map(lambda (alpha, akeys): (alpha, akeys[playerId - 1]), self.keys.values())
        auth_codes = self.authentication_codes(keys, value)
        return auth_codes

    def authentication_codes(self, keys, v):
        auth_codes = []
        for alpha, beta in keys:
            auth_codes.append(alpha * v + beta)
        return BeDOZaMessageList(auth_codes)

    def generate_keys(self):
        alpha, betas = self.get_keys()
        return BeDOZaKeyList(alpha, betas)

class KeyLoader:

    def load_keys(self, field):
        return {1: (field(2), [field(1), field(2), field(3)]),
                2: (field(3), [field(4), field(5), field(6)]),
                3: (field(4), [field(7), field(8), field(9)])}

class BeDOZaRuntime(SimpleArithmetic, Runtime, HashBroadcastMixin, KeyLoader, RandomShareGenerator):
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
        return alpha * v + beta

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

        def recombine_value(shares_codes, keyList):
            isOK = True
            n = len(self.players)
            alpha = keyList.alpha
            keys = keyList.keys
            x = 0
            for inx in xrange(0, n):
                xi = shares_codes[inx]
                mi = shares_codes[n + inx]
                beta = keys[inx]
                x += xi
                mi_prime = self.MAC(alpha, beta, xi)
                if not (isOK and mi == mi_prime):
                    raise BeDOZaException("Wrong commitment, expected %s, got %s = %s*%s + %s." % (mi.value, mi_prime.value, alpha.value, xi.value, beta.value))
            return x

        def exchange((xi, keyList, codes), receivers):
            # Send share to all receivers.
            pc = tuple(self.program_counter)
            for other_id in receivers:
                self.protocols[other_id].sendShare(pc, xi)
                self.protocols[other_id].sendShare(pc, codes.auth_codes[other_id - 1])
            if self.id in receivers:
                num_players = len(self.players.keys())
                values = num_players * [None]
                codes = num_players * [None]
                for inx, other_id in enumerate(self.players.keys()):
                    values[inx] =  self._expect_share(other_id, field)
                    codes[inx] = self._expect_share(other_id, field)
                result = gatherResults(values + codes)
                result.addCallbacks(recombine_value, self.error_handler, callbackArgs=(keyList,))
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

    def get_alpha(self):
        return self.keys[0]

    def _plus_public(self, x, c, field):
        (xi, xks, xms) = x
        if self.id == 1:
            xi = xi + c
        xks.keys[0] = xks.keys[0] - xks.alpha * c
        return BeDOZaShare(self, field, xi, xks, xms)

    def _plus(self, (x, y), field):
        """Addition of share-tuples *x* and *y*.

        Each party ``P_i`` computes:
        ``[x]_i = (x_i, xk, xm)``
        ``[y]_i = (y_i, yk, ym)``
        ``[z]_i = [x]_i + [y]_i
                = (x_i + y_i mod p, {xk^{i}_{j} + yk^{i}_{j} mod p}_{j=0}^{j=n}, {xm^{i}_{j} + ym^{i}_{j} mod p}_{j=0}^{j=n})
        """
        (xi, xks, xms) = x
        (yi, yks, yms) = y
        zi = xi + yi
        zks = xks + yks
        zms = xms + yms
        return (zi, zks, zms)

    def _minus_public_right(self, x, c, field):
        (xi, xks, xms) = x
        if self.id == 1:
            xi = xi - c
        xks.keys[0] = xks.keys[0] + xks.alpha * c
        return BeDOZaShare(self, field, xi, xks, xms)

    def _minus_public_left(self, x, c, field):
        y = self._constant_multiply(x, field(-1))
        return self._plus_public(y, c, field)
    
    def _minus(self, (x, y), field):
        """Subtraction of share-tuples *x* and *y*.

        Each party ``P_i`` computes:
        ``[x]_i = (x_i, xk, xm)``
        ``[y]_i = (y_i, yk, ym)``
        ``[z]_i = [x]_i - [y]_i
                = (x_i - y_i mod p, {xk^{i}_{j} - yk^{i}_{j} mod p}_{j=0}^{j=n}, {xm^{i}_{j} - ym^{i}_{j} mod p}_{j=0}^{j=n})
        """
        (xi, xks, xms) = x
        (yi, yks, yms) = y
        zi = xi - yi
        zks = xks - yks
        zms = xms - yms
        return (zi, zks, zms)

    def _cmul(self, share_x, share_y, field):
        """Multiplication of a share with a constant.

        Either share_x or share_y must be a BeDOZaShare but not
        both. Returns None if both share_x and share_y are
        BeDOZaShares.
        """
        if not isinstance(share_x, Share):
            # Then share_y must be a Share => local multiplication. We
            # clone first to avoid changing share_y.
            assert isinstance(share_y, Share), \
                "At least one of the arguments must be a share."
            result = share_y.clone()
            result.addCallback(self._constant_multiply, share_x)
            return result
        if not isinstance(share_y, Share):
            # Likewise when share_y is a constant.
            assert isinstance(share_x, Share), \
                "At least one of the arguments must be a share."
            result = share_x.clone()
            result.addCallback(self._constant_multiply, share_y)
            return result
        return None

    def _constant_multiply(self, x, c):
        """Multiplication of a share-tuple with a constant c."""
        assert(isinstance(c, FieldElement))
        xi, xks, xms = x
        zi = c * xi
        zks = BeDOZaKeyList(xks.alpha, map(lambda k: c * k, xks.keys))
        zms = BeDOZaMessageList(map(lambda m: c * m, xms.auth_codes))
        return (zi, zks, zms)
