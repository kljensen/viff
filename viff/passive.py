# -*- coding: utf-8 -*-
#
# Copyright 2008 VIFF Development Team.
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

"""Passively secure VIFF runtime."""

import operator

from viff import shamir
from viff.runtime import Runtime, Share, ShareList, gather_shares, preprocess
from viff.prss import prss, prss_lsb, prss_zero, prss_multi
from viff.field import GF256, FieldElement
from viff.util import rand, profile

from twisted.internet.defer import gatherResults


class PassiveRuntime(Runtime):
    """The VIFF runtime.

    The runtime is used for sharing values (:meth:`shamir_share` or
    :meth:`prss_share`) into :class:`~viff.runtime.Share` object and
    opening such shares (:meth:`open`) again. Calculations on shares
    is normally done through overloaded arithmetic operations, but it
    is also possible to call :meth:`add`, :meth:`mul`, etc. directly
    if one prefers.

    Each player in the protocol uses a :class:`~viff.runtime.Runtime`
    object. To create an instance and connect it correctly with the
    other players, please use the :func:`~viff.runtime.create_runtime`
    function instead of instantiating a :class:`~viff.runtime.Runtime`
    directly. The :func:`~viff.runtime.create_runtime` function will
    take care of setting up network connections and return a
    :class:`Deferred` which triggers with the
    :class:`~viff.runtime.Runtime` object when it is ready.
    """

    def __init__(self, player, threshold, options=None):
        """Initialize runtime."""
        Runtime.__init__(self, player, threshold, options)

    def output(self, share, receivers=None, threshold=None):
        return self.open(share, receivers, threshold)

    def open(self, share, receivers=None, threshold=None):
        """Open a secret sharing.

        The *receivers* are the players that will eventually obtain
        the opened result. The default is to let everybody know the
        result. By default the :attr:`threshold` + 1 shares are
        reconstructed, but *threshold* can be used to override this.

        Communication cost: every player sends one share to each
        receiving player.
        """
        assert isinstance(share, Share)
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()
        if threshold is None:
            threshold = self.threshold

        def filter_good_shares(results):
            # Filter results, which is a list of (success, share)
            # pairs.
            return [result[1] for result in results
                    if result is not None and result[0]][:threshold+1]

        def recombine(shares):
            assert len(shares) > threshold
            result = ShareList(shares, threshold+1)
            result.addCallback(filter_good_shares)
            result.addCallback(shamir.recombine)
            return result

        def exchange(share):
            # Send share to all receivers.
            for peer_id in receivers:
                if peer_id != self.id:
                    pc = tuple(self.program_counter)
                    self.protocols[peer_id].sendShare(pc, share)
            # Receive and recombine shares if this player is a receiver.
            if self.id in receivers:
                deferreds = []
                for peer_id in self.players:
                    if peer_id == self.id:
                        d = Share(self, share.field, (share.field(peer_id), share))
                    else:
                        d = self._expect_share(peer_id, share.field)
                        d.addCallback(lambda s, peer_id: (s.field(peer_id), s), peer_id)
                    deferreds.append(d)
                return recombine(deferreds)

        result = share.clone()
        self.schedule_callback(result, exchange)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    @profile
    def add(self, share_a, share_b):
        """Addition of shares.

        Communication cost: none.
        """
        if not isinstance(share_b, Share):
            # Addition with constant. share_a always is a Share by
            # operator overloading in Share. Clone share_a to avoid
            # changing it.
            result = share_a.clone()
            result.addCallback(lambda a, b: b + a, share_b)
            return result
        
        result = gather_shares([share_a, share_b])
        result.addCallback(lambda (a, b): a + b)
        return result

    def sub(self, share_a, share_b):
        """Subtraction of shares.

        Communication cost: none.
        """
        field = getattr(share_a, "field", getattr(share_b, "field", None))
        if not isinstance(share_a, Share):
            share_a = Share(self, field, share_a)
        if not isinstance(share_b, Share):
            share_b = Share(self, field, share_b)

        result = gather_shares([share_a, share_b])
        result.addCallback(lambda (a, b): a - b)
        return result

    @profile
    def lin_comb(self, coefficients, shares):
        """Linear combination of shares.

        Communication cost: none. Saves the construction of unnecessary shares
        compared to using add() and mul()."""

        for coeff in coefficients:
            assert not isinstance(coeff, Share), \
                "Coefficients should not be shares."

        for share in shares:
            assert isinstance(share, Share), \
                "Shares should be shares."

        assert len(coefficients) == len(shares), \
            "Number of coefficients and shares should be equal."

        def computation(shares, coefficients):
            return sum(map(operator.mul, coefficients, shares))

        result = gather_shares(shares)
        result.addCallback(computation, coefficients)
        return result

    @profile
    def mul(self, share_a, share_b):
        """Multiplication of shares.

        Communication cost: 1 Shamir sharing.
        """
        assert isinstance(share_a, Share), \
            "share_a must be a Share."

        if not isinstance(share_b, Share):
            # Local multiplication. share_a always is a Share by
            # operator overloading in Share. We clone share_a first
            # to avoid changing it.
            result = share_a.clone()
            result.addCallback(lambda a: share_b * a)
            return result

        # At this point both share_a and share_b must be Share
        # objects. So we wait on them, multiply and reshare.

        def share_recombine(number):
            shares = shamir.share(number, self.threshold, self.num_players)

            exchanged_shares = []
            for peer_id, share in shares:
                d = self._exchange_shares(peer_id.value, share)
                d.addCallback(lambda share, peer_id: (peer_id, share), peer_id)
                exchanged_shares.append(d)

            # Recombine the first 2t+1 shares.
            result = gather_shares(exchanged_shares[:2*self.threshold+1])
            result.addCallback(shamir.recombine)
            return result

        result = gather_shares([share_a, share_b])
        result.addCallback(lambda (a, b): a * b)
        self.schedule_callback(result, share_recombine)

        # do actual communication
        self.activate_reactor()

        return result

    def pow(self, share, exponent):
        """Exponentation of a share to an integer by square-and-multiply."""

        assert isinstance(exponent, (int, long)), "Exponent must be an integer"
        assert exponent >= 0, "Exponent must be non-negative"

        if exponent == 0:
            return 1
        elif exponent % 2 == 0:
            tmp = share ** (exponent / 2)
            return tmp * tmp
        else:
            return share * (share ** (exponent-1))

    def xor(self, share_a, share_b):
        field = share_a.field
        if not isinstance(share_b, Share):
            if not isinstance(share_b, FieldElement):
                share_b = field(share_b)
            share_b = Share(self, field, share_b)

        if field is GF256:
            return share_a + share_b
        else:
            return share_a + share_b - 2 * share_a * share_b

    def prss_key(self):
        """Create unique key for PRSS.

        This increments the program counter and returns it as a tuple.
        Each straight-line program (typically a callback attached to
        some :class:`Deferred`) is executed in a context with unique
        starting program counter. This ensures that consequetive calls
        to PRSS-related methods will use unique program counters.
        """

        # This is called by every function using PRSS, so do it here.
        # If the assertion is not met, things go wrong, i.e. the PRSS
        # functions generate shares with higher degrees than what
        # open() and mul() expect.
        assert self.threshold >= \
               len(self.players) - len(self.players[self.id].keys.keys()[0]), \
               "PRSS functions have higher threshold than the runtime."

        self.increment_pc()
        return tuple(self.program_counter)

    def prss_share(self, inputters, field, element=None):
        """Creates pseudo-random secret sharings.

        This protocol creates a secret sharing for each player in the
        subset of players specified in *inputters*. Each inputter
        provides an integer. The result is a list of shares, one for
        each inputter.

        The protocol uses the pseudo-random secret sharing technique
        described in the paper "Share Conversion, Pseudorandom
        Secret-Sharing and Applications to Secure Computation" by
        Ronald Cramer, Ivan Damgård, and Yuval Ishai in Proc. of TCC
        2005, LNCS 3378. `Download
        <http://www.cs.technion.ac.il/~yuvali/pubs/CDI05.ps>`__

        Communication cost: Each inputter does one broadcast.
        """
        # Verifying parameters.
        if element is None:
            assert self.id not in inputters, "No element given."
        else:
            assert self.id in inputters, \
                "Element given, but we are not sharing?"

        n = self.num_players

        # Key used for PRSS.
        key = self.prss_key()

        # The shares for which we have all the keys.
        all_shares = []

        # Shares we calculate from doing PRSS with the other players.
        tmp_shares = {}

        prfs = self.players[self.id].dealer_prfs(field.modulus)

        # Compute and broadcast correction value.
        if self.id in inputters:
            for player in self.players:
                share = prss(n, player, field, prfs[self.id], key)
                all_shares.append((field(player), share))
            shared = shamir.recombine(all_shares[:self.threshold+1])
            correction = element - shared
            # if this player is inputter then broadcast correction value
            # TODO: more efficient broadcast?
            pc = tuple(self.program_counter)
            for peer_id in self.players:
                if self.id != peer_id:
                    self.protocols[peer_id].sendShare(pc, correction)

        # Receive correction value from inputters and compute share.
        result = []
        for player in inputters:
            tmp_shares[player] = prss(n, self.id, field, prfs[player], key)
            if player == self.id:
                d = Share(self, field, correction)
            else:
                d = self._expect_share(player, field)
            d.addCallback(lambda c, s: s + c, tmp_shares[player])
            result.append(d)

        # Unpack a singleton list.
        if len(result) == 1:
            return result[0]
        else:
            return result

    def prss_share_random(self, field, binary=False):
        """Generate shares of a uniformly random element from the field given.

        If binary is True, a 0/1 element is generated. No player
        learns the value of the element.

        Communication cost: none if binary=False, 1 open otherwise.
        """
        if field is GF256 and binary:
            modulus = 2
        else:
            modulus = field.modulus

        # Key used for PRSS.
        prss_key = self.prss_key()
        prfs = self.players[self.id].prfs(modulus)
        share = prss(self.num_players, self.id, field, prfs, prss_key)

        if field is GF256 or not binary:
            return Share(self, field, share)

        # Open the square and compute a square-root
        result = self.open(Share(self, field, share*share),
                           threshold=2*self.threshold)

        def finish(square, share, binary):
            if square == 0:
                # We were unlucky, try again...
                return self.prss_share_random(field, binary)
            else:
                # We can finish the calculation
                root = square.sqrt()
                # When the root is computed, we divide the share and
                # convert the resulting -1/1 share into a 0/1 share.
                return Share(self, field, (share/root + 1) / 2)

        self.schedule_callback(result, finish, share, binary)
        return result

    def prss_share_random_multi(self, field, quantity, binary=False):
        """Does the same as calling *quantity* times :meth:`prss_share_random`,
        but with less calls to the PRF. Sampling of a binary element is only
        possible if the field is :class:`GF256`.

        Communication cost: none.
        """
        assert not binary or field == GF256, "Binary sampling not possible " \
            "for this field, use prss_share_random()."

        if field is GF256 and binary:
            modulus = 2
        else:
            modulus = field.modulus

        # Key used for PRSS.
        prss_key = self.prss_key()
        prfs = self.players[self.id].prfs(modulus ** quantity)
        shares = prss_multi(self.num_players, self.id, field, prfs, prss_key,
                            modulus, quantity)
        return [Share(self, field, share) for share in shares]

    def prss_share_zero(self, field, quantity):
        """Generate *quantity* shares of the zero element from the
        field given.

        Communication cost: none.
        """
        # Key used for PRSS.
        prss_key = self.prss_key()
        prfs = self.players[self.id].prfs(field.modulus)
        zero_share = prss_zero(self.num_players, self.threshold, self.id,
                               field, prfs, prss_key, quantity)
        return [Share(self, field, zero_share[i]) for i in range(quantity)]

    def prss_double_share(self, field, quantity):
        """Make *quantity* double-sharings using PRSS.

        The pair of shares will have degree t and 2t where t is the
        default threshold for the runtime.
        """
        r_t = self.prss_share_random_multi(field, quantity)
        z_2t = self.prss_share_zero(field, quantity)
        return (r_t, [r_t[i] + z_2t[i] for i in range(quantity)])

    def prss_share_bit_double(self, field):
        """Share a random bit over *field* and GF256.

        The protocol is described in "Efficient Conversion of
        Secret-shared Values Between Different Fields" by Ivan Damgård
        and Rune Thorbek available as `Cryptology ePrint Archive,
        Report 2008/221 <http://eprint.iacr.org/2008/221>`__.
        """
        n = self.num_players
        k = self.options.security_parameter
        prfs = self.players[self.id].prfs(2**k)
        prss_key = self.prss_key()

        b_p = self.prss_share_random(field, binary=True)
        r_p, r_lsb = prss_lsb(n, self.id, field, prfs, prss_key)

        b = self.open(b_p + r_p)
        # Extract least significant bit and change field to GF256.
        b.addCallback(lambda i: GF256(i.value & 1))
        b.field = GF256

        # Use r_lsb to flip b as needed.
        return (b_p, b ^ r_lsb)

    def prss_shamir_share_bit_double(self, field):
        """Shamir share a random bit over *field* and GF256."""
        n = self.num_players
        k = self.options.security_parameter
        prfs = self.players[self.id].prfs(2**k)
        prss_key = self.prss_key()
        inputters = range(1, self.num_players + 1)

        ri = rand.randint(0, 2**k - 1)
        ri_p = self.shamir_share(inputters, field, ri)
        ri_lsb = self.shamir_share(inputters, GF256, ri & 1)

        r_p = reduce(self.add, ri_p)
        r_lsb = reduce(self.add, ri_lsb)

        b_p = self.prss_share_random(field, binary=True)
        b = self.open(b_p + r_p)
        # Extract least significant bit and change field to GF256.
        b.addCallback(lambda i: GF256(i.value & 1))
        b.field = GF256

        # Use r_lsb to flip b as needed.
        return (b_p, b ^ r_lsb)

    def powerchain(self, share, max):
        """Returns the list [*share*, *share*^2, *share*^4, ...,
        *share*^(i^max)]."""
        result = [share]
        for i in range(max):
            share = share * share
            result.append(share)
        return result

    @preprocess("prss_powerchains")
    def prss_powerchain(self, max=7):
        """Generate a random secret share in GF256 and returns
        [*share*, *share*^2, *share*^4, ..., *share*^(i^max)]."""
        share = self.prss_share_random(GF256)
        return self.powerchain(share, max)

    def prss_powerchains(self, max=7, quantity=20):
        """Does *quantity* times the same as :meth:`prss_powerchain`.
        Used for preprocessing."""
        quantity = min(quantity, 20)
        shares = self.prss_share_random_multi(GF256, quantity)
        return [gatherResults(self.powerchain(share, max)) for share in shares]

    def input(self, inputters, field, number=None, threshold=None):
        """Input *number* to the computation.

        The input is shared using the :meth:`shamir_share` method.
        """
        return self.shamir_share(inputters, field, number, threshold)

    def shamir_share(self, inputters, field, number=None, threshold=None):
        """Secret share *number* over *field* using Shamir's method.

        The number is shared using polynomial of degree *threshold*
        (defaults to :attr:`threshold`). Returns a list of shares
        unless there is only one inputter in which case the
        share is returned directly.

        In code it is used like this::

            a, b, c = runtime.shamir_share([1, 2, 3], Zp, x)

        where ``Zp`` is a field and ``x`` is a Python integer holding
        the input of each player (three inputs in total).

        If only a subset of the players provide input it looks like
        this::

            if runtime.id == 1:
                a = runtime.shamir_share([1], Zp, x)
            else:
                a = runtime.shamir_share([1], Zp)

        Instead of branching when calling :meth:`shamir_share`, one
        can give ``None`` as input::

            if runtime.id == 1:
                x = int(raw_input("Input x: "))
            else:
                x = None
            a = runtime.shamir_share([1], Zp, x)

        which might be practical in some cases.

        Communication cost: n elements transmitted.
        """
        assert number is None or self.id in inputters
        if threshold is None:
            threshold = self.threshold

        results = []
        for peer_id in inputters:
            # Unique program counter per input.
            self.increment_pc()

            if peer_id == self.id:
                pc = tuple(self.program_counter)
                shares = shamir.share(field(number), threshold,
                                      self.num_players)
                for other_id, share in shares:
                    if other_id.value == self.id:
                        results.append(Share(self, share.field, share))
                    else:
                        self.protocols[other_id.value].sendShare(pc, share)
            else:
                results.append(self._expect_share(peer_id, field))

        # do actual communication
        self.activate_reactor()

        # Unpack a singleton list.
        if len(results) == 1:
            return results[0]
        else:
            return results
