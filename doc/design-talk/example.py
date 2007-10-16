import sys
from viff.field import GF
from viff.config import load_config
from viff.runtime import Runtime
from viff.util import dprint

Z31 = GF(31)
my_id, conf = load_config(sys.argv[1])
my_input = Z31(int(sys.argv[2]))

rt = Runtime(conf, my_id, 1)
x, y, z = rt.shamir_share(my_input)
result = rt.mul(rt.add(x, y), z)

rt.open(result)
dprint("Result: %s", result)
rt.wait_for(result)
