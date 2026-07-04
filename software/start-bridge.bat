@echo off
REM ============================================================
REM  DE-5000  ->  RN4871 BLE  ->  com0com COM-Port  Bridge
REM  Doppelklick zum Starten. Fenster offen lassen waehrend Messung.
REM ============================================================

set MAC=AA:BB:CC:DD:EE:FF
set COM=COM6
set BAUD=9600

cd /d "%~dp0"

echo ============================================================
echo  RN4871 BLE -^> COM-Bridge
echo  MAC : %MAC%
echo  COM : %COM%   (DE-6000 Software auf COM7, 9600 8N1 stellen)
echo  Baud: %BAUD%
echo ============================================================
echo.

python scripts\ble_to_com_bridge.py --mac %MAC% --com %COM% --baud %BAUD%

echo.
echo Bridge beendet. Taste druecken zum Schliessen...
pause >nul
