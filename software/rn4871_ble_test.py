#!/usr/bin/env python3
"""
RN4871 BLE Transparent UART Test

Verbindet sich via BLE mit dem RN4871, sendet Testdaten und
überprüft ob diese auf dem UART ankommen (und umgekehrt).

Voraussetzung:
  - pip install bleak pyserial
  - Modul im Transparent UART Mode (SS,C0 gesetzt)
  - UART-Adapter an /dev/ttyUSB0

Aufruf:
  python3 rn4871_ble_test.py [MAC_ADRESSE]
"""

import asyncio
import serial
import time
import sys
import threading

# MAC aus BLE-Scan: python3 rn4871_ble_test.py --scan
MAC_DEFAULT = "AA:BB:CC:DD:EE:FF"
PORT        = "/dev/ttyUSB0"

# RN4871 Transparent UART Service UUIDs
UART_SVC = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
UART_TX  = "49535343-1e4d-4bd9-ba61-23c647249616"  # Notify: Modul -> BLE Central
UART_RX  = "49535343-8841-43f4-a8d4-ecbe34729bb3"  # Write:  BLE Central -> Modul


async def scan():
    from bleak import BleakScanner
    print("Scanne 8 Sekunden nach BLE-Geräten...")
    devices = await BleakScanner.discover(timeout=8)
    for d in devices:
        print(f"  {d.address}  {d.name!r}")


async def test(mac):
    from bleak import BleakClient

    ble_received = []

    def on_notify(sender, data):
        print(f"  BLE <- Modul: {data!r}")
        ble_received.append(data)

    print(f"Verbinde mit {mac}...")
    async with BleakClient(mac, timeout=10) as c:
        print("Verbunden! Services:")
        found_uart = False
        for svc in c.services:
            marker = " <-- Transparent UART!" if UART_SVC.lower() == svc.uuid.lower() else ""
            print(f"  {svc.uuid}{marker}")
            if UART_SVC.lower() == svc.uuid.lower():
                found_uart = True
                for ch in svc.characteristics:
                    print(f"    {ch.uuid}  {ch.properties}")

        if not found_uart:
            print("\nFEHLER: Transparent UART Service nicht gefunden!")
            print("  -> SS,C0 konfigurieren mit rn4871_configure.py")
            return

        print("\nTransparent UART gefunden! Starte Test...")
        await c.start_notify(UART_TX, on_notify)

        # Test 1: BLE -> UART
        msg = b"BLE->UART Test\r\n"
        print(f"Sende via BLE: {msg!r}")
        await c.write_gatt_char(UART_RX, msg)
        await asyncio.sleep(1)

        # UART lesen
        with serial.Serial(PORT, 115200, timeout=1) as ser:
            uart_data = ser.read(ser.in_waiting or 64)
            if uart_data:
                print(f"UART empfangen: {uart_data!r}  -> OK!")
            else:
                print("UART: nichts empfangen")

        # Test 2: UART -> BLE
        with serial.Serial(PORT, 115200, timeout=1) as ser:
            msg2 = b"UART->BLE Test\r\n"
            print(f"Sende via UART: {msg2!r}")
            ser.write(msg2)
        await asyncio.sleep(1)

        if ble_received:
            print(f"BLE empfangen: {ble_received}  -> OK!")
        else:
            print("BLE: nichts empfangen (UART->BLE)")

        await c.stop_notify(UART_TX)
        print("\nTest abgeschlossen.")


if __name__ == '__main__':
    if '--scan' in sys.argv:
        asyncio.run(scan())
    else:
        mac = sys.argv[1] if len(sys.argv) > 1 else MAC_DEFAULT
        asyncio.run(test(mac))
