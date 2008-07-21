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

def execute(executable, *args):
    """Execute *executable* when the reactor is started."""
    d = Deferred()
    def run():
        p = getProcessOutput(path.abspath(executable),
                             args=args, env=os.environ)
        p.chainDeferred(d)
    reactor.callLater(0, run)
    return d

class AppsTest(TestCase):
    """Test examples in apps/ directory."""

    def setUp(self):
        """Switch to apps/ directory and generate config files."""
        self.oldcwd = os.getcwd()
        os.chdir(path.join(path.dirname(__file__), '..', '..', 'apps'))

        p = execute('generate-config-files.py', '-n', '3', '-t', '1',
                    'localhost:10000', 'localhost:20000', 'localhost:30000')
        return p

    def tearDown(self):
        """Switch back to the old working directory."""
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

        m1 = execute('millionaires.py', 'player-1.ini')
        m2 = execute('millionaires.py', 'player-2.ini')
        m3 = execute('millionaires.py', 'player-3.ini')
        
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

        p1 = execute('share-open.py', 'player-1.ini', '17')
        p2 = execute('share-open.py', 'player-2.ini', '40')
        p3 = execute('share-open.py', 'player-3.ini', '235')
        
        result = gatherResults([p1, p2, p3])
        result.addCallback(check_outputs)
        return result
