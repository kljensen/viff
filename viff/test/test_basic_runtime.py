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

from twisted.internet.defer import Deferred, gatherResults
from twisted.trial.unittest import TestCase

from viff.test.util import RuntimeTestCase, protocol

class ProgramCounterTest(RuntimeTestCase):
    """Program counter tests."""

    @protocol
    def test_initial_value(self, runtime):
        self.assertEquals(runtime.program_counter, [0])

    @protocol
    def test_simple_operation(self, runtime):
        """Test an operation which makes no further calls.

        Each call should increment the program counter by one.
        """
        runtime.synchronize()
        self.assertEquals(runtime.program_counter, [1])
        runtime.synchronize()
        self.assertEquals(runtime.program_counter, [2])

    @protocol
    def test_complex_operation(self, runtime):
        """Test an operation which makes nested calls.

        This verifies that the program counter is only incremented by
        one, even for a complex operation.
        """
        # Exclusive-or is calculated as x + y - 2 * x * y, so add,
        # sub, and mul are called.
        runtime.xor(self.Zp(0), self.Zp(1))
        self.assertEquals(runtime.program_counter, [1])
        runtime.xor(self.Zp(0), self.Zp(1))
        self.assertEquals(runtime.program_counter, [2])


    @protocol
    def test_callback(self, runtime):
        """Test a scheduled callback.

        The callback should see the program counter as it was when the
        callback was added and not the current value.
        """

        def verify_program_counter(_):
            self.assertEquals(runtime.program_counter, [0])

        d = Deferred()
        runtime.callback(d, verify_program_counter)

        runtime.synchronize()
        self.assertEquals(runtime.program_counter, [1])

        # Now trigger verify_program_counter.
        d.callback(None)
