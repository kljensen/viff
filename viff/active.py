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

"""A thresholdbased actively secure runtime."""

from math import ceil

from gmpy import numdigits

from twisted.internet.defer import gatherResults, Deferred

from viff import shamir
from viff.util import rand
from viff.matrix import Matrix, hyper
from viff.passive import PassiveRuntime
from viff.runtime import Share, preprocess, gather_shares
from viff.constants import ECHO, READY, SEND


class BrachaBroadcastMixin:
    """Bracha broadcast mixin class. This mixin class adds a
    :meth:`broadcast` method which can be used for a reliable
    broadcast.
    """

    def _broadcast(self, sender, message=None):
        """Perform a Bracha broadcast.

        A Bracha broadcast is reliable against an active adversary
        corrupting up to t < n/3 of the players. For more details, see
        the paper "An asynchronous [(n-1)/3]-resilient consensus
        protocol" by G. Bracha in Proc. 3rd ACM Symposium on
        Principles of Distributed Computing, 1984, pages 154-162.
        """
        # We need a unique program counter for each call.
        self.increment_pc()

        result = Deferred()
        pc = tuple(self.program_counter)
        n = self.num_players
        t = self.threshold

        # For each distinct message (and program counter) we save a
        # dictionary for each of the following variables. The reason
        # is that we need to count for each distinct message how many
        # echo and ready messages we have received.

        bracha_echo = {}
        bracha_ready = {}
        bracha_sent_ready = {}
        bracha_delivered = {}

        def unsafe_broadcast(data_type, message):
            # Performs a regular broadcast without any guarantees. In
            # other words, it sends the message to each player except
            # for this one.
            for protocol in self.protocols.itervalues():
                protocol.sendData(pc, data_type, message)

            # do actual communication
            self.activate_reactor()

        def echo_received(message, peer_id):
            # This is called when we receive an echo message. It
            # updates the echo count for the message and enters the
            # ready state if the count is high enough.
            ids = bracha_echo.setdefault(message, [])
            ready = bracha_sent_ready.setdefault(message, False)

            if peer_id not in ids:
                ids.append(peer_id)
                if len(ids) >= ceil((n+t+1)/2) and not ready:
                    bracha_sent_ready[message] = True
                    unsafe_broadcast(READY, message)
                    ready_received(message, self.id)

        def ready_received(message, peer_id):
            # This is called when we receive a ready message. It
            # updates the ready count for the message. Depending on
            # the count, we may either stay in the same state or enter
            # the ready or delivered state.
            ids = bracha_ready.setdefault(message, [])
            ready = bracha_sent_ready.setdefault(message, False)
            delivered = bracha_delivered.setdefault(message, False)
            if peer_id not in ids:
                ids.append(peer_id)
                if len(ids) == t+1 and not ready:
                    bracha_sent_ready[message] = True
                    unsafe_broadcast(READY, message)
                    ready_received(message, self.id)

                elif len(ids) == 2*t+1 and not delivered:
                    bracha_delivered[message] = True
                    result.callback(message)

        def send_received(message):
            # This is called when we receive a send message. We react
            # by sending an echo message to each player. Since the
            # unsafe broadcast doesn't send a message to this player,
            # we simulate it by calling the echo_received function.
            unsafe_broadcast(ECHO, message)
            echo_received(message, self.id)


        # In the following we prepare to handle a send message from
        # the sender and at most one echo and one ready message from
        # each player.
        for peer_id in self.players:
            if peer_id != self.id:
                d_echo = Deferred().addCallback(echo_received, peer_id)
                self._expect_data(peer_id, ECHO, d_echo)

                d_ready = Deferred().addCallback(ready_received, peer_id)
                self._expect_data(peer_id, READY, d_ready)

        # If this player is the sender, we transmit a send message to
        # each player. We send one to this player by calling the
        # send_received function.
        if self.id == sender:
            unsafe_broadcast(SEND, message)
            send_received(message)
        else:
            d_send = Deferred().addCallback(send_received)
            self._expect_data(sender, SEND, d_send)

        # do actual communication
        self.activate_reactor()

        return result

    def broadcast(self, senders, message=None):
        """Perform one or more Bracha broadcast(s).

        The list of *senders* given will determine the subset of players
        who wish to broadcast a message. If this player wishes to
        broadcast, its ID must be in the list of senders and the
        optional *message* parameter must be used.

        If the list of senders consists only of a single sender, the
        result will be a single element, otherwise it will be a list.

        A Bracha broadcast is reliable against an active adversary
        corrupting up to t < n/3 of the players. For more details, see
        the paper "An asynchronous [(n-1)/3]-resilient consensus
        protocol" by G. Bracha in Proc. 3rd ACM Symposium on
        Principles of Distributed Computing, 1984, pages 154-162.
        """
        assert message is None or self.id in senders

        result = []

        for sender in senders:
            if sender == self.id:
                result.append(self._broadcast(sender, message))
            else:
                result.append(self._broadcast(sender))

        if len(result) == 1:
            return result[0]

        return result


