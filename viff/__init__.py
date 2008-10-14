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

"""
Virtual Ideal Functionality Framework.

VIFF is a Python framework for writing multi-party computations (MPC)
in an easy, efficient, and secure way.

Overview
========

VIFF allows you to write a program which will interact with other
programs in order to execute a joint computation. This is called a
multi-party computation, MPC for short.

The programs will implement what we call a virtual ideal functionality
(IF). The idea is that the behavior of the programs should be
indistinguishable from the behavior of programs interacting with a
so-called ideal functionality. An ideal functionality is a player that
cannot be corrupted, also known as a trusted third party (TTP).

Interacting with an IF is easy: all players give their inputs to the
IF, which computes the results. The results are then distributed to
the correct players. The inputs and the results are sent over secure
channels, and since the IF cannot be corrupted, this ideal protocol
must be secure.

In the real world there is no IF, but VIFF allows you to implement a
virtual ideal functionality. The behavior of a bunch of programs using
VIFF is indistinguishable from program running in the ideal world. It
is indistinguishable in the sense that everything that can happen in
the real world protocol could happen in the ideal world too. And since
no attacks can occur in the ideal world, no attacks can occur in the
real world as well. Such a multi-party computation (MPC) is called a
secure multi-party computation (SMPC).

Security Assumptions
--------------------

Please note that like all cryptographic systems, VIFF is only secure
as long as certain assumptions are fulfilled. These assumptions
include:

  - The adversary can only corrupt up to a certain threshold of the
    total number of players. The threshold will normally be 1/2 of the
    players, so for three players, at most one player may be
    corrupted (there must be an honest majority).

  - The adversary is computationally bounded. The protocols used by
    VIFF rely on certain computational hardness assumptions, and
    therefore only polynomial time adversaries are allowed.

  - The adversary is passive. Being passive means that the adversary
    only monitors the network traffic, but still follows the protocol.
    We plan to add support for active (Byzantine) adversaries in a
    future version.

The precise assumptions for each protocol will eventually be included
in the documentation for the corresponding method, but this has not
yet been done.

Architecture
============

VIFF consists of several modules. The L{runtime} module contains the
L{Runtime} and L{Share} classes, in which the main functionality is
implemented. The L{field} module contains implementations of finite
fields --- these are the values inside the shares. Other modules
provide support functions.

Layers
------

The main functionality in VIFF is implemented in the L{Runtime} class.
This class offers methods to do addition, multiplication, etc. These
methods operate on L{Share} instances.

Shares hold either L{field.GF} or L{GF256} elements and are created
from the C{shamir_share} or C{prss_share} Runtime methods. Shares
overload the standard arithmetic operators, so you can write C{a + b -
c * d} with four shares, and it will be translated correctly into the
appropriate method calls on the Runtime instance associated with the
shares.

A field element contain the concrete value on which we do
calculations. This is just a normal Python (long) integer. The value
is wrapped in an object that will keep track of doing modulo
reductions as appropriate.

So in a nutshell, VIFF has these layers:

  - Top-level layer for application programs: There you manipulate
    Python integers or L{Share} instances.

  - Runtime layer: The runtime deals with Python integers or shares.

  - Field elements: Deals with arithmetic over Python integers, but
    with modulo reductions as needed.


Getting into VIFF
=================

As explained above, the main functionality in VIFF is the L{Runtime}
class, so please start there. Also, be sure to checkout the example
applications distributed in the C{apps} directory.

@authors: U{VIFF Development Team <mailto:viff-devel@viff.dk>}
@see: U{http://viff.dk/}
"""

__version__ = '0.7.1'
__license__ = 'GNU LGPL'

def release():
    """Get the full release number.

    If Mercurial is available, "hg identify" will be used to determine
    the state of the repository and a string of the form ``x.y-hash``
    is returned where ``hash`` is the changeset ID or tag. If the tag
    is the same as ``__version__``, then ``__version__`` is simply
    returned.
    """
    try:
        from subprocess import Popen, PIPE
        p = Popen(["hg", "identify"], stdout=PIPE)
        stdout, _ = p.communicate()
        if p.returncode != 0:
            extra = "unknown"
        else:
            parts = stdout.split()
            if len(parts) == 1 or parts[1] == "tip":
                # No tag for this changeset or only "tip".
                extra = parts[0]
            else:
                extra = parts[1]
    except OSError:
        extra = "unknown"

    if extra == __version__:
        return __version__
    else:
        return "%s-%s" % (__version__, extra)
