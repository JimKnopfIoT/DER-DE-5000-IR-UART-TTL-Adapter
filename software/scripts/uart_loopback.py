#!/usr/bin/env python3
"""Loopback-Test: TX und RX des CP2102 verbinden, dann starten.
Bei korrekter Verkabelung kommt das Gesendete zurück.
Falls fail → CP2102 selbst hat Problem."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

print('UART-Loopback-Test')
print('==================')
print('Annahme: CP2102 TX <-> RX direkt am Adapter verbunden (Jumper)')
print()

with serial.Serial(PORT, 115200, timeout=0.5, dsrdtr=False, rtscts=False) as s:
    s.reset_input_buffer()
    test = b'Hallo CP2102 Test 12345!\r\n'
    print(f'Sende: {test!r}')
    s.write(test)
    time.sleep(0.2)
    r = s.read(s.in_waiting or 100)
    print(f'Empfangen: {r!r}')
    if r == test:
        print('→ OK! Loopback funktioniert, CP2102 ist gesund.')
    elif test in r:
        print(f'→ Loopback OK + Extra-Bytes: {r}')
    elif len(r) == 0:
        print('→ FAIL: Nichts empfangen. TX-RX nicht verbunden oder Adapter defekt.')
    else:
        print('→ FAIL: Daten gehen verloren oder kommen verfälscht zurück. Adapter-Problem!')
