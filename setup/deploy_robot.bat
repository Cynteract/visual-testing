@echo off

:: Check for python
where /Q python.exe
IF %ERRORLEVEL% NEQ 0 (
    echo python not found, installing...
    winget install -e Python.Python.3.13
) ELSE (
    echo Python found
)

:: Check for fnm (Node Version Manager for Windows)
where /Q fnm.exe
IF %ERRORLEVEL% NEQ 0 (
    echo fnm not found, installing...
    winget install -e Schniz.fnm
) ELSE (
    echo fnm found
)

:: Run the setup script
python -m setup robot

pause