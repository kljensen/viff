# This is the VIFF setup script.
#
# For a global install by root, use:    python setup.py install
# For a local install into ~/opt, use:  python setup.py --home=~/opt
# For more options, use:                python setup.py --help

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

import sys
if not hasattr(sys, 'version_info') or sys.version_info < (2, 4, 0, 'final'):
    raise SystemExit, "VIFF requires Python version 2.4 or later."

from distutils.command.sdist import sdist
from distutils.core import setup

import viff

class hg_sdist(sdist):
    def get_file_list(self):
        try:
            from distutils.errors import DistutilsModuleError
            import subprocess
            p = subprocess.Popen(['hg', 'manifest'], stdout=subprocess.PIPE)
            exitcode = p.wait()
            if exitcode != 0:
                raise DistutilsModuleError("Mercurial exited with non-zero "
                                           "exit code: %d" % exitcode)
            files = p.stdout.read().strip().split('\n')

            # Add the files *before* the normal manifest magic is
            # done. That allows the manifest template to exclude some
            # files tracked by hg and to include others.
            self.filelist.extend(files)
            sdist.get_file_list(self)
        except OSError, e:
            raise DistutilsModuleError("could not execute Mercurial: %s" % e)

setup(name='viff',
      version=viff.__version__,
      author='VIFF Development Team',
      author_email='viff-devel@viff.dk',
      url='http://viff.dk/',
      description='A framework for secure multi-party computation (SMPC)',
      long_description="""\
The Virtual Ideal Functionality Framework is a framework for doing
secure multi-party computations (SMPC). Features include:

* secret sharing based on standard Shamir and pseudo-random secret
  sharing (PRSS).

* arithmetic with shares from Zp or GF(2^8): addition, multiplication,
  exclusive-or.

* two comparison protocols which compare secret shared Zp inputs, with
  secret GF(2^8) or Zp output.

* reliable Bracha broadcast secure against active adversaries.

* computations with any number of players for which an honest majority
  can be found.

All operations are automatically scheduled to run in parallel meaning
that an operation starts as soon as the operands are ready.
""",
      keywords=[
        'crypto', 'cryptography', 'multi-party computation', 'MPC', 'SMPC',
        'secure comparison', 'ideal functionality',
        'Shamir', 'pseudo-random secret sharing', 'PRSS', 'Bracha broadcast'
        ],
      license=viff.__license__,
      packages=['viff', 'viff.test', 'viff.libs'],
      platforms=['any'],
      classifiers=[
        'Development Status :: 3 - Alpha',
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Communications',
        'Topic :: Security :: Cryptography',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules'
        ],
      cmdclass={'sdist': hg_sdist}
      )

# When releasing VIFF, notify these sites:
#
# * http://viff.dk/
# * viff-devel@viff.dk
# * http://freshmeat.net/projects/viff/
# * http://pypi.python.org/pypi/viff/
# * http://directory.fsf.org/project/viff/
# * http://www.icewalkers.com/Linux/Software/532160/VIFF.html
# * http://www.hotscripts.com/Detailed/74748.html
# * http://sourcewell.berlios.de/appbyid.php?id=3572
# * python-announce-list@python.org
