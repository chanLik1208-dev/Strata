@echo off
rem Strata's desktop launcher (strata_gui.py): install, start and stop models in a window instead of the console.
rem It uses the Python environment START-HERE.bat makes; before the first install, any Python 3.10+ opens it.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" start "" ".venv\Scripts\pythonw.exe" strata_gui.py & exit /b
where pyw >nul 2>nul && start "" pyw -3 strata_gui.py && exit /b
where pythonw >nul 2>nul && start "" pythonw strata_gui.py && exit /b
echo  Python 3.10 or newer was not found. Double-click START-HERE.bat once (it installs Python), then this again.
pause
