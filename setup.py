#
# This is the VIFF setup script.
#
# For a global install by root, use:    python setup.py install
# For a local install into ~/opt, use:  python setup.py --home=~/opt
# For more options, use:                python setup.py --help

from distutils.core import setup

import viff

setup(name='viff',
      version=viff.__version__,
      author='Martin Geisler',
      author_email='mg@daimi.au.dk',
      url='http://viff.dk/',
      description='Virtual Ideal Functionality Framework',
      long_description="""\
VIFF is a framework for doing secure multi-party computations (SMPC).
Features include:

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
      license=viff.__license__,
      packages=['viff', 'viff.test'],
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
        ]
      )
