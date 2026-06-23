@echo off
title Stock Checker Pro - Installer
color 0B

echo.
echo  ============================================================
echo   Stock Checker Pro - Installation
echo  ============================================================
echo.

:: Get the folder where this bat file lives (no trailing backslash)
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

echo  App folder: %APP_DIR%
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
pip install customtkinter selenium webdriver-manager gspread google-auth google-auth-oauthlib beautifulsoup4 apscheduler xlsxwriter openpyxl pillow requests lxml cryptography --quiet

echo  [OK] Packages installed.

:: Create app data directories
echo  [..] Creating app directories...
if not exist "%USERPROFILE%\StockCheckerPro" mkdir "%USERPROFILE%\StockCheckerPro"
if not exist "%USERPROFILE%\StockCheckerPro\config" mkdir "%USERPROFILE%\StockCheckerPro\config"
if not exist "%USERPROFILE%\StockCheckerPro\data" mkdir "%USERPROFILE%\StockCheckerPro\data"
if not exist "%USERPROFILE%\StockCheckerPro\logs" mkdir "%USERPROFILE%\StockCheckerPro\logs"
echo  [OK] Directories created.

:: Create VBS launcher (launches app with no black console window)
echo  [..] Creating launcher...
set "VBS_PATH=%APP_DIR%\StockCheckerPro.vbs"
set "MAIN_PY=%APP_DIR%\main.py"
(
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.Run "pythonw.exe """ ^& "%MAIN_PY%" ^& """", 0, False
) > "%VBS_PATH%"
echo  [OK] Launcher created.

:: Create Desktop shortcut with blue icon
echo  [..] Creating Desktop shortcut...
set "ICON_PATH=%APP_DIR%\assets\logo.ico"
set "DESKTOP=%USERPROFILE%\Desktop"
set "LNK_PATH=%DESKTOP%\Stock Checker Pro.lnk"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%LNK_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\""%VBS_PATH%\"'; $s.WorkingDirectory = '%APP_DIR%'; $s.IconLocation = '%ICON_PATH%'; $s.Description = 'Stock Checker Pro'; $s.Save()"

if exist "%LNK_PATH%" (
    echo  [OK] Desktop shortcut created!
) else (
    echo  [WARN] Shortcut could not be placed on Desktop automatically.
    echo         You can double-click StockCheckerPro.vbs to launch the app.
)

echo.
echo  ============================================================
echo   Installation Complete!
echo  ============================================================
echo.
echo  A shortcut "Stock Checker Pro" has been added to your Desktop.
echo  Double-click it to launch the app.
echo.
echo  To pin to taskbar:
echo    Right-click the Desktop shortcut ^> "Pin to taskbar"
echo.
echo  First time setup:
echo    1. Open the app
echo    2. Go to Settings tab
echo    3. Enter your Marcone credentials
echo    4. Enter your Google Sheet URL
echo    5. Set your schedule in the Scheduler tab
echo.
pause
