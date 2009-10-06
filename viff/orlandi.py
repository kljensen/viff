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

from twisted.internet.defer import Deferred, DeferredList, gatherResults

from viff.runtime import Runtime, Share, ShareList, gather_shares
from viff.util import rand
from viff.constants import TEXT, PAILLIER
from viff.field import FieldElement
from viff.paillier import encrypt_r, decrypt

from hash_broadcast import HashBroadcastMixin

import commitment
commitment.set_reference_string(23434347834783478783478L, 489237823478234783478020L)

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
        Share.__init__(self, runtime, field, (value, rho, commitment))


class OrlandiRuntime(Runtime, HashBroadcastMixin):
    """The Orlandi runtime.

    The runtime is used for sharing values (:meth:`secret_share` or
    :meth:`shift`) into :class:`OrlandiShare` object and opening such
    shares (:meth:`open`) again. Calculations on shares is normally
    done through overloaded arithmetic operations, but it is also
    possible to call :meth:`add`, :meth:`mul`, etc. directly if one
    prefers.

    Each player in the protocol uses a :class:`Runtime` object. To
    create an instance and connect it correctly with the other
    players, please use the :func:`create_runtime` function instead of
    instantiating a Runtime directly. The :func:`create_runtime`
    function will take care of setting up network connections and
    return a :class:`Deferred` which triggers with the
    :class:`Runtime` object when it is ready.
    """

    def __init__(self, player, threshold=None, options=None):
        """Initialize runtime."""
        Runtime.__init__(self, player, threshold, options)
        self.threshold = self.num_players - 1

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

    def output(self, share, receivers=None, threshold=None):
        return self.open(share, receivers, threshold)

    def _send_orlandi_share(self, other_id, pc, xi, rhoi, Cx):
        """Send the share *xi*, *rhoi*, and the commitment *Cx* to party *other_id*."""
        self.protocols[other_id].sendShare(pc, xi)
        self.protocols[other_id].sendShare(pc, rhoi[0])
        self.protocols[other_id].sendShare(pc, rhoi[1])
        self.protocols[other_id].sendData(pc, TEXT, repr(Cx))

    def _expect_orlandi_share(self, peer_id, field):
        """Waits for a number ``x``, ``rho``, and the commitment for ``x``."""
        xi = self._expect_share(peer_id, field)
        Cx = Deferred()        
        rhoi1 = self._expect_share(peer_id, field)
        rhoi2 = self._expect_share(peer_id, field)
        self._expect_data(peer_id, TEXT, Cx)
        sls = ShareList([xi, rhoi1, rhoi2, Cx])
        def combine(ls):
            expected_num = 4;
            if len(ls) is not expected_num:
                raise OrlandiException("Cannot share number, trying to create a share,"
                                       " expected %s components got %s." % (expected_num, len(ls)))
            s1, xi = ls[0]
            s2, rhoi1 = ls[1]
            s3, rhoi2 = ls[2]
            s4, Cx = ls[3]
            Cxx = commitment.deserialize(Cx)
            if not (s1 and s2 and s3 and s4):
                raise OrlandiException("Cannot share number, trying to create share,"
                                       " but a component did arrive properly.")
            return OrlandiShare(self, field, xi, (rhoi1, rhoi2), Cxx)
        sls.addCallbacks(combine, self.error_handler)
        return sls

    def _expect_orlandi_share_xi_rhoi(self, peer_id, field):
        xi = self._expect_share(peer_id, field)
        rhoi1 = self._expect_share(peer_id, field)
        rhoi2 = self._expect_share(peer_id, field)
        sls = ShareList([xi, rhoi1, rhoi2])
        def combine(ls):
            expected_num = 3;
            if len(ls) is not expected_num:
                raise OrlandiException("Cannot share number, trying to create a share,"
                                       " expected %s components got %s." % (expected_num, len(ls)))

            s1, xi = ls[0]
            s2, rhoi1 = ls[1]
            s3, rhoi2 = ls[2]
            if not (s1 and s2 and s3):
                raise OrlandiException("Cannot share number, trying to create share "
                                       "but a component did arrive properly.")
            return OrlandiShare(self, field, xi, (rhoi1, rhoi2))
        sls.addCallbacks(combine, self.error_handler)
        return sls

    def secret_share(self, inputters, field, number=None, threshold=None):
        """Share the value, number, among all the parties using additive shareing.

        To share an element ``x in Z_p``, choose random ``x_1, ..., x_n-1 in Z_p``, 
        define ``x_n = x - SUM_i=1^n-1 x_i mod p``.

        Choose random values ``rho_x1, ..., rho_xn in (Z_p)^2``, define 
        ``rho_x = SUM_i=1^n rho_x,i`` and ``C_x = Com_ck(x, p_x)``.
        
        Send ``[x]_i = (x_i, rho_xi, C_x)`` to party ``P_i``.
        """
        assert number is None or self.id in inputters
        self.threshold = self.num_players - 1

        self.program_counter[-1] += 1

        def additive_shares_with_rho(x):
            """Returns a tuple of a list of tuples (player id, share, rho) and rho.

            Chooses random elements ``x_1, ..., x_n-1`` in field and ``x_n`` st. 
            ``x_n = x - Sum_i=1^n-1 x_i``.

            Chooses random pair of elements ``rho_1, ..., rho_n in Z_p^2``
            and define ``rho_n = Sum_i=1^n rho_i``.

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
                the_others = []
                for other_id, xi, rhoi in shares:
                    if other_id == self.id:
                        results.append(OrlandiShare(self, field, xi, rhoi, Cx))
                    else:
                        # Send ``xi``, ``rhoi``, and commitment
                        self._send_orlandi_share(other_id, pc, xi, rhoi, Cx)
            else:
                # Expect ``xi``, ``rhoi``, and commitment
                results.append(self._expect_orlandi_share(peer_id, field))
        # do actual communication
        self.activate_reactor()
        # Unpack a singleton list.
        if len(results) == 1:
            return results[0]
        return results

    def open(self, share, receivers=None, threshold=None):
        """Share reconstruction.

        Every partyi broadcasts a share pair ``(x_i', rho_x,i')``.

        The parties compute the sums ``x'``, ``rho_x'`` and 
        check ``Com_ck(x',rho_x' = C_x``.

        If yes, return ``x = x'``, else else return :const:`None`.
        """
        assert isinstance(share, Share)
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()
        assert threshold is None
        threshold = self.num_players - 1

        field = share.field

        self.program_counter[-1] += 1

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
            shares = [(field(long(x)), field(long(rho1)), field(long(rho2))) for x, rho1, rho2 in map(self.list_str, ls)]
            return shares
            
        def exchange((xi, (rhoi1, rhoi2), Cx), receivers):
            # Send share to all receivers.
            ds = self.broadcast(self.players.keys(), receivers, str((str(xi.value), str(rhoi1.value), str(rhoi2.value))))

            if self.id in receivers:
                result = gatherResults(ds)
                result.addCallbacks(deserialize, self.error_handler)
                result.addCallbacks(recombine_value, self.error_handler, callbackArgs=(Cx,))
                return result

        result = share.clone()
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def random_share(self, field):
        """Generate a random share in the field, field.

        To generate a share of a random element ``r in Z_p``, party ``P_i`` 
        chooses at random ``r_i, rho_ri in Z_p X (Z_p)^2`` and
        broadcast ``C_r^i = Com_ck(r_i, rho_ri)``.

        Every party computes ``C_r = PRODUCT_i=1^n C_r^i = Com_ck(r, rho_r)``,
        where ``r_i = SUM_i=1^n r_i and rho_r = SUM_i=1^n rho_ri``.

        Party ``P_i sets [r]_i = (r_i, rho_ri, C_r)``.

        """
        self.program_counter[-1] += 1

        # P_i chooses at random r_i, rho_ri in Z_p x (Z_p)^2
        ri = field(rand.randint(0, field.modulus - 1))     
        rhoi1 = field(rand.randint(0, field.modulus - 1))
        rhoi2 = field(rand.randint(0, field.modulus - 1))

        # compute C_r^i = Com_ck(r_i, rho_ri).
        Cri = commitment.commit(ri.value, rhoi1, rhoi2)

        # Broadcast C_r^i.
        sls = gatherResults(self.broadcast(self.players.keys(), self.players.keys(), repr(Cri)))

        def compute_commitment(ls):
            Cr = ls.pop()
            for Cri in ls:
                Cr = Cr * Cri
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
    
    def add(self, share_a, share_b):
        """Addition of shares.

        Communication cost: none.

        Each party ``P_i`` computes:
        ``[z]_i = [x]_i + [y]_i
                = (x_i + y_i mod p, rho_xi + rho_yi mod p, C_x * C_y)``.

        """
        def is_share(s, field):
            if not isinstance(s, Share):
                if not isinstance(s, FieldElement):
                    s = field(s)
                (v, rhov, Cv) = self._additive_constant(field(0), s)
                return OrlandiShare(self, field, v, rhov, Cv)
            return s

        # Either share_a or share_b must have an attribute called "field". 
        field = getattr(share_a, "field", getattr(share_b, "field", None))

        share_a = is_share(share_a, field)
        share_b = is_share(share_b, field)

        # Add rho_xi and rho_yi and compute the commitment.
        def compute_sums((x, y)):
            (zi, (rhozi1, rhozi2), Cz) = self._plus(x, y)
            return OrlandiShare(self, field, zi, (rhozi1, rhozi2), Cz)

        result = gather_shares([share_a, share_b])
        result.addCallbacks(compute_sums, self.error_handler)
        return result

    def sub(self, share_a, share_b):
        """Subtraction of shares.

        Communication cost: none.

        Each party ``P_i`` computes:
        ``[z]_i = [x]_i - [y]_i
                = (x_i - y_i mod p, rho_x,i - rho_y,i mod p, C_x * C_y)``.

        """
        def is_share(s, field):
            if not isinstance(s, Share):
                if not isinstance(s, FieldElement):
                    s = field(s)
                (v, rhov, Cv) = self._additive_constant(field(0), s)
                return OrlandiShare(self, field, v, rhov, Cv)
            return s

        # Either share_a or share_b must have an attribute called "field". 
        field = getattr(share_a, "field", getattr(share_b, "field", None))

        share_a = is_share(share_a, field)
        share_b = is_share(share_b, field)

        # Subtract xi and yi, rhoxi and rhoyi, and compute the commitment
        def compute_subs((x, y)):
            zi, (rhozi1, rhozi2), Cz = self._minus(x, y)
            return OrlandiShare(self, field, zi, (rhozi1, rhozi2), Cz)

        result = gather_shares([share_a, share_b])
        result.addCallbacks(compute_subs, self.error_handler)
        return result

    def input(self, inputters, field, number=None, threshold=None):
        """Input *number* to the computation.

        The input is shared using the :meth:`shift` method.
        """
        return self.shift(inputters, field, number)


    def shift(self, inputters, field, number=None):
        """Shift of a share.
        
        Useful for input.

        Communication cost: ???.

        Assume the parties are given a random share ``[r]`` by a trusted dealer. 
        Then we denote the following protocol but ``[x] = Shift(P_i, x, [r])``.

        1) ``r = OpenTo(P_i, [r]``

        2) ``P_i broadcasts Delta = r - x``

        3) ``[x] = [r] - Delta``

        """
        # TODO: Communitcation costs?
        assert (self.id in inputters and number != None) or (self.id not in inputters)

        self.program_counter[-1] += 1

        results = []
        def hack(_, peer_id):
            # Assume the parties are given a random share [r] by a trusted dealer.
            share_r = self.random_share(field)
            # 1) r = OpenTo(P_i, [r])
            open_r = self.open(share_r, [peer_id])
            def subtract_delta(delta, share_r):
                delta = field(long(delta))
                x = self.sub(share_r, delta)
                return x
            if peer_id == self.id:
                def g(r, x):
                    delta = r - x
                    delta = self.broadcast([peer_id], self.players.keys(), str(delta.value))
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

    def mul(self, share_x, share_y):
        """Multiplication of shares.

        Communication cost: ???.
        """
        # TODO: Communication cost?
        assert isinstance(share_x, Share) or isinstance(share_y, Share), \
            "At least one of share_x and share_y must be a Share."

        self.program_counter[-1] += 1

        field = getattr(share_x, "field", getattr(share_y, "field", None))

        a, b, c = self._get_triple(field)
        return self._basic_multiplication(share_x, share_y, a, b, c)

    def _additive_constant(self, zero, field_element):
        """Greate an additive constant.

        Any additive constant can be interpreted as:
        ``[c]_1 = (c, 0, Com_ck(c,0))`` and
        ``[c]_i = (0, 0, Com_ck(c,0)) for i != 1``.
        """
        v = zero
        if self.id == 1:
            v = field_element
        Cx = commitment.commit(field_element.value, zero.value, zero.value)
        return (v, (zero, zero), Cx)

    def _plus(self, x, y):
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

    def _minus(self, x, y):
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

    def _cmul(self, share_x, share_y, field):
        """Multiplication of a share with a constant.

        Either share_x or share_y must be an OrlandiShare but not both.
        Returns None if both share_x and share_y are OrlandiShares.

        """
        def constant_multiply(x, c):
            assert(isinstance(c, FieldElement))
            zi, rhoz, Cx = self._const_mul(c.value, x)
            return OrlandiShare(self, field, zi, rhoz, Cx)
        if not isinstance(share_x, Share):
            # Then share_y must be a Share => local multiplication. We
            # clone first to avoid changing share_y.
            assert isinstance(share_y, Share), \
                "At least one of the arguments must be a share."
            result = share_y.clone()
            result.addCallback(constant_multiply, share_x)
            return result
        if not isinstance(share_y, Share):
            # Likewise when share_y is a constant.
            assert isinstance(share_x, Share), \
                "At least one of the arguments must be a share."
            result = share_x.clone()
            result.addCallback(constant_multiply, share_y)
            return result
        return None

    def _const_mul(self, c, x):
        """Multiplication of a share-tuple with a constant c."""
        assert(isinstance(c, long) or isinstance(c, int))
        xi, (rhoi1, rhoi2), Cx = x
        zi = xi * c
        rhoz = (rhoi1 * c, rhoi2 * c)
        Cz = Cx**c
        return (zi, rhoz, Cz)

    def _get_share(self, field, value):
        Cc = commitment.commit(value * 3, 0, 0)
        c = OrlandiShare(self, field, field(value), (field(0), field(0)), Cc)
        return c

    def _get_triple(self, field):
        n = field(0)
        Ca = commitment.commit(6, 0, 0)
        a = OrlandiShare(self, field, field(2), (n, n), Ca)
        Cb = commitment.commit(12, 0, 0)
        b = OrlandiShare(self, field, field(4), (n, n), Cb)
        Cc = commitment.commit(72, 0, 0)
        c = OrlandiShare(self, field, field(24), (n, n), Cc)
        return (a, b, c)

    def _basic_multiplication(self, share_x, share_y, triple_a, triple_b, triple_c):
        """Multiplication of shares give a triple.

        Communication cost: ???.
        
        ``d = Open([x] - [a])``
        ``e = Open([y] - [b])``
        ``[z] = e[x] + d[y] - [de] + [c]``
        """
        assert isinstance(share_x, Share) or isinstance(share_y, Share), \
            "At least one of share_x and share_y must be a Share."

        self.program_counter[-1] += 1

        field = getattr(share_x, "field", getattr(share_y, "field", None))
        n = field(0)

        cmul_result = self._cmul(share_x, share_y, field)
        if cmul_result is  not None:
            return cmul_result

        def multiply((x, y, d, e, c)):
            # [de]
            de = self._additive_constant(field(0), d * e)
            # e[x]
            t1 = self._const_mul(e.value, x)
            # d[y]
            t2 = self._const_mul(d.value, y)
            # d[y] - [de]
            t3 = self._minus(t2, de)
            # d[y] - [de] + [c]
            t4 = self._plus(t3, c)
            # [z] = e[x] + d[y] - [de] + [c]
            zi, rhoz, Cz = self._plus(t1, t4)
            return OrlandiShare(self, field, zi, rhoz, Cz)

        # d = Open([x] - [a])
        d = self.open(share_x - triple_a)
        # e = Open([y] - [b])
        e = self.open(share_y - triple_b)
        result = gather_shares([share_x, share_y, d, e, triple_c])
        result.addCallbacks(multiply, self.error_handler)

        # do actual communication
        self.activate_reactor()

        return result

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

        1) ``for i = 1, ..., d do [f_i] = rand(), [g_i] = rand()``

        2) ``for j = 1, ..., 2d+1 do
             [F_j] = [x] + SUM_i=1^d [f_i]*j^i 
             and
             [G_j] = [y] + SUM_i=1^d [g_i]*j^i`` 

        3) for j = 1, ..., 2d+1 do [H_j] = Mul([F_j], [G_j], [a_j], [b_j], [c_j])

        4) compute [H_0] = SUM_j=1^2d+1 delta_j[H_j] 

        5) output [z] = [H_0]

        delta_j = PRODUCT_k=1, k!=j^2d+1 k/(k-j).
        """
        assert isinstance(share_x, Share) or isinstance(share_y, Share), \
            "At least one of share_x and share_y must be a Share."

        self.program_counter[-1] += 1

        field = getattr(share_x, "field", getattr(share_y, "field", None))
        n = field(0)

        cmul_result = self._cmul(share_x, share_y, field)
        if cmul_result is not None:
            return cmul_result

        # 1) for i = 1, ..., d do [f_i] = rand(), [g_i] = rand()
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
            if 1 in t:
                f = t[1]
            if 2 in t:
                g = t[2]
