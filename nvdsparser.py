import struct


class NVDSParser(object):
    # TODO read from qnkey_db
    fields = {
        1: ('Device address',),
        2: ('Device name',),
        3: ('Clock drift',),
        4: ('External wake-up time',),
        5: ('Oscillator wake-up time',),
        6: ('Radio wake-up time',),
        7: ('Sleep mode enable',),
        8: ('Factory_Setting_2',),
        9: ('Factory_Setting_3',),
        10: ('Factory_Setting_4',),
        11: ('TK Type',),
        12: ('TK',),
        13: ('IRK',),
        14: ('CSRK',),
        15: ('LTK',),
        16: ('XCSEL',),
        17: ('Temperature offset',),
        18: ('ADC scale',),
        19: ('ADC VCM',),
        }

    def loads(self, data):
        """Returns python dict from NVDS data file. Values are raw data,
        numbers are little-endian, boolean is 0x00/0x01, some strings require
        0x00 ending (eg. Device name), device address is reversed"""

        sig, data = data[:4], data[4:]

        if sig != 'NVDS':
            raise Exception('Missing NVDS signature')

        values = dict()

        while True:
            key, unk1, size = struct.unpack('<BBH', data[:4])
            data = data[4:]

            if key == 0xff and unk1 == 0xff:
                break

            if unk1 != 6:
                raise Exception('unk1: expected 6, got %02x' % unk1)

            value, data = data[:size], data[size:]

            if size % 4 != 0:
                # Remove padding
                data = data[4 - size % 4:]

            values[key] = value

        return values

    def dumps(self, values):
        """Dumps data in the same format as returned by loads to NVDS file.
        In theory dumps(loads(nvds_file)) should be equal to nvds_file"""

        data = 'NVDS'

        for key, value in values.items():
            data += struct.pack('<BBH', key, 6, len(value))
            data += value

            if len(value) % 4 != 0:
                # Add padding
                data += '\xff' * (4 - len(value) % 4)

        data += '\xff' * (4096 - len(data))

        return data

    def describe(self, key):
        """Returns textual description of selected key"""
        return self.fields.get(key, ('Unknown',))[0],

if __name__ == "__main__":
    import pprint

    p = NVDSParser()

    # Simple test
    with open('testfile') as fd:
        data = fd.read()
        parsed = p.loads(data)
        pprint.pprint(parsed)
        print('dumps(loads(data)) == data: %r' % (p.dumps(parsed) == data,))
