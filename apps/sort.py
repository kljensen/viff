#!/usr/bin/python

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

# This example demonstrates how a secure sorting algorithm can be
# implemented using VIFF. The algorithm used is bitonic sort which was
# chosen in order to maximize the amount of work (comparisons) done in
# parallel. Bitonic sort uses 1/2 * log n * (log n + 1) comparator
# stages and each stage consists of n/2 parallel comparisons. The
# total number of comparisons is thus in O(n log^2 n).
#
# This is larger than the lower bound of Omega(n log n) for comparison
# based sorting algorithms, achieved by mergesort and other well known
# algorithms. The problem with mergesort is its merging step: to merge
# two sorted arrays of length n/2 one needs up to n comparisons, and
# what is worse, the comparisons must be made one after another. The
# mergesort does one merge with lists of size n/2, two merges with
# lists of size n/4, and so on. This gives a total chain of
# comparisons of length n + n/2 + n/4 + ... + 1 = 2n - 1, which is
# more than the O(log^2 n) stages needed by the Bitonic Sort.
#
# TODO: Implement mergesort too to better back this up.
#
# See this page for more analysis and a Java implementation:
#
# http://iti.fh-flensburg.de/lang/algorithmen/sortieren/bitonic/bitonicen.htm
#
# It requires ProgressBar v. 2.2 found on
# http://pypi.python.org/pypi/progressbar/
#
# TODO: Predict the number of comparisons and support preprocessing.
#

# Give a player configuration file as a command line argument or run
# the example with '--help' for help with the command line options.

from math import log, floor
from optparse import OptionParser
import viff.reactor
viff.reactor.install()
from twisted.internet import reactor

from progressbar import ProgressBar, Percentage, Bar, ETA, ProgressBarWidget

from viff.field import GF
from viff.runtime import Runtime, create_runtime, gather_shares
from viff.comparison import Toft07Runtime
from viff.config import load_config
from viff.util import find_prime, rand, dprint

# Parse command line arguments.
parser = OptionParser()
parser.add_option("--modulus",
                  help="lower limit for modulus (can be an expression)")
parser.add_option("-s", "--size", type="int",
                  help="array size")
parser.add_option("-m", "--max", type="int",
                  help="maximum size of array numbers")
parser.add_option("-t", "--test", action="store_true",
                  help="run doctests on this file")

parser.set_defaults(modulus=2**65, size=8, max=100, test=False)

Runtime.add_options(parser)

options, args = parser.parse_args()

if len(args) == 0:
    parser.error("you must specify a config file")

Zp = GF(find_prime(options.modulus, blum=True))


class Protocol:

    def setup_progress_bar(self):

        class HowManyWidget(ProgressBarWidget):
            "Showing the number of finished comparisons/total number"

            def update(self, pbar):
                return "Comparisons %s/%s" % (pbar.currval, pbar.maxval)

        widgets = ['Sorting: ', Percentage(), ' ',
                   Bar(marker='0', left='[', right=']'),
                   ' ', ETA(), ' ', HowManyWidget()]
        return ProgressBar(widgets=widgets,
                           maxval=Protocol.predict_sort(options.size))

    def __init__(self, runtime):
        self.progressbar = self.setup_progress_bar()
        self.rt = runtime
        self.comparisons = 0

        array = self.make_array()
        sorted = self.sort(array)

        array = gather_shares(map(runtime.open, array))
        sorted = gather_shares(map(runtime.open, sorted))

        self.progressbar.start()

        def finish(result):
            self.progressbar.finish()
            print # This line goes on top of the progressbar
            dprint("Original array: %s", array)
            dprint("Sorted array:   %s", result)
            print "Made %d comparisons" % self.comparisons
            runtime.shutdown()

        sorted.addCallback(finish)

    @staticmethod
    def predict_sort(array_size):
        """ Calculate how many comparisons will be made by the bitonic
        sort
        >>> predict_sort(8)
        24
        >>> predict_sort(10)
        33
        """

        def predict_bitonic_sort(n):
            if n > 1:
                m = n >> 1
                return predict_bitonic_sort(m) + \
                    predict_bitonic_sort(n - m) + predict_bitonic_merge(n)
            else:
                return 0

        def predict_bitonic_merge(n):
            if n > 1:
                m = 1 << (int(floor(log(n-1, 2))))
                return n-m + predict_bitonic_merge(m) + \
                    predict_bitonic_merge(n - m)
            else:
                return 0

        return predict_bitonic_sort(array_size)

    def make_array(self):
        array = []
        for i in range(options.size):
            inputter = (i % 3) + 1
            if inputter == self.rt.id:
                number = rand.randint(1, options.max)
                print "Sharing array[%d] = %s" % (i, number)
            else:
                number = None
            share = self.rt.shamir_share([inputter], Zp, number)
            array.append(share)
        return array

    def sort(self, array):
        # Make a shallow copy -- the algorithm wont be in-place anyway
        # since we create lots of new Shares as we go along.
        array = array[:]

        def bitonic_sort(low, n, ascending):
            if n > 1:
                m = n // 2
                bitonic_sort(low, m, ascending=not ascending)
                bitonic_sort(low + m, n - m, ascending)
                bitonic_merge(low, n, ascending)

        def bitonic_merge(low, n, ascending):
            if n > 1:
                # Choose m as the greatest power of 2 less than n.
                m = 2**int(floor(log(n-1, 2)))
                for i in range(low, low + n - m):
                    compare(i, i+m, ascending)
                bitonic_merge(low, m, ascending)
                bitonic_merge(low + m, n - m, ascending)

        def compare(i, j, ascending):

            def tick_progressbar(dummy):
                """This is added as a callback to the deferred in le, and
                therefor must pass on the result of the comparison to
                where it is actually used."""
                self.comparisons += 1
                self.progressbar.update(self.comparisons)
                return dummy

            def xor(a, b):
                # TODO: We use this simple xor until
                # http://tracker.viff.dk/issue60 is fixed.
                return a + b - 2*a*b

            le = array[i] <= array[j] # a deferred
            le.addCallback(tick_progressbar)

            # We must swap array[i] and array[j] when they sort in the
            # wrong direction, that is, when ascending is True and
            # array[i] > array[j], or when ascending is False (meaning
            # descending) and array[i] <= array[j].
            #
            # Using array[i] <= array[j] in both cases we see that
            # this is the exclusive-or:
            b = xor(ascending, le)

            # We now wish to calculate
            #
            #   ai = b * array[j] + (1-b) * array[i]
            #   aj = b * array[i] + (1-b) * array[j]
            #
            # which uses four secure multiplications. We can rewrite
            # this to use only one secure multiplication:
            ai, aj = array[i], array[j]
            b_ai_aj = b * (ai - aj)

            array[i] = ai - b_ai_aj
            array[j] = aj + b_ai_aj

        bitonic_sort(0, len(array), ascending=True)
        return array

# Run doctests
if options.test:
    import doctest                #pragma NO COVER
    doctest.testmod(verbose=True) #pragma NO COVER

# Load configuration file.
id, players = load_config(args[0])

# Create a deferred Runtime and ask it to run our protocol when ready.
pre_runtime = create_runtime(id, players, 1,
                             options, runtime_class=Toft07Runtime)
pre_runtime.addCallback(Protocol)

# Start the Twisted event loop.
reactor.run()
