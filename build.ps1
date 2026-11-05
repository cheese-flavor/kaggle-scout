$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$scoutPython = (Get-Command python).Source
$scoutPreviousPath = $env:PATH
try {
    # Native tools such as Poppler can expose an incompatible icuuc.dll on PATH.
    # Build with Python and Windows only; Qt uses the Windows system ICU runtime.
    $scoutPythonDir = Split-Path -Parent $scoutPython
    $env:PATH = "$scoutPythonDir;$scoutPythonDir\Scripts;$env:SystemRoot\System32;$env:SystemRoot"
    & $scoutPython -m PyInstaller --clean --noconfirm --windowed --onedir --name KaggleScout --icon assets/scout.ico --version-file version_info.txt --add-data 'assets;assets' --workpath work/build app.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
} finally {
    $env:PATH = $scoutPreviousPath
}
Write-Output 'Ready: dist\KaggleScout\KaggleScout.exe'
