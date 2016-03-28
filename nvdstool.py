#!/usr/bin/env python

"""
QN902x NVDS tool
Copyright (c) 2016 Piotr Dobrowolski

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import serial
import crc16
import struct
import logging
import time
import argparse

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class QNClient(object):
    connect_baudrate = 9600
    baudrate = None
    port = None

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        self.ser = serial.Serial(port)
        self.baudrate = baudrate

    def connect(self, timeout=10):
        """Does handshaking with bootloader"""
        # TODO DTR
        self.ser.close()
        self.ser.baudrate = self.connect_baudrate
        self.ser.timeout = 0.02
        self.ser.open()

        logger.info('Connecting...')

        start_time = time.time()
        while True:
            self.ser.write('\x33')
            resp = self.ser.read(1)

            if resp:
                if resp == '\x01':
                    break
                else:
                    raise Exception('Unexpected response! %r' % resp)

            if timeout > 0 and time.time() - start_time > timeout:
                raise Exception('Timeout')

        logger.info('Connected')

        # This is special, don't touch this
        self.ser.write('\x33')
        self.send_command(0x34, '\x2c\x08\x00\x00')
        self.read_packet()

        self.ser.close()
        self.ser.baudrate = self.baudrate
        self.ser.timeout = 0.5
        self.ser.open()

        self.send_command(0x34, '\x2c\x08\x00\x00')
        self.read_packet()

    @classmethod
    def build_packet(self, cmd, data):
        msg = struct.pack('<bHx', cmd, len(data)) + data
        checksum = crc16.crc16xmodem(msg)
        return '\x71' + msg + struct.pack('<H', checksum)

    def send_command(self, cmd, data):
        logger.debug('Sending %02X command: %r', cmd, data)
        self.ser.write(self.build_packet(cmd, data))
        self.ser.flush()

    def read_packet(self):
        sync = self.ser.read(1)
        if sync != '\x01':
            raise Exception('0x01 expected, got %r' % sync)

        header = self.ser.read(5)

        if not header:
            # No header received
            return None

        startbyte, cmd, data_len = struct.unpack('<cbHx', header)

        if startbyte != '\x71':
            raise Exception('0x71 expected, got %r' % startbyte)

        data = self.ser.read(data_len)

        crc = crc16.crc16xmodem(header[1:] + data)
        if self.ser.read(2) != struct.pack('<H', crc):
            raise Exception('Invalid checksum')

        return data

    def read_nvds(self):
        self.send_command(0x3b, '\x00\x00\x00\x00')
        self.read_packet()

        nvds_data = ''
        for n in range(16):
            self.send_command(0x46, '\x00\x01\x00\x00')
            nvds_data += self.read_packet()

        if nvds_data[:4] != 'NVDS':
            logger.warning('No NVDS header found')

        return nvds_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='NVDS tool for Quintic QN902x BLE SoC'
        )

    parser.add_argument('--port', dest='port', default='/dev/ttyUSB0')
    parser.add_argument('--baudrate', dest='baudrate', default=115200)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-R', '--read', dest='read_fname',
                       help='Read NVDS data to file')
    group.add_argument('-W', '--write', dest='write_fname',
                       help='Write NVDS data from file')

    args = parser.parse_args()

    client = QNClient(args.port, args.baudrate)
    client.connect()

    if args.read_fname:
        with open(args.read_fname, 'w') as fd:
            fd.write(client.read_nvds())
        logger.info('NVDS data saved to %s', args.read_fname)

    elif args.write_fname:
        raise NotImplemented
