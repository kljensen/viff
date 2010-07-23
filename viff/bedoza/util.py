# Copyright 2010 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License (LGPL) as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General
# Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with VIFF. If not, see <http://www.gnu.org/licenses/>.

from twisted.internet.defer import Deferred, gatherResults

from viff.constants import TEXT

def _send(runtime, vals, serialize=str, deserialize=int):
    """Send vals[i] to player i + 1. Returns deferred list.

    Works as default for integers. If other stuff has to be
    sent, supply another serialization, deserialition.
    """
    runtime.increment_pc()
    
    pc = tuple(runtime.program_counter)
    for p in runtime.players:
        msg = serialize(vals[p - 1])
        runtime.protocols[p].sendData(pc, TEXT, msg)
    def err_handler(err):
        print err
    values = []
    for p in runtime.players:
        d = Deferred()
        d.addCallbacks(deserialize, err_handler)
        runtime._expect_data(p, TEXT, d)
        values.append(d)
    result = gatherResults(values)
    return result

def _convolute(runtime, val, serialize=str, deserialize=int):
    """As send, but sends the same val to all players."""
    return _send(runtime, [val] * runtime.num_players,
                 serialize=serialize, deserialize=deserialize)

def _convolute_gf_elm(runtime, gf_elm):
    return _convolute(runtime, gf_elm,
                      serialize=lambda x: str(x.value),
                      deserialize=lambda x: gf_elm.field(int(x)))

def _send_gf_elm(runtime, vals):
    return _send(runtime, vals, 
                 serialize=lambda x: str(x.value),
                 deserialize=lambda x: gf_elm.field(int(x)))
