@echo off
setlocal
cd /d "%~dp0"
call "%~dp0find_python.bat"
if errorlevel 1 goto failed
"%QQPASS_PYTHON%" -c "import sys, tkinter; assert sys.version_info >= (3,10); r=tkinter.Tk(); r.withdraw(); r.update(); r.destroy()"
if errorlevel 1 goto failed
"%QQPASS_PYTHON%" -m unittest discover -s tests -v
if errorlevel 1 goto failed
"%QQPASS_PYTHON%" -c "import PyInstaller" >nul 2>nul
if not errorlevel 1 goto package
rem Build-only dependency. Application runtime never needs a network connection.
if not exist ".venv-build\Scripts\python.exe" "%QQPASS_PYTHON%" -m venv .venv-build
if errorlevel 1 goto failed
set "QQPASS_PYTHON=%~dp0.venv-build\Scripts\python.exe"
if defined QQPASS_WHEELS (
    "%QQPASS_PYTHON%" -m pip install --no-index --find-links "%QQPASS_WHEELS%" -r requirements-build.txt
) else (
    "%QQPASS_PYTHON%" -m pip install -r requirements-build.txt
)
if errorlevel 1 goto failed
:package
"%QQPASS_PYTHON%" build_exe.py
if errorlevel 1 goto failed
rem Every build gets an isolated real-Tk check of its actual executable.
"%QQPASS_PYTHON%" check_exe.py
if errorlevel 1 goto failed
echo Build complete: dist\QQPassManager.exe
if not defined QQPASS_NO_PAUSE pause
exit /b 0
:failed
echo Build failed. See the error above. No success is implied.
if not defined QQPASS_NO_PAUSE pause
exit /b 1
