#!/usr/bin/env python3
"""Zeigt ALLE Bytes vom Modul (hex + ascii) für 20s."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

with serial.Serial(PORT, 115200, timeout=0.05, dsrdtr=False, rtscts=False) as s:
    s.reset_input_buffer()
    print('Raw-Monitor aktiv — JETZT Reset drücken!\n')
    t0 = time.time()
    reboot_count = 0
    rolling = b''

    while time.time() - t0 < 20:
        chunk = s.read(s.in_waiting or 1)
        if chunk:
            t = time.time() - t0
            for byte in chunk:
                ch = chr(byte) if 32 <= byte < 127 else '.'
                print(f'[t={t:.3f}s] 0x{byte:02X} {ch!r}')
            rolling += chunk
            if len(rolling) > 200:
                rolling = rolling[-100:]
            if b'%REBOOT%' in rolling:
                reboot_count += 1
                print(f'  ^^^ %REBOOT% #{reboot_count}')
                rolling = b''

    print(f'\nFertig. {reboot_count} Reboots in 20s.')
