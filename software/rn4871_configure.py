#!/usr/bin/env python3
"""
RN4871 Transparent UART Konfiguration

Strategie (automatisch):
  1. Falls Crash-Loop (wiederholte %REBOOT%): SF,2 im 4s-Fenster senden → stabil
  2. In stabilem Zustand: $$$  → CMD> → SS,C0 → AOK → R,1
  3. Power Cycle danach erforderlich (GATT-Tabelle neu bauen)

Voraussetzung:
  - P2_0 NICHT auf GND (Application Mode)
  - Windows + Linux Bluetooth AUS
  - UART-Adapter an /dev/ttyUSB0

Aufruf:
  python3 rn4871_configure.py [/dev/ttyUSB0]
"""

import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

# Timing-Konstanten (aus User Guide DS50002466C, Abschnitt 1.3 und 2.4.21)
# Guard time: 100ms UART-Stille VOR dem ersten $
GUARD_TIME = 0.15      # 150ms (etwas mehr als das Minimum 100ms)
CMD_WAIT = 0.4         # Wartezeit nach $$$ auf CMD>
CRASH_WINDOW = 0.12    # Delay nach %REBOOT% bevor $$$ gesendet wird


def open_port():
    # dsrdtr=False, rtscts=False: kritisch! Sonst hält DTR das Modul in Reset
    return serial.Serial(PORT, 115200, timeout=0.2, dsrdtr=False, rtscts=False)


def try_enter_cmd(ser):
    """Versucht Command Mode via $$$. Gibt True zurück wenn CMD> empfangen."""
    ser.reset_input_buffer()
    time.sleep(GUARD_TIME)   # 100ms+ Stille VOR $$$
    ser.write(b'$$$')
    time.sleep(CMD_WAIT)
    resp = ser.read(ser.in_waiting or 64)
    print(f"  $$$ -> {resp!r}")
    return b'CMD>' in resp


def send_cmd(ser, cmd, wait=0.4):
    ser.write(cmd if cmd.endswith(b'\r\n') else cmd + b'\r\n')
    time.sleep(wait)
    r = ser.read(ser.in_waiting or 64)
    print(f"  {cmd.decode().strip()} -> {r.decode('ascii','replace').strip()!r}")
    return r


def phase1_stop_crashloop(ser, max_reboots=12):
    """Phase 1: SF,2 im Crash-Loop-Fenster senden um stabilen Zustand zu erreichen."""
    print("\n[Phase 1] Warte auf %REBOOT% (Crash-Loop)...")
    buf = b''
    t0 = time.time()
    reboot_count = 0

    while time.time() - t0 < 60:
        b = ser.read(1)
        if b:
            buf += b
            print(b.decode('ascii', 'replace'), end='', flush=True)
            if len(buf) > 200:
                buf = buf[-100:]

        if b'%REBOOT%' in buf:
            reboot_count += 1
            buf = b''
            print(f"\n  → %REBOOT% #{reboot_count} erkannt, {CRASH_WINDOW*1000:.0f}ms warten...")
            time.sleep(CRASH_WINDOW)
            ser.reset_input_buffer()

            # SF,2 senden (Factory Reset → stoppt Crash-Loop)
            ser.write(b'$$$')
            time.sleep(CMD_WAIT)
            r = ser.read(ser.in_waiting or 64)
            print(f"  $$$ -> {r!r}")

            if b'CMD>' in r:
                print("  CMD> erhalten! Sende SF,2...")
                r2 = send_cmd(ser, b'SF,2', wait=0.3)
                if b'Reboot' in r2 or b'AOK' in r2 or b'REBOOT' in r2.upper():
                    print("  SF,2 OK! Warte auf stabilen Neustart...")
                    # Warte bis Crash-Loop aufhört (~8s)
                    time.sleep(8)
                    return True
                else:
                    print(f"  SF,2 kein Reboot-Token: {r2!r} — warte auf nächsten Versuch")
            else:
                print("  Kein CMD> — nächster Versuch")

        if reboot_count >= max_reboots:
            print(f"  {max_reboots} Reboots ohne SF,2 — Abbruch")
            return False

    print("  Timeout — kein Crash-Loop erkannt")
    return False


def phase2_set_services(ser, max_tries=5):
    """Phase 2: Im stabilen Zustand $$$ senden und SS,C0 setzen."""
    print("\n[Phase 2] Versuche Command Mode für SS,C0...")

    for attempt in range(1, max_tries + 1):
        print(f"  Versuch {attempt}/{max_tries}:")
        if try_enter_cmd(ser):
            print("  CMD> erhalten!")

            # Aktuelle Services lesen
            r = send_cmd(ser, b'GS')
            # SS,C0 setzen (Device Info 0x80 + Transparent UART 0x40 = 0xC0)
            r = send_cmd(ser, b'SS,C0')

            if b'AOK' in r:
                print("  AOK! SS,C0 gesetzt.")
                # Neustart
                r_reboot = send_cmd(ser, b'R,1', wait=1.0)
                print(f"  R,1 -> {r_reboot!r}")
                return True
            else:
                print(f"  Kein AOK: {r!r}")
                send_cmd(ser, b'R,1', wait=1.0)  # trotzdem neu starten
        else:
            print("  Kein CMD>")

        time.sleep(2)

    return False


def check_no_crashloop(ser, observe_secs=6):
    """Beobachtet UART: gibt True zurück wenn kein Crash-Loop (kein %REBOOT%)."""
    print(f"\n[Check] Beobachte UART {observe_secs}s auf Crash-Loop...")
    buf = b''
    t0 = time.time()
    reboot_seen = False
    while time.time() - t0 < observe_secs:
        b = ser.read(1)
        if b:
            buf += b
            print(b.decode('ascii', 'replace'), end='', flush=True)
        if b'%REBOOT%' in buf:
            reboot_seen = True
            buf = b''
    print()
    return not reboot_seen


def main():
    print(f"Öffne {PORT} (dsrdtr=False, rtscts=False)...")
    with open_port() as ser:
        time.sleep(0.3)
        ser.reset_input_buffer()

        # Erst prüfen ob Crash-Loop aktiv ist
        in_stable_state = check_no_crashloop(ser, observe_secs=5)

        if not in_stable_state:
            print("Crash-Loop erkannt → Phase 1: SF,2 senden")
            ok = phase1_stop_crashloop(ser)
            if not ok:
                print("FEHLER: SF,2 konnte nicht gesendet werden.")
                return
        else:
            print("Kein Crash-Loop → direkt zu Phase 2")

        # Phase 2: SS,C0 setzen
        ok = phase2_set_services(ser)

        if ok:
            print("\n" + "="*50)
            print("ERFOLG! Transparent UART konfiguriert.")
            print("Jetzt: Modul vollständig vom Strom trennen (5s),")
            print("       dann einschalten → GATT-Tabelle wird neu gebaut.")
            print("Dann: python3 rn4871_ble_test.py <MAC>")
            print("="*50)
        else:
            print("\nFEHLER: SS,C0 konnte nicht gesetzt werden.")
            print("Mögliche Ursachen:")
            print("  1. Linux/Windows BT ist noch an (auto-connect blockiert $$$)")
            print("  2. P2_0 ist auf GND (Bootloader-Modus)")
            print("  3. Modul nicht erreichbar")


if __name__ == '__main__':
    main()
