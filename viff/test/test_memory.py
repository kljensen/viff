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

from viff.field import GF256
from viff.runtime import Share
from viff.test.util import RuntimeTestCase, protocol

class MemoryTest(RuntimeTestCase):
    """Tests that memory is freed when the expected data has
    arrived."""

    def check_empty(self, _, runtime):
        """Check that all protocols are empty."""
        for p in runtime.protocols.itervalues():
            self.assertEquals(p.incoming_data, {})

    @protocol
    def test_empty_incoming_data(self, runtime):
        """Check that a single sharing does not leak memory."""
        if runtime.id == 1:
            x = runtime.shamir_share([1], self.Zp, 10)
        else:
            x = runtime.shamir_share([1], self.Zp)

        def check(_):
            for p in runtime.protocols.itervalues():
                self.assertEquals(p.incoming_data, {})

        x.addCallback(self.check_empty, runtime)
        return x

    @protocol
    def test_intermediate_released(self, runtime):
        """Check that a complex calculation does not leak memory."""
        x, y, z = runtime.shamir_share([1, 2, 3], self.Zp, runtime.id)
        w = x * y + z
        w.addCallback(self.check_empty, runtime)
        return w
