# Copyright 2009 VIFF Development Team.
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

"""Tests for viff.aes."""


from viff.test.util import RuntimeTestCase, protocol

from viff.field import GF256
from viff.runtime import gather_shares, Share
from viff.aes import bit_decompose, AES

from viff.test.rijndael import S, rijndael


__doctest__ = ["viff.aes"]


class BitDecompositionTestCase(RuntimeTestCase):
    """Test GF256 bit decomposition."""

    def verify(self, runtime, results, expected_results):
        self.assert_type(results, list)
        opened_results = []

        for result, expected in zip(results, expected_results):
            self.assert_type(result, Share)
            opened = runtime.open(result)
            opened.addCallback(self.assertEquals, expected)
            opened_results.append(opened)
        
        return gather_shares(opened_results)

    @protocol
    def test_bit_decomposition(self, runtime):
        share = Share(runtime, GF256, GF256(99))
        return self.verify(runtime, bit_decompose(share),
                           [1,1,0,0,0,1,1,0])


class AESTestCase(RuntimeTestCase):
    def verify(self, runtime, results, expected_results):
        self.assert_type(results, list)
        opened_results = []
        
        for result_row, expected_row in zip(results, expected_results):
            self.assert_type(result_row, list)
            self.assertEquals(len(result_row), len(expected_row))

            for result, expected in zip(result_row, expected_row):
                self.assert_type(result, Share)
                opened = runtime.open(result)
                opened.addCallback(self.assertEquals, expected)
                opened_results.append(opened)

        return gather_shares(opened_results)

    def _test_byte_sub(self, runtime, aes):
        results = []
        expected_results = []

        for i in range(4):
            results.append([])
            expected_results.append([])

            for j in range(4):
                b = 60 * i + j
                results[i].append(Share(runtime, GF256, GF256(b)))
                expected_results[i].append(S[b])

        aes.byte_sub(results)
        self.verify(runtime, results, expected_results)

    @protocol
    def test_byte_sub_with_masking(self, runtime):
        self._test_byte_sub(runtime, AES(runtime, 128, 
                                         use_exponentiation=False))

    @protocol
    def test_byte_sub_with_exponentiation(self, runtime):
        self._test_byte_sub(runtime, AES(runtime, 128, 
                                         use_exponentiation=True))

    @protocol
    def test_key_expansion(self, runtime):
        aes = AES(runtime, 256)
        key = []
        ascii_key = []

        for i in xrange(8):
            key.append([])

            for j in xrange(4):
                b = 15 * i + j
                key[i].append(Share(runtime, GF256, GF256(b)))
                ascii_key.append(chr(b))

        result = aes.key_expansion(key)

        r = rijndael(ascii_key)
        expected_result = []

        for round_key in r.Ke:
            for word in round_key:
                split_word = []
                expected_result.append(split_word)

                for j in xrange(4):
                    split_word.insert(0, word % 256)
                    word /= 256

        self.verify(runtime, result, expected_result)

    @protocol
    def test_encrypt(self, runtime):
        cleartext = "Encrypt this!!!!"
        key = "Supposed to be secret!?!"

        aes = AES(runtime, 192)
        r = rijndael(key)

        result = aes.encrypt(cleartext, key)
        expected = [ord(c) for c in r.encrypt(cleartext)]

        return self.verify(runtime, [result], [expected])
