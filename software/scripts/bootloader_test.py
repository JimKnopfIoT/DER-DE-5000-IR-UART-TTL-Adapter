#!/usr/bin/env python3
"""HCI-Ping zum Bootloader. P2_0 muss auf GND liegen, Reset gedrückt sein."""
import serial, time, struct, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

with serial.Serial(PORT, 115200, timeout=1, dsrdtr=False, rtscts=False) as s:
    s.reset_input_buffer()
    # HCI Create Connection (Opcode 0x0405), 13 byte Nullparameter = Bootloader-Connect
    pkt = struct.pack('<BHB', 0x01, 0x0405, 13) + bytes(13)
    print(f'Sende HCI Connect: {pkt.hex()}')
    s.write(pkt)
    time.sleep(0.5)
    r = s.read(s.in_waiting or 32)
    if r:
        print(f'Antwort ({len(r)} bytes): {r.hex()}')
        if len(r) >= 4 and r[0] == 0x04:
            print('→ HCI-Event erkannt — Bootloader lebt!')
        else:
            print('→ Antwort unklar — eventuell Application Mode')
    else:
        print('→ Keine Antwort. Bootloader/Modul nicht erreichbar.')
