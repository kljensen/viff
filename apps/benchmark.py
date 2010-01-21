#!/usr/bin/env python

# Copyright 2007, 2008, 2009 VIFF Development Team.
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

# This example benchmarks multiplications and comparisons. Run it with
# '--help' on the command line to see the available options.
#
# Two lists of shares are created and the numbers are multiplied or
# compared pair-wise. This can be scheduled in two ways: parallel or
# sequentially. Parallel execution looks like this:
#
#      *        *             *
#     / \      / \    ...    / \
#   a1   b1  a2   b2       an   bn
#
# Given sufficient bandwidth and computational power all operations
# should be executed in parallel.
#
# Sequential execution looks like this:
#
#      *
#     / \
#   a1   b1
#
#      *
#     / \
#   a2   b2
#
#     ...
#
#      *
#     / \
#   an   bn
#
# Here the next operation is only started when the previous has
# finished.
#
# In all cases the time reported is measured from the moment when the
# operands are ready until all the results are ready.

import sys
import time
from math import log
from optparse import OptionParser

import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from viff.field import GF, FakeGF
from viff.runtime import Runtime, create_runtime, make_runtime_class
from viff.passive import PassiveRuntime
from viff.active import (BasicActiveRuntime,
                         TriplesHyperinvertibleMatricesMixin, TriplesPRSSMixin)
from viff.comparison import ComparisonToft05Mixin, ComparisonToft07Mixin
from viff.equality import ProbabilisticEqualityMixin
from viff.paillier import PaillierRuntime
from viff.config import load_config
from viff.util import find_prime

commitment = None
pypaillier = None
try:
    import commitment  
except ImportError:
    commitment = None

try:
    from pypaillier import encrypt_r, decrypt, tripple_2c, tripple_3a
    pypaillier = "PyPaillier is loaded."
except:
    pypaillier = None

if commitment and pypaillier:
    from viff.orlandi import OrlandiRuntime
else:
    OrlandiRuntime = None
    OrlandiShare = None

from benchutil import (SelfcontainedBenchmarkStrategy,
                       NeededDataBenchmarkStrategy,
                       ParallelBenchmark, SequentialBenchmark,
                       BinaryOperation, NullaryOperation)

# Hack in order to avoid Maximum recursion depth exceeded
# exception;
sys.setrecursionlimit(5000)


last_timestamp = time.time()

operations = {"mul"       : ("mul", [], BinaryOperation),
              "compToft05": ("greater_than_equal",
                             [ComparisonToft05Mixin], BinaryOperation),
              "compToft07": ("greater_than_equal",
                             [ComparisonToft07Mixin], BinaryOperation),
              "eq"        : ("eq", [ProbabilisticEqualityMixin], BinaryOperation),
              "triple_gen": ("triple_gen", [], NullaryOperation)}

runtimes = {"PassiveRuntime": PassiveRuntime,
            "PaillierRuntime": PaillierRuntime,
            "BasicActiveRuntime": BasicActiveRuntime,
            "OrlandiRuntime": OrlandiRuntime}

mixins = {"TriplesHyperinvertibleMatricesMixin" : TriplesHyperinvertibleMatricesMixin,
          "TriplesPRSSMixin": TriplesPRSSMixin,
          "ComparisonToft05Mixin": ComparisonToft05Mixin,
          "ComparisonToft07Mixin": ComparisonToft07Mixin,
          "ProbabilisticEqualityMixin": ProbabilisticEqualityMixin}

parser = OptionParser(usage="Usage: %prog [options] config_file")
parser.add_option("-m", "--modulus",
                  help="lower limit for modulus (can be an expression)")
parser.add_option("-r", "--runtime", type="choice", choices=runtimes.keys(),
                  help="the name of the basic runtime to test")
parser.add_option("-n", "--num_players", action="store_true", dest="num_players",
                  help="number of players")
parser.add_option("--mixins", type="string",
                  help="Additional mixins which must be added to the runtime")
parser.add_option("--prss", action="store_true",
                  help="use PRSS for preprocessing")
parser.add_option("--hyper", action="store_false", dest="prss",
                  help="use hyperinvertible matrices for preprocessing")
