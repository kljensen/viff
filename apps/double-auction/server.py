# Copyright 2007, 2008 VIFF Development Team.
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

from twisted.internet import reactor
from twisted.internet.protocol import Factory
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
