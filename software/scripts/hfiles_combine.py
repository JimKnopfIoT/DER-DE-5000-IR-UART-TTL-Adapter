#!/usr/bin/env python3
"""Kombiniert die 4 H-Files (H00-H03) zu einer Hex-Datei."""
import sys, os
from intelhex import IntelHex

HDIR = os.environ.get('RN4871_HEXDIR', 'RN4870-71_Firmware_1.44/Hex_Files')
OUT = os.path.join(HDIR, 'rn4871_hfiles_combined.hex')

combined = IntelHex()
combined.padding = 0xFF
for n, off in enumerate([0x00000, 0x10000, 0x20000, 0x30000]):
    fn = f'{HDIR}/RN487x_V1.44.H0{n}'
    ih = IntelHex()
    ih.loadhex(fn)
    for start, end in ih.segments():
        combined.puts(off + start, bytes(ih.tobinarray(start=start, end=end-1)))
    print(f'Loaded H0{n}: offset 0x{off:05X}')

combined.write_hex_file(OUT)
print(f'\nWritten: {OUT}')
