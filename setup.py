#
# This is the VIFF setup script.
#
# For a global install by root, use:    python setup.py install
# For a local install into ~/opt, use:  python setup.py --home=~/opt
# For more options, use:                python setup.py --help

from distutils.command.sdist import sdist
from distutils.core import setup

import viff

class hg_sdist(sdist):
    def get_file_list(self):
        try:
            # Attempt the import here so that users can run the other
            # Distutils commands without needing Mercurial.
            from mercurial import hg
        except ImportError:
            from distutils.errors import DistutilsModuleError
            raise DistutilsModuleError("could not import mercurial")

        repo = hg.repository(None)
        changeset = repo.changectx()
        files = changeset.manifest().keys()
        
        # Add the files *before* the normal manifest magic is done.
        # That allows the manifest template to exclude some files
        # tracked by hg and to include others.
        self.filelist.extend(files)
        sdist.get_file_list(self)

setup(name='viff',
      version=viff.__version__,
      author='Martin Geisler',
      author_email='mg@daimi.au.dk',
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

* computations with any number of players for which an honest majority
  can be found.

All operations are automatically scheduled to run in parallel meaning
that an operation starts as soon as the operands are ready.
""",
      keywords=[
        'cryptography', 'multi-party computation', 'MPC', 'SMPC',
        'secure comparison', 'ideal functionality',
        'Shamir', 'pseudo-random secret sharing', 'PRSS'
        ],
      license=viff.__license__,
      packages=['viff', 'viff.test'],
      platforms=['any'],
      classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Communications',
        'Topic :: Security :: Cryptography',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules'
        ],
      cmdclass={'sdist': hg_sdist}
      )
