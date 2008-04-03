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

"""Tests of comparison protocols."""

import operator

from viff.comparison import Toft05Runtime, Toft07Runtime
from viff.test.util import RuntimeTestCase, BinaryOperatorTestCase


class Toft05GreaterThanTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft05Runtime
    operator = operator.gt


class Toft05GreaterThanEqualTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft05Runtime
    operator = operator.ge


class Toft05LessThanTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft05Runtime
    operator = operator.lt


class Toft05LessThanEqualTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft05Runtime
    operator = operator.le


class Toft07GreaterThanTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft07Runtime
    operator = operator.gt


class Toft07GreaterThanEqualTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft07Runtime
    operator = operator.ge


class Toft07LessThanTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft07Runtime
    operator = operator.lt


class Toft07LessThanEqualTest(BinaryOperatorTestCase, RuntimeTestCase):
    runtime_class = Toft07Runtime
    operator = operator.le
