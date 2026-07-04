@echo off
REM ============================================================
REM  DE-5000 Diagnose: rohe BLE-Frames anzeigen (kein COM-Port)
REM  Zum Pruefen ob saubere 00 0D ... 0D 0A Frames ankommen.
REM ============================================================

set MAC=AA:BB:CC:DD:EE:FF

cd /d "%~dp0"

echo ============================================================
echo  RN4871 BLE Hex-Monitor (Diagnose)
echo  MAC : %MAC%
echo  Erwartet: Frames 00 0D ... 0D 0A  alle ~500 ms
echo  Ctrl-C zum Beenden
echo ============================================================
echo.

python scripts\ble_hex_monitor.py --mac %MAC%

echo.
echo Monitor beendet. Taste druecken zum Schliessen...
pause >nul
