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

from twisted.internet.defer import Deferred, gatherResults

from viff.test.util import RuntimeTestCase, protocol
from viff.runtime import increment_pc


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
        runtime.schedule_callback(d, verify_program_counter)

        runtime.synchronize()
        self.assertEquals(runtime.program_counter, [1])

        # Now trigger verify_program_counter.
        d.callback(None)

    @protocol
    def test_nested_calls(self, runtime):
        """Test Runtime methods that call other methods.

        We create a couple of functions that are used as fake methods.
        """

        @increment_pc
        def method_a(runtime):
            # First top-level call, so first entry is 1. No calls to
            # other methods decorated with increment_pc has been made,
            # so the second entry is 0.
            self.assertEquals(runtime.program_counter, [1, 0])
            method_b(runtime, 1)

            self.assertEquals(runtime.program_counter, [1, 1])
            method_b(runtime, 2)

            # At this point two sub-calls has been made:
            self.assertEquals(runtime.program_counter, [1, 2])

        @increment_pc
        def method_b(runtime, count):
            # This method is called twice from method_a:
            self.assertEquals(runtime.program_counter, [1, count, 0])

        # Zero top-level calls:
        self.assertEquals(runtime.program_counter, [0])
        method_a(runtime)

        # One top-level call:
        self.assertEquals(runtime.program_counter, [1])

    @protocol
    def test_multiple_callbacks(self, runtime):

        d1 = Deferred()
        d2 = Deferred()

        def verify_program_counter(_, count):
            self.assertEquals(runtime.program_counter, [1, count, 0])

        @increment_pc
        def method_a(runtime):
            self.assertEquals(runtime.program_counter, [1, 0])

            runtime.schedule_callback(d1, verify_program_counter, 1)
            runtime.schedule_callback(d2, verify_program_counter, 2)

        method_a(runtime)

        # Trigger verify_program_counter.
        d1.callback(None)
        d2.callback(None)

        return gatherResults([d1, d2])
    test_multiple_callbacks.skip = ("TODO: Scheduling callbacks fails to "
                                    "increment program counter!")

    @protocol
    def test_multi_send(self, runtime):
        """Test sending multiple times from a Runtime method."""

        # First send a couple of times to everybody.
        for peer_id in range(1, self.num_players+1):
            if peer_id != runtime.id:
                pc = tuple(runtime.program_counter)
                runtime.protocols[peer_id].sendData(pc, 42, 100)
                runtime.protocols[peer_id].sendData(pc, 42, 200)
                runtime.protocols[peer_id].sendData(pc, 42, 300)

        # Then receive the data.
        deferreds = []
        for peer_id in range(1, self.num_players+1):
            if peer_id != runtime.id:
                d100 = Deferred().addCallback(self.assertEquals, 100)
                d200 = Deferred().addCallback(self.assertEquals, 200)
                d300 = Deferred().addCallback(self.assertEquals, 300)
                runtime._expect_data(peer_id, 42, d100)
                runtime._expect_data(peer_id, 42, d200)
                runtime._expect_data(peer_id, 42, d300)
                deferreds.extend([d100, d200, d300])

        return gatherResults(deferreds)
