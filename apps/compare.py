#!/usr/bin/python

import sys, time, random

from twisted.internet.defer import gatherResults

from pysmpc.field import IntegerFieldElement, GF256Element
from pysmpc.runtime import Runtime
from pysmpc.generate_config import load_config

def output(x, format="output: %s"):
    print format % x
    return x

IntegerFieldElement.modulus = 2039

id, players = load_config(sys.argv[1])
print "I am player %d" % id

rt = Runtime(players, id, 1)

bits = []

l = 7

rand = dict([(i, random.Random(i)) for i in players])

inputs = []
for i in range(3):
    input = dict([(j, rand[j].randint(0,pow(2,l))) for j in players])
    inputs.append(input)

# Fixed input for easier debugging
inputs.append({1: 20, 2: 25, 3: 0})

for input in inputs:
    x, y, z = rt.shamir_share(IntegerFieldElement(input[id]))
    bit = rt.greater_than(x,y)
    rt.open(bit)
    bit.addCallback(lambda b: b == GF256Element(1))
    bit.addCallback(lambda b, x, y: "%3d >= %3d: %-5s (%s)" % (x, y, b, b == (x >= y)),
                    input[1], input[2])
    bit.addCallback(output, "%s")
    bits.append(bit)

results = gatherResults(bits)

rt.wait_for(results)
