#!/usr/bin/env python3
"""Versucht CMD-Mode im Silent-Zustand (kein Reset, Modul still)."""
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

    # 1s nach UART hören, dann 200ms Guard
    print('1s lauschen (UART sollte still sein)...')
    t0 = time.time()
    pre = b''
    while time.time() - t0 < 1.0:
        x = s.read(s.in_waiting or 1)
        if x: pre += x
    if pre:
        print(f'  UART hat {len(pre)} Bytes geliefert: {pre[:80]!r}')
    else:
        print('  Stille ✓')

    time.sleep(0.2)  # 200ms Guard
    s.reset_input_buffer()

    print('\nSende $$$ ...')
    s.write(b'$$$')

    r = b''
    t0 = time.time()
    while time.time() - t0 < 2.0:
        x = s.read(1)
        if x: r += x
        if b'CMD>' in r: break

    if b'CMD>' in r:
        ms = (time.time() - t0) * 1000
        print(f'  CMD> nach {ms:.0f}ms! Antwort: {r!r}')
        print('\nLese D...')
        s.write(b'D\r\n')
        rd = read_to_cmd(s, 1.0)
        print(f'D -> {rd.decode("ascii","replace")}')

        print('\nLese GS...')
        s.write(b'GS\r\n')
        rg = read_to_cmd(s, 0.5)
        print(f'GS -> {rg.decode("ascii","replace")}')
    else:
        print(f'  Kein CMD> ({r!r}). Modul antwortet nicht auf $$$.')
        print('  → Vermutlich richtig stuck. Reset nötig.')
