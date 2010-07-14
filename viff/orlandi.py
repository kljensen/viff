# Copyright 2009 VIFF Development Team.
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

"""Full threshold actively secure runtime.

.. warning:: The code in this module relies on a proprietary
   third-party module for doing commitments using elliptic curves. You
   will therefore not be able to run it with a plain VIFF
   installation.
"""

import operator

from twisted.internet.defer import Deferred, gatherResults, succeed

from viff.runtime import Share, gather_shares, preprocess
from viff.util import rand
from viff.constants import TEXT, PAILLIER
from viff.field import FieldElement
from viff.paillier import encrypt_r, decrypt

from viff.simplearithmetic import SimpleArithmeticRuntime

from hash_broadcast import HashBroadcastMixin

try:
    from pypaillier import encrypt_r, decrypt, tripple_2c, tripple_3a

except ImportError:
    # The pypaillier module is not released yet, so we cannot expect
    # the import to work.
    print "Error: The pypaillier module or one of the used functions are not available."

try:
    import commitment
    commitment.set_reference_string(23434347834783478783478L,
                                    489237823478234783478020L)
except ImportError:
    # The commitment module is not public, so we cannot expect the
    # import to work. Catching the ImportError here allows the
    # benchmark and tests to import viff.orlandi without blowing up.
    # It is only if the OrlandiRuntime is used that things blow up.
    print "Error: The commitment module is not available."

try:
    import tripple

except ImportError:
    # The tripple module is not released yet, so we cannot expect
    # the import to work.
    print "Error: The tripple module is not available."

# import logging
# LOG_FILENAME = 'logging_example.out'
# logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,)

class OrlandiException(Exception):
    pass

class OrlandiShare(Share):
    """A share in the Orlandi runtime.

    A share in the Orlandi runtime is a 3-tuple ``(x_i, rho_i, Cr_i)`` of:

    - A share of a number, ``x_i``
    - A tuple of two random numbers, ``rho_i = (rho_i1, rho_i2)``
    - A commitment to the number and the random numbers, ``Cr_i``

    The :class:`Runtime` operates on shares, represented by this class.
    Shares are asynchronous in the sense that they promise to attain a
    value at some point in the future.

    Shares overload the arithmetic operations so that ``x = a + b``
    will create a new share *x*, which will eventually contain the
    sum of *a* and *b*. Each share is associated with a
    :class:`Runtime` and the arithmetic operations simply call back to
    that runtime.
    """

    def __init__(self, runtime, field, value=None, rho=None, commitment=None):
        self.share = value
        self.rho = rho
        self.commitment = commitment
        Share.__init__(self, runtime, field, (value, rho, commitment))
      
