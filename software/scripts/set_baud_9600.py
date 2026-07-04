#!/usr/bin/env python3
"""RN4871 UART-Baudrate auf 9600 setzen (fuer DE-5000, der 9600 baud sendet).

Lauft ueber die physische UART (CP2102 an RX/TX/GND/+3V3 des Moduls).
Modul-Default ist 115200 -> wir verbinden mit 115200, gehen in CMD-Mode,
setzen SB,09 (Index 09 = 9600) und rebooten. Danach verbindet das Script
zur Kontrolle mit 9600 neu und prueft, ob CMD-Mode wieder erreichbar ist.

WICHTIG: DE-5000 waehrend der Konfiguration NICHT auf den Phototransistor
richten - sonst stoeren IR-Bytes das $$$ am gemeinsamen RX-Pin.

Usage: python3 set_baud_9600.py [/dev/ttyUSB0]
"""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
BAUD_INDEX = '09'          # 09 = 9600 (Tabelle: 03=115200 default ... 09=9600)
OLD_BAUD = 115200
NEW_BAUD = 9600


def read_to_cmd(s, timeout=2.0):
    r = b''
    t0 = time.time()
    while time.time() - t0 < timeout:
        x = s.read(1)
        if x:
            r += x
        if r.endswith(b'CMD>'):
            break
    return r


def enter_cmd(s):
    """Guard-Time, $$$ senden, auf CMD> warten. True bei Erfolg."""
    s.reset_input_buffer()
    time.sleep(0.3)            # Pre-Guard (Stille noetig)
    s.reset_input_buffer()
    s.write(b'$$$')
    r = read_to_cmd(s, 2.0)
    return b'CMD>' in r, r


# --- Schritt 1: mit aktueller Baud (115200) konfigurieren -------------------
print(f'[1] Verbinde mit {OLD_BAUD} baud auf {PORT} ...')
with serial.Serial(PORT, OLD_BAUD, timeout=0.05, dsrdtr=False, rtscts=False) as s:
    ok, r = enter_cmd(s)
    if not ok:
        print(f'    Kein CMD> bei {OLD_BAUD} ({r!r}).')
        print(f'    Vielleicht laeuft das Modul schon auf {NEW_BAUD}? Pruefe mit Schritt 2,')
        print('    oder Reset/Power-Cycle und nochmal. Abbruch.')
        sys.exit(1)
    print('    CMD> ✓')

    s.write(b'GB\r\n')          # aktuelle Baud anzeigen (falls unterstuetzt)
    print(f'    GB (aktuell): {read_to_cmd(s, 1.0).decode("ascii","replace").strip()}')

    print(f'    Sende SB,{BAUD_INDEX} (-> {NEW_BAUD} baud) ...')
    s.write(f'SB,{BAUD_INDEX}\r\n'.encode())
    print(f'    Antwort: {read_to_cmd(s, 1.0).decode("ascii","replace").strip()}')

    print('    R,1 (Reboot) ...')
    s.write(b'R,1\r\n')
    r = b''
    t0 = time.time()
    while time.time() - t0 < 3:
        x = s.read(1)
        if x:
            r += x
        if b'%REBOOT%' in r:
            break
    print(f'    {r.decode("ascii","replace").strip()}')

print('    Warte auf Boot ...')
time.sleep(1.5)

# --- Schritt 2: mit 9600 neu verbinden und verifizieren ---------------------
print(f'[2] Verifiziere: verbinde mit {NEW_BAUD} baud ...')
with serial.Serial(PORT, NEW_BAUD, timeout=0.05, dsrdtr=False, rtscts=False) as s:
    ok, r = enter_cmd(s)
    if ok:
        print(f'    CMD> ✓  -> Modul laeuft jetzt auf {NEW_BAUD} baud. FERTIG.')
        s.write(b'---\r\n')     # CMD-Mode sauber verlassen
        time.sleep(0.2)
        sys.exit(0)
    else:
        print(f'    Kein CMD> bei {NEW_BAUD} ({r!r}).')
        print('    -> Power-Cycle (5s Strom aus) und Script-Schritt 2 nochmal testen,')
        print('       oder pruefen ob SB,09 die richtige Index-Nummer ist.')
        sys.exit(1)
