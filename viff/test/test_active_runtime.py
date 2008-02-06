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

import os
from random import Random

from twisted.internet.defer import gatherResults

from viff.field import GF256
from viff.runtime import Share

from viff.test.util import RuntimeTestCase, protocol

class ActiveRuntimeTest(RuntimeTestCase):

    num_players = 4

    @protocol
    def test_broadcast(self, runtime):
        """Test Bracha broadcast."""
        # TODO: Figure out how to introduce network errors and test
        # those too.
        if runtime.id == 1:
            x = runtime.broadcast(1, "Hello world!")
        else:
            x = runtime.broadcast(1)

        x.addCallback(self.assertEquals, "Hello world!")
        return x
