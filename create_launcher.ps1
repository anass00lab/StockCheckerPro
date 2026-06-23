# Stock Checker Pro - Create proper launcher with correct icon
# Run this once from PowerShell inside the StockCheckerPro folder

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$IconPath = Join-Path $AppDir "assets\logo.ico"
$MainScript = Join-Path $AppDir "main.py"
$LauncherPath = Join-Path $AppDir "StockCheckerPro.vbs"
$ShortcutPath = Join-Path $AppDir "Stock Checker Pro.lnk"

# Create a VBScript launcher (runs pythonw so no black window appears)
$vbs = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw.exe """ & "$MainScript" & """", 0, False
"@
$vbs | Out-File -FilePath $LauncherPath -Encoding ASCII

# Create a proper Windows shortcut with the correct icon
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$LauncherPath`""
$Shortcut.WorkingDirectory = $AppDir
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Stock Checker Pro"
$Shortcut.Save()

Write-Host "Launcher created successfully!" -ForegroundColor Green
Write-Host "Shortcut location: $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now:" -ForegroundColor Yellow
Write-Host "  1. Double-click 'Stock Checker Pro.lnk' to open the app" -ForegroundColor White
Write-Host "  2. Right-click it and choose 'Pin to taskbar'" -ForegroundColor White
Write-Host ""
pause
