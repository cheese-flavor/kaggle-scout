$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python -m PyInstaller --noconfirm --windowed --onedir --name KaggleScout --icon assets/scout.ico --version-file version_info.txt --add-data 'assets;assets' app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Output 'Ready: dist\KaggleScout\KaggleScout.exe'