parser.add_option("-t", "--threshold", type="int",
                  help="corruption threshold")
parser.add_option("-c", "--count", type="int",
                  help="number of operations")
parser.add_option("-o", "--operation", type="choice", choices=operations.keys(),
                  help="operation to benchmark")
parser.add_option("-p", "--parallel", action="store_true",
                  help="execute operations in parallel")
parser.add_option("-s", "--sequential", action="store_false", dest="parallel",
                  help="execute operations in sequence")
parser.add_option("-f", "--fake", action="store_true",
                  help="skip local computations using fake field elements")
parser.add_option("--args", type="string",
                  help=("additional arguments to the runtime, the format is "
                        "a comma separated list of id=value pairs e.g. "
                        "--args s=1,d=0,lambda=1"))
parser.add_option("--needed_data", type="string",
                  help=("name of a file containing already computed "
                        "dictionary of needed_data. Useful for skipping "
                        "generating the needed data, which usually "
                        "elliminates half the execution time. Format of file: "
                        "\"{('random_triple', (Zp,)): [(3, 1), (3, 4)]}\""))
parser.add_option("--pc", type="string",
                  help=("The program counter to start from when using "
                        "explicitly provided needed_data. Format: [3,0]"))

parser.set_defaults(modulus=2**65, threshold=1, count=10,
                    runtime="PassiveRuntime", mixins="", num_players=2, prss=True,
                    operation="mul", parallel=True, fake=False,
                    args="", needed_data="")

print "*" * 64

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if not args:
    parser.error("you must specify a config file")

id, players = load_config(args[0])

if not 1 <= options.threshold <= len(players):
    parser.error("threshold out of range")

if options.fake:
    print "Using fake field elements"
    Field = FakeGF
else:
    Field = GF


Zp = Field(find_prime(options.modulus))
print "Using field elements (%d bit modulus)" % log(Zp.modulus, 2)


count = options.count
print "I am player %d, will %s %d numbers" % (id, options.operation, count)


# Identify the base runtime class.
if options.runtime == "OrlandiRuntime" and not OrlandiRuntime:
    print "Error: The following modules did not load correctly:"
    if not commitment:
        print "commitment"
    if not pypaillier:
        print "pypaillier"
    if not OrlandiRuntime:
        print "OrlandiRuntime"
    exit(1)
base_runtime_class = runtimes[options.runtime]

# Identify the additional mixins.
actual_mixins = []
if options.mixins:
    actual_mixins = [mixins[mixin] for mixin in options.mixins.split(',')]


# Identify the operation and it mixin dependencies.
operation = operations[options.operation][0]
actual_mixins += operations[options.operation][1]
operation_arity = operations[options.operation][2]

print "Using the base runtime: %s." % base_runtime_class
if actual_mixins:
    print "With the following mixins:"
    for mixin in actual_mixins:
        print "- %s" % mixin.__name__

runtime_class = make_runtime_class(base_runtime_class, actual_mixins)

pre_runtime = create_runtime(id, players, options.threshold,
                             options, runtime_class)

def update_args(runtime, options):
    args = {}
    if options.args:
        for arg in options.args.split(','):
            id, value = arg.split('=')
            args[id] = long(value)
        runtime.set_args(args)
    return runtime


pre_runtime.addCallback(update_args, options)

if options.parallel:
    benchmark = ParallelBenchmark
else:
    benchmark = SequentialBenchmark

needed_data = ""
if options.needed_data:
    needed_data = eval(open(options.needed_data).read())

if options.needed_data and options.pc:
    bases = (benchmark, NeededDataBenchmarkStrategy, operation_arity)
    options.pc = eval(options.pc)
else:
    bases = (benchmark, SelfcontainedBenchmarkStrategy, operation_arity)

print "Using the Benchmark bases:"
for b in bases:
    print "- %s" % b.__name__
benchmark = type("ExtendedBenchmark", bases, {})

def do_benchmark(runtime, operation, benchmark, field, count, *args):
    benchmark(runtime, operation, field, count).benchmark(*args)

pre_runtime.addCallback(do_benchmark, operation, benchmark,
                        Zp, count, needed_data, options.pc)

print "#### Starting reactor ###"
reactor.run()
