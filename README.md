QN902x tools
============
A set of tools useful when doing stuff around Quintic QN902x BLE SoCs (eg.
QN9021, which is quite popular in random chinese electronics, such as $4 BLE
"tags")

Installation
------------
These tools only require python (only 2.7 tested), `python-serial` (`pyserial`)
and `crc16` package. You can install all requirements by simply issuing:

    pip install -r requirements.txt

qntool
--------
Upload application binary or read / write NVDS data (that includes some basic
configuration values, such as device address and name)

nvdsparser
----------
Python class used for modification of NVDS file (parsing to python dict and
dumping back again to NVDS format). No UI for now

License
-------
MIT, unless stated otherwise
