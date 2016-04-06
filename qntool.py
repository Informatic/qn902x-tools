#!/usr/bin/env python

"""
QN902x programming tool
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QNClient(object):
    connect_baudrate = 9600
    baudrate = None
    clock = None
    port = None

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, clock=16000000):
        self.ser = serial.Serial(port)
        self.baudrate = baudrate
        self.clock = clock

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

        clock_reg = struct.pack('<L', self.calc_div(self.clock, self.baudrate))

        # This is special, don't touch this
        self.send_command(0x34, clock_reg)  # '\x2c\x08\x00\x00')
        self.read_packet(True)

        self.ser.close()
        self.ser.baudrate = self.baudrate
        self.ser.timeout = 0.5
        self.ser.open()
        self.send_command(0x34, clock_reg)
        self.read_packet(True)

    def calc_div(self, clock, baudrate):
        """Calculates UART register value to pass to bootloader"""
        tmp = 16 * baudrate
        inter_div = clock / tmp
        frac_div = ((clock - inter_div * tmp) * 64 + tmp / 2) / tmp
        return (inter_div << 8) + frac_div

    @classmethod
    def build_packet(self, cmd, data):
        msg = struct.pack('<bHx', cmd, len(data)) + data
        checksum = crc16.crc16xmodem(msg)
        return '\x71' + msg + struct.pack('<H', checksum)

    def send_command(self, cmd, data=''):
        logger.debug('Sending %02X command: %r', cmd, data)
        self.ser.write(self.build_packet(cmd, data))
        self.ser.flush()

    def read_packet(self, only_confirm=False):
        sync = self.ser.read(1)
        if sync != '\x01':  # 0x01 == success, 0x02 == failure
            raise Exception('0x01 expected, got %r' % sync)

        if only_confirm:
            return

        self.ser.timeout = 5
        startbyte = self.ser.read(1)

        logger.debug('Got response (%r)', startbyte)

        if not startbyte:
            raise Exception('No start byte received!')

        if startbyte in ('\x03', '\x04'):
            # Single byte response
            # 0x03 == success, 0x04 == failure
            return ord(startbyte)

        header = self.ser.read(4)
        self.ser.timeout = 0.5

        cmd, data_len = struct.unpack('<bHx', header)

        if startbyte != '\x71':
            raise Exception('0x71 expected, got %r' % startbyte)

        data = self.ser.read(data_len)
        logger.debug('Response read - %d bytes', data_len)

        crc = crc16.crc16xmodem(header + data)
        if self.ser.read(2) != struct.pack('<H', crc):
            raise Exception('Invalid checksum')

        return data

    def read_nvds(self):
        self.set_program_address(0)

        nvds_data = ''
        for n in range(16):
            self.send_command(0x46, '\x00\x01\x00\x00')
            nvds_data += self.read_packet()

        try:
            self.validate_nvds(nvds_data)
        except:
            logger.warning('Invalid NVDS data', exc_info=True)

        return nvds_data

    def validate_nvds(self, nvds_data):
        if nvds_data[:4] != 'NVDS':
            raise Exception('Missing NVDS header')

        if len(nvds_data) != 4096:
            raise Exception('Invalid NVDS data length')

    def reboot(self):
        self.send_command(0x4a)
        return self.read_packet(True)

    def set_load_target(self, target):
        """Changes load target, 1 equals flash, 0 equals SRAM"""
        self.send_command(0x39, struct.pack('<L', int(target)))
        return self.read_packet(True)

    def get_bootloader_version(self):
        self.send_command(0x36)
        return self.read_packet()

    def get_chip_id(self):
        self.send_command(0x37)
        return self.read_packet()

    def get_flash_id(self):
        self.send_command(0x38)
        return self.read_packet()

    def program(self, data):
        self.send_command(0x45, data)
        return self.read_packet()

    def set_program_address(self, address):
        self.send_command(0x3b, struct.pack('<L', address))
        return self.read_packet(True)

    def sector_erase(self, sector_count):
        self.send_command(0x42, struct.pack('<L', sector_count))
        return self.read_packet()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Programming tool for Quintic QN902x BLE SoC'
        )

    parser.add_argument('--port', dest='port', default='/dev/ttyUSB0',
                        help='programming port (default: ttyUSB0)')
    parser.add_argument('--baudrate', dest='baudrate', type=int,
                        default=115200,
                        help='connection baudrate (default: 115200)')
    parser.add_argument('--clock', dest='clock', type=int, default=16,
                        help='SoC main clock in MHz (default: 16)')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-R', '--read', dest='read_fname',
                       help='read NVDS data to file')
    group.add_argument('-W', '--write', dest='write_fname',
                       help='write NVDS data from file')
    group.add_argument('-P', '--program', dest='program_fname',
                       help='upload application binary')
    parser.add_argument('-f', '--force', dest='force', action='store_true',
                        help='force write of possibly invalid data')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='show debug information')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    client = QNClient(args.port, args.baudrate, args.clock * 1000000)
    client.connect()

    if args.read_fname:
        with open(args.read_fname, 'w') as fd:
            fd.write(client.read_nvds())
        logger.info('NVDS data saved to %s', args.read_fname)

    elif args.write_fname:
        with open(args.write_fname, 'r') as fd:
            nvds_data = fd.read()

            try:
                client.validate_nvds(nvds_data)
            except:
                logger.warning('Invalid NVDS data', exc_info=True)

                if not args.force:
                    exit(1)

            logger.info('Erasing...')
            client.set_program_address(0)
            client.sector_erase(1)

            client.set_program_address(0)
            for n in range(0, len(nvds_data), 256):
                logger.info('Programming... %.2f%%', 100.0*n/len(nvds_data))
                client.program(nvds_data[n:n+256])

            logger.info('Finished.')

    elif args.program_fname:
        with open(args.program_fname, 'r') as fd:
            program_data = fd.read()
            logger.info('Erasing...')

            # TODO: verification

            client.set_program_address(0x1000)
            client.sector_erase(0x0f)
            client.set_program_address(0x1100)

            # ?
            client.send_command(0x4c, '\x00\x00\x00\x10')
            client.read_packet()

            client.send_command(0x4d, '\xd4\x00\x00\x10')
            client.read_packet()

            for n in range(0, len(program_data), 256):
                logger.info('Programming... %.2f%%', 100.0*n/len(program_data))
                client.program(program_data[n:n+256])

    client.reboot()
