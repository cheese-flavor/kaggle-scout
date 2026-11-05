$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$scoutExe = Join-Path $PSScriptRoot 'dist\KaggleScout\KaggleScout.exe'
$scoutData = Join-Path $PSScriptRoot ('work\smoke-' + [Guid]::NewGuid().ToString('N'))
$scoutOldData = $env:SCOUT_DATA_DIR
try {
    $env:SCOUT_DATA_DIR = $scoutData
    $scoutProcess = Start-Process -FilePath $scoutExe -ArgumentList '--preview', '--smoke' -WindowStyle Hidden -PassThru
    if (-not $scoutProcess.WaitForExit(30000)) {
        $scoutProcess.Kill()
        throw 'Packaged application did not finish its startup check'
    }
    if ($scoutProcess.ExitCode -ne 0) { throw "Packaged application failed: $($scoutProcess.ExitCode)" }
    $scoutScreenshot = Join-Path $PSScriptRoot 'dist\KaggleScout\work\app-smoke.png'
    if (-not (Test-Path -LiteralPath $scoutScreenshot)) { throw 'Startup screenshot was not generated' }
    if ((Get-Item -LiteralPath $scoutScreenshot).LastWriteTime -lt (Get-Date).AddMinutes(-1)) { throw 'Startup screenshot was not refreshed' }
    Write-Output 'PASS: packaged GUI starts, renders, and exits successfully'
} finally {
    $env:SCOUT_DATA_DIR = $scoutOldData
}
