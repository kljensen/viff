# Copyright 2007, 2008 VIFF Development Team.
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

"""Miscellaneous utility functions.

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
from gmpy import mpz

#: Seed for L{rand}.
_seed = os.environ.get('SEED')

if _seed is None:
    # If the environment variable is not set, then a random seed is
    # chosen.
    _seed = random.randint(0, 10000)
    print 'Seeding random generator with random seed %d' % _seed
    #: Random number generator used by all VIFF code.
    #:
    #: The generator is by default initialized with a random seed,
    #: unless the environment variable C{SEED} is set to a value, in
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


def wrapper(func):
    """Decorator used for wrapper functions.

    It is important to use this decorator on any wrapper functions in
    order to ensure that they end up with correct C{__name__} and
    C{__doc__} attributes.

    In addition, if the environment variable C{EPYDOC} is defined,
    then the wrapper functions will be turned into functions that I{do
    not} wrap -- instead they let their argument function through
    unchanged. This is done so that epydoc can see the true function
    arguments when generating documentation. Just remember that your
    code will break if C{EPYDOC} is set, so it should only be used
    when epydoc is being run.

    @param func: the function that will be wrapped.
    @type func: callable
    """
    if os.environ.get('EPYDOC'):
        # Return a decorator which ignores the functions it is asked
        # to decorate and instead returns func:
        return lambda _: func
    else:
        # Return a decorator which does nothing to the function it is
        # asked to decorate, except update the __name__ and __doc__
        # attributes to match the original wrapped function.
        def decorator(f):
            f.__name__ = func.__name__
            f.__doc__ = func.__doc__
            return f
        return decorator


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


def find_prime(lower_bound, blum=False):
    """Find a prime above a lower bound.

    If a prime is given as the lower bound, then this prime is
    returned:

    >> find_prime(37)
    37L

    The bound can be a Python expression as a string. This makes it
    easy for users to specify command line arguments that generates
    primes of a particular bit length:

    >>> find_prime("2**100") # 100 bit prime
    1267650600228229401496703205653L

    Blum primes (a prime p such that p % 4 == 3) can be found as well:

    >>> find_prime(12)
    13L
    >>> find_prime(12, blum=True)
    19L

    If the bound is negative, 2 (the smallest prime) is returned:

    >>> find_prime(-100)
    2L
    """
    lower_bound = eval(str(lower_bound), {}, {})
    if lower_bound < 0:
        prime = mpz(2)
    else:
        prime = mpz(lower_bound - 1).next_prime()

    if blum:
        while prime % 4 != 3:
            prime = prime.next_prime()

    return long(prime)


if __name__ == "__main__":
    import doctest    #pragma NO COVER
    doctest.testmod() #pragma NO COVER
