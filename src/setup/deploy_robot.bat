@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

:: Check for pyenv-windows (Python Version Manager for Windows)
where /Q pyenv
IF %ERRORLEVEL% NEQ 0 (
    echo pyenv not found, installing...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1' -OutFile '%SCRIPT_DIR%install-pyenv-win.ps1'"
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install-pyenv-win.ps1"
) ELSE (
    echo pyenv OK
)

:: Check for project's Python version

call python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python version not found, installing...
    call pyenv install
) ELSE (
    echo Python version OK
)

:: Check for fnm (Node Version Manager for Windows)
where /Q fnm.exe
IF %ERRORLEVEL% NEQ 0 (
    echo fnm not found, installing...
    winget install -e Schniz.fnm
) ELSE (
    echo fnm OK
)

:: Run the setup script
set PYTHONPATH=src
python -m setup robot

pause