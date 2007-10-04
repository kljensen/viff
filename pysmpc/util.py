# Copyright 2007 Martin Geisler
#
# This file is part of PySMPC
#
# PySMPC is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PySMPC is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PySMPC in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

"""Utility methods."""

import os
import random
import warnings
from twisted.internet.defer import Deferred, succeed, gatherResults

_seed = os.environ.get('SEED')

if _seed is None:
    # If the environmental variable is not set, then a random seed is
    # chosen.
    _seed = random.randint(0, 10000)
    print 'Seeding random generator with random seed %d' % _seed
    rand = random.Random(_seed)
elif _seed == '':
    # If it is set, but set to the empty string (SEED=), then no seed
    # is used.
    rand = random.SystemRandom()
else:
    # Otherwise use the seed given, which must be an integer.
    _seed = int(_seed)
    print 'Seeding random generator with seed %d' % _seed
    rand = random.Random(_seed)


def deprecation(message):
    """Issue a deprecation warning."""
    warnings.warn(message, DeprecationWarning, stacklevel=3)


def dlift(func):
    """Lift a function to handle deferred arguments.

    Use this as a decorator. The decorated function accepts the same
    arguments as the original function, but arguments for the lifted
    function can be Deferreds. The return value of the lifted function
    will always be a Deferred.

    Keyword arguments are not lifted.
    """
    def lifted(*args, **kwargs):
        """Lifted wrapper function."""
        deferred_args = []
        for arg in args:
            if not isinstance(arg, Deferred):
                arg = succeed(arg)
            deferred_args.append(arg)

        # One might opt to lift any keyword arguments too, but it has
        # been left out for now since it is somewhat complicated with
        # multiple DeferredLists waiting on each other.

        results = gatherResults(deferred_args)
        results.addCallback(lambda results: func(*results, **kwargs))
        return results

    lifted.func_name = func.func_name
    return lifted
        
@dlift
def dprint(fmt, *args):
    """Deferred print which waits on Deferreds.

    Works like this print statement, except that dprint waits on any
    Deferreds given in args. When all Deferreds are ready, the print
    is done.
    """
    print fmt % tuple(args)
