#!/usr/bin/python

import sys

from pysmpc.field import *
from pysmpc.runtime import Runtime
from pysmpc.generate_config import load_config

def output(x, format="output: %s"):
    print format % x
    return x

id, players = load_config(sys.argv[1])
input = GF256Element(int(sys.argv[2]))

print "I am player %d and will input %s" % (id, input)

rt = Runtime(players, id, 1)

print "-" * 64
print "Program started"
print

shares = rt.share_bit(input)

while len(shares) > 1:
    a = shares.pop(0)
    b = shares.pop(0)
    shares.append(rt.xor_bit(a,b))

xor = shares[0]

rt.open(xor)

xor.addCallback(output, "result: %s")
    
rt.wait_for(xor)
