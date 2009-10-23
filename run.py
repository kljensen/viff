#!/usr/bin/env python

# Copyright 2008 VIFF Development Team.
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

"""Simple build generator for VIFF.

Instead of creating a Makefile which would probably only run on
GNU/Linux and similar systems, we have created this little program to
run the commands used when building releases of VIFF.
"""

import sys, os, shutil
from os.path import isdir, join, getsize
from subprocess import Popen
from pprint import pprint
from textwrap import wrap
from base64 import b64decode

from twisted.python.procutils import which

def abort(msg, *args, **kwargs):
    if args:
        msg = msg % args
    print
    print "*** %s" % msg
    sys.exit(kwargs.get('exit_code', 1))

def find_program(program):
    possibilities = which(program)
    if not possibilities:
        abort("Could not find '%s' in PATH", program)
    return possibilities[0]

def execute(args, env={}, work_dir=None):
    print "Executing"
    pprint(args)
    if env:
        print "in environment"
        pprint(env)
    if work_dir:
        print "in working directory '%s'" % work_dir
    print

    if 'PATH' in os.environ:
        if 'PATH' in env:
            env['PATH'] += os.pathsep + os.environ['PATH']
        else:
            env['PATH'] = os.environ['PATH']

    if 'PYTHONPATH' in os.environ:
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] += os.pathsep + os.environ['PYTHONPATH']
        else:
            env['PYTHONPATH'] = os.environ['PYTHONPATH']

    try:
        p = Popen(args, env=env, cwd=work_dir)
        rc = p.wait()
        if rc != 0:
            abort("Exited with exit code %d", rc, exit_code=rc)
    except OSError, e:
        abort(e)
    except KeyboardInterrupt:
        abort("Interrupted")

def ensure_dir(path):
    if not isdir(path):
        try:
            os.makedirs(path)
        except OSError, e:
            abort(e)


# Dictionary mapping command line arguments to [function, arguments]
# lists.
command_table = {}

def command(name, *required_args):
    def wrapper(func):
        command_table[name] = [func, required_args]
        return func
    return wrapper

@command('build')
def build():
    """Build a VIFF distribution."""

    # Generate HTML docs in doc/html.
    if isdir('doc/html'):
        shutil.rmtree('doc/html')
    sphinx('doc/html')

    # Pack everything up with Distutils.
    execute(["python", "setup.py", "sdist", "--force-manifest",
             "--formats=bztar,gztar,zip"])

    # Generate binary Windows installer (which has no docs, though).
    execute(["python", "setup.py", "bdist", "--formats=wininst"])

@command('sphinx', 'target')
def sphinx(target):
    """Generate VIFF manual using Sphinx."""
    ensure_dir(target)
    execute(["sphinx-build", "-N", "doc", target])

@command('coverage', 'target')
def coverage(target):
    """Run Trial unit tests and collect coverage data."""
    ensure_dir(target)
    trial = find_program("trial")
    execute(["trace2html.py", "-o", target, "-w", "viff", "-b", "viff.test",
             "--run-command", trial, "--reporter", "timing", "viff"])

    # The trace2html script references an image called blank.png, but
    # this is not included in the output! So we have stored a blank
    # 10x12 pixel PNG image here. In addition we have images of an
    # upwards and downwards arrow. The image data is base64 encoded.
    images = {
        'blank': 'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAQAAADxYuQrAAAAAXNSR0IA' \
            'rs4c6QAAAAxJREFUCNdjYBi5AAAA/AAB3Q3J0QAAAABJRU5ErkJggg==',
        'up': 'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAQAAADxYuQrAAAAAXNSR0IArs4' \
            'c6QAAAD1JREFUCNdjYKAiYGaYycCMLljA8J+hAFVIhuEzw3+GzwwyjEiCpQy3' \
            'GDYwBDCooRvwn4GBgYEJm30UCgIAjEkJGS0CllcAAAAASUVORK5CYII=',
        'down': 'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAQAAADxYuQrAAAAAXNSR0IAr' \
            's4c6QAAAD5JREFUCNdjYKAq+M/AwMDAhE2GQkEWJHYpwy0GBgZ/BjVkBTIMnx' \
            'n+M3xmkEHVV8Dwn6EA3TBmhpkMzAwMAPNoCGsXUhMyAAAAAElFTkSuQmCC'
        }

    ensure_dir("%s/images" % target)

    for name, data in images.iteritems():
        filename = "%s/images/%s.png" % (target, name)
        fp = open(filename, 'w')
        fp.write(b64decode(data))
        fp.close()

    # To use the images we need to append some extra rules to the
    # stylesheet.
    extra_css = """
img.ascending {
  background-image: url("images/up.png");
}

img.descending {
  background-image: url("images/down.png");
}
"""

    filename = "%s/trace2html.css" % target
    fp = open(filename, 'a')
    fp.write(extra_css)
    fp.close()


@command('upload', 'source', 'target', 'key')
def upload(source, target, key):
    """Upload source to http://viff.dk/target. This requires an SSH
    private key that has access to viff.dk."""
    if not isdir(source):
        abort("%s should be a directory", source)
    if not os.access(key, os.R_OK):
        abort("Cannot read %s", key)

    execute(['rsync', '--recursive', '--links',
             '--human-readable', '--stats', '--verbose',
             '--chmod', 'go=rX',
             '-e', 'ssh -l viff -i %s' % key,
             source, 'viff.dk:~/viff.dk/%s' % target])

@command('size')
def size():
    """Calculate the size in KiB of the working copy currently checked
    out."""
    total = 0
    for root, dirs, files in os.walk('.'):
        total += sum(getsize(join(root, name)) for name in files)
        if '.hg' in dirs:
            dirs.remove('.hg')
    print total // 1024


@command('pyflakes')
def pyflakes():
    """Find static errors using Pyflakes."""
    pyfiles = []
    for root, dirs, files in os.walk('.'):
        pyfiles.extend([join(root, name) for name in files if name.endswith('.py')])
        if 'libs' in dirs:
            # Do not recurse into the 'viff/libs' directory.
            dirs.remove('libs')

    if sys.platform == "win32":
        execute(['pyflakes.bat'] + pyfiles)
    else:
        execute(['pyflakes'] + pyfiles)


@command('trial', 'python')
def trial(python):
    """Execute Trial using the Python executable given."""
    trial = find_program("trial")
    trial_env = {}

    # Twisted on Windows needs the SYSTEMROOT env variable, see
    # http://tracker.viff.dk/issue18
    if sys.platform == "win32":
        if os.environ['SYSTEMROOT']:
            trial_env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
        else:
            abort("Twisted Trial needs SYSTEMROOT env variable.")

    execute([python, trial, '--reporter=bwverbose', 'viff.test'],
            env=trial_env)


@command('help')
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
    print "Available commands (the arguments in angle brackets are required):"
    for command, doc in commands:
        # The docstring might contain newlines followed by an
        # indention. So we split it up into lines, strip each line,
        # and finally we combine all lines into one long string.
        # combine them again.
        doc = " ".join(map(str.strip, doc.splitlines()))
        lines = wrap(doc, doc_width)
        print "  %-*s%s" % (command_width, command, lines[0])
        for line in lines[1:]:
            print "  %-*s%s" % (command_width, '', line)


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
