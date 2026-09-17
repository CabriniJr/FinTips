# Publica o FinTips no GitHub com a trava de PII antes.
#
#   .\scripts\publicar.ps1 "mensagem do commit"
#
# Faz, nesta ordem: confere PII -> mostra o que vai subir -> commita ->
# rebase com o remoto -> push. Para em qualquer erro.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Mensagem
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Achar-Bash {
    foreach ($c in @("bash", "C:\Program Files\Git\bin\bash.exe", "$env:ProgramFiles\Git\bin\bash.exe")) {
        if (Get-Command $c -ErrorAction SilentlyContinue) { return $c }
        if (Test-Path $c) { return $c }
    }
    return $null
}

Write-Host "`n[1/5] trava de PII" -ForegroundColor Cyan
$bash = Achar-Bash
if ($bash) {
    & $bash "scripts/check-pii.sh" "--all"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nPUSH ABORTADO: dado pessoal nos arquivos do commit." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  bash do Git não encontrado — a trava NÃO rodou." -ForegroundColor Yellow
    $r = Read-Host "  continuar mesmo assim? (s/N)"
    if ($r -ne "s") { exit 1 }
}

Write-Host "`n[2/5] o que vai subir" -ForegroundColor Cyan
git add -A
git status --short
$suspeitos = git diff --cached --name-only | Where-Object {
    $_ -match '^data/|^relatorios/|fintips-salt|^config\.yaml' -or
    ($_ -match '\.ofx$' -and $_ -ne 'tests/fixture.ofx')
}
if ($suspeitos) {
    Write-Host "`nPUSH ABORTADO: estes arquivos não deveriam ser versionados:" -ForegroundColor Red
    $suspeitos | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}

Write-Host "`n[3/5] commit" -ForegroundColor Cyan
if (git diff --cached --quiet) {
    Write-Host "  nada para commitar"
} else {
    git commit -m $Mensagem
}

Write-Host "`n[4/5] rebase com o remoto" -ForegroundColor Cyan
git pull --rebase origin main

Write-Host "`n[5/5] push" -ForegroundColor Cyan
git push -u origin main

Write-Host "`npublicado: https://github.com/CabriniJr/FinTips" -ForegroundColor Green
