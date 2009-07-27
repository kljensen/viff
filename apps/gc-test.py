#!/usr/bin/env python

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

# This application will is meant for 3 players. They will run forever,
# sharing and summing integers. After 100 iterations the time per
# iteration and the current memory allocation is printed. The
# allocation should stay *constant* since shares are released at the
# same speed as they are allocated.

import sys
from time import time

import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from viff.field import GF
from viff.runtime import create_runtime
from viff.config import load_config
from viff.util import find_prime

id, players = load_config(sys.argv[1])


def memory_usage():
    """Read memory usage of the current process."""
    status = None
    try:
        # This will only work on systems with a /proc file system
        # (like Linux).
        status = open('/proc/self/status', 'r')
        for line in status:
            if line.startswith('VmRSS'):
                parts = line.split()
                return parts[1]
        return 'unknown'
    finally:
        if status is not None:
            status.close()

class Protocol:

    def __init__(self, runtime):
        self.Zp = GF(find_prime(2**64))
        self.runtime = runtime
        self.last_time = time()
        self.share_next(0)

    def share_next(self, n):
        if isinstance(n, self.Zp):
            n = n.value

        if n % 100 == 0:
            now = time()
            memory = memory_usage()
            print "Iteration %d: %.1f ms/iteration, allocated %s KiB" \
                  % (n, 10*(now - self.last_time), memory)
            self.last_time = now

        x, y, z = self.runtime.shamir_share([1, 2, 3], self.Zp, n + 1)
        n = self.runtime.open(x + y - z)
        n.addCallback(self.share_next)

pre_runtime = create_runtime(id, players, 1)
pre_runtime.addCallback(Protocol)
reactor.run()
