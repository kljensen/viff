#!/usr/bin/python

import sys

import pysmpc.shamir
from pysmpc.field import *

if sys.argv[1].find(":") == -1:
    F = IntegerFieldElement
    F.modulus = int(sys.argv.pop(1))
else:
    F = GF256Element

shares = [map(int, arg.split(":")) for arg in sys.argv[1:]]
shares = [(F(id), F(share)) for id,share in shares]

print "Shares:", shares
print "Result:", shamir.recombine(shares)