class TriplesHyperinvertibleMatricesMixin:
    """Mixin class which generates multiplication triples using
    hyperinvertible matrices."""

    #: A hyper-invertible matrix.
    #:
    #: It should be suitable for :attr:`num_players` players, but
    #: since we don't know the total number of players yet, we set it
    #: to :const:`None` here and update it as necessary.
    _hyper = None

    def _verify_single(self, shares, rvec, T, field, degree):
        """Verify shares.

        It is checked that they correspond to polynomial of the
        expected degree.

        If the verification succeeds, the T shares are returned,
        otherwise the errback is called.
        """
        # TODO: This is necessary since shamir.recombine expects
        # to receive a list of *pairs* of field elements.
        shares = map(lambda (i, s): (field(i+1), s), enumerate(shares))

        # Verify the sharings. If any of the assertions fail and
        # raise an exception, the errbacks will be called on the
        # share returned by single_share_random.
        assert shamir.verify_sharing(shares, degree), \
               "Could not verify %s, degree %d" % (shares, degree)

        # If we reach this point the n - T shares were verified
        # and we can safely return the first T shares.
        return rvec[:T]

    def _exchange_single(self, svec, rvec, T, field, degree, inputters):
        """Exchange and (if possible) verify shares."""
        pc = tuple(self.program_counter)

        # We send our shares to the verifying players.
        for offset, share in enumerate(svec):
            if T+1+offset != self.id:
                self.protocols[T+1+offset].sendShare(pc, share)

        if self.id > T:
            # The other players will send us their shares of si_1
            # and si_2 and we will verify it.
            si = []
            for peer_id in inputters:
                if self.id == peer_id:
                    si.append(Share(self, field, svec[peer_id - T - 1]))
                else:
                    si.append(self._expect_share(peer_id, field))
            result = gatherResults(si)
            result.addCallback(self._verify_single, rvec, T, field, degree)
            return result
        else:
            # We cannot verify anything, so we just return the
            # first T shares.
            return rvec[:T]

        # do actual communication
        self.activate_reactor()


    def single_share_random(self, T, degree, field):
        """Share a random secret.

        The guarantee is that a number of shares are made and out of
        those, the *T* that are returned by this method will be
        correct sharings of a random number using *degree* as the
        polynomial degree.
        """
        # TODO: Move common code between single_share and
        # double_share_random out to their own methods.
        inputters = range(1, self.num_players + 1)
        if self._hyper is None:
            self._hyper = hyper(self.num_players, field)

        # Generate a random element.
        si = rand.randint(0, field.modulus - 1)

        # Every player shares the random value with two thresholds.
        svec = self.shamir_share(inputters, field, si, degree)
        rvec = self._hyper * Matrix([svec]).transpose()
        rvec = rvec.transpose().rows[0]

        result = gather_shares(svec[T:])
        self.schedule_callback(result, self._exchange_single,
                               rvec, T, field, degree, inputters)
        return result

    def double_share_random(self, T, d1, d2, field):
        """Double-share a random secret using two polynomials.

        The guarantee is that a number of shares are made and out of
        those, the *T* that are returned by this method will be correct
        double-sharings of a random number using *d1* and *d2* as the
        polynomial degrees.
        """
        inputters = range(1, self.num_players + 1)
        if self._hyper is None:
            self._hyper = hyper(self.num_players, field)

        # Generate a random element.
        si = rand.randint(0, field.modulus - 1)

        # Every player shares the random value with two thresholds.
        svec1 = self.shamir_share(inputters, field, si, d1)
        svec2 = self.shamir_share(inputters, field, si, d2)

        # Apply the hyper-invertible matrix to svec1 and svec2.
        rvec1 = self._hyper * Matrix([svec1]).transpose()
        rvec2 = self._hyper * Matrix([svec2]).transpose()

        # Get back to normal lists of shares.
        rvec1 = rvec1.transpose().rows[0]
        rvec2 = rvec2.transpose().rows[0]

        def verify(shares):
            """Verify shares.

            It is checked that they correspond to polynomial of the
            expected degrees and that they can be recombined to the
            same value.

            If the verification succeeds, the T double shares are
            returned, otherwise the errback is called.
            """
            si_1, si_2 = shares

            # TODO: This is necessary since shamir.recombine expects
            # to receive a list of *pairs* of field elements.
            si_1 = map(lambda (i, s): (field(i+1), s), enumerate(si_1))
            si_2 = map(lambda (i, s): (field(i+1), s), enumerate(si_2))

            # Verify the sharings. If any of the assertions fail and
            # raise an exception, the errbacks will be called on the
            # double share returned by double_share_random.
            assert shamir.verify_sharing(si_1, d1), \
                   "Could not verify %s, degree %d" % (si_1, d1)
            assert shamir.verify_sharing(si_2, d2), \
                   "Could not verify %s, degree %d" % (si_2, d2)
            assert shamir.recombine(si_1[:d1+1]) == shamir.recombine(si_2[:d2+1]), \
                "Shares do not recombine to the same value"

            # If we reach this point the n - T shares were verified
            # and we can safely return the first T shares.
            return (rvec1[:T], rvec2[:T])

        def exchange(shares):
            """Exchange and (if possible) verify shares."""
            svec1, svec2 = shares
            pc = tuple(self.program_counter)

            # We send our shares to the verifying players.
            for offset, (s1, s2) in enumerate(zip(svec1, svec2)):
                if T+1+offset != self.id:
                    self.protocols[T+1+offset].sendShare(pc, s1)
                    self.protocols[T+1+offset].sendShare(pc, s2)

            if self.id > T:
                # The other players will send us their shares of si_1
                # and si_2 and we will verify it.
                si_1 = []
                si_2 = []
                for peer_id in inputters:
                    if self.id == peer_id:
                        si_1.append(Share(self, field, svec1[peer_id - T - 1]))
                        si_2.append(Share(self, field, svec2[peer_id - T - 1]))
                    else:
                        si_1.append(self._expect_share(peer_id, field))
                        si_2.append(self._expect_share(peer_id, field))
                result = gatherResults([gatherResults(si_1), gatherResults(si_2)])
                result.addCallback(verify)
                return result
            else:
                # We cannot verify anything, so we just return the
                # first T shares.
                return (rvec1[:T], rvec2[:T])

            # do actual communication
            self.activate_reactor()

        result = gather_shares([gather_shares(svec1[T:]), gather_shares(svec2[T:])])
        self.schedule_callback(result, exchange)
        return result

    @preprocess("generate_triples")
    def get_triple(self, field):
        # This is a waste, but this function is only called if there
        # are no pre-processed triples left.
        return self.generate_triples(field, quantity=1, gather=False)[0]

    def generate_triples(self, field, quantity=None, gather=True):
        """Generate multiplication triples.

        These are random numbers *a*, *b*, and *c* such that ``c =
        ab``. This function can be used in pre-processing.

        Returns a tuple with the number of triples generated and a
        Deferred which will yield a list of 3-tuples.
        """
        n = self.num_players
        t = self.threshold
        T = n - 2*t

        def make_triple(shares, results):
            a_t, b_t, (r_t, r_2t) = shares

            c_2t = []
            for i in range(T):
                # Multiply a[i] and b[i] without resharing.
                ci = gather_shares([a_t[i], b_t[i]])
                ci.addCallback(lambda (ai, bi): ai * bi)
                c_2t.append(ci)

            d_2t = [c_2t[i] - r_2t[i] for i in range(T)]
            d = [self.open(d_2t[i], threshold=2*t) for i in range(T)]
            c_t = [r_t[i] + d[i] for i in range(T)]

            if gather:
                for triple, result in zip(zip(a_t, b_t, c_t), results):
                    gatherResults(triple).chainDeferred(result)
            else:
                for triple, result_triple in zip(zip(a_t, b_t, c_t), results):
                    for item, result_item in zip(triple, result_triple):
                        item.chainDeferred(result_item)

        single_a = self.single_share_random(T, t, field)
        single_b = self.single_share_random(T, t, field)
        double_c = self.double_share_random(T, t, 2*t, field)

        if gather:
            results = [Deferred() for i in range(T)]
        else:
            results = [[Share(self, field) for i in range(3)] for i in range(T)]

        self.schedule_callback(gatherResults([single_a, single_b, double_c]), make_triple, results)
        return results

