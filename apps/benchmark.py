#!/usr/bin/python

# Copyright 2007, 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
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
# Given sufficient bandwidth all operations should be executed in
# parallel.
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

import time
from optparse import OptionParser
import operator

from twisted.internet import reactor

from viff.field import GF
from viff.runtime import Runtime, create_runtime, gather_shares
from viff.comparison import Toft05Runtime, Toft07Runtime
from viff.config import load_config
from viff.util import find_prime

last_timestamp = time.time()
start = 0


def record_start():
    global start
    start = time.time()
    print "*" * 64
    print "Started"


def record_stop(_):
    stop = time.time()
    print
    print "Total time used: %.3f sec" % (stop-start)
    print "Time per operation: %.3f ms" % (1000*float(stop-start) / count)
    print "*" * 6


parser = OptionParser()
parser.add_option("-m", "--modulus",
                  help="lower limit for modulus (can be an expression)")
parser.add_option("-c", "--count", type="int",
                  help="number of operations")
parser.add_option("-o", "--operation", type="choice",
                  choices=["mul", "comp", "compII"],
                  help="operation to benchmark, one of 'mul', 'comp', 'compII'")
parser.add_option("-p", "--parallel", action="store_true",
                  help="execute operations in parallel")
parser.add_option("-s", "--sequential", action="store_false", dest="parallel",
                  help="execute operations in sequence")

parser.set_defaults(modulus="30916444023318367583", count=10,
                    operation="mul", parallel=True)

# Add standard VIFF options.
Runtime.add_options(parser)

(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")

id, players = load_config(args[0])

Zp = GF(find_prime(options.modulus))
count = options.count
print "I am player %d, will %s %d numbers" % (id, options.operation, count)

# Defining the protocol as a class makes it easier to write the
# callbacks in the order they are called. This class is a base class
# that executes the protocol by calling the run_test method.
class Benchmark:

    def __init__(self, rt, operation):
        print "Runtime ready, starting protocol"
        self.rt = rt
        self.operation = operation
        self.a_shares = [self.rt.prss_share_random(Zp) for _ in range(count)]
        self.b_shares = [self.rt.prss_share_random(Zp) for _ in range(count)]
        shares_ready = gather_shares(self.a_shares + self.b_shares)
        shares_ready.addCallback(self.sync_test)

    def sync_test(self, _):
        print "Synchronizing test start."
        sync = self.rt.synchronize()
        sync.addCallback(self.countdown, 3)

    def countdown(self, _, seconds):
        if seconds > 0:
            print "Starting test in %d" % seconds
            reactor.callLater(1, self.countdown, None, seconds - 1)
        else:
            print "Starting test now"
            self.run_test(None)

    def run_test(self, _):
        raise NotImplemented("Override this abstract method in a sub class.")

    def finished(self, _):
        print "Finished, synchronizing shutdown."
        sync = self.rt.synchronize()
        sync.addCallback(self.shutdown)

    def shutdown(self, _):
        print "Shutdown."
        self.rt.shutdown()
        print "Stopped VIFF Runtime."

# This class implements a benchmark where run_test executes all
# operations in parallel.
class ParallelBenchmark(Benchmark):

    def run_test(self, _):
        print "Starting parallel test."
        c_shares = []
        record_start()
        while self.a_shares and self.b_shares:
            a = self.a_shares.pop()
            b = self.b_shares.pop()
            c_shares.append(self.operation(a, b))

        done = gather_shares(c_shares)
        done.addCallback(record_stop)
        done.addCallback(self.finished)

# A benchmark where the operations are executed one after each other.
class SequentialBenchmark(Benchmark):

    def run_test(self, _):
        print "Starting sequential test."
        record_start()
        self.single_operation(None)

    def single_operation(self, _):
        if self.a_shares and self.b_shares:
            a = self.a_shares.pop()
            b = self.b_shares.pop()
            c = self.operation(a, b)
            c.addCallback(self.single_operation)
        else:
            record_stop(None)
            self.finished(None)

if options.operation == "mul":
    operation = operator.mul
    runtime_class = Runtime
elif options.operation == "comp":
    operation = operator.ge
    runtime_class = Toft05Runtime
elif options.operation == "compII":
    operation = operator.ge
    runtime_class = Toft07Runtime

if options.parallel:
    benchmark = ParallelBenchmark
else:
    benchmark = SequentialBenchmark

pre_runtime = create_runtime(id, players, (len(players) -1)//2, options, runtime_class)
pre_runtime.addCallback(benchmark, operation)

print "#### Starting reactor ###"
reactor.run()
