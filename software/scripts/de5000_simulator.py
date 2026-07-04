#!/usr/bin/env python3
"""
DER DE-5000 Protokoll-Simulator

Sendet 17-Byte-Pakete im DE-5000-Format an einen UART-Port.
Der UART-Port ist üblicherweise /dev/ttyUSB0 (CP2102 → RN4871).
Über BLE laufen die Pakete dann zu Windows → bridge → COM-Port → DER-DE-5000-Software.

Format (siehe protocol.md):
  Byte 0: 0x00          (Header)
  Byte 1: 0x0D          (Header)
  Byte 2: Flags         (LCR AUTO/Auto-Range/Serial/Parallel...)
  Byte 3: Config        (Test-Frequenz in Bits 5-7)
  Byte 4: Tolerance     (0 = nicht gesetzt)
  Byte 5: Primary qty   (1=L, 2=C, 3=R, 4=DC-R)
  Byte 6-7: Primary val (MSB, LSB)
  Byte 8: Primary info  (Bits 0-2 = Multiplier, Bits 3-7 = Units)
  Byte 9: Primary disp  (0 = normal)
  Byte 10: Secondary qty (0=none, 1=D, 2=Q, 3=ESR, 4=Theta)
  Byte 11-12: Sec val (MSB, LSB)
  Byte 13: Sec info  (Multiplier+Units)
  Byte 14: Sec disp
  Byte 15: 0x0D (Footer)
  Byte 16: 0x0A (Footer)

Aufruf:
  python3 de5000_simulator.py                     # Default: zyklisch Cs/D
  python3 de5000_simulator.py --port /dev/ttyUSB0
  python3 de5000_simulator.py --rate 0.5          # 500ms pro Paket
"""

import argparse
import serial
import struct
import time
import math

# Bauarten / Quantities
QTY_NONE = 0
QTY_INDUCTANCE = 1
QTY_CAPACITANCE = 2
QTY_RESISTANCE = 3
QTY_DC_RESISTANCE = 4

# Secondary qty
SEC_NONE = 0
SEC_D = 1     # Dissipation factor
SEC_Q = 2     # Quality factor
SEC_ESR = 3   # Equivalent series resistance
SEC_THETA = 4 # Phase angle

# Unit codes (für Bits 3-7 in Info-Byte)
UNIT_NONE = 0
UNIT_OHM = 1
UNIT_KOHM = 2
UNIT_MOHM = 3
UNIT_UH = 5
UNIT_MH = 6
UNIT_H = 7
UNIT_KH = 8
UNIT_PF = 9
UNIT_NF = 10
UNIT_UF = 11
UNIT_MF = 12
UNIT_PERCENT = 13
UNIT_DEGREE = 14

# Flags
FLAG_LCR_AUTO = 0x20
FLAG_AUTO_RANGE = 0x40
FLAG_PARALLEL = 0x80

# Frequenz-Codes (Bits 5-7 in Config-Byte)
FREQ_100 = 0
FREQ_120 = 1
FREQ_1K = 2
FREQ_10K = 3
FREQ_100K = 4
FREQ_DC = 5


def encode_measurement(value, unit_code):
    """
    Kodiert einen Messwert in (MSB, LSB, info_byte).
    Wählt HÖCHSTEN passenden Multiplier (10^-mul) für maximale Präzision,
    damit value*10^mul int passt (0-65535).
    """
    if value is None or math.isnan(value) or math.isinf(value):
        return 0x4E, 0x20, (unit_code << 3) | 0

    value = abs(float(value))

    # Höchsten mul finden wo scaled < 65536 noch gilt (bessere Präzision)
    best_mul = 0
    for mul in range(8):
        scaled = value * (10 ** mul)
        if scaled < 65536:
            best_mul = mul
        else:
            break  # alle weiteren überspringen

    int_val = int(round(value * (10 ** best_mul)))
    if int_val >= 65536:
        # Out of range (sollte nicht passieren nach Logik oben)
        return 0x4E, 0x20, (unit_code << 3) | 0
    msb = (int_val >> 8) & 0xFF
    lsb = int_val & 0xFF
    info = ((unit_code & 0x1F) << 3) | (best_mul & 0x07)
    return msb, lsb, info


def make_packet(main_qty, main_val, main_unit,
                sec_qty=SEC_NONE, sec_val=0, sec_unit=UNIT_NONE,
                freq=FREQ_100, flags=FLAG_LCR_AUTO | FLAG_AUTO_RANGE,
                main_overload=False, sec_overload=False,
                parallel=False):
    """Baut ein 17-Byte DE-5000-Paket."""
    pkt = bytearray(17)
    pkt[0] = 0x00
    pkt[1] = 0x0D
    pkt[2] = flags | (FLAG_PARALLEL if parallel else 0)
    pkt[3] = (freq & 0x07) << 5
    pkt[4] = 0  # Tolerance not set

    # Primary
    pkt[5] = main_qty
    m_msb, m_lsb, m_info = encode_measurement(main_val, main_unit)
    pkt[6] = m_msb
    pkt[7] = m_lsb
    pkt[8] = m_info
    pkt[9] = 3 if main_overload else 0   # 3 = OL

    # Secondary
    pkt[10] = sec_qty
    s_msb, s_lsb, s_info = encode_measurement(sec_val, sec_unit)
    pkt[11] = s_msb
    pkt[12] = s_lsb
    pkt[13] = s_info
    pkt[14] = 3 if sec_overload else 0

    pkt[15] = 0x0D
    pkt[16] = 0x0A
    return bytes(pkt)


def fmt_packet(pkt):
    return ' '.join(f'{b:02X}' for b in pkt)


