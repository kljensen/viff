#!/usr/bin/env python

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
import operator
from pprint import pformat

import viff.reactor
viff.reactor.install()
from twisted.internet import reactor
from twisted.internet.defer import Deferred

from viff.field import GF, GF256, FakeGF
from viff.runtime import Runtime, create_runtime, gather_shares, \
    make_runtime_class
from viff.passive import PassiveRuntime
from viff.active import BasicActiveRuntime, \
    TriplesHyperinvertibleMatricesMixin, TriplesPRSSMixin
from viff.comparison import ComparisonToft05Mixin, ComparisonToft07Mixin
from viff.equality import ProbabilisticEqualityMixin
from viff.paillier import PaillierRuntime
from viff.orlandi import OrlandiRuntime
from viff.config import load_config
from viff.util import find_prime, rand


# Hack in order to avoid Maximum recursion depth exceeded
# exception;
sys.setrecursionlimit(5000)


last_timestamp = time.time()
start = 0


def record_start(what):
    global start
    start = time.time()
    print "*" * 64
    print "Started", what


def record_stop(x, what):
    stop = time.time()
    print
    print "Total time used: %.3f sec" % (stop-start)
    print "Time per %s operation: %.0f ms" % (what, 1000*(stop-start) / count)
    print "*" * 6
    return x

operations = {"mul": (operator.mul,[]),
              "compToft05": (operator.ge, [ComparisonToft05Mixin]),
              "compToft07": (operator.ge, [ComparisonToft07Mixin]),
              "eq": (operator.eq, [ProbabilisticEqualityMixin])}

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
                  help="operation to benchmark")
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
                  help="additional arguments to the runtime, the format is a comma separated list of id=value pairs e.g. --args s=1,d=0,lambda=1")
parser.add_option("--needed_data", type="string",
                  help="name of a file containing already computed dictionary of needed_data. Useful for skipping generating the needed data, which usually elliminates half the execution time. Format of file: \"{('random_triple', (Zp,)): [(3, 1), (3, 4)]}\"")
parser.add_option("--pc", type="string",
                  help="The program counter to start from when using explicitly provided needed_data. Format: [3,0]")

parser.set_defaults(modulus=2**65, threshold=1, count=10,
                    runtime="PassiveRuntime", mixins="", num_players=2, prss=True,
                    operation=operations.keys()[0], parallel=True, fake=False, 
                    args="", needed_data="")

print "*" * 60

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if len(args) == 0:
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


class BenchmarkStrategy:

    def benchmark(self, *args):
        raise NotImplemented("Override this abstract method in subclasses")


class SelfcontainedBenchmarkStrategy(BenchmarkStrategy):

    def benchmark(self, *args):
        sys.stdout.flush()
        sync = self.rt.synchronize()
        self.doTest(sync, lambda x: x)
        self.rt.schedule_callback(sync, self.preprocess)
        self.doTest(sync, lambda x: self.rt.shutdown())


class NeededDataBenchmarkStrategy(BenchmarkStrategy):

    def benchmark(self, needed_data, pc, *args):
        self.pc = pc
        sys.stdout.flush()
        sync = self.rt.synchronize()
        self.rt.schedule_callback(sync, lambda x: needed_data)
        self.rt.schedule_callback(sync, self.preprocess)
        self.doTest(sync, lambda x: self.rt.shutdown())


