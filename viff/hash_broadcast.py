#!/usr/bin/env python

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

from twisted.internet.defer import Deferred

try:
    from hashlib import sha1
except ImportError:
    from sha import sha as sha1
from viff.constants import TEXT, INCONSISTENTHASH, OK, HASH

from twisted.internet.defer import gatherResults

error_msg = "Player %i, has received an inconsistent hash %s."

class InconsistentHashException(Exception):
    pass

class HashBroadcastMixin:
    """A weak-crusader broadcast scheme.

    A value is send using `send_value` and when received a hash is
    generated and exchanged among the receivers. If a receiver
    receives a hash which is not equal to the one he generated, then
    he aborts. Else he returns the received value and the computation
    continues."""

    def _send_message(self, pc, sender, receivers, message):
        for peer_id in receivers:
            self.protocols[peer_id].sendData(pc, TEXT, message)

    def _receive_broadcast(self, pc, unique_pc, sender, receivers):

        def message_received(m, unique_pc, receivers):
            # Compute hash of message.
            h = sha1(m).hexdigest()
            # Send the hash to all receivers.
            for peer_id in receivers:
                self.protocols[peer_id].sendData(unique_pc, HASH, str(h))
            return m, h
                
        # Set up receiver for hashes.
        # Note, we use the unique_pc to avoid data to cross
        # method invocation boundaries.
        for peer_id in receivers:
            hashes = []
            d_hash = Deferred()
            self._expect_data_with_pc(unique_pc, peer_id, HASH, d_hash)
            hashes.append(d_hash)

        # Set up receiving of the message.
        d_message = Deferred().addCallbacks(message_received, 
                                            self.error_handler, 
                                            callbackArgs=(unique_pc, receivers))
        self._expect_data(sender, TEXT, d_message)

	def combine(ls):                      
            m, h = ls[0]
            s = reduce(lambda x, y: (h == y and x) or INCONSISTENTHASH, [OK] + ls[1:])
            if not OK == s:
		raise InconsistentHashException(error_msg % (self.id, ls))
            return m

        r = gatherResults([d_message] + hashes)
        r.addCallback(combine)
        return r



    def broadcast(self, senders, receivers, message=None):
        """Broadcast the messeage from senders to receivers.

        Returns a list of deferreds if the calling player is among 
        the receivers and there are multiple senders.
        Returns a single element if there is only on sender, or the 
        calling player is among the senders only.

        The order of the resulting list is guaranteed to be the same order 
        as the list of senders.

        Senders and receivers should be lists containing the id of the senders 
        and receivers, respectively.

        Note: You send implicitly to your self."""
        assert message is None or self.id in senders

        self.increment_pc()

        pc = tuple(self.program_counter)
        if self.id in receivers or self.id in senders:
            results = [None] * len(senders)
        else:
            results = []

        if self.id in senders:
            self._send_message(pc, self.id, receivers, message)

        if self.id in receivers:
            for x in xrange(len(senders)):
                sender = senders[x]
                new_pc = list(self.program_counter)
                new_pc.append(x)
                results[x] = self._receive_broadcast(pc, tuple(new_pc), sender, receivers)

        if self.id in senders and self.id not in receivers:
            d = Deferred()
            d.callback(message)
            results = [d]

        if len(results) == 1:
            return results[0]

        return results
          
    def list_str(self, s):
        ls = []
        for x in s[1:-1].split(','):
            x = x.strip()
            ls.append(str(x)[1:-1])
        return ls

    def error_handler(self, ex):
        print "Error: ", ex
        return ex
