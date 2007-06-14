#!/usr/bin/python

import sys, time

from pysmpc.field import IntegerFieldElement, GF256Element
from pysmpc.runtime import Runtime
from pysmpc.generate_config import load_config

def output(x, format="output: %s"):
    print (("-"*64) + "\n" + format + "\n" + ("-"*64)) % x
    return x

id, players = load_config(sys.argv[1])
print "I am player %d" % id

rt = Runtime(players, id, (len(players) -1)//2)

IntegerFieldElement.modulus = 11

x, y, z = rt.share_int(IntegerFieldElement(0))

x_b = rt.int_to_bit(x)
#y_b = rt.int_to_bit(y)
#z_b = rt.int_to_bit(z)

#rt.open(x)
#rt.open(y)
#rt.open(z)

rt.open(x_b)
#rt.open(y_b)
#rt.open(z_b)

#x.addCallback(output, "x: %s")
#y.addCallback(output, "y: %s")
#z.addCallback(output, "z: %s")

x_b.addCallback(output, "x_b: %s")
#y_b.addCallback(output, "y_b: %s")
#z_b.addCallback(output, "z_b: %s")

rt.wait_for(x,y,z, x_b)#, y_b, z_b)
