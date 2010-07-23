# Copyright 2010 VIFF Development Team.
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

class BeDOZaMACList(object):

    def __init__(self, macs):
        self.macs = macs

    def get_macs(self):
        return self.macs

    def get_mac(self, inx):
        return self.macs[inx]

    def cmul(self, c):
        return BeDOZaMACList(map(lambda m: c * m, self.macs))
        
    def __add__(self, other):
        """Addition."""
        macs = []
        for c1, c2 in zip(self.macs, other.macs):
            macs.append(c1 + c2)
        return BeDOZaMACList(macs)

    def __sub__(self, other):
        """Subtraction."""
        macs = []
        for c1, c2 in zip(self.macs, other.macs):
            macs.append(c1 - c2)
        return BeDOZaMACList(macs)

    def __eq__(self, other):
        return self.macs == other.macs

    def __str__(self):
        return str(self.macs)

    def __repr__(self):
        return str(self)
    
