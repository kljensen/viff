#!/usr/bin/python

# Copyright 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

"""Simple build generator for VIFF.

Instead of creating a Makefile which would probably only run on
GNU/Linux and similar systems, we have created this little program to
run the commands used when building releases of VIFF.
"""

import sys, os
import os.path
from subprocess import Popen, call
from pprint import pprint
from textwrap import wrap

from twisted.python.procutils import which

def abort(msg, *args):
    if args:
        msg = msg % args
    print
    print "*** %s" % msg
    sys.exit(1)

def find_program(program):
    possibilities = which(program)
    if not possibilities:
        abort("Could not find '%s' in PATH", program)
    return possibilities[0]

def execute(args, env=None):
    print "Executing:"
    pprint(args)
    if env is not None:
        print "in environment:"
        pprint(env)
    print

    try:
        p = Popen(args, env=env)
        rc = p.wait()
        print
        print "Exit code: %d" % rc
        sys.exit(rc)
    except OSError, e:
        abort(e)
    except KeyboardInterrupt:
        abort("Interrupted")

def ensure_dir(path):
    if not os.path.isdir(path):
        try:
            os.makedirs(path)
        except OSError, e:
            abort(e)

def epydoc(build):
    """Generate API documentation using epydoc."""
    target = "%s/api" % build
    ensure_dir(target)
    execute(["epydoc", "-vv", "--config", "epydoc.conf"],
            {'EPYDOC': 'YES', 'target': target})

def coverage(build):
    """Run Trial unit tests and collect coverage data."""
    target = "%s/coverage" % build
    ensure_dir(target)
    trial = find_program("trial")
    execute(["trace2html.py", "-o", target, "-w", "viff", "-b", "viff.test",
             "--run-command", trial, "--reporter", "timing", "viff"])

def usage():
    """Show this help message and exit."""
    try:
        width = int(os.environ['COLUMNS'])
    except (KeyError, ValueError):
        width = 80
    width -= 4 # Indent two spaces on each side.

    def format(command, args):
        if args:
            return "%s <%s>" % (command, "> <".join(args))
        else:
            return "%s" % command

    commands = [(format(com, args), func.__doc__)
                for (com, (func, args)) in command_table.iteritems()]
    commands.sort()

    command_width = max(map(lambda (com, _): len(com), commands))
    command_width += 2
    doc_width = width - command_width

    print "VIFF Build Generation Tool"
    print
    print "Available commands:"
    for command, doc in commands:
        lines = wrap(doc, doc_width)
        print "  %-*s%s" % (command_width, command, lines[0])
        for line in lines[1:]:
            print "  %-*s%s" % (command_width, '', line)

# Dictionary mapping command line arguments to [function, arguments]
# lists.
command_table = {'epydoc':   [epydoc,   ["build"]],
                 'coverage': [coverage, ["build"]],
                 'help':     [usage,    []]}

if __name__ == "__main__":
    try:
        command = sys.argv[1]
    except IndexError:
        usage()
        abort("Please specify a command")

    args = sys.argv[2:]

    if command in command_table:
        func, required_args = command_table[command]
        if len(args) == len(required_args):
            func(*args)
        else:
            usage()
            plural = len(required_args) == 1 and 'argument' or 'arguments'
            abort("%s needs exactly %d %s, but %d was given",
                  command, len(required_args), plural, len(args))
    else:
        usage()
        abort("Unknown command: %s", command)
