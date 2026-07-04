#!/usr/bin/env python3
"""
BLE Hex-Monitor für Windows — zeigt alle Bytes vom RN4871 als Hex + DE-5000 Decode.

Standalone-Diagnose: keine com0com / DE-6000-Software nötig.
Bridge ggf. vorher stoppen, sonst Connect-Konflikt!

Voraussetzungen:
  pip install bleak

Aufruf (Windows-CMD):
  python ble_hex_monitor.py
  python ble_hex_monitor.py --mac AA:BB:CC:DD:EE:FF
  python ble_hex_monitor.py --pair          # erst koppeln (hilft, wenn Session nie ACTIVE wird)
  python ble_hex_monitor.py --timeout 40 --retries 3
"""

import asyncio
import sys
import time
import argparse
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

DEFAULT_MAC = "AA:BB:CC:DD:EE:FF"
UART_SERVICE = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
TX_CHAR      = "49535343-1e4d-4bd9-ba61-23c647249616"


def parse_de5000(buf):
    """Sucht 17-Byte-Frames mit Header 00 0D / Footer 0D 0A. Returns (frames, rest)."""
    frames = []
    i = 0
    while i + 17 <= len(buf):
        if buf[i] == 0x00 and buf[i+1] == 0x0D and buf[i+15] == 0x0D and buf[i+16] == 0x0A:
            frames.append(buf[i:i+17])
            i += 17
        else:
            i += 1
    # rest: alles ab erstem nicht-Frame-Anfang
    if frames:
        last = i
        return frames, buf[last:]
    # Kein Frame gefunden: behalte buf bis 16 Bytes (Header noch unvollständig)
    return [], buf[max(0, len(buf)-16):]


def decode_de5000(pkt):
    """Dekodiert ein 17-Byte-DE-5000-Frame in lesbare Form."""
    qty = {1:'L', 2:'C', 3:'R', 4:'DC-R', 0:'-'}.get(pkt[5], f'?{pkt[5]}')
    unit_map = {0:'-',1:'Ohm',2:'kOhm',3:'MOhm',5:'uH',6:'mH',7:'H',8:'kH',
                9:'pF',10:'nF',11:'uF',12:'mF',13:'%',14:'°'}
    main_val_raw = pkt[6]*256 + pkt[7]
    main_mul = pkt[8] & 7
    main_unit_code = (pkt[8] >> 3) & 0x1F
    main_unit = unit_map.get(main_unit_code, f'u{main_unit_code}')
    main_disp = pkt[9] & 0x0F
    disp_status = {0:'',1:'BLANK',2:'----',3:'OL',7:'PASS',8:'FAIL'}.get(main_disp, f'd{main_disp}')

    sec_qty = {0:'-',1:'D',2:'Q',3:'ESR',4:'Θ'}.get(pkt[10], f'?{pkt[10]}')
    sec_val_raw = pkt[11]*256 + pkt[12]
    sec_mul = pkt[13] & 7
    sec_unit_code = (pkt[13] >> 3) & 0x1F
    sec_unit = unit_map.get(sec_unit_code, f'u{sec_unit_code}')

    freq_map = {0:'100Hz', 1:'120Hz', 2:'1kHz', 3:'10kHz', 4:'100kHz', 5:'DC'}
    freq = freq_map.get((pkt[3] >> 5) & 7, '?')

    main_val = main_val_raw * (10**-main_mul)
    sec_val = sec_val_raw * (10**-sec_mul)

    flags = pkt[2]
    flag_str = []
    if flags & 0x01: flag_str.append('HOLD')
    if flags & 0x04: flag_str.append('DELTA')
    if flags & 0x20: flag_str.append('LCR-AUTO')
    if flags & 0x40: flag_str.append('AUTORANGE')
    if flags & 0x80: flag_str.append('PARALLEL')

    return (
        f'{qty}={main_val:.4f} {main_unit}'
        + (f' [{disp_status}]' if disp_status else '')
        + f'  {sec_qty}={sec_val:.4f} {sec_unit}'
        + f'  @ {freq}'
        + (f'  Flags={",".join(flag_str)}' if flag_str else '')
    )


async def scan(mac):
    """Sucht das Modul; gibt das Device zurück oder None."""
    target = await BleakScanner.find_device_by_address(mac, timeout=15)
    if target:
        return target
    # nochmal mit detection_callback (manchmal stabiler)
    ev = asyncio.Event()
    found = {}
    def cb(d, _):
        if d.address.upper() == mac.upper() and 'd' not in found:
            found['d'] = d
            ev.set()
    sc = BleakScanner(detection_callback=cb)
    await sc.start()
    try:
        await asyncio.wait_for(ev.wait(), timeout=15)
    except asyncio.TimeoutError:
        return None
    finally:
        await sc.stop()
    return found.get('d')


