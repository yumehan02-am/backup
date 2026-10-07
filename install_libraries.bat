@echo off
setlocal
cd /d "%~dp0"

echo Python library installer
echo.

py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
) else (
    python --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=python"
    ) else (
        echo Python is not installed or is not in PATH.
        echo Please install Python first, then run this batch file again.
        pause
        exit /b 1
    )
)

echo Using:
%PYTHON_CMD% --version
echo.

echo Checking pip...
%PYTHON_CMD% -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo pip is not available. Trying to enable pip...
    %PYTHON_CMD% -m ensurepip --upgrade
    if %errorlevel% neq 0 (
        echo Failed to enable pip.
        pause
        exit /b 1
    )
)

echo.
echo Updating pip...
%PYTHON_CMD% -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo Failed to update pip.
    pause
    exit /b 1
)

echo.
if exist requirements.txt (
    echo Installing libraries from requirements.txt...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Failed to install libraries.
        pause
        exit /b 1
    )
    echo Installation completed.
) else (
    echo No requirements.txt was found.
    echo If external libraries are added later, put them in requirements.txt.
    echo requirements.txt was not found. Nothing to install.
)

echo.
pause
