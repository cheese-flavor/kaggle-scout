$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$scoutPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $scoutPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Build environment creation failed' }
}
& $scoutPython -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$scoutPreviousPath = $env:PATH
try {
    # Native tools such as Poppler can expose an incompatible icuuc.dll on PATH.
    # Build with Python and Windows only; Qt uses the Windows system ICU runtime.
    $scoutPythonDir = Split-Path -Parent $scoutPython
    $env:PATH = "$scoutPythonDir;$env:SystemRoot\System32;$env:SystemRoot"
    & $scoutPython -m PyInstaller --clean --noconfirm --windowed --onedir --name KaggleScout --icon assets/scout.ico --version-file version_info.txt --add-data 'assets;assets' --workpath work/build app.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
} finally {
    $env:PATH = $scoutPreviousPath
}
Write-Output 'Ready: dist\KaggleScout\KaggleScout.exe'
