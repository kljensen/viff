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


import os
import random
import warnings

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
