param(
    [switch]$Dev,
    [switch]$Ragflow,
    [switch]$Ocr,
    [switch]$NoFormats,
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BootstrapArgs = @("$Root\scripts\bootstrap.py", "--root", $Root)
if ($Dev) { $BootstrapArgs += "--dev" }
if ($Ragflow) { $BootstrapArgs += "--ragflow" }
if ($Ocr) { $BootstrapArgs += "--ocr" }
if ($NoFormats) { $BootstrapArgs += "--no-formats" }
if ($NoInstall) { $BootstrapArgs += "--no-install" }
& python @BootstrapArgs
exit $LASTEXITCODE
