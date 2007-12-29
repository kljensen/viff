# Copyright 2007 Martin Geisler
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

from twisted.internet import reactor
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import LineReceiver


class ReceiveBid(LineReceiver):

    def __init__(self):
        self.auction_id = None
        self.client_id = None
        self.client_type = None
        self.bids = {}

    def lineReceived(self, line):
        print "Received '%s'" % line
        command, arg = line.split(":", 1)
        command = command.strip()
        arg = arg.strip()

        if command == "auction_id":
            self.auction_id = arg
        elif command == "client_id":
            self.client_id = arg
        elif command == "client_type":
            self.client_type = arg
        elif command.isdigit():
            self.bids[int(command)] = int(arg)
        elif command == "done":
            print "Done! Got %s" % self
        else:
            print "Could not recognize '%s'" % line
        
    def __repr__(self):
        return "<ReceiveBid auction_id: %s, client_id: %s, client_type: %s, bids: %s>" \
               % (self.auction_id, self.client_id, self.client_type, self.bids)


fac = Factory()
fac.protocol = ReceiveBid


reactor.listenTCP(6789, fac)
reactor.run()