def hint_session_timeout(mac):
    print('\n' + '=' * 64)
    print('VERBINDUNG FEHLGESCHLAGEN: GATT-Session wurde nicht ACTIVE.')
    print('(Das ist der Abbruch in bleak bei "await event.wait()".)')
    print('Mögliche Ursachen / Abhilfe:')
    print('  1. Ein anderes Tool hält die Verbindung schon:')
    print('     -> ble_to_com_bridge.py, DE-6000/DE-5000-Software, com0com schließen.')
    print('  2. Windows hat das Modul evtl. automatisch verbunden:')
    print('     -> In "Bluetooth & Geräte" das Gerät ENTFERNEN, dann neu starten.')
    print('  3. Windows braucht ein Pairing, um die Verbindung zu halten:')
    print(f'     -> python ble_hex_monitor.py --pair --mac {mac}')
    print('     -> oder in Windows einmal "Gerät hinzufügen" / koppeln.')
    print('  4. Modul kurz stromlos machen (neu booten) und erneut versuchen.')
    print('=' * 64)


async def run_session(target, do_pair, timeout):
    """Ein Verbindungsversuch. Returns Anzahl empfangener Bytes."""
    buf = bytearray()
    rx_total = 0

    async with BleakClient(target, timeout=timeout) as client:
        print('Verbunden.')

        if do_pair:
            try:
                print('Pairing...')
                await client.pair()
                print('Pairing ok.')
            except Exception as e:
                print(f'Pairing fehlgeschlagen (ignoriere): {e}')

        # Prüfen, ob die Transparent-UART-TX-Characteristic überhaupt vorhanden ist
        char = client.services.get_characteristic(TX_CHAR)
        if char is None:
            print('\nWARNUNG: TX-Characteristic nicht gefunden!')
            print(f'  Gesucht: {TX_CHAR}')
            print('  -> Transparent-UART-Service evtl. nicht aktiv (RN4871: "SS,C0" setzen).')
            print('  Vorhandene Characteristics:')
            for s in client.services:
                for c in s.characteristics:
                    print(f'    {c.uuid}  ({",".join(c.properties)})')
            return rx_total

        print('Subscribe TX-Notify... (Ctrl-C zum Beenden)\n')

        def on_notify(_, data):
            nonlocal buf, rx_total
            buf.extend(data)
            rx_total += len(data)
            t = time.strftime('%H:%M:%S')
            # Roh-Hex der eingehenden Notify
            hexstr = ' '.join(f'{b:02X}' for b in data)
            print(f'[{t}] RX {len(data):2d}B: {hexstr}')
            # 17-Byte-Frames suchen
            frames, rest = parse_de5000(bytes(buf))
            for f in frames:
                fhex = ' '.join(f'{b:02X}' for b in f)
                decoded = decode_de5000(f)
                print(f'         FRAME: {fhex}')
                print(f'         →  {decoded}')
            buf = bytearray(rest)

        await client.start_notify(TX_CHAR, on_notify)
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print('\nBeenden...')
        finally:
            try: await client.stop_notify(TX_CHAR)
            except: pass

    return rx_total


async def main(mac, do_pair, timeout, retries):
    print(f'BLE Hex-Monitor — verbindet mit {mac}')
    print('Wartet auf Daten. Ctrl-C zum Beenden.\n')

    target = await scan(mac)
    if not target:
        print('Modul nicht gefunden.')
        print('  -> MAC prüfen (--mac), Modul eingeschaltet/in Reichweite?')
        return

    print(f'Gefunden: {target.address}  {target.name!r}')

    rx_total = 0
    for attempt in range(1, retries + 1):
        try:
            rx_total = await run_session(target, do_pair, timeout)
            break
        except (asyncio.TimeoutError, TimeoutError):
            print(f'[Versuch {attempt}/{retries}] Timeout beim Verbinden.')
            if attempt < retries:
                print('  -> neuer Versuch in 2 s...')
                await asyncio.sleep(2)
            else:
                hint_session_timeout(mac)
        except BleakError as e:
            print(f'[Versuch {attempt}/{retries}] BleakError: {e}')
            if attempt < retries:
                await asyncio.sleep(2)
            else:
                hint_session_timeout(mac)

    print(f'\nGesamt empfangen: {rx_total} Bytes')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mac', default=DEFAULT_MAC)
    p.add_argument('--pair', action='store_true',
                   help='Gerät vor dem Lesen koppeln (hilft, wenn Session nie ACTIVE wird)')
    p.add_argument('--timeout', type=float, default=30,
                   help='Connect-Timeout in Sekunden (Default 30)')
    p.add_argument('--retries', type=int, default=3,
                   help='Anzahl Verbindungsversuche (Default 3)')
    args = p.parse_args()
    try:
        asyncio.run(main(args.mac, args.pair, args.timeout, args.retries))
    except KeyboardInterrupt:
        pass
