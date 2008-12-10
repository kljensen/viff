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

"""Test of apps/millionaires.py example."""

import re
import os
import os.path as path

from twisted.trial.unittest import TestCase
from twisted.internet import reactor
from twisted.internet.utils import getProcessOutput
from twisted.internet.defer import Deferred, gatherResults

from viff.field import GF256
from viff.util import rand

def execute(executable, *args):
    """Execute *executable* when the reactor is started."""
    d = Deferred()
    def run():
        p = getProcessOutput(path.abspath(executable),
                             args=args, env=os.environ, errortoo=True)
        p.chainDeferred(d)
    reactor.callLater(0, run)
    return d

class AppsTest(TestCase):
    """Test examples in apps/ directory."""

    def setUp(self):
        """Switch to apps/ directory and generate config files."""
        root_dir = path.abspath(path.join(path.dirname(__file__), "..", ".."))
        if root_dir not in os.environ.get("PYTHONPATH", ""):
            if "PYTHONPATH" in os.environ:
                os.environ["PYTHONPATH"] += os.pathsep + root_dir
            else:
                os.environ["PYTHONPATH"] = root_dir

        self.oldcwd = os.getcwd()
        os.chdir(path.join(root_dir, "apps"))

        port1, port2, port3 = rand.sample(xrange(10000, 30000), 3)
        p = execute("generate-config-files.py", "--prefix", "trial",
                    "--players", "3", "--threshold", "1",
                    "localhost:%d" % port1,
                    "localhost:%d" % port2,
                    "localhost:%d" % port3)
        return p

    def tearDown(self):
        """Switch back to the old working directory."""
        os.unlink("trial-1.ini")
        os.unlink("trial-2.ini")
        os.unlink("trial-3.ini")
        os.chdir(self.oldcwd)

    def test_millionaires(self):
        """Test apps/millionaires.py."""

        def check_outputs(outputs):
            millions = []
            for i, o in enumerate(outputs):
                self.assertIn("I am Millionaire %d" % (i+1) , o)

                match = re.search(r"I am worth (\d+) millions", o)
                millions.append((int(match.group(1)), i))
            millions.sort()

            for i, o in enumerate(outputs):
                lines = []
                for m, j in millions:
                    lines.append("  Millionaire %d" % (j+1))
                    if i == j:
                        lines[-1] += " (%d millions)" % m
                subtext = "\n".join(lines)
                self.assertIn(subtext, o)

        # TODO: Enable SSL again when we have a way of specifying the
        # name of the key and certificate. Right now the files are
        # always assumed to be named player-X.{key,cert}, but we want
        # them to be named trial-X.{key,cert} when testing.
        m1 = execute("millionaires.py", "--no-ssl", "trial-1.ini")
        m2 = execute("millionaires.py", "--no-ssl", "trial-2.ini")
        m3 = execute("millionaires.py", "--no-ssl", "trial-3.ini")

        result = gatherResults([m1, m2, m3])
        result.addCallback(check_outputs)
        return result

    def test_share_open(self):
        """Test apps/share-open.py."""

        def check_outputs(outputs):
            for o in outputs:
                self.assertIn("opened a: %s" % GF256(17), o)
                self.assertIn("opened b: %s" % GF256(40), o)
                self.assertIn("opened c: %s" % GF256(235), o)

        p1 = execute("share-open.py", "trial-1.ini", "17")
        p2 = execute("share-open.py", "trial-2.ini", "40")
        p3 = execute("share-open.py", "trial-3.ini", "235")

        result = gatherResults([p1, p2, p3])
        result.addCallback(check_outputs)
        return result

    def test_prss_and_open(self):
        """Test apps/prss-and-open.py."""

        def check_outputs(outputs):
            lines = []
            for o in outputs:
                for line in o.splitlines():
                    if line.startswith("bits:"):
                        lines.append(line)
                        break
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], lines[1])
            self.assertEqual(lines[1], lines[2])

        p1 = execute("prss-and-open.py", "trial-1.ini")
        p2 = execute("prss-and-open.py", "trial-2.ini")
        p3 = execute("prss-and-open.py", "trial-3.ini")

        result = gatherResults([p1, p2, p3])
        result.addCallback(check_outputs)
        return result

# TODO: add tests for other example applications.
