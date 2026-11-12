# Installazione automatica di stampa-mcp su Windows.
# Uso (PowerShell):  irm https://raw.githubusercontent.com/stricchi79-source/meteo/ccr-13173981-rfc8hu/stampa-mcp/installa.ps1 | iex

$ErrorActionPreference = 'Stop'
$Ramo = 'ccr-13173981-rfc8hu'
$Dest = Join-Path $env:USERPROFILE 'stampa-mcp'

function Passo($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function AggiornaPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}
function TrovaPython {
    foreach ($c in 'python', 'py') {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { return $cmd.Source }
    }
    return $null
}

Passo 'Python'
$py = TrovaPython
if (-not $py) {
    Write-Host 'Installo Python 3.12...'
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    AggiornaPath
    $py = TrovaPython
    if (-not $py) { throw 'Python non trovato dopo l''installazione: chiudi e riapri PowerShell e rilancia il comando.' }
}
Write-Host "Python: $py"

Passo 'SumatraPDF (per stampare i PDF)'
$sumatra = @("$env:LOCALAPPDATA\SumatraPDF\SumatraPDF.exe", 'C:\Program Files\SumatraPDF\SumatraPDF.exe') |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $sumatra) {
    winget install -e --id SumatraPDF.SumatraPDF --silent --accept-package-agreements --accept-source-agreements
} else { Write-Host 'Gia'' installato.' }

Passo "Scarico stampa-mcp in $Dest"
$zip = Join-Path $env:TEMP 'stampa-mcp.zip'
$tmp = Join-Path $env:TEMP 'stampa-mcp-estratto'
Invoke-WebRequest "https://github.com/stricchi79-source/meteo/archive/refs/heads/$Ramo.zip" -OutFile $zip -UseBasicParsing
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $zip $tmp
New-Item -ItemType Directory -Force $Dest | Out-Null
Copy-Item (Join-Path $tmp "meteo-$Ramo\stampa-mcp\*") $Dest -Recurse -Force
Copy-Item (Join-Path $tmp "meteo-$Ramo\stampa-mcp\.mcp.json") $Dest -Force
Remove-Item $zip, $tmp -Recurse -Force

# .mcp.json con il percorso completo di Python (piu' affidabile del semplice "python")
$cfg = @{ mcpServers = @{ stampante = @{ command = $py; args = @('server.py') } } }
$cfg | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Dest '.mcp.json') -Encoding UTF8

Passo 'Dipendenze Python'
& $py -m pip install --upgrade --quiet -r (Join-Path $Dest 'requirements.txt')

Passo 'Claude Code'
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    AggiornaPath
    $env:Path += ";$env:USERPROFILE\.local\bin"
} else { Write-Host 'Gia'' installato.' }

Passo 'Stampanti trovate'
Get-CimInstance Win32_Printer | ForEach-Object {
    $_.Name + $(if ($_.Default) { '   (predefinita)' } else { '' })
}
$m28 = Get-CimInstance Win32_Printer | Where-Object Name -like '*M28*' | Select-Object -First 1
if ($m28) {
    $porta = Get-PrinterPort -Name $m28.PortName -ErrorAction SilentlyContinue
    $ip = if ($porta.PrinterHostAddress) { $porta.PrinterHostAddress } else { $porta.PrinterHostIP }
    Write-Host "`nHP M28 trovata: $($m28.Name)" -ForegroundColor Green
    if ($ip) { Write-Host "Indirizzo IP: $ip" } else {
        Write-Host 'IP non ricavabile dalla porta (WSD): per il livello toner leggi l''IP in HP Smart e mettilo in .mcp.json (vedi README).' -ForegroundColor Yellow
    }
} else {
    Write-Host "`nNessuna stampante 'M28' trovata in Windows: aggiungila da Impostazioni > Stampanti e scanner." -ForegroundColor Yellow
}

Passo 'Collegamento sul Desktop'
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Stampa da telefono.lnk'
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = Join-Path $Dest 'avvia-da-telefono.bat'
$s.WorkingDirectory = $Dest
$s.Save()

if ($m28 -and (Read-Host "`nStampo una pagina di prova sulla M28? (s/n)") -eq 's') {
    "Prova stampa-mcp - $(Get-Date)`nSe leggi questo foglio, il PC stampa correttamente." |
        Out-Printer -Name $m28.Name
}

Write-Host "`nFatto!" -ForegroundColor Green
Write-Host '1. Se e'' la prima volta con Claude Code, apri PowerShell e scrivi:  claude   (per fare l''accesso), poi chiudi.'
Write-Host '2. Fai doppio clic su "Stampa da telefono" sul Desktop e lascia la finestra aperta.'
Write-Host '3. Dal telefono: app Claude > Code > la sessione del PC > "stampa un testo di prova".'
