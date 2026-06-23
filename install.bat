@echo off
title Stock Checker Pro - Installer
color 0B

echo.
echo  ============================================================
echo   Stock Checker Pro - Installation
echo  ============================================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Python is not installed or not in PATH.
    echo.
    echo  Please install Python 3.11 or later from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

echo  [OK] Python found.

:: Upgrade pip
echo  [..] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install dependencies
echo  [..] Installing required packages (this may take 2-3 minutes)...
pip install customtkinter selenium webdriver-manager gspread google-auth google-auth-oauthlib beautifulsoup4 apscheduler xlsxwriter openpyxl pillow requests lxml cryptography 2>nul

if %errorlevel% neq 0 (
    echo  [!] Some packages failed to install. Trying again...
    pip install customtkinter selenium webdriver-manager gspread google-auth google-auth-oauthlib beautifulsoup4 apscheduler xlsxwriter openpyxl pillow requests lxml cryptography
)

echo  [OK] Packages installed.

:: Create app data directories
echo  [..] Creating app directories...
if not exist "%USERPROFILE%\StockCheckerPro" mkdir "%USERPROFILE%\StockCheckerPro"
if not exist "%USERPROFILE%\StockCheckerPro\config" mkdir "%USERPROFILE%\StockCheckerPro\config"
if not exist "%USERPROFILE%\StockCheckerPro\data" mkdir "%USERPROFILE%\StockCheckerPro\data"
if not exist "%USERPROFILE%\StockCheckerPro\logs" mkdir "%USERPROFILE%\StockCheckerPro\logs"
echo  [OK] Directories created.

:: Create desktop shortcut
echo  [..] Creating desktop shortcut...
set SCRIPT_DIR=%~dp0
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Stock Checker Pro.lnk
set TARGET=%SCRIPT_DIR%run.bat

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Stock Checker Pro'; $s.Save()" 2>nul

echo  [OK] Desktop shortcut created.

:: Create run.bat
echo  [..] Creating launcher...
(
echo @echo off
echo cd /d "%SCRIPT_DIR%"
echo start /b pythonw main.py
) > "%SCRIPT_DIR%run.bat"

echo  [OK] Launcher created.

echo.
echo  ============================================================
echo   Installation Complete!
echo  ============================================================
echo.
echo  A shortcut "Stock Checker Pro" has been added to your Desktop.
echo  Double-click it to launch the app.
echo.
echo  First time setup:
echo  1. Open the app
echo  2. Go to Settings
echo  3. Enter your Marcone credentials
echo  4. Enter your Google Sheet URL
echo  5. Set your schedule in the Scheduler tab
echo.
pause
