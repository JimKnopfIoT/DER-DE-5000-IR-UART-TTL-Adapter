#!/usr/bin/env python3
"""SS,40 (Transparent UART) setzen — saubere CMD-Session bei stabilem Modul."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

def read_to_cmd(s, timeout=1.0):
    r = b''
    t0 = time.time()
    while time.time() - t0 < timeout:
        x = s.read(1)
        if x: r += x
        if r.endswith(b'CMD>'): break
    return r

with serial.Serial(PORT, 115200, timeout=0.1, dsrdtr=False, rtscts=False) as s:
    s.reset_input_buffer()
    print('Guard time (200ms Stille)...')
    time.sleep(0.2)
    s.reset_input_buffer()

    print('Sende $$$ ...')
    s.write(b'$$$')
    r = read_to_cmd(s, 2.0)
    if b'CMD>' not in r:
        print(f'  Kein CMD> ({r!r})')
        sys.exit(1)
    print('  CMD> ✓')

    print('\nGS (aktueller SS-Wert):')
    s.write(b'GS\r\n')
    print(f'  {read_to_cmd(s).decode("ascii","replace")}')

    print('SS,40 (Transparent UART aktivieren):')
    s.write(b'SS,40\r\n')
    print(f'  {read_to_cmd(s).decode("ascii","replace")}')

    print('SA,0 (kein Pairing, optional):')
    s.write(b'SA,0\r\n')
    print(f'  {read_to_cmd(s).decode("ascii","replace")}')

    print('D (alle Settings):')
    s.write(b'D\r\n')
    print(f'  {read_to_cmd(s, 1.5).decode("ascii","replace")}')

    print('R,1 (Reboot):')
    s.write(b'R,1\r\n')
    r = b''
    t0 = time.time()
    while time.time() - t0 < 3:
        x = s.read(1)
        if x: r += x
        if b'%REBOOT%' in r: break
    print(f'  {r.decode("ascii","replace")}')

    print('\n>>> Power Cycle empfohlen (5s Strom aus) damit GATT-Tabelle neu gebaut wird! <<<')
