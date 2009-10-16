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

from twisted.internet.defer import gatherResults

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


class Benchmark(object):
    """Abstract base class for all Benchmarks.

    For concrete classes see the `ParallelBenchmark` and
    `SequentialBenchmark` classes. A concrete class must be mixed with
    a `BenchmarkStrategy` and an `Operator`.
    """

    def __init__(self, rt, operation, field, count):
        self.rt = rt
        self.operation = getattr(rt, operation)
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

    def test(self, d, termination_function):
        self.rt.schedule_callback(d, self.generate_operation_arguments)
        self.rt.schedule_callback(d, self.sync_test)
        self.rt.schedule_callback(d, self.run_test)
        self.rt.schedule_callback(d, self.sync_test)
        self.rt.schedule_callback(d, self.finished, termination_function)
        return d

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


class ParallelBenchmark(Benchmark):
    """This class implements a benchmark where run_test executes all
    operations in parallel."""

    def run_test(self, shares):
        print "rt", self.rt.program_counter, self.pc
        if self.pc != None:
            self.rt.program_counter = self.pc
        else:
            self.pc = list(self.rt.program_counter)
        c_shares = []
        record_start("parallel test")
        while not self.is_operation_done():
            c_shares.append(self.do_operation())
            print "."

        done = gatherResults(c_shares)
        done.addCallback(record_stop, "parallel test", self.count)
        def f(x):
            needed_data = self.rt._needed_data
            self.rt._needed_data = {}
            return needed_data
        done.addCallback(f)
        return done


class SequentialBenchmark(Benchmark):
    """A benchmark where the operations are executed one after each
    other."""

    def run_test(self, _, termination_function, d):
        record_start("sequential test")
        self.single_operation(None, termination_function)

    def single_operation(self, _, termination_function):
        if not self.is_operation_done():
            c = self.do_operation()
            self.rt.schedule_callback(c, self.single_operation, termination_function)
        else:
            record_stop(None, "sequential test", self.count)
            self.finished(None, termination_function)


class Operation(object):
    """An abstract mixin which encapsulate the behaviour of an operation.

    An operation can be nullary, unary, binary, etc.
    """

    def generate_operation_arguments(self, _):
        """Generate the input need for performing the operation.

        Returns: None.
        """
        raise NotImplemented("Override this abstract method in subclasses")

    def is_operation_done(self):
        """Returns true if there are no more operations to perform.
        Used in sequential tests.

        Returns: Boolean.
        """
        raise NotImplemented("Override this abstract method in subclasses")

    def do_operation(self):
        """Perform the operation.

        Returns: A share containing the result of the operation.
        """
        raise NotImplemented("Override this abstract method in subclasses")

class BinaryOperation(Operation):
    """A binary operation."""

    def generate_operation_arguments(self, _):
        print "Generate operation arguments", self.rt.program_counter
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

    def is_operation_done(self):
        return not (self.a_shares and self.b_shares)

    def do_operation(self):
        a = self.a_shares.pop()
        b = self.b_shares.pop()
        return self.operation(a, b)


class NullaryOperation(Operation):
    """A nullary operation."""

    def generate_operation_arguments(self, _):
        self.nullary_tests = self.count
        return None

    def is_operation_done(self):
        return self.nullary_tests == 0

    def do_operation(self):
        self.nullary_tests -= 1
        return self.operation(self.field)


class BenchmarkStrategy(object):
    """A benchmark strategy defines how the benchmark is done."""

    def benchmark(self, *args):
        raise NotImplemented("Override this abstract method in subclasses")


class SelfcontainedBenchmarkStrategy(BenchmarkStrategy):
    """In a self contained benchmark strategy, all the needed data is
    generated on the fly."""

    def benchmark(self, *args):
        sys.stdout.flush()
        sync = self.rt.synchronize()
        self.test(sync, lambda x: x)
        self.rt.schedule_callback(sync, self.preprocess)
        self.test(sync, lambda x: self.rt.shutdown())


class NeededDataBenchmarkStrategy(BenchmarkStrategy):
    """In a needed data benchmark strategy, all the needed data has to
    have been generated before the test is run."""

    def benchmark(self, needed_data, pc, *args):
        self.pc = pc
        sys.stdout.flush()
        sync = self.rt.synchronize()
        self.rt.schedule_callback(sync, lambda x: needed_data)
        self.rt.schedule_callback(sync, self.preprocess)
        self.test(sync, lambda x: self.rt.shutdown())
