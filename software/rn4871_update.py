#!/usr/bin/env python3
"""
RN4871 Firmware Update over UART (HCI bootloader protocol)

Voraussetzung:
  - P2_0 auf GND + Reset: Modul im Bootloader-Modus
  - UART-Adapter an TX/RX des Moduls
  - pip install pyserial intelhex

Aufruf:
  python3 rn4871_update.py /dev/ttyUSB0 RN4870-71_Firmware_1.44/Hex_Files/RN487x_V1.44_Rehex_0EF2.HEX
"""

import serial
import struct
import sys
import time
from intelhex import IntelHex

# HCI Pakettypen
CMD_PKT   = 0x01
ACL_PKT   = 0x02
EVENT_PKT = 0x04

CHUNK_SIZE       = 128
FLASH_TOTAL_SIZE = 0x40000
TIMEOUT_S        = 10.0
ERASE_TIMEOUT_S  = 30.0


# ---------------------------------------------------------------------------
# Paket-Builder
# ---------------------------------------------------------------------------

def pkt_connect():
    """HCI Create Connection (opcode 0x0405) mit allen Nullen = Flash-Session."""
    params = bytes(13)  # addr(6) + type(2) + mode(1) + rsvd(1) + offset(2) + role(1)
    return struct.pack('<BHB', CMD_PKT, 0x0405, len(params)) + params


def pkt_disconnect(handle):
    """HCI Disconnect (opcode 0x0406)."""
    params = struct.pack('<HB', 0x0FFF, 0x00)
    return struct.pack('<BHB', CMD_PKT, 0x0406, len(params)) + params


def pkt_erase(handle):
    """ACL Data: Flash Erase (cmd_id 0x0112)."""
    # DATA_PKT body: cmd_id(2)+data_len(2)+mem_type(1)+mem_subtype(1)+addr(4)+size(4) = 14 bytes
    body = struct.pack('<HHBBII', 0x0112, 10, 0x03, 0x00, 0x00000000, 0x00000000)
    return struct.pack('<BHH', ACL_PKT, handle, len(body)) + body


def pkt_write_start(handle, data, total_size):
    """ACL Data: Write-Start mit write_continue-Flag (cmd_id 0x0111)."""
    acl_len = 14 + len(data)
    pgm_data_len = (acl_len - 4) | 0x8000  # bit 15 = write_continue
    body = struct.pack('<HHBBII', 0x0111, pgm_data_len, 0x03, 0x00, 0x00000000, total_size)
    body += data
    return struct.pack('<BHH', ACL_PKT, handle, acl_len) + body


def pkt_write_continue(handle, data, last=False):
    """ACL Data: Write-Continue (cmd_id 0x0001). last=True → kein write_continue-Flag."""
    acl_len = 4 + len(data)
    pgm_data_len = len(data) if last else (len(data) | 0x8000)
    body = struct.pack('<HH', 0x0001, pgm_data_len) + data
    return struct.pack('<BHH', ACL_PKT, handle, acl_len) + body


# ---------------------------------------------------------------------------
# UART-Empfang
# ---------------------------------------------------------------------------

def read_event(ser):
    """Liest ein HCI-Event-Paket (0x04). Gibt (event_code, data_bytes) zurück."""
    ptype = ser.read(1)
    if not ptype:
        raise TimeoutError("Timeout beim Lesen des Pakettyps")
    if ptype[0] != EVENT_PKT:
        raise ValueError(f"Unerwarteter Pakettyp: 0x{ptype[0]:02X} (erwartet EVENT 0x04)")
    event_code = ser.read(1)[0]
    length = ser.read(1)[0]
    data = ser.read(length)
    return event_code, data


def read_acl(ser):
    """Liest ein HCI-ACL-Datenpaket (0x02). Gibt (handle, data_bytes) zurück."""
    ptype = ser.read(1)
    if not ptype:
        raise TimeoutError("Timeout beim Lesen des ACL-Pakettyps")
    if ptype[0] != ACL_PKT:
        raise ValueError(f"Unerwarteter Pakettyp: 0x{ptype[0]:02X} (erwartet ACL 0x02)")
    handle = struct.unpack('<H', ser.read(2))[0]
    length = struct.unpack('<H', ser.read(2))[0]
    data = ser.read(length)
    return handle, data


