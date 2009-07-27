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

# This program will generate private keys and SSL/TLS certificates for
# the players. An extra key and certificate is made for signing the
# other keys.
#
# Each player needs three files to create a SSL/TLS connection: the
# certificate (player-X.cert), the private key (player-X.key), and the
# CA certificate (ca.cert).

from OpenSSL import crypto

def create_key(bits, type=crypto.TYPE_RSA):
    """Create a public/private key pair."""
    pk = crypto.PKey()
    pk.generate_key(type, bits)
    return pk

def save_key(key, filename):
    """Save a key as a PEM file."""
    fp = open(filename, "w")
    fp.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    fp.close()

def create_request(pk, common_name, digest="sha1"):
    """Create a certificate request."""
    req = crypto.X509Req()
    subj = req.get_subject()
    subj.CN = common_name

    req.set_pubkey(pk)
    req.sign(pk, digest)
    return req

def create_cert(req, issuer_cert, issuer_sk, serial, valid=365, digest="sha1"):
    """Generate a certificate given a certificate request."""
    cert = crypto.X509()
    cert.set_serial_number(serial)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(valid * 60 * 60 * 24)
    cert.set_issuer(issuer_cert.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(issuer_sk, digest)
    return cert

def save_cert(cert, filename):
    """Save a certificate as a PEM file."""
    fp = open(filename, "w")
    fp.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    fp.close()

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-p", "--prefix",
                      help="output filename prefix")
    parser.add_option("-k", "--key-size", type="int",
                      help="key size")
    parser.add_option("-n", "--players", dest="n", type="int",
                      help="number of players")
    parser.set_defaults(n=3, key_size=1024, prefix='player')

    (options, args) = parser.parse_args()

    ca_key = create_key(options.key_size)
    ca_req = create_request(ca_key, "VIFF Certificate Authority")
    ca_cert = create_cert(ca_req, ca_req, ca_key, 0)

    save_key(ca_key, "ca.key")
    save_cert(ca_cert, "ca.cert")

    for i in range(1, options.n + 1):
        key = create_key(options.key_size)
        req = create_request(key, "VIFF Player %d" % i)
        cert = create_cert(req, ca_cert, ca_key, i)

        save_key(key, "%s-%d.key" % (options.prefix, i))
        save_cert(cert, "%s-%d.cert" % (options.prefix, i))
