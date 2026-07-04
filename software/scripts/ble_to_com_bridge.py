#!/usr/bin/env python3
"""
RN4871 BLE → Windows COM-Port Bridge

Verbindet sich mit dem RN4871 über BLE Transparent UART und leitet
empfangene Daten an einen virtuellen COM-Port (com0com) weiter.
Die DER-DE-5000-Software liest die andere Seite des com0com-Paars.

Setup:
  1. Python 3.8+ auf Windows
  2. pip install bleak pyserial
  3. com0com installiert: https://com0com.sourceforge.net/
  4. com0com-Setup: CNCA0 ↔ CNCB0 (entspricht z.B. COM10 ↔ COM11)
     - COM10 = unser Endpoint (Script schreibt hierhin)
     - COM11 = DER-DE-5000-Software-Endpoint (Software liest hier)

Aufruf (Windows-CMD oder PowerShell):
  python ble_to_com_bridge.py
  python ble_to_com_bridge.py --mac AA:BB:CC:DD:EE:FF --com COM10
  python ble_to_com_bridge.py --baud 9600     # COM-Baudrate (an com0com)

Beenden: Ctrl+C
"""

import asyncio
import sys
import time
import argparse
from bleak import BleakScanner, BleakClient
import serial

# Defaults — kann via CLI überschrieben werden
DEFAULT_MAC = "AA:BB:CC:DD:EE:FF"   # Modul-MAC (aus Pair-Sequenz bekannt)
DEFAULT_COM = "COM10"               # com0com Endpoint A
DEFAULT_BAUD = 115200               # baud zum com0com (egal welcher Wert, virtual)
NAME_PREFIX = "RN487"               # falls MAC nicht passt: nach Name suchen

# RN4871 Transparent UART UUIDs
UART_SERVICE = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
TX_CHAR      = "49535343-1e4d-4bd9-ba61-23c647249616"  # Notify: Modul → PC
RX_CHAR      = "49535343-8841-43f4-a8d4-ecbe34729bb3"  # Write:  PC → Modul (optional)


async def find_device(mac):
    print(f"[BLE] Scanne nach Modul {mac} ...", flush=True)
    devices = await BleakScanner.discover(timeout=15)
    for d in devices:
        if d.address.upper() == mac.upper():
            print(f"[BLE] Gefunden: {d.address}  {d.name!r}", flush=True)
            return d
        if d.name and d.name.startswith(NAME_PREFIX):
            print(f"[BLE] Per Name gefunden: {d.address}  {d.name!r}", flush=True)
            return d
    return None


async def bridge_loop(mac, com_port, baud):
    """Endlosschleife mit Auto-Reconnect bei Disconnect."""
    while True:
        ser = None
        try:
            print(f"[COM] Öffne {com_port} (baud={baud}) ...", flush=True)
            ser = serial.Serial(com_port, baud, timeout=0.1, dsrdtr=False, rtscts=False)
            print(f"[COM] {com_port} offen.", flush=True)

            target = await find_device(mac)
            if not target:
                print("[BLE] Modul nicht gefunden, retry in 5s ...", flush=True)
                ser.close()
                await asyncio.sleep(5)
                continue

            print(f"[BLE] Verbinde mit {target.address} ...", flush=True)
            disconnect_event = asyncio.Event()

            def on_disconnect(client):
                print("[BLE] Disconnect erkannt.", flush=True)
                disconnect_event.set()

            async with BleakClient(target, timeout=25, disconnected_callback=on_disconnect) as client:
                print("[BLE] Verbunden, GATT-Discovery ...", flush=True)
                await asyncio.sleep(1)

                # Service-Check
                has_uart = False
                for svc in client.services:
                    if svc.uuid.lower() == UART_SERVICE:
                        has_uart = True
                        break
                if not has_uart:
                    print("[FEHLER] Transparent UART Service fehlt — SS,C0 setzen!", flush=True)
                    return

                rx_bytes_total = 0
                last_log_t = time.time()

                def on_notify(_, data):
                    nonlocal rx_bytes_total, last_log_t
                    try:
                        ser.write(bytes(data))
                        rx_bytes_total += len(data)
                        # Throttled-Log alle 2s
                        if time.time() - last_log_t > 2.0:
                            print(f"[BLE→COM] {rx_bytes_total} Bytes weitergeleitet ({len(data)}B: {bytes(data)[:32]!r})", flush=True)
                            last_log_t = time.time()
                    except Exception as e:
                        print(f"[FEHLER COM-Write]: {e}", flush=True)

                await client.start_notify(TX_CHAR, on_notify)
                print(f"[BLE] Notify auf TX-Char abonniert. Bridge läuft. Strg+C zum Beenden.", flush=True)

                # Optional: COM → BLE (für RX, falls DER-DE-5000-Software etwas senden will)
                async def com_to_ble():
                    while not disconnect_event.is_set():
                        try:
                            n = ser.in_waiting
                            if n > 0:
                                data = ser.read(n)
                                if data:
                                    await client.write_gatt_char(RX_CHAR, data, response=False)
                                    print(f"[COM→BLE] {len(data)}B: {data[:32]!r}", flush=True)
                        except Exception as e:
                            print(f"[FEHLER COM-Read]: {e}", flush=True)
                        await asyncio.sleep(0.05)

                com_task = asyncio.create_task(com_to_ble())

                # Warte auf Disconnect
                await disconnect_event.wait()
                com_task.cancel()
                try:
                    await com_task
                except asyncio.CancelledError:
                    pass

                print("[BLE] Verbindung verloren — Reconnect in 3s ...", flush=True)

        except KeyboardInterrupt:
            print("\n[!] Bridge beendet durch User.", flush=True)
            break
        except Exception as e:
            print(f"[FEHLER] {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(3)
        finally:
            if ser:
                try: ser.close()
                except: pass

        await asyncio.sleep(2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mac", default=DEFAULT_MAC, help=f"RN4871 MAC (default: {DEFAULT_MAC})")
    p.add_argument("--com", default=DEFAULT_COM, help=f"com0com Endpoint A (default: {DEFAULT_COM})")
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"COM-Baudrate (default: {DEFAULT_BAUD})")
    args = p.parse_args()

    print("=" * 60)
    print("RN4871 BLE ↔ COM Bridge")
    print(f"  Modul MAC: {args.mac}")
    print(f"  COM Port:  {args.com} (DER-DE-5000-Software liest den anderen com0com-Endpoint)")
    print(f"  Baudrate:  {args.baud}")
    print("=" * 60)

    try:
        asyncio.run(bridge_loop(args.mac, args.com, args.baud))
    except KeyboardInterrupt:
        print("\n[!] Beendet.")


if __name__ == "__main__":
    main()
