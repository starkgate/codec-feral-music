#!/usr/bin/python
#
# Copyright 2021 Josselin Stark
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import binascii
import os

import argparse

parser = argparse.ArgumentParser(
    description='Codec for RTW:RE music dat and idx files')
parser.add_argument('--rebuild', action='store_true', help='create idx and dat files')
parser.add_argument('--extract', action='store_true', help='extract music')
parser.add_argument('--input', type=str, required=True, help='folder where input data is located')
parser.add_argument('--output', type=str, required=True, help='folder where output data should be created')

args = parser.parse_args()

""" idx grammar
header
53 4E 44 2E 50 41 43 4B # SND.PACK / magic number
04 00 00 00 # ?
2D 00 00 00 # number of tracks
18 00 00 00 # offset of first track in idx (?)
71 FF 23 04 # ?

then list of music file metadata
18 00 00 00 # offset in dat file
A2 BA 09 00 # length in bytes
80 BB 00 00 # frequency of file (hertz)
00 00 00 00 # unknown
02 00 00 00 # channels
0D 00 00 00 # origin of music (?): 0D for RTW, 01 for Feral / remaster-only -> for the options menu perhaps
string # file path and name
00 FF FF FF # end of string

all integers are stored in little endian:
if length in bytes = 0xa2ba0900 and offset in dat file = 0x18000000
=> next file at 0x00 09 ba a2 + 0x00 00 00 18 = 0x 00 09 ba ba
"""

""" dat grammar
header
53 4E 44 2E 50 41 43 4B # SND.PACK / magic number
04 00 00 00 # ?
2D 00 00 00 # number of tracks
18 00 00 00 # offset of first track in dat (?)
71 FF 23 04 # ?

then list of music files
4F 67 67 53 00 02 00 00 00 00 00 00 00 00 # OggS header (?)
opus file # raw opus file
"""

def byte_to_string(b):
    return bytes.fromhex(b.decode("utf-8")).decode('ASCII')

def string_to_byte(s):
    return binascii.hexlify(s.encode('utf-8'))

def int_from_bytes(b):
    return int.from_bytes(binascii.unhexlify(b), byteorder = 'little')

def bytes_from_int(i):
    return binascii.hexlify((i).to_bytes(4, byteorder = 'little'))

def decode(file):

    # Open in binary mode (so you don't read two byte line endings on Windows as one byte)
    # and use with statement (always do this to avoid leaked file descriptors, unflushed files)
    with open(os.path.join(file, 'music.idx.feral'), 'rb') as f:
        # Slurp the whole file and efficiently convert it to hex all at once
        idx_hexdata = binascii.hexlify(f.read())

    with open(os.path.join(file, 'music.dat.feral'), 'rb') as f:
        # Slurp the whole file and efficiently convert it to hex all at once
        dat_hexdata = binascii.hexlify(f.read())

    dat_files = dat_hexdata.split(dat_delimiter)[1:]
    idx_file_names = idx_hexdata.split(idx_delimiter)[:-1] # remove empty last string

    result = {
        'header': {
            'name': idx_file_names[0][:16],
            'unknown': idx_file_names[0][16:24],
            'number_of_files': idx_file_names[0][24:32],
            'number_of_files_int': int_from_bytes(idx_file_names[0][24:32]),
            'unknown2': idx_file_names[0][32:48]
        },
        'files': []
    } # first item contains header
    idx_file_names[0] = idx_file_names[0][48:]

    for file, file_name in zip(dat_files, idx_file_names):
        result['files'] += [
            {
                'offset': file_name[:8],
                #'offset_int': int_from_bytes(file_name[:8]),
                'length': file_name[8:16],
                #'length_int': int_from_bytes(file_name[8:16]),
                'hertz': file_name[16:24],
                #'hertz_int': int_from_bytes(file_name[16:24]),
                'meta': file_name[24:32],
                'channels': file_name[32:40],
                'origin': file_name[40:48],
                'file_name': file_name[48:],
                'file_name_str': byte_to_string(file_name[48:]),
                'file': dat_delimiter + file
            }
        ]
    return result

def encode(dict):
    header = dict['header']['name'] +\
             dict['header']['unknown'] +\
             dict['header']['number_of_files'] +\
             dict['header']['unknown2']

    idx = header
    dat = header
    for f in dict['files']:
        idx += f['offset']
        idx += f['length']
        idx += f['hertz']
        idx += f['meta']
        idx += f['channels']
        idx += f['origin']
        idx += f['file_name']
        idx += idx_delimiter
        dat += f['file']

    return idx, dat

def export_decoded_opus(decoded, output_dir):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    for file in decoded['files']:
        with open(os.path.join(output_dir, os.path.basename(file['file_name_str'])), 'wb') as f:
            f.write(binascii.unhexlify(file['file']))

def import_decoded_opus(folder):
    result = {
        'header': {
            'name': string_to_byte('SND.PACK'),
            'unknown': b'04000000',
            'number_of_files': bytes_from_int(len(os.listdir(folder))),
            'unknown2': b'1800000071ff2304'
        },
        'files': []
    }

    offset = b'18000000' # start at 0x18
    for file in os.listdir(folder): # [os.path.basename(f['file_name_str']) for f in decoded['files']]:
        with open(os.path.join(folder, file), 'rb') as f:
            # Slurp the whole file and efficiently convert it to hex all at once
            opus_binary = binascii.hexlify(f.read())

            if "Feral" in file:
                origin = b'01000000'
                meta = b'08000000'
            else:
                origin = b'0d000000'
                meta = b'00000000'

            length = bytes_from_int(int(len(opus_binary)/2))
            file_name = "data/sounds/music/" + file

            result['files'] += [
                {
                    'offset': offset,
                    'length': length,
                    'hertz': opus_binary[80:88],
                    'meta': meta,
                    'channels': bytes_from_int(int_from_bytes(opus_binary[74:76])),
                    'origin': origin,
                    'file_name': string_to_byte(file_name),
                    'file_name_str': file_name,
                    'file': opus_binary
                }
            ]

            offset = bytes_from_int(int_from_bytes(offset) + int_from_bytes(length))

    return result

def export_encoded_binary(idx, dat, output_dir):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    with open(os.path.join(output_dir, 'music.idx.feral'), 'wb') as f:
        f.write(binascii.unhexlify(idx))
    with open(os.path.join(output_dir, 'music.dat.feral'), 'wb') as f:
        f.write(binascii.unhexlify(dat))

dat_delimiter = b'4f67675300020000000000000000'
idx_delimiter = b'00ffffff'

if args.rebuild:
    # import files from folder
    imported = import_decoded_opus(args.input)
    idx_encoded, dat_encoded = encode(imported)
    export_encoded_binary(idx_encoded, dat_encoded, output_dir=args.output)
elif args.extract:
    # decode dat and idx files
    decoded = decode(args.input)
    # export files from decoded data
    export_decoded_opus(decoded, output_dir=args.output)

else:
    print("Need to choose between rebuild and extract")
