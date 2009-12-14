# Copyright 2007, 2008, 2009 VIFF Development Team.
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

"""
Virtual Ideal Functionality Framework.

VIFF is a Python framework for writing multi-party computations (MPC)
in an easy, efficient, and secure way.
"""

__version__ = '1.0'
__license__ = 'GNU LGPL'

def release():
    """Get the full release number.

    If Mercurial is available, "hg identify" will be used to determine
    the state of the repository and a string of the form ``x.y-hash``
    is returned where ``hash`` is the changeset ID or tag. If the tag
    is the same as ``__version__``, then ``__version__`` is simply
    returned.
    """
    try:
        from subprocess import Popen, PIPE
        p = Popen(["hg", "identify"], stdout=PIPE)
        stdout, _ = p.communicate()
        if p.returncode != 0:
            extra = "unknown"
        else:
            parts = stdout.split()
            if len(parts) == 1 or parts[1] == "tip":
                # No tag for this changeset or only "tip".
                extra = parts[0]
            else:
                extra = parts[1]
    except OSError:
        extra = "unknown"

    if extra == __version__:
        return __version__
    else:
        return "%s-%s" % (__version__, extra)
