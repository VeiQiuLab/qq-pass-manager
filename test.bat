@echo off
setlocal
cd /d "%~dp0"
call "%~dp0find_python.bat"
if errorlevel 1 goto failed
"%QQPASS_PYTHON%" -m unittest discover -s tests -v
if errorlevel 1 goto failed
"%QQPASS_PYTHON%" app.py --self-test --report ".build\checks\source-selftest.json"
if errorlevel 1 goto failed
echo All tests passed.
if not defined QQPASS_NO_PAUSE pause
exit /b 0
:failed
echo Tests failed. See the error above.
if not defined QQPASS_NO_PAUSE pause
exit /b 1
