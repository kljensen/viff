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


"""Tests of the equality protocol(s)."""

import operator

from viff.equality import ProbabilisticEqualityMixin
from viff.test.util import RuntimeTestCase, BinaryOperatorTestCase
from viff.passive import PassiveRuntime

#: Declare doctests for Trial.
__doctests__ = ['viff.equality']


class EqualRuntime(PassiveRuntime, ProbabilisticEqualityMixin):
    """A runtime with the equality mixin."""
    pass


class ProbabilisticEqualityTestDifferent(BinaryOperatorTestCase,
                                         RuntimeTestCase):
    """Testing the equality with *a* and *b* different."""
    # Arbitrarily chosen.
    a = 12442
    b = 91243
    runtime_class = EqualRuntime
    operator = operator.eq


class ProbabilisticEqualityTestEqual(BinaryOperatorTestCase, RuntimeTestCase):
    """Testing the equality with *a* and *b* equal."""
    a = 4023
    b = 4023
    runtime_class = EqualRuntime
    operator = operator.eq


class ProbabilisticEqualityTestDiff1_1(BinaryOperatorTestCase,
                                       RuntimeTestCase):
    """Testing ``a == b`` where ``b = a + 1``."""
    a = 0
    b = 1
    runtime_class = EqualRuntime
    operator = operator.eq


class ProbabilisticEqualityTestDiff1_2(BinaryOperatorTestCase,
                                       RuntimeTestCase):
    """Testing ``a == b`` where ``a = b + 1``."""
    a = 1
    b = 0
    runtime_class = EqualRuntime
    operator = operator.eq
