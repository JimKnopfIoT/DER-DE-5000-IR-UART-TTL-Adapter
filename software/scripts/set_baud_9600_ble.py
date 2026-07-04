#!/usr/bin/env python3
"""RN4871 Baudrate via BLE Remote Command Mode auf 9600 setzen.

Schreibt $$$ an die RX-Characteristic und lauscht auf der TX-Notify.
Kommt CMD> zurueck -> Remote Command Mode ist aktiv -> SB,09 + R,1.
Kommt nichts -> Remote Command nicht aktiv, geht nur ueber UART (CP2102).

Usage: python3 set_baud_9600_ble.py [MAC]
"""
import asyncio, sys
from bleak import BleakScanner, BleakClient

MAC = sys.argv[1] if len(sys.argv) > 1 else "AA:BB:CC:DD:EE:FF"
UART_SERVICE = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
TX_CHAR = "49535343-1e4d-4bd9-ba61-23c647249616"   # Notify: Modul -> PC
RX_CHAR = "49535343-8841-43f4-a8d4-ecbe34729bb3"   # Write:  PC -> Modul

buf = bytearray()


def on_notify(_h, data):
    buf.extend(data)
    sys.stdout.write(data.decode("ascii", "replace"))
    sys.stdout.flush()


async def send(client, s, wait=1.2):
    """String schreiben, Antwort sammeln, gesammelte Bytes zurueckgeben."""
    mark = len(buf)
    await client.write_gatt_char(RX_CHAR, s.encode(), response=False)
    await asyncio.sleep(wait)
    return bytes(buf[mark:])


async def main():
    print(f"Suche {MAC} ...", flush=True)
    dev = await BleakScanner.find_device_by_address(MAC, timeout=20)
    if not dev:
        print("  Nicht gefunden. Laeuft das Modul / advertised es?")
        return 1
    print("  Gefunden. Verbinde ...", flush=True)

    async with BleakClient(dev, timeout=25) as client:
        print("  Verbunden. Subscribe TX-Notify ...", flush=True)
        await client.start_notify(TX_CHAR, on_notify)
        await asyncio.sleep(0.5)

        print("\n[1] Sende $$$ (Remote Command Entry) ...", flush=True)
        r = await send(client, "$$$", wait=2.0)
        if b"CMD>" not in buf:
            print("\n\n  ✗ Kein CMD> empfangen.", flush=True)
            print("    -> Remote Command Mode ist NICHT aktiv.", flush=True)
            print(f"    Empfangen war: {bytes(buf)!r}", flush=True)
            print("    Baudrate laesst sich nur ueber UART (CP2102) setzen.", flush=True)
            await client.stop_notify(TX_CHAR)
            return 2

        print("\n  ✓ CMD> -> Remote Command aktiv!", flush=True)

        print("\n[2] SB,09 (-> 9600 baud) ...", flush=True)
        await send(client, "SB,09\r", wait=1.2)

        print("\n[3] R,1 (Reboot, Verbindung wird getrennt) ...", flush=True)
        try:
            await send(client, "R,1\r", wait=2.0)
        except Exception as e:
            print(f"  (Disconnect beim Reboot, erwartet: {e})", flush=True)

        print("\n\n  ✓ Befehle gesendet. Modul rebootet jetzt auf 9600 baud.", flush=True)
        print("    Verifiziere danach mit ble_hex_monitor.py auf saubere Frames.", flush=True)
        try:
            await client.stop_notify(TX_CHAR)
        except Exception:
            pass
    return 0


sys.exit(asyncio.run(main()))
