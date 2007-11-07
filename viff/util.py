# Copyright 2007 Martin Geisler
#
# This file is part of VIFF
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

"""Utility function.

This module contains various utility functions used in all parts of
the VIFF code. The most important is the L{rand} random generator
which is seeded with a known seed each time. Using this generator for
all random numbers ensures that a protocol run can be reproduced at a
later time.
"""

import os
import random
import warnings
from twisted.internet.defer import Deferred, succeed, gatherResults

#: Seed for L{rand}.
_seed = os.environ.get('SEED')

if _seed is None:
    # If the environmental variable is not set, then a random seed is
    # chosen.
    _seed = random.randint(0, 10000)
    print 'Seeding random generator with random seed %d' % _seed
    #: Random number generator used by all VIFF code.
    #:
    #: The generator is by default initialized with a random seed,
    #: unless the environmental variable C{SEED} is set to a value, in
    #: which case that value is used instead. If C{SEED} is defined,
    #: but empty, then no seed is used and a protocol cannot be
    #: reproduced exactly.
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

    As an example, here is how to define a lazy addition and
    multiplication which works for integers (deferred or not):

    >>> @dlift
    ... def add(a, b):
    ...     return a + b
    ...
    >>> @dlift
    ... def mul(a, b):
    ...     return a * b
    ...
    >>> x = Deferred()
    >>> y = Deferred()
    >>> z = mul(add(x, 10), y)
    >>> x.callback(5)
    >>> y.callback(10)
    >>> z                                         # doctest: +ELLIPSIS
    <DeferredList at 0x...  current result: 150>
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

    >>> x = Deferred()
    >>> y = (1, 2, 3)
    >>> z = Deferred()
    >>> dprint("x: %d, y: %s, z: %s", x, y, z) # doctest: +ELLIPSIS
    <DeferredList at 0x...>
    >>> x.callback(10)
    >>> z.callback("Hello World")
    x: 10, y: (1, 2, 3), z: Hello World
    """
    print fmt % tuple(args)

def clone_deferred(original):
    """Clone a Deferred.

    The returned clone will fire with the same result as the original
    Deferred, but will otherwise be independent.

    It is an error to call callback on the clone as it will result in
    an AlreadyCalledError when the original Deferred is triggered.

    >>> x = Deferred()
    >>> x.addCallback(lambda result: result * 10) # doctest: +ELLIPSIS
    <Deferred at 0x...>
    >>> y = clone_deferred(x)
    >>> y.addCallback(lambda result: result + 1)  # doctest: +ELLIPSIS
    <Deferred at 0x...>
    >>> x.addCallback(lambda result: result + 2)  # doctest: +ELLIPSIS
    <Deferred at 0x...>
    >>> x.callback(1)
    >>> x                                         # doctest: +ELLIPSIS
    <Deferred at 0x...  current result: 12>
    >>> y                                         # doctest: +ELLIPSIS
    <Deferred at 0x...  current result: 11>
    """
    def split_result(result):
        clone.callback(result)
        return result
    clone = Deferred()
    original.addCallback(split_result)
    return clone

#: Indention level.
_indent = 0
#: Traced function call count.
_trace_counters = {}

def trace(func):
    """Trace function entry and exit.

    Using this decorator on a function will make it print a line on
    entry and exit. The line is indented in nested calls, and contains
    the number of calls made to each function.
    """
    def wrapper(*args, **kwargs):
        """
        Wrapper with tracing output.
        """
        global _indent
        count = _trace_counters.setdefault(func.func_name, 1)
        try:
            print "%s-> Entering: %s (%d)" % ("  " * _indent,
                                              func.func_name, count)
            _indent += 1
            _trace_counters[func.func_name] += 1
            return func(*args, **kwargs)
        finally:
            _indent -= 1
            print "%s<- Exiting:  %s (%d)" % ("  " * _indent,
                                              func.func_name, count)
    return wrapper

def println(format="", *args):
    """Print a line indented according to the stack depth.

    The L{_indent} variable holds the current stack depth.
    """
    if len(args) > 0:
        format = format % args

    print "%s %s" % ("  " * _indent, format)

    
if __name__ == "__main__":
    import doctest
    doctest.testmod()
