<#
.SYNOPSIS
    Buduje aplikację PyInstallerem i składa instalator Windows (Inno Setup).

.DESCRIPTION
    Uruchamiać na komputerze z Windowsem. Wymagane wcześniej:
      1. Python 3.9+  -> https://www.python.org/downloads/windows/
                         przy instalacji zaznacz "Add python.exe to PATH"
      2. Inno Setup 6 -> winget install -e --id JRSoftware.InnoSetup
                         (albo ręcznie z https://jrsoftware.org/isdl.php)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1

    Wersję bierze z APP_VERSION w main.py.
    Wynik: dist\installer\MathListGenerator-<wersja>-setup.exe

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1 -SkipInstaller

    Sama aplikacja (dist\MathListGenerator\), bez składania instalatora -
    przydatne do szybkiego sprawdzenia buildu bez Inno Setup.
#>
param(
    # Domyślnie brana z APP_VERSION w main.py.
    [string]$Version,
    # Pomija "pip install" - kolejne buildy tej samej wersji idą szybciej.
    [switch]$SkipDeps,
    # Buduje samą aplikację, bez instalatora (nie wymaga Inno Setup).
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

try {
    # --- Wersja: jedyne źródło prawdy to APP_VERSION w main.py ---
    if (-not $Version) {
        $verLine = Select-String -Path "main.py" -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' |
                 Select-Object -First 1
        if (-not $verLine) {
            throw "Nie znalazłem APP_VERSION w main.py - podaj wersję ręcznie przez -Version"
        }
        $Version = $verLine.Matches[0].Groups[1].Value
    }
    if ($Version -notmatch '^\d+\.\d+\.\d+$') {
        throw "Wersja musi mieć postać X.Y.Z, a dostałem: $Version"
    }
    Write-Host "Wersja: $Version"

    # --- Python: najpierw "python", potem launcher "py -3" ---
    if (Get-Command python.exe -ErrorAction SilentlyContinue) {
        $pyExe = "python"
        $pyArgs = @()
    }
    elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $pyExe = "py"
        $pyArgs = @("-3")
    }
    else {
        throw "Nie znaleziono Pythona. Zainstaluj go z https://www.python.org/downloads/windows/ " +
              "i zaznacz opcję 'Add python.exe to PATH'."
    }

    Write-Host "Python: $(& $pyExe @pyArgs --version)"

    if (-not $SkipDeps) {
        Write-Host "`n--- Instalacja zależności ---"
        & $pyExe @pyArgs -m pip install --upgrade pip
        & $pyExe @pyArgs -m pip install -r requirements.txt pyinstaller
        if ($LASTEXITCODE -ne 0) { throw "Instalacja zależności nie powiodła się" }
    }

    # --- Zasoby wersji wkompilowane w .exe (Właściwości -> Szczegóły) ---
    $v = $Version -split '\.'
    $verFile = Join-Path $root "build\file_version_info.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path $verFile) | Out-Null
    $verInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($v[0]), $($v[1]), $($v[2]), 0),
    prodvers=($($v[0]), $($v[1]), $($v[2]), 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '041504E4',
        [StringStruct('CompanyName', 'Szymon Elsner'),
         StringStruct('FileDescription', 'Generator list zadań'),
         StringStruct('FileVersion', '$Version.0'),
         StringStruct('InternalName', 'MathListGenerator'),
         StringStruct('OriginalFilename', 'MathListGenerator.exe'),
         StringStruct('ProductName', 'Math List Generator'),
         StringStruct('ProductVersion', '$Version')])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0415, 1252])])
  ]
)
"@
    # Bez BOM-u - PyInstaller czyta ten plik jako czysty UTF-8.
    [System.IO.File]::WriteAllText($verFile, $verInfo, (New-Object System.Text.UTF8Encoding($false)))

    Write-Host "`n--- Budowanie aplikacji (PyInstaller) ---"
    # --collect-all pypdfium2_raw dociąga pdfium.dll (pypdfium2 nie ma hooka do PyInstallera)
    & $pyExe @pyArgs -m PyInstaller --noconfirm --clean --windowed `
        --name MathListGenerator `
        --icon assets\icon.ico `
        --version-file $verFile `
        --add-data "DejaVuSans.ttf;." `
        --collect-all pypdfium2_raw `
        main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakończył się błędem" }

    # Katalog roboczy PyInstallera zawiera mylącą kopię .exe - sam bootloader, bez
    # python3xx.dll, więc uruchomiony daje "Failed to load Python DLL". Nic z tego
    # nie jest potrzebne (i tak budujemy z --clean), więc kasujemy po udanym buildzie.
    Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue

    if ($SkipInstaller) {
        Write-Host "`nGotowe (sama aplikacja, bez instalatora). Uruchamiaj:" -ForegroundColor Green
        Write-Host "  $(Join-Path $root 'dist\MathListGenerator\MathListGenerator.exe')"
        return
    }

    Write-Host "`n--- Składanie instalatora (Inno Setup) ---"
    # Inno Setup potrafi wylądować w kilku miejscach: instalacja dla wszystkich
    # (Program Files) albo dla użytkownika, np. gdy stawia go winget
    # (%LOCALAPPDATA%\Programs). Najpewniejsze jest to, co zapisał w rejestrze.
    $isccCandidates = @()
    foreach ($key in @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
    )) {
        if (Test-Path $key) {
            $loc = (Get-ItemProperty $key).InstallLocation
            if ($loc) { $isccCandidates += (Join-Path $loc "ISCC.exe") }
        }
    }
    $isccCandidates += @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )

    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
        if ($cmd) { $iscc = $cmd.Source }
    }
    if (-not $iscc) {
        throw "Nie znaleziono ISCC.exe. Zainstaluj Inno Setup 6: winget install -e --id JRSoftware.InnoSetup"
    }
    Write-Host "ISCC: $iscc"

    & $iscc "/DAppVersion=$Version" "installer\math-list-generator.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup zakończył się błędem" }

    $out = Join-Path $root "dist\installer\MathListGenerator-$Version-setup.exe"
    Write-Host "`nGotowy instalator:" -ForegroundColor Green
    Write-Host "  $out"
}
finally {
    Pop-Location
}