def read_any(ser):
    """Liest das nächste HCI-Paket. Unbekannte Bytes werden übersprungen."""
    while True:
        ptype = ser.read(1)
        if not ptype:
            raise TimeoutError("Timeout")
        t = ptype[0]
        if t == EVENT_PKT:
            event_code = ser.read(1)[0]
            length = ser.read(1)[0]
            data = ser.read(length)
            return (EVENT_PKT, event_code, data)
        elif t == ACL_PKT:
            handle = struct.unpack('<H', ser.read(2))[0]
            length = struct.unpack('<H', ser.read(2))[0]
            data = ser.read(length)
            return (ACL_PKT, handle, data)
        else:
            print(f"  [sync] unbekanntes Byte 0x{t:02X}, übersprungen")


def wait_for(ser, pkt_type):
    """Wartet auf ein Paket eines bestimmten Typs, ignoriert andere."""
    while True:
        pkt = read_any(ser)
        if pkt[0] == pkt_type:
            return pkt


def check_acl_status(data):
    """Prüft bytes [4:6] im ACL-Response-Payload auf 0x0000."""
    if len(data) < 6:
        raise RuntimeError(f"ACL-Antwort zu kurz: {data.hex()}")
    status = struct.unpack('<H', data[4:6])[0]
    if status != 0x0000:
        raise RuntimeError(f"Fehler in ACL-Antwort: 0x{status:04X}")


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(f"Aufruf: {sys.argv[0]} <serial_port> <hex_datei>")
        print(f"Beispiel: {sys.argv[0]} /dev/ttyUSB0 RN4870-71_Firmware_1.44/Hex_Files/RN487x_V1.44_Rehex_0EF2.HEX")
        sys.exit(1)

    port     = sys.argv[1]
    hex_file = sys.argv[2]

    # Firmware laden
    print(f"Lade Firmware: {hex_file}")
    ih = IntelHex()
    ih.loadhex(hex_file)
    firmware = bytes(ih.tobinarray(size=FLASH_TOTAL_SIZE))
    chunks = [firmware[i:i+CHUNK_SIZE] for i in range(0, len(firmware), CHUNK_SIZE)]
    print(f"Firmware: {len(firmware)} Bytes, {len(chunks)} Chunks à {CHUNK_SIZE} Bytes")

    print(f"\nÖffne Port {port} @ 115200...")
    with serial.Serial(port, 115200, timeout=TIMEOUT_S) as ser:
        time.sleep(0.1)
        ser.reset_input_buffer()

        # 1. Connect
        print("Verbinde mit Bootloader...")
        ser.write(pkt_connect())

        # Erstes Event: Command Status (0x0F), data[0] = 0x00
        pkt = wait_for(ser, EVENT_PKT)
        if pkt[2][0] != 0x00:
            raise RuntimeError(f"Connect Command Status Fehler: 0x{pkt[2][0]:02X}")

        # Zweites Event: Connection Complete (0x03), data[0]=0x00, data[1:3]=handle
        pkt = wait_for(ser, EVENT_PKT)
        if pkt[2][0] != 0x00:
            raise RuntimeError(f"Connection Complete Fehler: 0x{pkt[2][0]:02X}")
        handle = struct.unpack('<H', pkt[2][1:3])[0]
        print(f"Verbunden! Handle: 0x{handle:04X}")

        # 2. Erase
        print("Lösche Flash (kann ~10 Sekunden dauern)...")
        ser.timeout = ERASE_TIMEOUT_S
        ser.write(pkt_erase(handle))

        wait_for(ser, EVENT_PKT)           # Status-Event
        pkt = wait_for(ser, ACL_PKT)       # ACL-Antwort
        check_acl_status(pkt[2])
        ser.timeout = TIMEOUT_S
        print("Flash gelöscht.")
        ser.reset_input_buffer()  # etwaige Rest-Bytes verwerfen

        # 3. Firmware schreiben
        total = len(chunks)
        print(f"Schreibe {total} Chunks...")

        for i, chunk in enumerate(chunks):
            is_last = (i == total - 1)

            if i == 0:
                data_pkt = pkt_write_start(handle, chunk, len(firmware))
            else:
                data_pkt = pkt_write_continue(handle, chunk, last=is_last)

            ser.write(data_pkt)

            wait_for(ser, EVENT_PKT)
            pkt = wait_for(ser, ACL_PKT)
            check_acl_status(pkt[2])

            if (i + 1) % 128 == 0 or is_last:
                pct = (i + 1) / total * 100
                print(f"  {i+1}/{total} ({pct:.0f}%)")

        print("Schreiben abgeschlossen!")

        # 4. Disconnect
        print("Trenne Verbindung...")
        ser.write(pkt_disconnect(handle))
        wait_for(ser, EVENT_PKT)

        print("\nFertig! P2_0 von GND trennen und Modul neu starten.")


if __name__ == '__main__':
    main()
