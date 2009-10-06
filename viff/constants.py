# -*- coding: utf-8 -*-
#
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

__docformat__ = "restructuredtext"

# Constants used for communication.
SHARE    = 0
ECHO     = 1
READY    = 2
SEND     = 3
PAILLIER = 4
TEXT     = 5

# Used by the HashBroadcastMixin
INCONSISTENTHASH = 6
OK               = 7
HASH             = 8
SIGNAL           = 9