class TriplesPRSSMixin:
    """Mixin class for generating multiplication triples using PRSS."""

    @preprocess("generate_triples")
    def get_triple(self, field):
        result = self.generate_triples(field, quantity=1, gather=False)
        return result[0]

    def generate_triples(self, field, quantity=1, gather=True):
        """Generate *quantity* multiplication triples using PRSS.

        These are random numbers *a*, *b*, and *c* such that ``c =
        ab``. This function can be used in pre-processing.

        Returns a tuple with the number of triples generated and a
        Deferred which will yield a singleton-list with a 3-tuple.
        """

        # This adjusted to the PRF based on SHA1 (160 bits).
        quantity = min(quantity, max(int(160 /numdigits(field.modulus - 1, 2)), 1))

        a_t = self.prss_share_random_multi(field, quantity)
        b_t = self.prss_share_random_multi(field, quantity)
        r_t, r_2t = self.prss_double_share(field, quantity)
        c_t = [0] * quantity

        for i in range(quantity):
            # Multiply a and b without resharing.
            c_2t = gather_shares([a_t[i], b_t[i]])
            c_2t.addCallback(lambda (a, b): a * b)

            d_2t = c_2t - r_2t[i]
            d = self.open(d_2t, threshold=2*self.threshold)
            c_t[i] = r_t[i] + d

        if gather:
            return [gatherResults(triple) for triple in zip(a_t, b_t, c_t)]
        else:
            return zip(a_t, b_t, c_t)


