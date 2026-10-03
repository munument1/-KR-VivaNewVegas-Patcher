@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "vnvkr_gui.py"
) else (
  pyw -3 "vnvkr_gui.py"
)