class OrlandiMixin(HashBroadcastMixin):

    def compute_delta(self, d):
        def product(j):
            pt = 1
            pn = 1
            for k in xrange(1, 2 * d + 2):
                if k != j:
                    pt *= k
                    pn *= k - j
            return pt // pn

        delta = []
        for j in xrange(1, 2 * d + 2):
            delta.append(product(j))
        return delta

    def output(self, share, receivers=None):
        return self.open(share, receivers)

    def _send_orlandi_share(self, other_id, pc, xi, rhoi, Cx):
        """Send the share *xi*, *rhoi*, and the commitment *Cx* to
        party *other_id*."""
        self.protocols[other_id].sendShare(pc, xi)
        self.protocols[other_id].sendShare(pc, rhoi[0])
        self.protocols[other_id].sendShare(pc, rhoi[1])
        self.protocols[other_id].sendData(pc, TEXT, repr(Cx))

    def _expect_orlandi_share(self, peer_id, field):
        """Waits for a number ``x``, ``rho``, and the commitment for
        ``x``."""
        xi = self._expect_share(peer_id, field)
        Cx = Deferred()
        rhoi1 = self._expect_share(peer_id, field)
        rhoi2 = self._expect_share(peer_id, field)
        self._expect_data(peer_id, TEXT, Cx)
        sls = gather_shares([xi, rhoi1, rhoi2, Cx])
        def combine(ls):
            xi = ls[0]
            rhoi1 = ls[1]
            rhoi2 = ls[2]
            Cx = ls[3]
            Cxx = commitment.deserialize(Cx)
            return OrlandiShare(self, field, xi, (rhoi1, rhoi2), Cxx)
        sls.addCallbacks(combine, self.error_handler)
        return sls

    def secret_share(self, inputters, field, number=None):
        """Share the value *number* among all the parties using
        additive sharing.

        To share an element ``x in Z_p``, choose random ``x_1, ...,
        x_n-1 in Z_p``, define ``x_n = x - SUM_i=1^n-1 x_i mod p``.

        Choose random values ``rho_x1, ..., rho_xn in (Z_p)^2``,
        define ``rho_x = SUM_i=1^n rho_x,i`` and ``C_x = Com_ck(x,
        p_x)``.

        Send ``[x]_i = (x_i, rho_xi, C_x)`` to party ``P_i``.
        """
        assert number is None or self.id in inputters

        self.increment_pc()

        def additive_shares_with_rho(x):
            """Returns a tuple of a list of tuples (player id, share,
            rho) and rho.

            Chooses random elements ``x_1, ..., x_n-1`` in field and
            ``x_n`` st. ``x_n = x - Sum_i=1^n-1 x_i``.

            Chooses random pair of elements ``rho_1, ..., rho_n in
            Z_p^2`` and define ``rho_n = Sum_i=1^n rho_i``.

            Returns a pair of ``((player id, x_i, rho_i), rho)``.
            """
            shares = []
            rhos = []
            sum = 0
            rho1 = 0
            rho2 = 0
            for i in xrange(1, self.num_players):
                xi = field(rand.randint(0, field.modulus - 1))
                rhoi1 = field(rand.randint(0, field.modulus - 1))
                rhoi2 = field(rand.randint(0, field.modulus - 1))
                sum += xi
                rho1 += rhoi1
                rho2 += rhoi2
                shares.append((i, xi, (rhoi1, rhoi2)))
            xn = field(x) - sum
            rhon1 = field(rand.randint(0, field.modulus - 1))
            rhon2 = field(rand.randint(0, field.modulus - 1))
            shares.append((self.num_players, xn, (rhon1, rhon2)))
            rho1 += rhon1
            rho2 += rhon2
            return shares, (rho1, rho2)

        # Send ``[x]_i = (x_i, rho_x,i, C_x)`` to party ``P_i``.
        results = []
        for peer_id in inputters:
            if peer_id == self.id:
                pc = tuple(self.program_counter)
                shares, rho = additive_shares_with_rho(number)
                Cx = commitment.commit(number, rho[0].value, rho[1].value)
                # Distribute the shares
                for other_id, xi, rhoi in shares:
                    # Send ``xi``, ``rhoi``, and commitment
                    self._send_orlandi_share(other_id, pc, xi, rhoi, Cx)
            # Expect ``xi``, ``rhoi``, and commitment
            results.append(self._expect_orlandi_share(peer_id, field))
        # do actual communication
        self.activate_reactor()
        # Unpack a singleton list.
        if len(results) == 1:
            return results[0]
        return results

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

        def recombine_value(shares, Cx):
            x = 0
            rho1 = 0
            rho2 = 0
            for xi, rhoi1, rhoi2 in shares:
                x += xi
                rho1 += rhoi1
                rho2 += rhoi2
            Cx1 = commitment.commit(x.value, rho1.value, rho2.value)
            if Cx1 == Cx:
                return x
            else:
                #return x
                raise OrlandiException("Wrong commitment for value %s, %s, %s, found %s expected %s." %
                                       (x, rho1, rho2, Cx1, Cx))

        def deserialize(ls):
            shares = [(field(long(x)), field(long(rho1)), field(long(rho2)))
                      for x, rho1, rho2 in map(self.list_str, ls)]
            return shares

        def exchange((xi, (rhoi1, rhoi2), Cx), receivers):
            # Send share to all receivers.
            ds = self.broadcast(self.players.keys(), receivers,
                                str((str(xi.value),
                                     str(rhoi1.value),
                                     str(rhoi2.value))))

            if self.id in receivers:
                result = gatherResults(ds)
                result.addCallbacks(deserialize, self.error_handler)
                result.addCallbacks(recombine_value, self.error_handler,
                                    callbackArgs=(Cx,))
                return result

        result = share.clone()
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def open_two_values(self, share_a, share_b, receivers=None):
        """Share reconstruction of two shares."""
        assert isinstance(share_a, Share)
        assert isinstance(share_b, Share)
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()

        field = share_a.field

        self.increment_pc()

        def recombine_value(shares, Ca, Cb):
            a, b = 0, 0
            rhoa1, rhob1 = 0, 0
            rhoa2, rhob2 = 0, 0
            for ai, rhoai1, rhoai2, bi, rhobi1, rhobi2 in shares:
                a += ai
                b += bi
                rhoa1 += rhoai1
                rhob1 += rhobi1
                rhoa2 += rhoai2
                rhob2 += rhobi2
            Ca1 = commitment.commit(a.value, rhoa1.value, rhoa2.value)
            Cb1 = commitment.commit(b.value, rhob1.value, rhob2.value)
            if Ca1 == Ca and Cb1 == Cb:
                return a, b
            else:
                #return x
                raise OrlandiException("Wrong commitment for value %s, %s, %s, %s, %s, %s, found %s, %s expected %s, %s." %
                                       (a, rhoa1, rhoa2, b, rhob1, rhob2, Ca1, Cb1, Ca, Cb))

        def deserialize(ls):
            shares = [(field(long(ai)), field(long(rhoa1)), field(long(rhoa2)),
                       field(long(bi)), field(long(rhob1)), field(long(rhob2)))
                      for ai, rhoa1, rhoa2, bi, rhob1, rhob2 in map(self.list_str, ls)]
            return shares

        def exchange((a, b), receivers):
            (ai, (rhoai1, rhoai2), Ca) = a
            (bi, (rhobi1, rhobi2), Cb) = b
            # Send share to all receivers.
            ds = self.broadcast(self.players.keys(), receivers,
                                str((str(ai.value),
                                     str(rhoai1.value),
                                     str(rhoai2.value),
                                     str(bi.value),
                                     str(rhobi1.value),
                                     str(rhobi2.value))))

            if self.id in receivers:
                result = gatherResults(ds)
                result.addCallbacks(deserialize, self.error_handler)
                result.addCallbacks(recombine_value, self.error_handler,
                                    callbackArgs=(Ca, Cb))
                return result

        result = gather_shares([share_a, share_b])
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def open_multiple_values(self, shares, receivers=None):
        """Share reconstruction.

        Open multiple values in one burst. 
        If called with one value it is slower than the open method.
        If called with more than two values it is faster than using 
        multiple calls to the open method. 

        Every partyi broadcasts a share pair ``(x_i', rho_x,i')``.

        The parties compute the sums ``x'``, ``rho_x'`` and check
        ``Com_ck(x',rho_x') = C_x``.

        If yes, return ``x = x'``, else else return :const:`None`.
        """
        assert shares
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()

        field = shares[0].field

        self.increment_pc()

        def recombine_value((shares, Cx)):
            x = 0
            rho1 = 0
            rho2 = 0
            for xi, rhoi1, rhoi2 in shares:
                x += xi
                rho1 += rhoi1
                rho2 += rhoi2
            Cx1 = commitment.commit(x.value, rho1.value, rho2.value)
            if Cx1 == Cx:
                return x
            else:
                #return x
                raise OrlandiException("Wrong commitment for value %s, %s, %s, found %s expected %s." %
                                       (x, rho1, rho2, Cx1, Cx))

        def deserialize(ls, commitments):
            def convert_from_string_to_field(s):
                def field_long(x):
                    return field(long(x))
                xs = s[0:-1].split(';')
                ys = [x.split(':') for x in xs]
                return [map(field_long, xs) for xs in ys]
            shares = map(convert_from_string_to_field, ls)
            return map(recombine_value, zip(zip(*shares), commitments))

        def exchange(ls, receivers):
            commitments = [None] * len(ls)
            broadcast_string = ""
            for inx, (xi, (rhoi1, rhoi2), Cx) in enumerate(ls):
                broadcast_string += "%s:%s:%s;" % (xi.value, rhoi1.value, rhoi2.value)
                commitments[inx] = (Cx)
            # Send share to all receivers.
            ds = self.broadcast(self.players.keys(), receivers, broadcast_string)

            if self.id in receivers:
                result = gatherResults(ds)
                result.addCallbacks(deserialize, self.error_handler,
                                    callbackArgs=(commitments,))
                return result

        result = gather_shares(shares)
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def random_share(self, field):
        """Generate a random share in the field, field.

        To generate a share of a random element ``r in Z_p``, party
        ``P_i`` chooses at random ``r_i, rho_ri in Z_p X (Z_p)^2`` and
        broadcast ``C_r^i = Com_ck(r_i, rho_ri)``.

        Every party computes ``C_r = PRODUCT_i=1^n C_r^i = Com_ck(r,
        rho_r)``, where ``r_i = SUM_i=1^n r_i and rho_r = SUM_i=1^n
        rho_ri``.

        Party ``P_i sets [r]_i = (r_i, rho_ri, C_r)``.
        """
        self.increment_pc()

        # P_i chooses at random r_i, rho_ri in Z_p x (Z_p)^2
        ri = field(rand.randint(0, field.modulus - 1))
        rhoi1 = field(rand.randint(0, field.modulus - 1))
        rhoi2 = field(rand.randint(0, field.modulus - 1))

        # compute C_r^i = Com_ck(r_i, rho_ri).
        Cri = commitment.commit(ri.value, rhoi1, rhoi2)

        # Broadcast C_r^i.
        sls = gatherResults(self.broadcast(self.players.keys(), self.players.keys(), repr(Cri)))

        def compute_commitment(ls):
            Cr = reduce(operator.mul, ls)
            return OrlandiShare(self, field, ri, (rhoi1, rhoi2), Cr)

        def deserialize(ls):
            return [ commitment.deserialize(x) for x in ls ]

        sls.addCallbacks(deserialize, self.error_handler)
        sls.addCallbacks(compute_commitment, self.error_handler)

        s = Share(self, field)
        # We add the result to the chains in triple.
        sls.chainDeferred(s)

        # do actual communication
        self.activate_reactor()

        return s

    def _convert_public_to_share(self, c, field):
        """Convert a public value to a share.
        
        Any additive constant can be interpreted as:
        ``[c]_1 = (c, 0, Com_ck(c,0))`` and
        ``[c]_i = (0, 0, Com_ck(c,0)) for i != 1``.
        """
        zero = field(0)
        ci = zero
        if self.id == 1:
            ci = c
        return self._constant(ci, c, field)

    def _constant(self, xi, x, field):
        """Greate a share *xi* with commitment to value *x*."""
        zero = field(0)
        Cx = commitment.commit(x.value, 0, 0)
        return (xi, (zero, zero), Cx)

    def _plus_public(self, x, c, field):
        return self._do_arithmetic_op(x, c, field, self._plus)

    def _plus(self, (x, y), field):
        """Addition of share-tuples *x* and *y*.

        Each party ``P_i`` computes:
        ``[x]_i = (x_i, rho_xi, C_x)``
        ``[y]_i = (y_i, rho_yi, C_y)``
        ``[z]_i = [x]_i + [y]_i
                = (x_i + y_i mod p, rho_xi + rho_yi mod p, C_x * C_y)``.
        """
        (xi, (rhoxi1, rhoxi2), Cx) = x
        (yi, (rhoyi1, rhoyi2), Cy) = y
        zi = xi + yi
        rhozi1 = rhoxi1 + rhoyi1
        rhozi2 = rhoxi2 + rhoyi2
        Cz = Cx * Cy
        return (zi, (rhozi1, rhozi2), Cz)

    def _minus_public_right(self, x, c, field):
        return self._do_arithmetic_op(x, c, field, self._minus)

    def _minus_public_left(self, x, c, field):
        y = self._constant_multiply(x, field(-1))
        return self._do_arithmetic_op(y, c, field, self._plus)

    def _do_arithmetic_op(self, x, c, field, op):
        y = self._convert_public_to_share(c, field)
        (zi, rhoz, Cz) = op((x, y), field)
        return OrlandiShare(self, field, zi, rhoz, Cz)

    def _minus(self, (x, y), field):
        """Subtraction of share-tuples *x* and *y*.

        Each party ``P_i`` computes:
        ``[x]_i = (x_i, rho_x,i, C_x)``
        ``[y]_i = (y_i, rho_y,i, C_y)``
        ``[z]_i = [x]_i - [y]_i
                = (x_i - y_i mod p, rho_x,i - rho_y,i mod p, C_x / C_y)``.
        """
        xi, (rhoxi1, rhoxi2), Cx = x
        yi, (rhoyi1, rhoyi2), Cy = y
        zi = xi - yi
        rhozi1 = rhoxi1 - rhoyi1
        rhozi2 = rhoxi2 - rhoyi2
        Cz = Cx / Cy
        return (zi, (rhozi1, rhozi2), Cz)

    def input(self, inputters, field, number=None):
        """Input *number* to the computation.

        The input is shared using the :meth:`shift` method.
        """
        return self.shift(inputters, field, number)


    def shift(self, inputters, field, number=None):
        """Shift of a share.

        Useful for input.

        Communication cost: ???.

        Assume the parties are given a random share ``[r]`` by a
        trusted dealer. Then we denote the following protocol but
        ``[x] = Shift(P_i, x, [r])``.

        1. ``r = OpenTo(P_i, [r])``

        2. ``P_i broadcasts Delta = r - x``

        3. ``[x] = [r] - Delta``
        """
        # TODO: Communitcation costs?
        assert (self.id in inputters and number is not None) or (self.id not in inputters)

        self.increment_pc()

        results = []
        def hack(_, peer_id):
            # Assume the parties are given a random share [r] by a
            # trusted dealer.
            share_r = self.random_share(field)
            # 1. r = OpenTo(P_i, [r])
            open_r = self.open(share_r, [peer_id])
            def subtract_delta(delta, share_r):
                delta = field(long(delta))
                x = self.sub(share_r, delta)
                return x
            if peer_id == self.id:
                def g(r, x):
                    delta = r - x
                    delta = self.broadcast([peer_id], self.players.keys(),
                                           str(delta.value))
                    self.schedule_callback(delta, subtract_delta, share_r)
                    delta.addErrback(self.error_handler)
                    return delta
                self.schedule_callback(open_r, g, number)
                open_r.addErrback(self.error_handler)
                return open_r
            else:
                d = Deferred()
                def g(_, peer_id, share_r):
                    delta = self.broadcast([peer_id], self.players.keys())
                    self.schedule_callback(delta, subtract_delta, share_r)
                    delta.addErrback(self.error_handler)
                    return delta
                self.schedule_callback(d, g, peer_id, share_r)
                d.addErrback(self.error_handler)
                d.callback(None)
                return d

        for peer_id in inputters:
            s = Share(self, field)
            self.schedule_callback(s, hack, peer_id)
            s.addErrback(self.error_handler)
            s.callback(None)
            results.append(s)

        # do actual communication
        self.activate_reactor()

        if len(results) == 1:
             return results[0]
        return results

    def _constant_multiply(self, x, c):
        """Multiplication of a share-tuple with a constant c."""
        assert(isinstance(c, FieldElement))
        xi, (rhoi1, rhoi2), Cx = x
        zi = xi * c
        rhoz = (rhoi1 * c, rhoi2 * c)
        Cz = Cx**c.value
        return (zi, rhoz, Cz)

    def _get_share(self, field, value):
        Cc = commitment.commit(value * 3, 0, 0)
        c = OrlandiShare(self, field, field(value), (field(0), field(0)), Cc)
        return c

    def _minus_public_right_without_share(self, x, c, field):
        y = self._convert_public_to_share(c, field)
        return self._minus((x, y), field)
    
    def _wrap_in_share(self, (zi, rhoz, Cz), field):
        return OrlandiShare(self, field, zi, rhoz, Cz)

    @preprocess("random_triple")
    def _get_triple(self, field):
        results = [Share(self, field) for i in range(3)]
        def chain(triple, results):
            for i, result in zip(triple, results):
                result.callback(i)
        self.random_triple(field, 1)[0].addCallbacks(chain, self.error_handler,
                                                     (results,))
        return results
    
    def sum_poly(self, j, ls):
        exp  = j
        fj, (rhoj1, rhoj2), Cfj = ls[0]
        x    = fj*exp
        rho1 = rhoj1 * exp
        rho2 = rhoj2 * exp
        Cx   = Cfj**exp
        exp *= j

        for (fj, (rhoj1, rhoj2), Cfj) in ls[1:]:
            x += fj * exp
            rho1 += rhoj1 * exp
            rho2 += rhoj2 * exp
            Cx = Cx * (Cfj**exp)
            exp *= j
        return x, (rho1, rho2), Cx

    def leak_tolerant_mul(self, share_x, share_y, M):
        """Leak tolerant multiplication of shares.

        Communication cost: ???.

        Assuming a set of multiplicative triples:
        ``M = ([a_i], [b_i], [c_i]) for 1 <= i <= 2d + 1``.

        1. ``for i = 1, ..., d do [f_i] = rand(), [g_i] = rand()``

        2. Compute::

             for j = 1, ..., 2d+1 do
             [F_j] = [x] + SUM_i=1^d [f_i]*j^i
             and
             [G_j] = [y] + SUM_i=1^d [g_i]*j^i

        3. ``for j = 1, ..., 2d+1 do [H_j] = Mul([F_j], [G_j], [a_j],
           [b_j], [c_j])``

        4. compute ``[H_0] = SUM_j=1^2d+1 delta_j[H_j]`` where
           ``delta_j = PRODUCT_k=1, k!=j^2d+1 k/(k-j)``

        5. output ``[z] = [H_0]``
        """
        assert isinstance(share_x, Share) or isinstance(share_y, Share), \
            "At least one of share_x and share_y must be a Share."

        self.increment_pc()

        field = getattr(share_x, "field", getattr(share_y, "field", None))
        n = field(0)

        cmul_result = self._cmul(share_x, share_y, field)
        if cmul_result is not None:
            return cmul_result

        # 1. for i = 1, ..., d do [f_i] = rand(), [g_i] = rand()
        d = (len(M) - 1) // 2
        deltas = self.compute_delta(d)
        f = []
        g = []
        for x in xrange(d):
            f.append(self.random_share(field))
            g.append(self.random_share(field))

        def compute_polynomials(t):
            x, y = t[0]
            f = []
            g = []
            if len(t) == 3:
                f = t[1]
                g = t[2]