#             print "==> poly", self.id
#             print "x:", x
#             print "y:", y
#             print "f:", f
#             print "g:", g
            # 2) for j = 1, ..., 2d+1 do
            # [F_j] = [x] + SUM_i=1^d [f_i]*j^i 
            # and
            # [G_j] = [y] + SUM_i=1^d [g_i]*j^i 
            h0i, rhoh0, Ch0 = self._additive_constant(field(0), n)
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
        if g:
            ls.append(gather_shares(g))
        if f:
            ls.append(gather_shares(f))
        result = gather_shares(ls)
        self.schedule_callback(result, compute_polynomials)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        return result

    def triple_gen(self, field):
        """Generate a triple ``a, b, c`` s.t. ``c = a * b``.

        1) Every party ``P_i`` chooses random values ``a_i, r_i in Z_p X (Z_p)^2``,
        compute ``alpha_i = Enc_eki(a_i)`` and ``Ai = Com_ck(a_i, r_i)``, and
        broadcast them.

        2) Every party ``P_j`` does:
           (a) choose random ``b_j, s_j in Z_p X (Z_p)^2``.

           (b) compute ``B_j = ``Com_ck(b_j, s_j)`` and broadcast it.

           (c) ``P_j`` do towards every other party:
                i. choose random ``d_ij in Z_p^3``
               ii. compute and send 
                   ``gamma_ij = alpha_i^b_j Enc_ek_i(1;1)^d_ij`` to ``P_i``.

        3) Every party ``P_i`` does:
           (a) compute ``c_i = SUM_j Dec_sk_i(gamma_ij) - SUM_j d_ij mod p``

           (b) pick random ``t_i in (Z_p)^2``, compute and 
               broadcast ``C_i = Com_ck(c_i, t_i)``

        4) Everyone computes:
           ``(A, B, C) = (PRODUCT_i A_i, PRODUCT_i B_i, PRODUCT_i C_i)``
        
        5) Every party ``P_i`` outputs shares ``[a_i] = (a_i, r_i, A)``, 
           ``[b_i] = (b_i, s_i, B)``, and ``[c_i] = (c_i, t_i, C)``.

        """
        self.program_counter[-1] += 1

        def random_number(p):
            return field(rand.randint(0, p - 1))

        def product(ls):
            """Compute the product of the elements in the list *ls*."""
            b = commitment.deserialize(ls[0])
            for x in ls[1:]:
                b *= commitment.deserialize(x)
            return b

        def sum(ls):
            """Compute the sum of the elements in the list *ls*."""
            b = field(0)
            for x in ls:
                b += x
            return b

        def step45(Cs, alphas, gammas, alpha_randomness,
                   As, Bs, ai, bi, ci, r, s, t, dijs):
            """4) Everyone computes:
                  ``A = PRODUCT_i A_i``
                  ``B = PRODUCT_i B_i``
                  ``C = PRODUCT_i C_i``
        
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
            ls = decrypt_gammas(gammas)
            ci = sum(ls) - sum(dijs)
            # (b) pick random t_i in (Z_p)^2.
            t1 = random_number(field. modulus)
            t2 = random_number(field. modulus)
            t = (t1, t2)
            # C_i = Com_ck(c_i, t_i).
            Ci = commitment.commit(ci.value, t1.value, t2.value)
            
            # Broadcast Ci.
            Cs = self.broadcast(self.players.keys(), self.players.keys(), repr(Ci))
            result = gatherResults(Cs)
            result.addCallbacks(step45, self.error_handler, callbackArgs=(alphas, gammas, alpha_randomness, 
                                                                          As, Bs, ai, bi, ci, r, s, t, dijs))
            return result

        def step2c(Bs, As, alphas, alpha_randomness, ai, bj, r, s):
            """(c) P_j do, towards every other party:
                   i. choose random d_i,j in Z_p^3
                   ii. compute and send 
            gamma_ij = alpha_i^b_j Enc_ek_i(1;1)^d_ij to P_i.
            """

            # (c) P_j do, towards every other party:
            dijs = [None] * len(self.players.keys())
            results = [None] * len(self.players.keys())
            pc = tuple(self.program_counter)
            for pi in self.players.keys():
                n = self.players[pi].pubkey[0]
                nsq = n * n
                # choose random d_i,j in Z_p^3
                dij = random_number(field.modulus**3)
                # Enc_ek_i(1;1)^d_ij
                enc = encrypt_r(1, 1, self.players[pi].pubkey)
                t1 = pow(enc, dij.value, nsq)
                # alpha_i^b_j.
                t2 = pow(alphas[pi - 1], bj.value, nsq)
                # gamma_ij = alpha_i^b_j Enc_ek_i(1;1)^d_ij
                gammaij = (t2) * (t1) % nsq
                # Broadcast gamma_ij
                if pi != self.id:
                    self.protocols[pi].sendData(pc, PAILLIER, str(gammaij))
                    d = Deferred()
                    d.addCallbacks(lambda value: long(value), self.error_handler)
                    self._expect_data(pi, PAILLIER, d)
                else:
                    d = Deferred()
                    d.callback(gammaij)
                dijs[pi - 1] = dij
                results[pi - 1] = d
            result = gatherResults(results)
            self.schedule_callback(result, step3, alphas, alpha_randomness, 
                                   As, Bs, ai, bj, r, s, dijs)
            result.addErrback(self.error_handler)
            return result

        def step2ab((alphas, As), ai, r, alpha_randomness):
            """2) Every party P_j does:
                  (a) choose random b_j, s_j in Z_p X (Z_p)^2.

                  (b) compute B_j = Com_ck(b_j, s_j) and broadcast it.
            """
            # (a) choose random b_j, s_j in Z_p X (Z_p)^2.
            bj = random_number(field.modulus)
            s1 = random_number(field.modulus)
            s2 = random_number(field.modulus)
            # (b) compute B_j = Com_ck(b_j, s_j).
            Bj = commitment.commit(bj.value, s1.value, s2.value)

            # Broadcast B_j.
            results = self.broadcast(self.players.keys(), self.players.keys(), repr(Bj))
            result = gatherResults(results)
            self.schedule_callback(result, step2c, As, alphas, alpha_randomness, 
                                   ai, bj, r, (s1, s2))
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
        n, g = self.players[self.id].pubkey
        alpha_randomness = rand.randint(1, long(n))
        alphai = encrypt_r(ai.value, alpha_randomness, (n, g))
        # and A_i = Com_ck(a_i, r_i).
        Ai = commitment.commit(ai.value, r1.value, r2.value)

        # broadcast alpha_i and A_i.
        ds = self.broadcast(sorted(self.players.keys()), sorted(self.players.keys()), str(alphai) + ":" + repr(Ai))

        result = gatherResults(ds)
        def split_alphas_and_As(ls):
            alphas = []
            As = []
            for x in ls:
                alpha, Ai = x.split(':')
                alphas.append(long(alpha))
                As.append(Ai)
            return alphas, As
        self.schedule_callback(result, split_alphas_and_As)
        self.schedule_callback(result, step2ab, ai, (r1, r2), alpha_randomness)
        result.addErrback(self.error_handler)
        return result
                

    def error_handler(self, ex):
        print "Error: ", ex
        return ex

