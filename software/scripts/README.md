# RN4871 Scripts — Quick Reference

Alle Scripts brauchen Python 3.8+. Voraussetzung:
```bash
pip install pyserial intelhex bleak
```

Für BB3-Steuerung: Netzteil muss auf `192.0.2.10:5025` (SCPI/TCP) erreichbar sein.

## Flash-Workflow

```bash
# 1. P2_0 auf GND legen + Reset drücken
python3 scripts/bootloader_test.py
# Erwartung: "→ HCI-Event erkannt — Bootloader lebt!" + 21 Bytes saubere Antwort

# 2. Flash (H-Files = bevorzugt, Rehex hat Bug)
python3 scripts/update_slow.py /dev/ttyUSB0 \
  ../RN4870-71_Firmware_1.44/Hex_Files/rn4871_hfiles_combined.hex

# 3. P2_0 von GND trennen + Reset drücken
# 4. BB3 Power Cycle (5 s OFF, dann ON)
```

## Diagnose

```bash
# Live UART + BB3-Strom über 60s
python3 scripts/uart_trace.py 60 > trace.log

# Strom-Schwankung beobachten
python3 scripts/bb3_watch.py 1 30   # CH1, 30 Sekunden

# CP2102 selbst testen (TX↔RX am Adapter brücken)
python3 scripts/uart_loopback.py

# Raw UART monitor (zeigt jeden Byte)
python3 scripts/raw_monitor.py
```

## Konfigurations-Versuche

```bash
# CMD-Mode im 15ms-Fenster nach %REBOOT% — für SS,/SA,/etc.
python3 scripts/cmd_after_reboot.py

# Wenn Modul silent advertised: $$$ mit normalem Guard
python3 scripts/silent_cmd.py
```

## BLE-Tests

```bash
# Aus Hauptverzeichnis
python3 ../rn4871_ble_test.py --scan        # alle Geräte
python3 ../rn4871_ble_test.py AA:BB:CC:DD:EE:FF   # connect + GATT discovery

# Windows-Empfänger (auf Windows-PC laufen lassen)
python scripts/windows_receiver.py
```

## H-Files kombinieren (falls combined.hex nicht da)

```bash
python3 scripts/hfiles_combine.py
# Erzeugt: RN4870-71_Firmware_1.44/Hex_Files/rn4871_hfiles_combined.hex
```

## Sicherheits-Regeln

1. **BB3 CH1 Limit anfangs 30 mA** bei neuem Modul (VDD/GND-Vertauschung sichtbar als Brownout)
2. Wenn OK: Limit auf **100 mA** (BLE-Peaks brauchen mehr als 30 mA)
3. **3.3 V Pflicht**, nicht 3.0 V
4. **Serial port immer** mit `dsrdtr=False, rtscts=False`

## Bekannte Stolperfallen

| Symptom | Ursache | Workaround |
|---|---|---|
| Strom konstant 4 mA, kein Adv | Stuck mode | Hardware-Reset drücken |
| Flash-Sync-Errors | Stromversorgung wackelt oder 3.0 V | 3.3 V + festes Kabel |
| 100 mA bei 1.4 V | VDD/GND vertauscht | Sofort OFF, Verkabelung prüfen |
| Connect-Timeout aus bleak | Modul advertised gerade nicht | Power-Cycle + 10s-Window |
| Phone findet's nicht | TX-Power zu niedrig | `SGA,0` setzen (riskant) oder näher dran |
| Crash-Loop alle ~4s | Pair-Bug in V1.44 H-Files | Bisher keine Lösung |

Vollständige Dokumentation und der Weg dorthin: siehe die **Software**-Sektion in der Haupt-[README](../../README.md) des Repos.

> Hinweis: MAC-Adressen und Netzwerk-Hosts in diesen Scripts sind Platzhalter
> (`AA:BB:CC:DD:EE:FF`, `192.0.2.10`). Eigene Werte per `--mac` bzw. der
> Umgebungsvariable `BB3_HOST` übergeben. Die Microchip-Firmware (V1.44) ist
> aus Lizenzgründen **nicht** enthalten — für die Flash-Scripts selbst besorgen.
