#!/bin/sh

# Copyright 2007 Martin Geisler
#
# This file is part of VIFF
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

PROFILE_DIR=$HOME/.daimi-setup/bash/bashrc.d
RC=$PROFILE_DIR/viff.rc

MG_PYTHONPATH=/users/mg/opt/lib/python2.4/site-packages
MG_PATH=/users/mg/opt/bin
MG_VIFF=/users/mg/simap/viff

if [ ! -d $PROFILE_DIR ]; then
    echo "$PROFILE_DIR not found."
    echo "Sorry, could not understand your setup, aborting."
    exit 1
fi

if [ -f $RC ]; then
    echo "$RC already exists."
    echo "Please remove before running this script again, aborting."
    exit 1
fi

echo -n "* Checking for Trial and Mercurial:"
if which trial hg > /dev/null 2>&1; then
    echo " found."
else
    echo " not found."

    echo "  Adjusting PATH to fix this."
    echo "# PATH setup for VIFF" >> $RC
    echo "PATH=\$PATH:$MG_PATH" >> $RC
    echo >> $RC
fi

echo -n "* Checking for VIFF dependencies (Twisted, ConfigObj, GMPY):"
if python -c 'import twisted, configobj, gmpy' 2> /dev/null; then
    echo " found."
else
    echo " not found."

    echo "  Adjusting PYTHONPATH to fix this."

    echo "# PYTHONPATH setup for VIFF dependencies" >> $RC
    echo "PYTHONPATH=\$PYTHONPATH:$MG_PYTHONPATH" >> $RC
    echo "export PYTHONPATH" >> $RC
    echo >> $RC
fi

if [ -f $RC ]; then
    source $RC
fi

DEFAULT=~/viff

echo
echo "VIFF will now be checked out from Martin's repository."
echo "Where should the files be placed?"
read -p "Press ENTER to accept the default. [$DEFAULT] " CHECKOUT

if [ -z "$CHECKOUT" ]; then
    CHECKOUT=$DEFAULT
fi

hg clone $MG_VIFF $CHECKOUT

echo "Adding $CHECKOUT to your PYTHONPATH"
echo "# PYTHONPATH setup for VIFF checkout" >> $RC
echo "PYTHONPATH=\$PYTHONPATH:$CHECKOUT" >> $RC
echo "export PYTHONPATH" >> $RC
echo >> $RC

echo
echo "For more information please see these resources:"
echo "Python:"
echo "  file:///users/mg/doc/python/index.html"
echo "Twisted:"
echo "  http://twistedmatrix.com/projects/core/documentation/howto/"
echo "Mercurial (hg):"
echo "  http://www.selenic.com/mercurial/"
echo
echo "To undo this configuration, simply delete"
echo "  $RC"
echo
echo "Enjoy!"
