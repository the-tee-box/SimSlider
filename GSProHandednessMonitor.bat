@echo off
REM GSPro Handedness Monitor Launcher
REM This launches the Python script in the background

cd /d "%~dp0"
python gspro_monitor.py
pause