@echo off

REM Move to the directory where this batch file is located.
cd /d "%~dp0"

"..\.venv\Scripts\python.exe" app.py

pause