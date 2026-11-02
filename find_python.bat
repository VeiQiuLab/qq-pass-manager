@echo off
rem Internal helper. Sets QQPASS_PYTHON without changing the user's environment.
if defined QQPASS_PYTHON (
    if exist "%QQPASS_PYTHON%" exit /b 0
    echo QQPASS_PYTHON does not point to a Python executable.
    exit /b 1
)
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "QQPASS_PYTHON=%%P"
if defined QQPASS_PYTHON exit /b 0
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "QQPASS_PYTHON=%%P"
if defined QQPASS_PYTHON exit /b 0
echo Python 3.10+ with tkinter was not found. Install the official Windows Python, or run the included EXE.
exit /b 1
