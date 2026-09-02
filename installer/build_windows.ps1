<#
.SYNOPSIS
    Buduje aplikację PyInstallerem i składa instalator Windows (Inno Setup).

.DESCRIPTION
    Uruchamiać na komputerze z Windowsem. Wymagane wcześniej:
      1. Python 3.9+  -> https://www.python.org/downloads/windows/
                         przy instalacji zaznacz "Add python.exe to PATH"
      2. Inno Setup 6 -> https://jrsoftware.org/isdl.php

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1 -Version 1.0.0

    Wynik: dist\installer\MathListGenerator-1.0.0-setup.exe
#>
param(
    [string]$Version = "0.0.0",
    [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

try {
    # --- Python: najpierw "python", potem launcher "py -3" ---
    $python = $null
    if (Get-Command python.exe -ErrorAction SilentlyContinue) {
        $python = @("python")
    }
    elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $python = @("py", "-3")
    }
    else {
        throw "Nie znaleziono Pythona. Zainstaluj go z https://www.python.org/downloads/windows/ " +
              "i zaznacz opcję 'Add python.exe to PATH'."
    }

    Write-Host "Python: $(& $python[0] $python[1..($python.Length-1)] --version)"

    if (-not $SkipDeps) {
        Write-Host "`n--- Instalacja zależności ---"
        & $python[0] $python[1..($python.Length-1)] -m pip install --upgrade pip
        & $python[0] $python[1..($python.Length-1)] -m pip install -r requirements.txt pyinstaller
        if ($LASTEXITCODE -ne 0) { throw "Instalacja zależności nie powiodła się" }
    }

    Write-Host "`n--- Budowanie aplikacji (PyInstaller) ---"
    # --collect-all pypdfium2_raw dociąga pdfium.dll (pypdfium2 nie ma hooka do PyInstallera)
    & $python[0] $python[1..($python.Length-1)] -m PyInstaller --noconfirm --clean --windowed `
        --name MathListGenerator `
        --icon assets\icon.ico `
        --add-data "DejaVuSans.ttf;." `
        --collect-all pypdfium2_raw `
        main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakończył się błędem" }

    Write-Host "`n--- Składanie instalatora (Inno Setup) ---"
    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
        if ($cmd) { $iscc = $cmd.Source }
    }
    if (-not $iscc) {
        throw "Nie znaleziono ISCC.exe. Zainstaluj Inno Setup 6 z https://jrsoftware.org/isdl.php"
    }

    & $iscc "/DAppVersion=$Version" "installer\math-list-generator.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup zakończył się błędem" }

    $out = Join-Path $root "dist\installer\MathListGenerator-$Version-setup.exe"
    Write-Host "`nGotowe: $out"
}
finally {
    Pop-Location
}
