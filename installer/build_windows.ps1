<#
.SYNOPSIS
    Buduje aplikację PyInstallerem i składa instalator Windows (Inno Setup).

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
    if (-not $SkipDeps) {
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt pyinstaller
    }

    # --collect-all pypdfium2_raw dociąga pdfium.dll (pypdfium2 nie ma hooka do PyInstallera)
    pyinstaller --noconfirm --clean --windowed `
        --name MathListGenerator `
        --icon assets\icon.ico `
        --add-data "DejaVuSans.ttf;." `
        --collect-all pypdfium2_raw `
        main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakończył się błędem" }

    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
        if ($cmd) { $iscc = $cmd.Source }
    }
    if (-not $iscc) {
        throw "Nie znaleziono ISCC.exe. Zainstaluj Inno Setup 6: https://jrsoftware.org/isdl.php"
    }

    & $iscc "/DAppVersion=$Version" "installer\math-list-generator.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup zakończył się błędem" }

    Write-Host "Gotowe: dist\installer\MathListGenerator-$Version-setup.exe"
}
finally {
    Pop-Location
}
