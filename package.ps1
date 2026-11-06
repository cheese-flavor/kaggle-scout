param([string]$Version = '0.7.0')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Use a semantic version such as 0.1.0' }
$scoutExe = Join-Path $PSScriptRoot 'dist\KaggleScout\KaggleScout.exe'
$scoutRuntime = Join-Path $PSScriptRoot 'dist\KaggleScout\_internal'
if (-not (Test-Path -LiteralPath $scoutExe)) { throw 'Run build.ps1 first' }
$scoutStage = Join-Path $PSScriptRoot ('work\package-' + [Guid]::NewGuid().ToString('N'))
$scoutApp = Join-Path $scoutStage 'KaggleScout'
$scoutReleases = Join-Path $PSScriptRoot 'releases'
New-Item -ItemType Directory -Path $scoutApp, $scoutReleases -Force | Out-Null
# Copy an explicit allowlist so credentials, data, and test stores cannot be packaged.
Copy-Item -LiteralPath $scoutExe -Destination $scoutApp
Copy-Item -LiteralPath $scoutRuntime -Destination $scoutApp -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $scoutApp
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'SECURITY.md') -Destination $scoutApp
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install.ps1') -Destination $scoutApp
@'
Kaggle Scout - Windows portable edition

1. Extract the entire ZIP.
2. Run KaggleScout.exe inside the KaggleScout folder.
3. Optional: run install.ps1 to install program files under LocalAppData/Programs.
4. Connect your Kaggle account using your personal API token or kaggle.json.
5. Confirm your profile and save to start collecting competitions.

Keep the _internal folder next to KaggleScout.exe.
This application does not call generative AI APIs.
Credentials are encrypted for the current Windows user; reconnect on a new PC.
Settings and history are stored in LocalAppData/KaggleScout, outside the program folder.
Use KaggleScout.exe --portable only if you want data saved next to the executable.
The app keeps monitoring in the system tray after closing its window.
Use the tray menu to quit completely. Monitoring requires the PC and app to run.
'@ | Set-Content -LiteralPath (Join-Path $scoutApp 'START-HERE.txt') -Encoding utf8
$scoutZip = Join-Path $scoutReleases "KaggleScout-v$Version-windows-x64.zip"
Compress-Archive -LiteralPath $scoutApp -DestinationPath $scoutZip -Force
Get-FileHash -LiteralPath $scoutZip -Algorithm SHA256 | Format-List
Write-Output "Ready: $scoutZip"
