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

a, b, c = rt.share_bit(input)

rt.open(a)
rt.open(b)
rt.open(c)

a.addCallback(output, "\n### opened a: %s ###\n")
b.addCallback(output, "\n### opened b: %s ###\n")
c.addCallback(output, "\n### opened c: %s ###\n")

rt.wait_for(a,b,c)
