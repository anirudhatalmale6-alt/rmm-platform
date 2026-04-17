@echo off
REM ==========================================================================
REM RMM Agent Installer for Windows
REM ==========================================================================
REM Usage:  install.bat <api-url> <registration-token>
REM Example: install.bat https://abc123.execute-api.ap-southeast-2.amazonaws.com/prod reg-abc123def456
REM
REM This script:
REM   1. Installs Python dependencies (psutil, pywin32)
REM   2. Registers the agent with the RMM server
REM   3. Installs and starts the Windows service
REM
REM Run as Administrator!
REM ==========================================================================

echo ================================================
echo   RMM Agent Installer
echo ================================================
echo.

REM Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Check arguments
if "%~1"=="" (
    echo Usage: install.bat ^<api-url^> ^<registration-token^>
    echo Example: install.bat https://abc123.execute-api.../prod reg-abc123def456
    pause
    exit /b 1
)
if "%~2"=="" (
    echo Usage: install.bat ^<api-url^> ^<registration-token^>
    pause
    exit /b 1
)

set API_URL=%~1
set REG_TOKEN=%~2
set INSTALL_DIR=C:\ProgramData\RMMAgent\bin
set AGENT_DIR=%~dp0

echo API URL: %API_URL%
echo Token:   %REG_TOKEN:~0,10%...
echo.

REM ---------------------------------------------------------------------------
REM Step 1: Check Python
REM ---------------------------------------------------------------------------

echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo       Python found.
echo.

REM ---------------------------------------------------------------------------
REM Step 2: Install dependencies
REM ---------------------------------------------------------------------------

echo [2/4] Installing dependencies...
pip install psutil pywin32 --quiet
python -m pywin32_postinstall -install >nul 2>&1
echo       Dependencies installed.
echo.

REM ---------------------------------------------------------------------------
REM Step 3: Register agent
REM ---------------------------------------------------------------------------

echo [3/4] Registering agent with RMM server...
cd /d "%AGENT_DIR%"
python agent.py --register --token %REG_TOKEN% --api-url %API_URL%
if %errorlevel% neq 0 (
    echo ERROR: Registration failed. Check the token and API URL.
    pause
    exit /b 1
)
echo       Agent registered successfully.
echo.

REM ---------------------------------------------------------------------------
REM Step 4: Install and start Windows service
REM ---------------------------------------------------------------------------

echo [4/4] Installing Windows service...
cd /d "%AGENT_DIR%"

REM Stop and remove existing service if present
python service.py stop >nul 2>&1
python service.py remove >nul 2>&1

REM Install and start
python service.py install
python service.py start

echo       Service installed and started.
echo.

echo ================================================
echo   INSTALLATION COMPLETE
echo ================================================
echo.
echo   Service Name: RMMAgent
echo   Log Location: C:\ProgramData\RMMAgent\logs\
echo   Config:       C:\ProgramData\RMMAgent\config.json
echo.
echo   To check status:  sc query RMMAgent
echo   To stop:          python service.py stop
echo   To uninstall:     python service.py remove
echo.

pause
