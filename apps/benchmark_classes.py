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

import sys
import time

from pprint import pformat

from viff.runtime import gather_shares
from viff.util import rand

start = 0


def record_start(what):
    global start
    start = time.time()
    print "*" * 64
    print "Started", what


def record_stop(x, what, count):
    stop = time.time()
    print
    print "Total time used: %.3f sec" % (stop-start)
    print "Time per %s operation: %.0f ms" % (what, 1000*(stop-start) / count)
    print "*" * 6
    return x


# Defining the protocol as a class makes it easier to write the
# callbacks in the order they are called. This class is a base class
# that executes the protocol by calling the run_test method.
class Benchmark:

    def __init__(self, rt, operation, field, count):
        self.rt = rt
        self.operation = operation
        self.pc = None
        self.field = field
        self.count = count
        
    def preprocess(self, needed_data):
        print "Preprocess", needed_data
        if needed_data:
            print "Starting preprocessing"
            record_start("preprocessing")
            preproc = self.rt.preprocess(needed_data)
            preproc.addCallback(record_stop, "preprocessing", self.count)
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
        for i in range(self.count):
            inputter = (i % len(self.rt.players)) + 1
            if inputter == self.rt.id:
                a = rand.randint(0, self.field.modulus)
                b = rand.randint(0, self.field.modulus)
            else:
                a, b = None, None
            self.a_shares.append(self.rt.input([inputter], self.field, a))
            self.b_shares.append(self.rt.input([inputter], self.field, b))
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
        done.addCallback(record_stop, "parallel test", self.count)
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
            record_stop(None, "sequential test", self.count)
            self.finished(None, termination_function)


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
