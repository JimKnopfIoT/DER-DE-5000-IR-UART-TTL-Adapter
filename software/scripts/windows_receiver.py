#!/usr/bin/env python3
"""
Windows BLE-Empfänger für RN4871 Transparent UART.

Verbindet sich mit dem RN4871-Modul (oder dem zuerst gefundenen),
subscribed die TX-Characteristic und gibt alle empfangenen Daten aus.

Voraussetzungen:
  - Modul ist mit Windows einmal manuell gepaired (Bluetooth-Einstellungen → Gerät hinzufügen).
  - pip install bleak
  - Python 3.8+

Aufruf:
  python windows_receiver.py                  # Sucht RN4870-XXXX
  python windows_receiver.py AA:BB:CC:DD:EE:FF  # Bestimmte MAC
  python windows_receiver.py --raw            # Hex-Ausgabe statt ASCII
"""

import asyncio
import sys
from datetime import datetime
from bleak import BleakClient, BleakScanner

# RN4870/71 Transparent UART UUIDs
UART_SERVICE = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
TX_CHAR      = "49535343-1e4d-4bd9-ba61-23c647249616"   # Modul → PC (Notify)
RX_CHAR      = "49535343-8841-43f4-a8d4-ecbe34729bb3"   # PC → Modul (Write, ungenutzt hier)

NAME_PREFIX  = "RN487"   # findet RN4870-XXXX und RN4871-XXXX


def parse_args():
    mac = None
    raw = False
    for arg in sys.argv[1:]:
        if arg == "--raw":
            raw = True
        elif ":" in arg:
            mac = arg.upper()
    return mac, raw


async def find_device(mac_filter):
    print("Scanne 12 s nach BLE-Geräten...")
    devices = await BleakScanner.discover(timeout=12)
    for d in devices:
        name = (d.name or "")
        match_mac  = mac_filter and d.address.upper() == mac_filter
        match_name = (not mac_filter) and name.startswith(NAME_PREFIX)
        if match_mac or match_name:
            print(f"  ✓ Gefunden: {d.address}  {name!r}")
            return d
    print("  ✗ Keine passenden Geräte gefunden.")
    print("    Tipp: Modul in Windows Bluetooth-Einstellungen pairen.")
    return None


async def run(mac_filter, raw):
    device = await find_device(mac_filter)
    if not device:
        return 1

    print(f"\nVerbinde mit {device.address}...")
    async with BleakClient(device, timeout=20) as client:
        print("Verbunden.")

        # Services prüfen
        has_uart = False
        for svc in client.services:
            if svc.uuid.lower() == UART_SERVICE:
                has_uart = True
                break
        if not has_uart:
            print("FEHLER: Transparent UART Service nicht vorhanden.")
            print("  → Modul mit SS,C0 konfigurieren und Power Cycle machen.")
            return 1

        # Notify-Callback
        def on_tx(_, data: bytearray):
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            if raw:
                hex_str = data.hex(' ').upper()
                print(f"[{ts}] {hex_str}")
            else:
                try:
                    text = bytes(data).decode('ascii', errors='replace')
                    print(f"[{ts}] {text!r}")
                except Exception:
                    print(f"[{ts}] {data!r}")

        await client.start_notify(TX_CHAR, on_tx)
        print(f"\nLausche auf TX-Notifications (UUID {TX_CHAR})")
        print("Strg+C zum Beenden.\n")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nBeenden...")
        finally:
            await client.stop_notify(TX_CHAR)

    return 0


if __name__ == "__main__":
    mac, raw = parse_args()
    try:
        rc = asyncio.run(run(mac, raw))
    except KeyboardInterrupt:
        rc = 0
    sys.exit(rc)
