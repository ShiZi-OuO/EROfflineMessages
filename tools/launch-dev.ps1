param(
    [ValidateSet('baseline','observer','replay-prototype','world-expansion','world-variant-prototype','native-query-probe','native-region-capture')]
    [string]$Mode = 'replay-prototype',
    [string]$GameDirectory = 'F:\Steam\steamapps\common\ELDEN RING\Game'
)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$gameExecutable = Join-Path $GameDirectory 'eldenring.exe'
$loaderExecutable = Join-Path $GameDirectory 'bin\me3.exe'
$profileFile = Join-Path $projectDirectory "profiles\$Mode.me3"
if (Get-Process eldenring -ErrorAction SilentlyContinue) {
    throw 'Exit the game normally before launching another profile.'
}
if (Get-Process -Name 'EasyAntiCheat*','start_protected_game' -ErrorAction SilentlyContinue) {
    throw 'Anti-cheat is running. Launch refused.'
}
if (!(Test-Path -LiteralPath $loaderExecutable)) { throw 'ME3 executable not found.' }
if (!(Test-Path -LiteralPath $profileFile)) { throw 'Development profile not found.' }
$executableHash = (Get-FileHash -LiteralPath $gameExecutable -Algorithm SHA256).Hash
if ($executableHash -ne 'F9118FEA2CFD8FA3901E8060BFADB1552CB2471771DED8A5B662C4E298FFB328') {
    throw 'This prototype requires the exact verified EXE 2.7.2.0.'
}
# Explicit loader avoids the host's older .me3 association. No existing profile is edited.
& $loaderExecutable launch --game eldenring --exe $gameExecutable --profile $profileFile
exit $LASTEXITCODE
