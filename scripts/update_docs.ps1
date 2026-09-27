# Atualização coordenada do pacote de documentação.
#
# O protocolo Farol 2.0 recebe uma fonte explícita e executa aquisição, skill,
# router, manifesto e validação; indexação externa é opt-in.
param(
    [string]$Sources = "",
    [string]$Slug = "fastapi",
    [string]$Output = "",
    [string]$License = "",
    [switch]$IndexRag,
    [switch]$AllowPrivateNetwork
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($Sources) {
    if (-not $Output) { $Output = Join-Path $Root (Join-Path "artifacts" $Slug) }
    $Arguments = @("-m", "docops", "run", $Sources, "--output", $Output, "--slug", $Slug)
    if ($License) { $Arguments += @("--license", $License) }
    if ($IndexRag) { $Arguments += "--index-rag" }
    if ($AllowPrivateNetwork) { $Arguments += "--allow-private-network" }
    Write-Host "== docops :: aquisição + skill + router + RAG =="
    & python @Arguments
    exit $LASTEXITCODE
}

Write-Host "Farol 2.0 requires -Sources <path>. The legacy update_rag.py corpus runner has been removed." -ForegroundColor Yellow
Write-Host "Example: .\scripts\update_docs.ps1 -Sources documents/fixtures/acme-docs -Slug example -License MIT"
exit 2
