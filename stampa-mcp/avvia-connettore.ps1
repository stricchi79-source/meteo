# Avvia il server della stampante come connettore remoto per claude.ai,
# pubblicato su Internet in HTTPS tramite Tailscale Funnel.
# Uso: tasto destro > "Esegui con PowerShell" (oppure: powershell -ExecutionPolicy Bypass -File avvia-connettore.ps1)

Set-StrictMode -Off
$ErrorActionPreference = 'Stop'
$Cartella = $PSScriptRoot
$Porta = 8765

function Ok($t)   { Write-Host $t -ForegroundColor Green }
function Warn($t) { Write-Host $t -ForegroundColor Yellow }

# --- Tailscale -------------------------------------------------------------
$ts = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $ts -and (Test-Path 'C:\Program Files\Tailscale\tailscale.exe')) { $ts = 'C:\Program Files\Tailscale\tailscale.exe' }
if (-not $ts) {
    Write-Host 'Installo Tailscale...'
    winget install -e --id Tailscale.Tailscale --silent --accept-package-agreements --accept-source-agreements
    $ts = 'C:\Program Files\Tailscale\tailscale.exe'
}
$ts = if ($ts -is [string]) { $ts } else { $ts.Source }

$stato = & $ts status --json 2>$null | ConvertFrom-Json
if (-not $stato -or $stato.BackendState -ne 'Running') {
    Warn 'Accedi a Tailscale nella finestra che si apre (account gratuito), poi rilancia questo script.'
    & $ts up
    exit 1
}
$dominio = $stato.Self.DNSName.TrimEnd('.')

# --- Server MCP in modalita' HTTP -------------------------------------------
$py = (Get-Content (Join-Path $Cartella '.mcp.json') -Raw | ConvertFrom-Json).mcpServers.stampante.command
if (-not $py) { $py = 'python' }
& $py -m pip install --quiet --upgrade -r (Join-Path $Cartella 'requirements.txt')

Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath $py -ArgumentList 'server.py', '--http' -WorkingDirectory $Cartella -WindowStyle Minimized
Start-Sleep -Seconds 4
$token = (Get-Content (Join-Path $Cartella 'token.txt') -Raw).Trim()

# --- Funnel (HTTPS pubblico) -------------------------------------------------
Write-Host 'Pubblico su Internet con Tailscale Funnel...'
Write-Host '(la prima volta potrebbe chiederti di aprire un link per abilitare HTTPS e Funnel: fallo e rilancia)'
& $ts funnel --bg $Porta

$url = "https://$dominio/$token/mcp"

# --- Verifica ----------------------------------------------------------------
$init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"verifica","version":"1"}}}'
$h = @{ Accept = 'application/json, text/event-stream' }
try {
    $r = Invoke-WebRequest -Uri $url -Method Post -Body $init -ContentType 'application/json' -Headers $h -UseBasicParsing -TimeoutSec 20
    if ($r.StatusCode -eq 200 -and $r.Content -match 'serverInfo') { Ok 'Verifica: il server risponde in HTTPS come server MCP.' }
    else { Warn "Verifica: risposta inattesa ($($r.StatusCode))." }
} catch { Warn "Verifica non riuscita: $($_.Exception.Message)" }

Write-Host ''
Ok '=== URL del connettore da inserire su claude.ai ==='
Write-Host $url -ForegroundColor White
Set-Clipboard -Value $url
Ok '(copiato negli appunti)'
Write-Host ''
Write-Host 'claude.ai > Impostazioni > Connettori > Aggiungi connettore personalizzato > incolla l''URL.'
Write-Host "File stampabili dal connettore: cartella $env:USERPROFILE\Stampa"
Warn 'Tieni segreto questo URL: chi lo conosce puo'' usare la stampante. Per cambiarlo cancella token.txt e rilancia.'
Write-Host ''
Write-Host 'Per spegnere il connettore:  tailscale funnel reset   e chiudi la finestra Python.'