#             print "==> poly", self.id
#             print "x:", x
#             print "y:", y
#             print "t:", t, len(t)
#             print "f:", f
#             print "g:", g
            # 2) for j = 1, ..., 2d+1 do
            # [F_j] = [x] + SUM_i=1^d [f_i]*j^i
            # and
            # [G_j] = [y] + SUM_i=1^d [g_i]*j^i
            h0i, rhoh0, Ch0 = self._convert_public_to_share(n, field)
            H0 = OrlandiShare(self, field, h0i, rhoh0, Ch0)
            xi, (rhoxi1, rhoxi2), Cx = x
            yi, (rhoyi1, rhoyi2), Cy = y

            for j in xrange(1, 2*d + 2):
                Fji = xi
                rho1_Fji = rhoxi1
                rho2_Fji = rhoxi2
                C_Fji = Cx
                if f != []:
                    # SUM_i=1^d [f_i]*j^i
                    vi, (rhovi1, rhovi2), Cv = self.sum_poly(j, f)
                    # [F_j] = [x] + SUM_i=1^d [f_i]*j^i
                    Fji += vi
                    rho1_Fji += rhovi1
                    rho2_Fji += rhovi2
                    C_Fji *= Cv
                Gji = yi
                rho1_Gji = rhoyi1
                rho2_Gji = rhoyi2
                C_Gji = Cy
                if g != []:
                    # SUM_i=1^d [g_i]*j^i
                    wi, (rhowi1, rhowi2), Cw = self.sum_poly(j, g)
                    # [G_j] = [y] + SUM_i=1^d [g_i]*j^i
                    Gji += wi
                    rho1_Gji += rhowi1
                    rho2_Gji += rhowi2
                    C_Gji *= Cw
                Fj = OrlandiShare(self, field, Fji, (rho1_Fji, rho2_Fji), C_Fji)
                Gj = OrlandiShare(self, field, Gji, (rho1_Gji, rho2_Gji), C_Gji)
                a, b, c = M.pop(0)

                # [H_j] = Mul([F_j], [G_j], [a_j], [b_j], [c_j])
                Hj = self._basic_multiplication(Fj, Gj, a, b, c)
                dj = self._cmul(field(deltas[j - 1]), Hj, field)
                H0 = H0 + dj
            # 5) output [z] = [H_0]
            return H0

        ls = [gather_shares([share_x, share_y])]
        if g and f:
            ls.append(gather_shares(f))
            ls.append(gather_shares(g))
        result = gather_shares(ls)
        self.schedule_callback(result, compute_polynomials)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        return result

    def triple_gen(self, field):
        """Generate a triple ``a, b, c`` s.t. ``c = a * b``.

        1. Every party ``P_i`` chooses random values ``a_i, r_i in Z_p
           X (Z_p)^2``, compute ``alpha_i = Enc_eki(a_i)`` and ``Ai =
           Com_ck(a_i, r_i)``, and broadcast them.

        2. Every party ``P_j`` does:

           a. choose random ``b_j, s_j in Z_p X (Z_p)^2``.

           b. compute ``B_j = ``Com_ck(b_j, s_j)`` and broadcast it.

           c. ``P_j`` do towards every other party:

                i. choose random ``d_ij in Z_p^3``

                ii. compute and send
                    ``gamma_ij = alpha_i^b_j Enc_ek_i(1;1)^d_ij`` to ``P_i``.


        3. Every party ``P_i`` does:

           a. compute ``c_i = SUM_j Dec_sk_i(gamma_ij) - SUM_j d_ij mod p``

           b. pick random ``t_i in (Z_p)^2``, compute and
              broadcast ``C_i = Com_ck(c_i, t_i)``

        4. Everyone computes:
           ``(A, B, C) = (PRODUCT_i A_i, PRODUCT_i B_i, PRODUCT_i C_i)``

        5. Every party ``P_i`` outputs shares ``[a_i] = (a_i, r_i, A)``,
           ``[b_i] = (b_i, s_i, B)``, and ``[c_i] = (c_i, t_i, C)``.

        """
        self.increment_pc()

        def random_number(p):
            return field(rand.randint(0, p - 1))

        def product(ls):
            """Compute the product of the elements in the list *ls*."""
            return  reduce(operator.mul, map(commitment.deserialize, ls))

        def step45(Cs, alphas, gammas, alpha_randomness,
                   As, Bs, ai, bi, ci, r, s, t, dijs):
            """4) Everyone computes::
                  A = PRODUCT_i A_i
                  B = PRODUCT_i B_i
                  C = PRODUCT_i C_i

               5) Every party ``P_i`` outputs shares ``[a_i] = (a_i, r_i, A)``,
                  ``[b_i] = (b_i, s_i, B)``, and ``[c_i] = (c_i, t_i, C)``.
            """
            A = product(As)
            B = product(Bs)
            C = product(Cs)
            a = OrlandiShare(self, field, ai, r, A)
            b = OrlandiShare(self, field, bi, s, B)
            c = OrlandiShare(self, field, ci, t, C)
            return (a, b, c, (alphas, alpha_randomness, gammas, dijs))

        def decrypt_gammas(ls):
            """Decrypt all the elements of the list *ls*."""
            rs = []
            for x in ls:
                rs.append(field(decrypt(x, self.players[self.id].seckey)))
            return rs

        def step3(gammas, alphas, alpha_randomness, As, Bs, ai, bi, r, s, dijs):
            """3) Every party ``P_i`` does:
                  (a) compute
                  ``c_i = SUM_j Dec_sk_i(gamma_ij) - SUM_j d_ji mod p``

                  (b) pick random ``t_i in (Z_p)^2``, compute and
                      broadcast ``C_i = Com_ck(c_i, t_i)``
            """
            # c_i = SUM_j Dec_sk_i(gamma_ij) - SUM_j d_ji mod p.
            ls = [list(x) for x in zip(gammas, dijs)]
            ci = field(tripple_3a(ls, self.players[self.id].seckey))
            # (b) pick random t_i in (Z_p)^2.
            t1 = random_number(field.modulus)
            t2 = random_number(field.modulus)
            t = (t1, t2)
            # C_i = Com_ck(c_i, t_i).
            Ci = commitment.commit(ci.value, t1.value, t2.value)

            # Broadcast Ci.
            Cs = self.broadcast(self.players.keys(), self.players.keys(),
                                repr(Ci))
            result = gatherResults(Cs)
            result.addCallbacks(step45, self.error_handler,
                                callbackArgs=(alphas, gammas, alpha_randomness,
                                              As, Bs, ai, bi, ci, r, s, t, dijs))
            return result

        def step2c((alphas, As, Bs), alpha_randomness, ai, bj, r, s):
            """(c) P_j do, towards every other party:
                   i. choose random d_i,j in Z_p^3
                   ii. compute and send
            gamma_ij = alpha_i^b_j Enc_ek_i(1;1)^d_ij to P_i.
            """

            # (c) P_j do, towards every other party:
            dijs = [None] * len(self.players.keys())
            results = [None] * len(self.players.keys())
            pc = tuple(self.program_counter)
            p3 = field.modulus**3
            bjvalue = bj.value
            for pi in self.players.keys():
                # choose random d_i,j in Z_p^3
                dij = random_number(p3).value
                # gamma_ij = alpha_i^b_j Enc_ek_i(1;1)^d_ij
                # gammaij = tripple_2c(alphas[pi - 1], bj.value, dij, self.players[pi].pubkey)
                player = self.players[pi]
                fixed_base = player.pubkey['fixed_base']
                gammaij = fixed_base.calc(dij, alphas[pi - 1], bjvalue)
                
                # Broadcast gamma_ij
                if pi != self.id:
                    self.protocols[pi].sendData(pc, PAILLIER, str(gammaij))
                    d = Deferred()
                    d.addCallbacks(lambda value: long(value), self.error_handler)
                    self._expect_data(pi, PAILLIER, d)
                else:
                    d = succeed(gammaij)
                dijs[pi - 1] = dij
                results[pi - 1] = d
            result = gatherResults(results)
            self.schedule_callback(result, step3, alphas, alpha_randomness,
                                   As, Bs, ai, bj, r, s, dijs)
            result.addErrback(self.error_handler)
            return result


        # 1) Every party P_i chooses random values a_i, r_i in Z_p X (Z_p)^2,
        #    compute alpha_i = Enc_eki(a_i) and Ai = Com_ck(a_i, r_i), and
        #    broadcast them.

        # Every party P_i chooses random values a_i, r_i in Z_p X (Z_p)^2
        ai = random_number(field.modulus)
        r1 = random_number(field.modulus)
        r2 = random_number(field.modulus)

        # compute alpha_i = Enc_eki(a_i)
        pubkey = self.players[self.id].pubkey
        alpha_randomness = rand.randint(1, long(pubkey['n']))
        alphai = encrypt_r(ai.value, alpha_randomness, pubkey)
        # and A_i = Com_ck(a_i, r_i).
        Ai = commitment.commit(ai.value, r1.value, r2.value)

        # choose random b_j, s_j in Z_p X (Z_p)^2.
        bj = random_number(field.modulus)
        s1 = random_number(field.modulus)
        s2 = random_number(field.modulus)
        # compute B_j = Com_ck(b_j, s_j).
        Bj = commitment.commit(bj.value, s1.value, s2.value)

        # broadcast alpha_i, A_i, B_j.
        ds = self.broadcast(sorted(self.players.keys()),
                            sorted(self.players.keys()),
                            str(alphai) + ":" + repr(Ai) + ":" + repr(Bj))

        alphas_As_Bs = gatherResults(ds)
        def split_alphas_As_Bs(ls):
            alphas = []
            As = []
            Bs = []
            for x in ls:
                alpha, Ai, Bj = x.split(':')
                alphas.append(long(alpha))
                As.append(Ai)
                Bs.append(Bj)
            return alphas, As, Bs
        alphas_As_Bs.addCallbacks(split_alphas_As_Bs, self.error_handler)

        self.schedule_callback(alphas_As_Bs, step2c, alpha_randomness, 
                               ai, bj, (r1, r2), (s1, s2))
        alphas_As_Bs.addErrback(self.error_handler)
        return alphas_As_Bs


    def triple_test(self, field):
        """Generate a triple ``(a, b, c)`` where ``c = a * b``.

        The triple ``(a, b, c)`` is checked against the
        triple ``(x, y, z)`` and a random value ``r``.

        """
        triple1 = self.triple_gen(field)
        triple2 = self.triple_gen(field)
        r = self.open(self.random_share(field))

        def check(v, a, b, c, ec):
            if v.value != 0:
                raise OrlandiException("TripleTest failed - The two triples were inconsistent.")
            return (a, b, c, ec)

        def compute_value(((a, b, c, ec), (x, y, z, _), r)):
            l = self._cmul(r, x, field)
            m = self._cmul(r, y, field)
            n = self._cmul(r*r, z, field)
            d = c - self._basic_multiplication(a, b, l, m, n)
            r = self.open(d)
            r.addCallbacks(check, self.error_handler, callbackArgs=(a, b, c, ec))
            return r

        result = gatherResults([triple1, triple2, r])
        self.schedule_callback(result, compute_value)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        return result

    def random_triple(self, field, quantity=1):
        """Generate a list of triples ``(a, b, c)`` where ``c = a * b``.

        The triple ``(a, b, c)`` is secure in the Fcrs-hybrid model.

        """
        self.increment_pc()

        M = []