# Test-Szenarien
SCENARIOS = [
    # (description, main_qty, main_val, main_unit, sec_qty, sec_val, sec_unit, freq)
    ("Cs=96.82uF @ 100Hz",  QTY_CAPACITANCE, 96.82, UNIT_UF, SEC_D, 0.0755, UNIT_NONE, FREQ_100),
    ("Cs=96.20uF @ 120Hz",  QTY_CAPACITANCE, 96.20, UNIT_UF, SEC_D, 0.0795, UNIT_NONE, FREQ_120),
    ("Cs=88.06uF @ 1kHz",   QTY_CAPACITANCE, 88.06, UNIT_UF, SEC_D, 0.2567, UNIT_NONE, FREQ_1K),
    ("Cs=78.51uF @ 10kHz",  QTY_CAPACITANCE, 78.51, UNIT_UF, SEC_D, 1.7748, UNIT_NONE, FREQ_10K),
    ("Rs=1.23Ohm @ 100Hz",  QTY_RESISTANCE,  1.23, UNIT_OHM, SEC_NONE, 0, UNIT_NONE, FREQ_100),
    ("Rs=1.10Ohm @ 120Hz",  QTY_RESISTANCE,  1.10, UNIT_OHM, SEC_NONE, 0, UNIT_NONE, FREQ_120),
    ("Ls=4.7mH @ 1kHz",     QTY_INDUCTANCE,  4.7, UNIT_MH, SEC_Q, 12.5, UNIT_NONE, FREQ_1K),
    ("Ls=4.65mH @ 10kHz",   QTY_INDUCTANCE,  4.65, UNIT_MH, SEC_Q, 95.2, UNIT_NONE, FREQ_10K),
]


FREQ_LOOKUP = {100: FREQ_100, 120: FREQ_120, 1000: FREQ_1K, 10000: FREQ_10K, 100000: FREQ_100K}


def auto_cap_unit(value_uf):
    """Wählt automatisch passende Einheit für Kapazitätswert (in µF)."""
    val_f = value_uf * 1e-6
    if val_f < 1e-9:      return value_uf * 1e6, UNIT_PF
    elif val_f < 1e-6:    return value_uf * 1e3, UNIT_NF
    elif val_f < 1e-3:    return value_uf,       UNIT_UF
    else:                  return value_uf / 1e3, UNIT_MF


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/ttyUSB0", help="Serial port (default: /dev/ttyUSB0)")
    p.add_argument("--baud", type=int, default=115200,
                   help="Baud-Rate für Linux-UART zum RN4871 (default: 115200 = RN4871-Default. "
                        "Das DE-5000-Protokoll spec'd 9600, aber Inhalt zählt — Baudrate ist nur Linux↔Modul-Strecke.")
    p.add_argument("--rate", type=float, default=0.5, help="Sekunden zwischen Paketen (default 0.5)")
    p.add_argument("--once", action="store_true", help="Nur einmal alle Szenarien durchlaufen")
    # Single-value Test:
    p.add_argument("--cap", type=float, help="Single Kondensator-Wert in µF (z.B. 9.875)")
    p.add_argument("--ind", type=float, help="Single Induktivität in mH")
    p.add_argument("--res", type=float, help="Single Widerstand in Ohm")
    p.add_argument("--freq", type=int, default=1000, help="Test-Frequenz in Hz (100/120/1000/10000/100000), default 1000")
    p.add_argument("--d", type=float, default=0.05, help="Sekundärwert D (Dissipation Factor), default 0.05")
    args = p.parse_args()

    freq_code = FREQ_LOOKUP.get(args.freq, FREQ_1K)

    # Single-Value Mode?
    single = None
    if args.cap is not None:
        val, unit = auto_cap_unit(args.cap)
        single = ("Cs", QTY_CAPACITANCE, val, unit, SEC_D, args.d, UNIT_NONE, freq_code,
                  f"Cs={args.cap}µF (val={val:.4f}, unit={unit}) @ {args.freq}Hz, D={args.d}")
    elif args.ind is not None:
        single = ("Ls", QTY_INDUCTANCE, args.ind, UNIT_MH, SEC_Q, 10.0, UNIT_NONE, freq_code,
                  f"Ls={args.ind}mH @ {args.freq}Hz")
    elif args.res is not None:
        single = ("Rs", QTY_RESISTANCE, args.res, UNIT_OHM, SEC_NONE, 0, UNIT_NONE, freq_code,
                  f"Rs={args.res}Ω @ {args.freq}Hz")

    print(f"DE-5000 Simulator → {args.port} @ {args.baud} baud, {args.rate}s pro Paket")
    print("Strg+C zum Beenden.\n")

    ser = serial.Serial(args.port, args.baud, timeout=0.5, dsrdtr=False, rtscts=False)

    try:
        cycle = 0
        if single:
            # Endlos den einen Wert senden
            _, mq, mv, mu, sq, sv, su, freq, desc = single
            while True:
                pkt = make_packet(mq, mv, mu, sq, sv, su, freq)
                ser.write(pkt)
                ser.flush()
                print(f"  [{cycle:04d}] {desc} TX: {fmt_packet(pkt)}", flush=True)
                cycle += 1
                time.sleep(args.rate)
        else:
            while True:
                for desc, mq, mv, mu, sq, sv, su, freq in SCENARIOS:
                    pkt = make_packet(mq, mv, mu, sq, sv, su, freq)
                    ser.write(pkt)
                    ser.flush()
                    print(f"  [{cycle:04d}] {desc:30s} TX: {fmt_packet(pkt)}", flush=True)
                    cycle += 1
                    time.sleep(args.rate)
                if args.once:
                    break
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
