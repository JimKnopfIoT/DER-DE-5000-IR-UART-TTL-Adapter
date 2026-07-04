@echo off
REM ============================================================
REM  RN4871 Baudrate via BLE auf 9600 setzen (Remote Command).
REM  Voraussetzung: Windows ist mit dem Modul gepairt,
REM  und die Bridge (start-bridge.bat) ist NICHT gleichzeitig offen.
REM ============================================================

set MAC=AA:BB:CC:DD:EE:FF

cd /d "%~dp0"

echo ============================================================
echo  RN4871 Baud -^> 9600 via BLE
echo  MAC : %MAC%
echo  (Bridge vorher schliessen! Nur eine BLE-Verbindung gleichzeitig.)
echo ============================================================
echo.

python scripts\set_baud_9600_ble.py %MAC%

echo.
echo Taste druecken zum Schliessen...
pause >nul