class BasicActiveRuntime(PassiveRuntime):
    """Basic runtime secure against active adversaries.

    This class depends on either
    :class:`TriplesHyperinvertibleMatricesMixin` or
    :class:`TriplesPRSSMixin` to provide a :meth:`get_triple` method.

    Instead of using this class directly, one should probably use
    :class:`ActiveRuntime` instead.
    """

    def get_triple(self, field):
        raise NotImplementedError

    def mul(self, share_x, share_y):
        """Multiplication of shares.

        Preprocessing: 1 multiplication triple.
        Communication: 2 openings.
        """
        assert isinstance(share_x, Share), \
            "share_x must be a Share."

        if not isinstance(share_y, Share):
            # Local multiplication. share_x always is a Share by
            # operator overloading in Share. We clone share_x first
            # to avoid changing it.
            result = share_x.clone()
            result.addCallback(lambda x: share_y * x)
            return result

        # At this point both share_x and share_y must be Share
        # objects. We multiply them via a multiplication triple.
        (a, b, c), _ = self.get_triple(share_x.field)
        d = self.open(share_x - a)
        e = self.open(share_y - b)

        # TODO: We ought to be able to simply do
        #
        #   return d*e + d*y + e*x + c
        #
        # but that leads to infinite recursion since d and e are
        # Shares, not FieldElements. So we have to do a bit more
        # work... The following callback also leads to recursion, but
        # only one level since d and e are FieldElements now, which
        # means that we return in the above if statements.
        result = gather_shares([d, e])
        result.addCallback(lambda (d,e): d*e + d*b + e*a + c)
        return result


class ActiveRuntime(TriplesPRSSMixin, BasicActiveRuntime):
    """Default mix of :class:`BasicActiveRuntime` and
    :class:`TriplesPRSSMixin`."""
    pass
