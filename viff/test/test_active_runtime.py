# Copyright 2008 VIFF Development Team.
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

from twisted.internet.defer import gatherResults

from viff.test.util import RuntimeTestCase, protocol


class ActiveRuntimeTest(RuntimeTestCase):
    """Test for active security."""

    #: Number of players.
    #:
    #: The protocols for active security needs n > 3t+1, so with the
    #: default threshold of t=1, we need n=4.
    num_players = 4

    @protocol
    def test_broadcast(self, runtime):
        """Test Bracha broadcast."""
        # TODO: Figure out how to introduce network errors and test
        # those too.
        if runtime.id == 1:
            x = runtime.broadcast([1], "Hello world!")
        else:
            x = runtime.broadcast([1])

        if runtime.id == 2:
            y, z = runtime.broadcast([2, 3], "Hello two!")
        elif runtime.id == 3:
            y, z = runtime.broadcast([2, 3], "Hello three!")
        else:
            y, z = runtime.broadcast([2, 3])

        x.addCallback(self.assertEquals, "Hello world!")
        
        y.addCallback(self.assertEquals, "Hello two!")
        z.addCallback(self.assertEquals, "Hello three!")
        
        return gatherResults([x, y, z])
