@echo off
cd /d "%~dp0\.."

if exist "F:\anaconda3\python.exe" (
  "F:\anaconda3\python.exe" scripts\dev_dashboard.py
) else (
  python scripts\dev_dashboard.py
)
