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

from viff.runtime import Share, gather_shares
from viff.field import FieldElement

class SimpleArithmetic:
    """Provides methods for addition and subtraction.

    Provides set: {add, sub}.
    Requires set: {self._plus((x,y), field),
                   self._minus((x,y), field),
                   self._plus_public(x, c, field),
                   self._minus_public_right(x, c, field),
                   self._minus_public_left(x, c, field)}.
    """

    def add(self, share_a, share_b):
        """Addition of shares.

        share_a is assumed to be an instance of Share.
        If share_b is also an instance of Share then self._plus gets called.
        If not then self._plus_public get called.
        """
        return self.both_shares(share_a, share_b, self._plus_public, self._plus)

    def both_shares(self, share_a, share_b, if_not, if_so):
        field = share_a.field
        if not isinstance(share_b, Share):
            if not isinstance(share_b, FieldElement):
                share_b = field(share_b)
            share_a.addCallbacks(if_not, self.error_handler, callbackArgs=(share_b, field))
            return share_a
        else:
            result = gather_shares([share_a, share_b])
            result.addCallbacks(if_so, self.error_handler, callbackArgs=(field,))
            return result

    def sub(self, share_a, share_b):
        """Subtraction of shares.

        If share_a is an instance of Share but not share_b, then self._minus_public_right gets called.
        If share_b is an instance of Share but not share_b, then self._minus_public_left gets called.
        If share_a and share_b are both instances of Share then self._minus get called.
        """
        if not isinstance(share_b, Share):
            field = share_a.field
            if not isinstance(share_b, FieldElement):
                share_b = field(share_b)
            share_a.addCallbacks(self._minus_public_right, self.error_handler, callbackArgs=(share_b, field))
            return share_a
        elif not isinstance(share_a, Share):
            field = share_b.field
            if not isinstance(share_a, FieldElement):
                share_a = field(share_a)
            share_b.addCallbacks(self._minus_public_left, self.error_handler, callbackArgs=(share_a, field))
            return share_b
        else:
            field = share_a.field
            result = gather_shares([share_a, share_b])
            result.addCallbacks(self._minus, self.error_handler, callbackArgs=(field,))
            return result
