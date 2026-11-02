@echo off
setlocal
cd /d "%~dp0"
if exist "QQPassManager.exe" (
    start "" "%~dp0QQPassManager.exe" %*
    exit /b 0
)
if exist "dist\QQPassManager.exe" (
    start "" "%~dp0dist\QQPassManager.exe" %*
    exit /b 0
)
call "%~dp0find_python.bat"
if errorlevel 1 goto failed
"%QQPASS_PYTHON%" app.py %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Launch failed. See the error above.
if not defined QQPASS_NO_PAUSE pause
exit /b 1
