# -*- coding: utf-8 -*-
#
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

"""VIFF reactor to have control over the scheduling."""

__docformat__ = "restructuredtext"

from twisted.internet.selectreactor import SelectReactor


class ViffReactor(SelectReactor):
    """VIFF reactor.

    The only difference to the SelectReactor is the loop call.
    From there, doIteration() can be called recursively."""

    def __init__(self):
        SelectReactor.__init__(self)
        self.loopCall = lambda: None
   
    def setLoopCall(self, f):
        self.loopCall = f

    def doIteration(self, t):
        # Do the same as in mainLoop() first.
        self.runUntilCurrent()
        t2 = self.timeout()

        if t2 is not None:
            t = min(t, self.running and t2)

        SelectReactor.doIteration(self, t)
        self.loopCall()

def install():
    """Use the VIFF reactor."""
    reactor = ViffReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
