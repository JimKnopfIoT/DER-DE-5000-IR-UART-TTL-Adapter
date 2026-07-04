#!/usr/bin/env python3
"""$$$ direkt nach %REBOOT% (innerhalb 1s-Fenster bei SR=0x0008)."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

def read_to_cmd(s, timeout=2.0):
    r = b''
    t0 = time.time()
    while time.time() - t0 < timeout:
        x = s.read(1)
        if x: r += x
        if r.endswith(b'CMD>'): break
    return r

with serial.Serial(PORT, 115200, timeout=0.005, dsrdtr=False, rtscts=False) as s:
    s.reset_input_buffer()
    print('Drücke Reset am RN4871 (oder warte auf nächsten %REBOOT%)...')
    buf = b''
    t0 = time.time()

    while time.time() - t0 < 60:
        b = s.read(1)
        if b:
            buf += b
            sys.stdout.write(b.decode('ascii', 'replace'))
            sys.stdout.flush()

        if b'%REBOOT%' in buf:
            print('\n  → %REBOOT% gefunden! Sende $$$ sofort...')
            # 30ms Guard (sollte für Boot-Stille reichen)
            time.sleep(0.05)
            s.reset_input_buffer()
            s.write(b'$$$')
            r = read_to_cmd(s, 1.0)
            if b'CMD>' in r:
                print(f'\n  CMD> ✓ ({r!r})')
                # Konfigurieren
                for cmd in [b'GS', b'SS,40', b'SA,0', b'SR,2000', b'D']:
                    s.write(cmd + b'\r\n')
                    print(f'  {cmd.decode()} -> {read_to_cmd(s, 1.5).decode("ascii","replace")}')
                # Reboot
                s.write(b'R,1\r\n')
                rb = b''
                t1 = time.time()
                while time.time() - t1 < 3:
                    x = s.read(1)
                    if x: rb += x
                    if b'%REBOOT%' in rb: break
                print(f'  R,1 -> {rb.decode("ascii","replace")}')
                print('\n>>> Erfolg! Power Cycle empfohlen damit GATT-Tabelle neu gebaut wird. <<<')
                sys.exit(0)
            else:
                print(f'\n  Kein CMD> ({r!r})')
                buf = b''
                # Versuche bei nächstem %REBOOT%
