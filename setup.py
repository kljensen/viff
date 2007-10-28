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
""",
      license=viff.__license__,
      packages=['viff', 'viff.test'])
