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

from twisted.internet.defer import Deferred, gatherResults

from viff.runtime import Runtime, Share, ShareList, gather_shares
from viff.util import rand
from viff.constants import TEXT

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
                raise OrlandiException("Wrong commitment for value %s, found %s expected %s." % 
                                       (x, Cx1, Cx))

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

    def error_handler(self, ex):
        print "Error: ", ex
        return ex