# Defining the protocol as a class makes it easier to write the
# callbacks in the order they are called. This class is a base class
# that executes the protocol by calling the run_test method.
class Benchmark:

    def __init__(self, rt, operation):
        self.rt = rt
        self.operation = operation
        self.pc = None
        
    def preprocess(self, needed_data):
        print "Preprocess", needed_data
        if needed_data:
            print "Starting preprocessing"
            record_start("preprocessing")
            preproc = self.rt.preprocess(needed_data)
            preproc.addCallback(record_stop, "preprocessing")
            return preproc
        else:
            print "Need no preprocessing"
            return None

    def doTest(self, d, termination_function):
        self.rt.schedule_callback(d, self.begin)
        self.rt.schedule_callback(d, self.sync_test)
        self.rt.schedule_callback(d, self.run_test)
        self.rt.schedule_callback(d, self.sync_test)
        self.rt.schedule_callback(d, self.finished, termination_function)
        return d

    def begin(self, _):
        print "begin", self.rt.program_counter
        print "Runtime ready, generating shares"
        self.a_shares = []
        self.b_shares = []
        for i in range(count):
            inputter = (i % len(self.rt.players)) + 1
            if inputter == self.rt.id:
                a = rand.randint(0, Zp.modulus)
                b = rand.randint(0, Zp.modulus)
            else:
                a, b = None, None
            self.a_shares.append(self.rt.input([inputter], Zp, a))
            self.b_shares.append(self.rt.input([inputter], Zp, b))
        shares_ready = gather_shares(self.a_shares + self.b_shares)
        return shares_ready

    def sync_test(self, x):
        print "Synchronizing test start."
        sys.stdout.flush()
        sync = self.rt.synchronize()
        self.rt.schedule_callback(sync, lambda y: x)
        return sync

    def run_test(self, _):
        raise NotImplemented("Override this abstract method in a sub class.")

    def finished(self, needed_data, termination_function):
        sys.stdout.flush()

        if self.rt._needed_data:
            print "Missing pre-processed data:"
            for (func, args), pcs in needed_data.iteritems():
                print "* %s%s:" % (func, args)
                print "  " + pformat(pcs).replace("\n", "\n  ")

        return termination_function(needed_data)

# This class implements a benchmark where run_test executes all
# operations in parallel.
class ParallelBenchmark(Benchmark):

    def run_test(self, shares):
        print "rt", self.rt.program_counter, self.pc
        if self.pc != None:
            self.rt.program_counter = self.pc
        else:
            self.pc = list(self.rt.program_counter)
        c_shares = []
        record_start("parallel test")
        while self.a_shares and self.b_shares:
            a = self.a_shares.pop()
            b = self.b_shares.pop()
            c_shares.append(self.operation(a, b))
            print "."

        done = gather_shares(c_shares)
        done.addCallback(record_stop, "parallel test")
        def f(x):
            needed_data = self.rt._needed_data
            self.rt._needed_data = {}
            return needed_data
        done.addCallback(f)
        return done


# A benchmark where the operations are executed one after each other.
class SequentialBenchmark(Benchmark):

    def run_test(self, _, termination_function, d):
        record_start("sequential test")
        self.single_operation(None, termination_function)

    def single_operation(self, _, termination_function):
        if self.a_shares and self.b_shares:
            a = self.a_shares.pop()
            b = self.b_shares.pop()
            c = self.operation(a, b)
            self.rt.schedule_callback(c, self.single_operation, termination_function)
        else:
            record_stop(None, "sequential test")
            self.finished(None, termination_function)

# Identify the base runtime class.
base_runtime_class = runtimes[options.runtime]

# Identify the additional mixins.
actual_mixins = []
if options.mixins != "":
    actual_mixins = [mixins[mixin] for mixin in options.mixins.split(',')]


# Identify the operation and it mixin dependencies.
operation = operations[options.operation][0]
actual_mixins += operations[options.operation][1]

print "Using the base runtime: %s." % base_runtime_class
if actual_mixins:
    print "With the following mixins:"
    for mixin in actual_mixins:
        print "- %s" % mixin

runtime_class = make_runtime_class(base_runtime_class, actual_mixins)

if options.parallel:
    benchmark = ParallelBenchmark
else:
    benchmark = SequentialBenchmark

needed_data = ""
if options.needed_data != "":
    file = open(options.needed_data, 'r')
    for l in file:
        needed_data += l
    needed_data = eval(needed_data)

if options.needed_data != "" and options.pc != "":
    bases = (benchmark,) + (NeededDataBenchmarkStrategy,) + (object,)
    options.pc = eval(options.pc)
else:
    bases = (benchmark,) + (SelfcontainedBenchmarkStrategy,) + (object,)
benchmark = type("ExtendedBenchmark", bases, {})

pre_runtime = create_runtime(id, players, options.threshold,
                             options, runtime_class)

def update_args(runtime, options):
    args = {}
    if options.args != "":
        for arg in options.args.split(','):
            id, value = arg.split('=')
            args[id] = long(value)
        runtime.set_args(args)
    return runtime


pre_runtime.addCallback(update_args, options)

def do_benchmark(runtime, operation, benchmark, *args):
    benchmark(runtime, operation).benchmark(*args)

pre_runtime.addCallback(do_benchmark, operation, benchmark, needed_data, options.pc)

print "#### Starting reactor ###"
reactor.run()