# print "Generating %i triples... relax, have a break..." % ((1 + self.s_lambda) * (2 * self.d + 1) * quantity)

        for x in xrange((1 + self.s_lambda) * (2 * self.d + 1) * quantity):
            M.append(self.triple_test(field))

        def step3(ls):
            """Coin-flip a subset test_set of M of size lambda(2d + 1)M."""
            size = self.s_lambda * (2 * self.d + 1) * quantity
            inx = 0
            p_half = field.modulus // 2
            def coin_flip(v, ls, test_set):
                candidate = ls.pop(0)
                if p_half > v:
                    test_set.append(candidate)
                else:
                    ls.append(candidate)
                if size > len(test_set):
                    r = self.random_share(field)
                    r = self.output(r)
                    self.schedule_callback(r, coin_flip, ls, test_set)
                    r.addErrback(self.error_handler)
                    return r
                return ls, test_set
            r = self.random_share(field)
            r = self.output(r)
            self.schedule_callback(r, coin_flip, ls, [])
            r.addErrback(self.error_handler)
            return r

        def step45(lists):
            """For all i in test_set the parties reveal
            the randomness used for TripleTest() and checks that
            the randomness is consistent with the actual values."""
            M_without_test_set = lists[0]
            T = lists[1]

            def get_share(x, ls):
                share = ls[x * 4]
                rho1 = ls[x * 4 + 1]
                rho2 = ls[x * 4 + 2]
                commitment = ls[x * 4 + 3]
                return (share, rho1, rho2, commitment)

            def send_share(player_id, pc, a):
                self._send_orlandi_share(player_id, pc, a.share, a.rho, a.commitment)

            def receive_shares(player_id):
                Cx = Deferred()
                xi = self._expect_share(player_id, field)
                rho1 = self._expect_share(player_id, field)
                rho2 = self._expect_share(player_id, field)
                self._expect_data(player_id, TEXT, Cx)
                Cx.addCallbacks(commitment.deserialize,
                                self.error_handler)
                return gatherResults([xi, rho1, rho2, Cx])

            def send_long(player_id, pc, l):
                self.protocols[player_id].sendData(pc, TEXT, str(l))

            def receive_long(player_id):
                l = Deferred()
                self._expect_data(player_id, TEXT, l)
                l.addCallbacks(long, self.error_handler)
                return l

            def check((ais, bis, cis, alpha_randomness, dijs), alphas, gammas):
                """So if B receives ai, bi, dij, ri, si, and the
                randomness used in the computation of alpha, he then
                checks that:

                1) the alpha_i he received is equals to the encryption
                   of ai and the commitment he received, Ai, is equal
                   to the commitment of ai and ri

                2) the commitment he received, Bj, is equal to the
                   commitment of bj and sj

                3) the gammaij he received is equal to the gammaij he
                   now computes based on the values he reveives

                4) a, b, c is a triple, a * b = c

                5) ai, bi < p and dij < p^3
                """
                a = 0
                a_rho1 = 0
                a_rho2 = 0
                b = 0
                b_rho1 = 0
                b_rho2 = 0
                c = 0
                c_rho1 = 0
                c_rho2 = 0

                for x in xrange(len(ais)):
                    (ai, a_rhoi1, a_rhoi2, A) = ais[x]
                    (bi, b_rhoi1, b_rhoi2, B) = bis[x]
                    (ci, c_rhoi1, c_rhoi2, C) = cis[x]
                    # 5) ai, bi < p...
                    if ai >= field.modulus:
                        raise OrlandiException("Inconsistent share ai, ai >= p: %i" % ai)
                    if bi >= field.modulus:
                        raise OrlandiException("Inconsistent share bi, bi >= p: %i" % bi)
                    a += ai
                    a_rho1 += a_rhoi1
                    a_rho2 += a_rhoi2
                    b += bi
                    b_rho1 += b_rhoi1
                    b_rho2 += b_rhoi2
                    c += ci
                    c_rho1 += c_rhoi1
                    c_rho2 += c_rhoi2
                    # 1) the alpha_i he received is equals to the encryption of ai...
                    alphai = encrypt_r(ai.value, alpha_randomness[x],
                                       self.players[x + 1].pubkey)
                    if not(alphas[x] == alphai):
                        raise OrlandiException("Inconsistent alpha from player %i, %i, %i" % (x + 1, alphas[x], alphai))

                A1 = commitment.commit(a.value, a_rho1.value, a_rho2.value)
                B1 = commitment.commit(b.value, b_rho1.value, b_rho2.value)
                C1 = commitment.commit(c.value, c_rho1.value, c_rho2.value)

                # 1) ... and the commitment he received, Ai, is equal
                # to the commitment of ai and ri.
                if A1 != A:
                    raise OrlandiException("Inconsistent commitment for value %s, found %s expected %s." % (a, A1, A))
                # 2) the commitment he received, Bj, is equal to the
                # commitment of bj and sj.
                if B1 != B:
                    raise OrlandiException("Inconsistent commitment for value %s, found %s expected %s." % (b, B1, B))
                if C1 != C:
                    raise OrlandiException("Inconsistent commitment for value %s, found %s expected %s." % (c, C1, C))
                # 4) a, b, c is a triple, a * b = c
                if a * b != c:
                    raise OrlandiException("Inconsistent triple, %i * %i does not equals %i." % (a, b, c))


                # 3) the gammaij he received is equal to the gammaij
                # he now computes based on the values he reveives
                player = self.players[self.id]
                fixed_base = player.pubkey['fixed_base']
                alpha = alphas[self.id - 1]
                modulus_3 = field.modulus**3
                for j in xrange(len(ais)):
                    dij = dijs[j]
                    # 5) ... and dij < p^3.
                    if dij >= (modulus_3):
                        raise OrlandiException("Inconsistent random value dij %i from player %i" % (dij, j + 1))
                    # gamma_ij = alpha_i^b_j Enc_ek_i(1;1)^d_ij
                    # gammaij = tripple_2c(alphas[self.id - 1], bis[j][0].value, 
                    #                   dij, self.players[self.id].pubkey)
                    gammaij = fixed_base.calc(dij, alpha, bis[j][0].value)
                    if gammaij != gammas[j]:
                        raise OrlandiException("Inconsistent gammaij, %i, %i" % (gammaij, gammas[j]))

                return True

            dls_all = []
            for (a, b, c, (alphas, alpha_randomness, gammas, dijs)) in T:
                ds_a = [None] * len(self.players)
                ds_b = [None] * len(self.players)
                ds_c = [None] * len(self.players)
                ds_alpha_randomness = [None] * len(self.players)
                ds_dijs = [None] * len(self.players)
                pc = tuple(self.program_counter)

                for player_id in xrange(1, len(self.players.keys()) + 1):
                    if player_id == self.id:
                        ds_a[player_id - 1] = succeed([a.share, a.rho[0], a.rho[1], a.commitment])
                        ds_b[player_id - 1] = succeed([b.share, b.rho[0], b.rho[1], b.commitment])
                        ds_c[player_id - 1] = succeed([c.share, c.rho[0], c.rho[1], c.commitment])
                        ds_alpha_randomness[player_id - 1] = succeed(alpha_randomness)
                        ds_dijs[player_id - 1] = succeed(dijs[player_id - 1])
                    # Receive and recombine shares if this player is a
                    # receiver.
                    else:
                        send_share(player_id, pc, a)
                        send_share(player_id, pc, b)
                        send_share(player_id, pc, c)
                        send_long(player_id, pc, alpha_randomness)
                        send_long(player_id, pc, dijs[player_id - 1])

                        ds_a[player_id - 1] = receive_shares(player_id)
                        ds_b[player_id - 1] = receive_shares(player_id)
                        ds_c[player_id - 1] = receive_shares(player_id)
                        ds_alpha_randomness[player_id - 1] = receive_long(player_id)
                        ds_dijs[player_id - 1] = receive_long(player_id)
                dls_a = gatherResults(ds_a)
                dls_b = gatherResults(ds_b)
                dls_c = gatherResults(ds_c)
                dls_dijs = gatherResults(ds_dijs)
                dls_alpha_randomness = gatherResults(ds_alpha_randomness)

                dls = gatherResults([dls_a, dls_b, dls_c, dls_alpha_randomness, dls_dijs])
                dls.addCallbacks(check, self.error_handler, callbackArgs=[alphas, gammas])
                dls_all.append(dls)

            def result(x):
                ls = []
                for a, b, c, _ in M_without_test_set:
                    ls.append((a, b, c))
                return ls

            dls_all = gatherResults(dls_all)
            dls_all.addCallbacks(result, self.error_handler)
            return dls_all

        def step6(M_without_test_set):
            """Partition M without test_set in quantity random subsets
            M_i of size (2d + 1).
            """
            subsets = []
            size = 2 * self.d + 1
            for x in xrange(quantity):
                subsets.append([])

            def put_in_set(v, M_without_test_set, subsets):
                if 0 == len(M_without_test_set):
                    return subsets
                v = v.value % quantity
                if size > len(subsets[v]):
                    subsets[v].append(M_without_test_set.pop(0))
                r = self.random_share(field)
                r = self.output(r)
                self.schedule_callback(r, put_in_set, M_without_test_set, subsets)
                r.addErrback(self.error_handler)
                return r
            r = self.random_share(field)
            r = self.output(r)
            self.schedule_callback(r, put_in_set, M_without_test_set, subsets)
            r.addErrback(self.error_handler)
            return r

        results = [Deferred() for i in xrange(quantity)]

        def step7(Msets):
            """For i = 1,...,M do:
            a) [a] <- Fpp(rand,...), [b] <- Fpp(rand,...)
            b) [r] <- Fpp(rand,...),
            c) [c] <- LTMUL([a], [b], M_i)
            d) Open([c] + [r])
            """
            ds = []
            for Mi, result in zip(Msets, results):
                a = self.random_share(field)
                b = self.random_share(field)
                r = self.random_share(field)
                c = self.leak_tolerant_mul(a, b, Mi)
                d = self.open(c + r)
                def return_abc(x, a, b, c, result):
                    gatherResults([a, b, c]).chainDeferred(result)
                d.addCallbacks(return_abc, self.error_handler, callbackArgs=(a, b, c, result))

        result = gatherResults(M)
        self.schedule_callback(result, step3)
        result.addErrback(self.error_handler)
        self.schedule_callback(result, step45)
        self.schedule_callback(result, step6)
        self.schedule_callback(result, step7)

        # do actual communication
        self.activate_reactor()
        return results

    def error_handler(self, ex):
        print "Error: ", ex
        return ex

    def set_args(self, args):
        """args is a dictionary."""
        self.s = args['s']
        self.d = args['d']
        self.s_lambda = args['lambda']


class OrlandiRuntime(OrlandiMixin, SimpleArithmeticRuntime):
    """The Orlandi runtime.

    The runtime is used for sharing values (:meth:`secret_share` or
    :meth:`shift`) into :class:`OrlandiShare` object and opening such
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
        SimpleArithmeticRuntime.__init__(self, player, threshold, options)
        self.threshold = self.num_players - 1
        self.s = 1
        self.d = 0
        self.s_lambda = 1
