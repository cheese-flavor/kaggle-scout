param([string]$Version = '0.4.0')
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid version' }
$scoutSource = Join-Path $PSScriptRoot 'dist\KaggleScout'
if (-not (Test-Path -LiteralPath (Join-Path $scoutSource 'KaggleScout.exe'))) {
    # The release ZIP places its executable directly alongside this installer.
    $scoutSource = $PSScriptRoot
}
$scoutExeSource = Join-Path $scoutSource 'KaggleScout.exe'
$scoutRuntime = Join-Path $scoutSource '_internal'
if (-not (Test-Path -LiteralPath $scoutExeSource) -or -not (Test-Path -LiteralPath $scoutRuntime)) { throw 'Build or extract the app first' }
$scoutInstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\KaggleScout'
$scoutInstall = Join-Path $scoutInstallRoot "versions\$Version"
$scoutExe = Join-Path $scoutInstall 'KaggleScout.exe'
$scoutRunning = Get-Process KaggleScout -ErrorAction SilentlyContinue
if ($scoutRunning) { throw 'Quit Kaggle Scout from its tray menu before installing' }
New-Item -ItemType Directory -Force -Path $scoutInstall | Out-Null
# Only program files are copied. Updates never copy a source data directory over user data.
Copy-Item -LiteralPath $scoutExeSource -Destination $scoutExe -Force
Copy-Item -LiteralPath $scoutRuntime -Destination $scoutInstall -Recurse -Force
foreach ($scoutDoc in @('README.md', 'SECURITY.md', 'START-HERE.txt')) {
    $scoutDocSource = Join-Path $PSScriptRoot $scoutDoc
    if (Test-Path -LiteralPath $scoutDocSource) { Copy-Item -LiteralPath $scoutDocSource -Destination $scoutInstall -Force }
}
# For a first installation only, the bundled app safely backs up legacy SQLite data.
$scoutLegacyData = Join-Path $scoutSource 'data'
if (-not (Test-Path -LiteralPath (Join-Path $scoutLegacyData 'scout.sqlite3'))) {
    $scoutBackupRoot = Join-Path $PSScriptRoot 'work\private-data-backups'
    $scoutPointer = Join-Path $scoutBackupRoot 'latest.txt'
    if (Test-Path -LiteralPath $scoutPointer) {
        $scoutCandidate = [IO.Path]::GetFullPath((Get-Content -LiteralPath $scoutPointer -Raw).Trim())
        $scoutAllowedRoot = [IO.Path]::GetFullPath($scoutBackupRoot) + [IO.Path]::DirectorySeparatorChar
        if (-not $scoutCandidate.StartsWith($scoutAllowedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid legacy backup path' }
        $scoutLegacyData = $scoutCandidate
    }
}
if (Test-Path -LiteralPath (Join-Path $scoutLegacyData 'scout.sqlite3')) {
    $scoutMigration = Start-Process -FilePath $scoutExe -ArgumentList @('--migrate-from', ('"' + $scoutLegacyData + '"')) -WindowStyle Hidden -PassThru
    if (-not $scoutMigration.WaitForExit(30000)) { $scoutMigration.Kill(); throw 'Data migration timed out; existing data was retained' }
    if ($scoutMigration.ExitCode -ne 0) { throw 'Data migration failed; existing data was retained' }
}
$scoutShell = New-Object -ComObject WScript.Shell
$scoutDesktop = [Environment]::GetFolderPath('Desktop')
$scoutShortcut = $scoutShell.CreateShortcut((Join-Path $scoutDesktop 'Kaggle Scout.lnk'))
$scoutShortcut.TargetPath = $scoutExe
$scoutShortcut.WorkingDirectory = $scoutInstall
$scoutShortcut.IconLocation = "$scoutExe,0"
$scoutShortcut.Description = 'Kaggle Scout - 개인 맞춤 대회 알림'
$scoutShortcut.Save()
$scoutStartMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Kaggle Scout.lnk'
$scoutMenuShortcut = $scoutShell.CreateShortcut($scoutStartMenu)
$scoutMenuShortcut.TargetPath = $scoutExe
$scoutMenuShortcut.WorkingDirectory = $scoutInstall
$scoutMenuShortcut.IconLocation = "$scoutExe,0"
$scoutMenuShortcut.Save()
# Preserve the user's existing automatic-start preference, updating only our own entry.
$scoutRunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (Get-ItemProperty -LiteralPath $scoutRunKey -Name KaggleScout -ErrorAction SilentlyContinue) {
    Set-ItemProperty -LiteralPath $scoutRunKey -Name KaggleScout -Value ('"' + $scoutExe + '" --background')
}
Write-Output "Installed: $scoutExe"
Write-Output "Data: $(Join-Path $env:LOCALAPPDATA 'KaggleScout')"
