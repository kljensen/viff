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

"""
B{VIFF}: Virtual Ideal Functionality Framework, a Python framework for
writing secure-multi-party computations (SMPC).

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


Architecture
============

VIFF consists of several modules. The L{runtime} module contains the
L{Runtime} class, in which the main functionality is implemented. The
L{field} module contains implementations of finite fields --- there
are the value you do calculations on using the runtime. Other modules
provide support functions.

Layers
------

The main functionality in VIFF is implemented in the L{Runtime} class.
This class offers methods to do addition, multiplication, etc. These
methods operate on what we call I{shares}.

Shares can be either L{field.GF} or L{GF256} elements or C{Deferred}s
yielding such elements. The result values from methods in the runtime
is normally deferred field elements.

Field elements contain the concrete value on which we do calculations.
This is just normal Python (long) integers. The value is wrapped in an
object that will keep track of doing modulo reductions as appropriate.

So in a nutshell, VIFF has these layers:

  - Top-level layer for application programs: There you manipulate
    Python integers (for example as inputs to C{shamir_share} or
    C{prss_share}) or shares.

  - Runtime layer: The runtime deals with Python integers or shares,
    but these are normally changed into field elements as soon as
    possible by attaching a callbacks to any C{Deferred}s and then
    working directly on the field elements in the callback.

  - Field elements: Deals with arithmetic over Python integers, but
    with modulo reductions as needed.


Getting into VIFF
=================

As explained above, the main functionality in VIFF is the L{Runtime}
class, so please start there. Also, be sure to checkout the example
applications distributed in the C{apps} directory.

@author: U{Martin Geisler <mg@daimi.au.dk>}
@author: U{Tomas Toft <tomas@daimi.au.dk>}
@see: U{http://viff.dk/}
"""

__version__ = '0.1.1'
__license__ = 'GNU GPL'
