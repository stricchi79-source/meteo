"""Server MCP per stampare sulla stampante di casa (Windows).

Gira sul PC collegato alla stampante. Strumenti esposti:
  - elenca_stampanti      stampanti installate, predefinita e stato
  - stampa_file           stampa un file presente sul PC (PDF, TXT, immagini, Office...)
  - stampa_da_url         scarica un file da un link e lo stampa
  - stampa_testo          stampa del testo semplice
  - coda_di_stampa        lavori in coda su una stampante
  - annulla_stampe        svuota la coda di una stampante

Avvio: python server.py   (trasporto stdio, lo lancia Claude in automatico)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stampante")

# Cartella dove salvare i file scaricati da URL.
CARTELLA_DOWNLOAD = Path(
    os.environ.get("STAMPA_CARTELLA", Path(tempfile.gettempdir()) / "stampa-mcp")
)
MAX_DOWNLOAD_MB = 50
COPIE_MAX = 20

ESTENSIONI_TESTO = {".txt", ".log", ".csv", ".md"}


# --------------------------------------------------------------------------- #
# Utilità
# --------------------------------------------------------------------------- #

def _verifica_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError(
            "Questo server funziona solo su Windows (il PC collegato alla stampante)."
        )


def _powershell(script: str, env: dict[str, str] | None = None,
                stdin: str | None = None, timeout: int = 120) -> str:
    """Esegue uno script PowerShell. I valori variabili si passano SOLO via
    variabili d'ambiente ($env:...), mai concatenati nello script, per evitare
    problemi di virgolette e iniezioni di comandi."""
    _verifica_windows()
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    prefisso = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; $ErrorActionPreference = 'Stop'; "
    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", prefisso + script],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        env=full_env, timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip() or "Errore PowerShell")
    return res.stdout.strip()


def _stampante_predefinita() -> str:
    return _powershell(
        "(Get-CimInstance Win32_Printer | Where-Object Default).Name"
    )


def _risolvi_stampante(stampante: str | None) -> str:
    """Restituisce il nome esatto della stampante (accetta anche parte del nome)."""
    if not stampante:
        nome = _stampante_predefinita()
        if not nome:
            raise RuntimeError("Nessuna stampante predefinita impostata su Windows.")
        return nome
    nomi = json.loads(_powershell(
        "@(Get-CimInstance Win32_Printer | ForEach-Object Name) | ConvertTo-Json -Compress"
    ) or "[]")
    if isinstance(nomi, str):
        nomi = [nomi]
    for n in nomi:
        if n.lower() == stampante.lower():
            return n
    candidati = [n for n in nomi if stampante.lower() in n.lower()]
    if len(candidati) == 1:
        return candidati[0]
    if not candidati:
        raise RuntimeError(f"Stampante '{stampante}' non trovata. Disponibili: {nomi}")
    raise RuntimeError(f"'{stampante}' è ambiguo, corrisponde a: {candidati}")


def _trova_sumatra() -> str | None:
    candidati = [
        os.environ.get("SUMATRA_PATH", ""),
        shutil.which("SumatraPDF") or "",
        os.path.expandvars(r"%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe"),
        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
    ]
    for c in candidati:
        if c and os.path.isfile(c):
            return c
    return None


def _stampa(percorso: Path, stampante: str, copie: int,
            fronte_retro: bool, bianco_nero: bool) -> str:
    est = percorso.suffix.lower()
    copie = max(1, min(int(copie), COPIE_MAX))

    if est == ".pdf":
        sumatra = _trova_sumatra()
        if sumatra:
            impostazioni = [f"{copie}x"]
            impostazioni.append("duplexlong" if fronte_retro else "simplex")
            impostazioni.append("monochrome" if bianco_nero else "color")
            subprocess.run(
                [sumatra, "-print-to", stampante,
                 "-print-settings", ",".join(impostazioni),
                 "-silent", "-exit-when-done", str(percorso)],
                check=True, timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return f"Inviato '{percorso.name}' a '{stampante}' ({copie} copie, via SumatraPDF)."

    if est in ESTENSIONI_TESTO:
        for _ in range(copie):
            _powershell(
                "Get-Content -LiteralPath $env:SM_FILE -Encoding UTF8 | Out-Printer -Name $env:SM_PRN",
                env={"SM_FILE": str(percorso), "SM_PRN": stampante},
            )
        return f"Inviato '{percorso.name}' a '{stampante}' ({copie} copie)."

    # Tutto il resto (immagini, Word, Excel, PDF senza SumatraPDF): usa
    # l'applicazione associata al tipo di file con il verbo "PrintTo".
    script = (
        "for ($i = 0; $i -lt [int]$env:SM_COPIE; $i++) { "
        "  $p = Start-Process -FilePath $env:SM_FILE -Verb PrintTo "
        "       -ArgumentList ('\"' + $env:SM_PRN + '\"') -PassThru -WindowStyle Hidden; "
        "  if ($p) { $p | Wait-Process -Timeout 120 -ErrorAction SilentlyContinue } "
        "}"
    )
    try:
        _powershell(script, env={"SM_FILE": str(percorso), "SM_PRN": stampante,
                                 "SM_COPIE": str(copie)}, timeout=300)
    except RuntimeError as e:
        consiglio = (" Per i PDF installa SumatraPDF (gratuito) per una stampa affidabile."
                     if est == ".pdf" else "")
        raise RuntimeError(
            f"Windows non sa stampare i file '{est}' con l'app associata: {e}.{consiglio}"
        ) from e
    nota = " Fronte/retro e bianco/nero non applicati (servono le preferenze della stampante)." \
        if (fronte_retro or bianco_nero) else ""
    return f"Inviato '{percorso.name}' a '{stampante}' ({copie} copie, tramite l'app associata).{nota}"


# --------------------------------------------------------------------------- #
# Strumenti MCP
# --------------------------------------------------------------------------- #

@mcp.tool()
def elenca_stampanti() -> str:
    """Elenca le stampanti installate sul PC, indicando la predefinita e lo stato."""
    out = _powershell(
        "@(Get-CimInstance Win32_Printer | Select-Object Name, Default, WorkOffline, "
        "@{n='Stato';e={$_.PrinterStatus}}) | ConvertTo-Json -Compress"
    )
    stampanti = json.loads(out or "[]")
    if isinstance(stampanti, dict):
        stampanti = [stampanti]
    stati = {1: "altro", 2: "sconosciuto", 3: "pronta", 4: "in stampa",
             5: "in riscaldamento", 6: "ferma", 7: "offline"}
    righe = []
    for s in stampanti:
        stato = stati.get(s.get("Stato"), str(s.get("Stato")))
        if s.get("WorkOffline"):
            stato = "offline"
        righe.append(f"- {s['Name']}{' (predefinita)' if s.get('Default') else ''}: {stato}")
    return "\n".join(righe) or "Nessuna stampante trovata."


@mcp.tool()
def stampa_file(percorso: str, stampante: str | None = None, copie: int = 1,
                fronte_retro: bool = False, bianco_nero: bool = False) -> str:
    """Stampa un file che si trova sul PC.

    Args:
        percorso: percorso completo del file (es. C:\\Users\\me\\Documents\\bolletta.pdf).
        stampante: nome (anche parziale) della stampante; vuoto = predefinita.
        copie: numero di copie (1-20).
        fronte_retro: stampa fronte/retro (solo PDF con SumatraPDF).
        bianco_nero: stampa in bianco e nero (solo PDF con SumatraPDF).
    """
    p = Path(os.path.expandvars(os.path.expanduser(percorso))).resolve()
    if not p.is_file():
        raise RuntimeError(f"File non trovato: {p}")
    return _stampa(p, _risolvi_stampante(stampante), copie, fronte_retro, bianco_nero)


@mcp.tool()
def stampa_da_url(url: str, stampante: str | None = None, copie: int = 1,
                  fronte_retro: bool = False, bianco_nero: bool = False) -> str:
    """Scarica un file da un link (http/https) sul PC e lo stampa.
    Utile per stampare da fuori casa un PDF o un'immagine raggiungibile via web."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise RuntimeError("Sono ammessi solo link http o https.")
    CARTELLA_DOWNLOAD.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers={"User-Agent": "stampa-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        nome = Path(urllib.parse.unquote(parsed.path)).name or "documento"
        tipo = r.headers.get_content_type()
        if not Path(nome).suffix:
            nome += {"application/pdf": ".pdf", "image/jpeg": ".jpg",
                     "image/png": ".png", "text/plain": ".txt"}.get(tipo, "")
        dest = CARTELLA_DOWNLOAD / nome
        limite = MAX_DOWNLOAD_MB * 1024 * 1024
        letti = 0
        with open(dest, "wb") as f:
            while chunk := r.read(64 * 1024):
                letti += len(chunk)
                if letti > limite:
                    raise RuntimeError(f"File più grande di {MAX_DOWNLOAD_MB} MB.")
                f.write(chunk)
    return _stampa(dest, _risolvi_stampante(stampante), copie, fronte_retro, bianco_nero)


@mcp.tool()
def stampa_testo(testo: str, stampante: str | None = None, copie: int = 1) -> str:
    """Stampa del testo semplice (una nota, una lista della spesa, ...)."""
    nome = _risolvi_stampante(stampante)
    for _ in range(max(1, min(int(copie), COPIE_MAX))):
        _powershell("$input | Out-Printer -Name $env:SM_PRN",
                    env={"SM_PRN": nome}, stdin=testo)
    return f"Testo inviato a '{nome}'."


@mcp.tool()
def coda_di_stampa(stampante: str | None = None) -> str:
    """Mostra i lavori in coda sulla stampante (vuoto = predefinita)."""
    nome = _risolvi_stampante(stampante)
    out = _powershell(
        "@(Get-PrintJob -PrinterName $env:SM_PRN | Select-Object Id, DocumentName, "
        "@{n='Stato';e={\"$($_.JobStatus)\"}}, PagesPrinted, TotalPages) | ConvertTo-Json -Compress",
        env={"SM_PRN": nome},
    )
    lavori = json.loads(out or "[]")
    if isinstance(lavori, dict):
        lavori = [lavori]
    if not lavori:
        return f"Nessun lavoro in coda su '{nome}'."
    return "\n".join(
        f"- #{j['Id']} {j['DocumentName']}: {j['Stato'] or 'in attesa'} "
        f"({j['PagesPrinted']}/{j['TotalPages']} pagine)" for j in lavori
    )


@mcp.tool()
def annulla_stampe(stampante: str | None = None) -> str:
    """Annulla tutti i lavori in coda sulla stampante (vuoto = predefinita)."""
    nome = _risolvi_stampante(stampante)
    _powershell("Get-PrintJob -PrinterName $env:SM_PRN | Remove-PrintJob",
                env={"SM_PRN": nome})
    return f"Coda di '{nome}' svuotata."


# --------------------------------------------------------------------------- #
# Stato stampante via SNMP (stampanti di rete, es. HP M28w in Wi-Fi)
# --------------------------------------------------------------------------- #

def _ber_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _ber(tag: int, payload: bytes) -> bytes:
    return bytes([tag]) + _ber_len(len(payload)) + payload


def _ber_int(v: int) -> bytes:
    return _ber(0x02, v.to_bytes(max(1, (v.bit_length() + 8) // 8), "big", signed=True))


def _ber_oid(oid: str) -> bytes:
    parti = [int(x) for x in oid.strip(".").split(".")]
    out = bytearray([parti[0] * 40 + parti[1]])
    for p in parti[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.append(0x80 | (p & 0x7F))
            p >>= 7
        out.extend(reversed(chunk))
    return _ber(0x06, bytes(out))


def _ber_leggi(data: bytes, i: int) -> tuple[int, bytes, int]:
    """Legge un elemento TLV: restituisce (tag, valore, indice successivo)."""
    tag = data[i]
    n = data[i + 1]
    i += 2
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(data[i:i + k], "big")
        i += k
    return tag, data[i:i + n], i + n


def _decodifica_oid(b: bytes) -> str:
    parti = [b[0] // 40, b[0] % 40]
    v = 0
    for x in b[1:]:
        v = (v << 7) | (x & 0x7F)
        if not x & 0x80:
            parti.append(v)
            v = 0
    return ".".join(map(str, parti))


def _snmp_get(host: str, oids: list[str], community: str = "public",
              timeout: float = 3.0) -> dict[str, object]:
    """SNMP v1 GET minimale, senza librerie esterne."""
    import random
    import socket

    req_id = random.randint(1, 2**30)
    varbinds = b"".join(_ber(0x30, _ber_oid(o) + b"\x05\x00") for o in oids)
    pdu = _ber(0xA0, _ber_int(req_id) + _ber_int(0) + _ber_int(0) + _ber(0x30, varbinds))
    msg = _ber(0x30, _ber_int(0) + _ber(0x04, community.encode()) + pdu)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        for _ in range(2):
            s.sendto(msg, (host, 161))
            try:
                data, _ = s.recvfrom(65535)
                break
            except socket.timeout:
                continue
        else:
            raise RuntimeError(
                f"La stampante {host} non risponde (SNMP). È accesa e in rete? "
                "SNMP è attivo nel suo pannello web (Rete > SNMP)?")

    _, msg_body, _ = _ber_leggi(data, 0)
    i = 0
    for _ in range(2):  # versione, community
        _, _, i = _ber_leggi(msg_body, i)
    _, pdu_body, _ = _ber_leggi(msg_body, i)
    j = 0
    _, _, j = _ber_leggi(pdu_body, j)          # request id
    _, err, j = _ber_leggi(pdu_body, j)        # error status
    _, _, j = _ber_leggi(pdu_body, j)          # error index
    _, vbl, _ = _ber_leggi(pdu_body, j)

    risultati: dict[str, object] = {}
    k = 0
    while k < len(vbl):
        _, vb, k = _ber_leggi(vbl, k)
        _, oid_b, m = _ber_leggi(vb, 0)
        tag, val, _ = _ber_leggi(vb, m)
        oid = _decodifica_oid(oid_b)
        if tag in (0x02, 0x41, 0x42, 0x43):
            risultati[oid] = int.from_bytes(val, "big", signed=(tag == 0x02))
        elif tag == 0x04:
            risultati[oid] = val
        else:
            risultati[oid] = None
    if int.from_bytes(err, "big"):
        raise ValueError("La stampante ha rifiutato la richiesta SNMP (dato non disponibile).")
    return risultati


def _ip_stampante(stampante: str | None) -> str:
    if os.environ.get("STAMPANTE_IP"):
        return os.environ["STAMPANTE_IP"]
    nome = _risolvi_stampante(stampante)
    ip = _powershell(
        "Set-StrictMode -Off; $p = Get-Printer -Name $env:SM_PRN; "
        "$porta = Get-PrinterPort -Name $p.PortName -ErrorAction SilentlyContinue; "
        "$ip = $null; foreach ($n in 'PrinterHostAddress','PrinterHostIP') { "
        "  if (-not $ip -and $porta -and $porta.PSObject.Properties[$n]) { $ip = $porta.$n } }; "
        "if (-not $ip -and $p.PortName -match '(\\d+\\.\\d+\\.\\d+\\.\\d+)') { $ip = $Matches[1] }; "
        "$ip",
        env={"SM_PRN": nome},
    )
    if not ip:
        raise RuntimeError(
            f"Non trovo l'indirizzo IP di '{nome}' (probabilmente è collegata con porta WSD). "
            "Indica il parametro 'ip' (lo trovi nell'app HP Smart o stampando il report di "
            "configurazione) oppure imposta la variabile d'ambiente STAMPANTE_IP.")
    return ip


OID_DESCRIZIONE = "1.3.6.1.2.1.25.3.2.1.3.1"
OID_STATO = "1.3.6.1.2.1.25.3.5.1.1.1"
OID_ERRORI = "1.3.6.1.2.1.25.3.5.1.2.1"
OID_PAGINE = "1.3.6.1.2.1.43.10.2.1.4.1.1"
OID_CONS_NOME = "1.3.6.1.2.1.43.11.1.1.6.1.{}"
OID_CONS_MAX = "1.3.6.1.2.1.43.11.1.1.8.1.{}"
OID_CONS_LIV = "1.3.6.1.2.1.43.11.1.1.9.1.{}"

ERRORI_STAMPANTE = [  # bit di hrPrinterDetectedErrorState (dal più significativo)
    "carta in esaurimento", "carta esaurita", "toner in esaurimento", "toner esaurito",
    "sportello aperto", "carta inceppata", "offline", "richiede assistenza",
    "vassoio di ingresso mancante", "vassoio di uscita mancante",
    "materiale di consumo mancante", "vassoio di uscita quasi pieno",
    "vassoio di uscita pieno", "vassoio di ingresso vuoto", "manutenzione in ritardo",
]


@mcp.tool()
def stato_stampante(stampante: str | None = None, ip: str | None = None) -> str:
    """Controlla una stampante di rete (es. HP M28w in Wi-Fi): livello toner,
    stato, errori (carta, inceppamenti, sportello) e pagine stampate in totale.

    Args:
        stampante: nome della stampante su Windows (vuoto = predefinita), usato per trovarne l'IP.
        ip: indirizzo IP della stampante, se lo conosci (ha la precedenza).
    """
    host = ip or _ip_stampante(stampante)
    oids = [OID_DESCRIZIONE, OID_STATO, OID_ERRORI, OID_PAGINE]
    for n in (1, 2):
        oids += [OID_CONS_NOME.format(n), OID_CONS_MAX.format(n), OID_CONS_LIV.format(n)]
    try:
        r = _snmp_get(host, oids)
    except ValueError:
        # In SNMP v1 basta un dato mancante (es. secondo consumabile) per far
        # rifiutare tutta la richiesta: chiedo i dati uno alla volta.
        r = {}
        for o in oids:
            try:
                r.update(_snmp_get(host, [o]))
            except ValueError:
                pass

    righe = []
    descr = r.get(OID_DESCRIZIONE)
    if isinstance(descr, bytes):
        righe.append(f"Stampante: {descr.decode(errors='replace').strip()} ({host})")
    else:
        righe.append(f"Stampante: {host}")

    stato = {1: "altro", 2: "sconosciuto", 3: "pronta", 4: "in stampa", 5: "in riscaldamento"}
    righe.append(f"Stato: {stato.get(r.get(OID_STATO), 'sconosciuto')}")

    err = r.get(OID_ERRORI)
    problemi = []
    if isinstance(err, bytes) and err:
        bits = int.from_bytes(err, "big")
        totale = len(err) * 8
        problemi = [nome for i, nome in enumerate(ERRORI_STAMPANTE)
                    if i < totale and bits & (1 << (totale - 1 - i))]
    righe.append("Avvisi: " + (", ".join(problemi) if problemi else "nessuno"))

    for n in (1, 2):
        nome = r.get(OID_CONS_NOME.format(n))
        liv = r.get(OID_CONS_LIV.format(n))
        mx = r.get(OID_CONS_MAX.format(n))
        if not isinstance(nome, bytes) or not isinstance(liv, int):
            continue
        nome_s = nome.decode(errors="replace").strip()
        if isinstance(mx, int) and mx > 0 and liv >= 0:
            pct = round(liv * 100 / mx)
            barra = "█" * (pct // 10) + "░" * (10 - pct // 10)
            righe.append(f"{nome_s}: {barra} {pct}%")
        elif liv == -3:
            righe.append(f"{nome_s}: presente (livello non disponibile)")
        else:
            righe.append(f"{nome_s}: livello sconosciuto")

    pagine = r.get(OID_PAGINE)
    if isinstance(pagine, int):
        righe.append(f"Pagine stampate in totale: {pagine}")
    return "\n".join(righe)


if __name__ == "__main__":
    mcp.run()
