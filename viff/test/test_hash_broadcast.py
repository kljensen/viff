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

from twisted.internet.defer import Deferred, DeferredList

from viff.test.util import RuntimeTestCase, protocol
from viff.field import GF

from viff.comparison import Toft05Runtime
from viff.hash_broadcast import HashBroadcastMixin

class BroadcastRuntime(Toft05Runtime, HashBroadcastMixin):
    """Mix of :class:`Toft05Runtime` and
    :class:`HashBroadcastRuntime`."""
    pass

class HashBroadcastTest(RuntimeTestCase):
    """Test for the hash broadcast mixin."""

    # Number of players.
    num_players = 3

    runtime_class = BroadcastRuntime

    timeout = 10
    @protocol
    def test_send(self, runtime):
        """Test of send a value."""
        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        value = 42

        receivers = [2, 3]
        if 1 == runtime.id:
            d = runtime.broadcast([1], receivers, str(value))
        else:
            d = runtime.broadcast([1], receivers)
        def check(x):
            self.assertEquals(int(x), 42)
        d.addCallback(check)
        return d
            

    @protocol
    def test_send_two_senders_in_parallel(self, runtime):
        """Test of send a value."""
        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        def check(ls):
            for s, x in ls:
                self.assertEquals(int(x), 42)
            return ls

        value = 42

        receivers = [2, 3]
        if 1 == runtime.id:
            d1 = runtime.broadcast([1], receivers, str(value))
        else:
            d1 = runtime.broadcast([1], receivers)

        if 2 == runtime.id:
            d2 = runtime.broadcast([2], [3], str(value))
        else:
            d2 = runtime.broadcast([2], [3])

        ds = [d1]
        if [] != d2:
            ds.append(d2)
        dls = DeferredList(ds)
        dls.addCallback(check)
        return dls
            
    @protocol
    def test_send_multiple_senders_in_one_burst(self, runtime):
        """Test of send a value."""
        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        value = 42
        if 1 == runtime.id:
            value = 7

        if 1 == runtime.id or 3 == runtime.id:
            ds = runtime.broadcast([1, 3], [2], str(value))

        if 2 == runtime.id:
            ds = runtime.broadcast([1, 3], [2])
            dls = DeferredList(ds)
            def check(ls):
                self.assertEquals(int(ls[0][1]), 7)
                self.assertEquals(int(ls[1][1]), 42)
                return ls
            dls.addCallback(check)
            return dls
        return None
            

    @protocol
    def test_sender_in_receivers(self, runtime):
        """Test of send a value."""
        self.Zp = GF(6277101735386680763835789423176059013767194773182842284081)

        value = 42
        if 1 == runtime.id:
            d = runtime.broadcast([1], [1, 2, 3], str(value))
        else:
            d = runtime.broadcast([1], [1, 2, 3])

        def check(x):
            self.assertEquals(int(x), 42)
            return x
        d.addCallback(check)
        return d

    @protocol
    def test_complex(self, runtime):
        def check(ls):
            for x, v in ls:
                self.assertEquals(runtime.list_str(v), ['7', '9', '13'])
            
        receivers = [1, 2, 3]
        def exchange((xi, rhoi1, rhoi2)):
            # Send share to all receivers.
            ds = runtime.broadcast(receivers, receivers, str((str(xi), str(rhoi1), str(rhoi2))))
            dls = DeferredList(ds)
            dls.addCallbacks(check, runtime.error_handler)
            return dls

        result = Deferred()
        result.addCallbacks(exchange, runtime.error_handler)
        result.callback((7, 9, 13))
        return result

    @protocol
    def test_complex2(self, runtime):
        def check(ls):
            if (2 == runtime.id) or (1 == runtime.id):
                self.assertEquals(ls[0][1], "V1")
                self.assertEquals(ls[1][1], "V1")
                self.assertEquals(ls[2][1], "V1")
                self.assertEquals(ls[3][1], "V2")
            else:
                self.assertEquals(ls[0][1], "V1")
                self.assertEquals(ls[1][1], "V1")
                self.assertEquals(ls[2][1], "V1")
                self.assertEquals(ls[3][1], "V2")
                self.assertEquals(ls[4][1], "V2")
        field = self.Zp
        results = []
        results += runtime.broadcast(runtime.players.keys(), runtime.players.keys(), "V1")
        if runtime.id in [1, 2]:
            v = runtime.broadcast([1, 2], [3], "V2")
            if isinstance(v, list):
                results += v
            else:
                results.append(v)
        else:
            results += runtime.broadcast([1, 2], [3])
        if 3 == runtime.id:
            results += [runtime.broadcast([3], runtime.players.keys(), str(7))]
        else:
            results += [runtime.broadcast([3], runtime.players.keys())]
        dls = DeferredList(results)
        runtime.schedule_callback(dls, check)
        dls.addErrback(runtime.error_handler)
        return dls
