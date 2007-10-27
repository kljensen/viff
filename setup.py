#
# This is the VIFF setup script.
#
# For a global install by root, use:    python setup.py install
# For a local install into ~/opt, use:  python setup.py --home=~/opt
# For more options, use:                python setup.py --help

from distutils.core import setup

setup(name='viff',
      version='0.1.1',
      author='Martin Geisler',
      author_email='mg@daimi.au.dk',
      url='http://viff.dk/',
      description='Virtual Ideal Functionality Framework',
      long_description="""\
VIFF is a framework for doing secure multi-party computations (SMPC).
""",
      license='GNU GPL',
      packages=['viff', 'viff.test'])
