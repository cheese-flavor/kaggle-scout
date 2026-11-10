param([string]$BuildEnvironment = (Join-Path $PSScriptRoot '.venv'))
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$scoutPython = Join-Path $BuildEnvironment 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $scoutPython)) {
    python -m venv $BuildEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Build environment creation failed' }
}
& $scoutPython -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $scoutPython -c 'from installation import backup_legacy_for_build; backup_legacy_for_build()'
if ($LASTEXITCODE -ne 0) { throw 'Legacy data backup failed; refusing to replace build directory' }
$scoutPreviousPath = $env:PATH
try {
    # Native tools such as Poppler can expose an incompatible icuuc.dll on PATH.
    # Build with Python and Windows only; Qt uses the Windows system ICU runtime.
    $scoutPythonDir = Split-Path -Parent $scoutPython
    $env:PATH = "$scoutPythonDir;$env:SystemRoot\System32;$env:SystemRoot"
    & $scoutPython -m PyInstaller --clean --noconfirm --workpath work/build KaggleScout.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
} finally {
    $env:PATH = $scoutPreviousPath
}
& $scoutPython bundle_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
Write-Output 'Ready: dist\KaggleScout\KaggleScout.exe'
