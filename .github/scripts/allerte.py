"""Raccoglie le allerte per Castelnuovo Bormida e le salva in allerte.json.

Fonti (entrambe con licenza CC BY 4.0):
  - Protezione Civile, Bollettino di criticità nazionale/allerta (allerta ufficiale per zona):
    https://github.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica
  - MeteoAlarm, avvisi meteo per il Piemonte (vento, neve, ghiaccio, caldo, freddo, nebbia, temporali):
    https://feeds.meteoalarm.org

Gira su GitHub Actions ogni 30 minuti; scrive il file solo se il contenuto cambia.
Solo libreria standard di Python.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

COMUNE = "Castelnuovo Bormida"
REGIONE = "Piemonte"
DPC_REPO = "pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "allerte.json")

LIVELLI = [("ROSSA", 3), ("ARANCIONE", 2), ("GIALLA", 1)]
RISCHI = {"idrogeologico": "Per rischio idrogeologico", "idraulico": "Per rischio idraulico",
          "temporali": "Per rischio temporali"}


def get(url, api=False):
    h = {"User-Agent": "meteo-allerte/1.0"}
    if api and os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def livello(testo):
    t = (testo or "").upper()
    for nome, n in LIVELLI:
        if "ALLERTA " + nome in t:
            return n
    return 0


def protezione_civile():
    tree = get(f"https://api.github.com/repos/{DPC_REPO}/git/trees/master:files", api=True)
    nomi = sorted(x["path"] for x in tree["tree"] if re.fullmatch(r"\d{8}_\d{4}\.json", x["path"]))
    ultimo = nomi[-1]
    raw = f"https://raw.githubusercontent.com/{DPC_REPO}/master/files/"
    boll = get(raw + ultimo)
    giorno0 = dt.date(int(ultimo[:4]), int(ultimo[4:6]), int(ultimo[6:8]))
    giorni, zona = [], None
    for k, quando in (("today", 0), ("tomorrow", 1)):
        topo = get(boll[k]["topo_json"])
        geoms = list(topo["objects"].values())[0]["geometries"]
        p = next(g["properties"] for g in geoms if COMUNE in (g.get("properties") or {}).get("Comuni", []))
        zona = p.get("Nome zona")
        g = {"data": (giorno0 + dt.timedelta(days=quando)).isoformat()}
        for chiave, campo in RISCHI.items():
            g[chiave] = livello(p.get(campo))
        giorni.append(g)
    return {"zona": zona, "bollettino": boll.get("name"), "giorni": giorni}


def meteoalarm():
    d = get("https://feeds.meteoalarm.org/api/v1/warnings/feeds-italy")
    adesso = dt.datetime.now(dt.timezone.utc)
    visti, out = set(), []
    for w in d.get("warnings", []):
        a = w.get("alert", {})
        if a.get("msgType") == "Cancel":
            continue
        for inf in a.get("info", []):
            if not inf.get("language", "").startswith("it"):
                continue
            if not any(REGIONE in x.get("areaDesc", "") for x in inf.get("area", [])):
                continue
            par = {x["valueName"]: x["value"] for x in inf.get("parameter", [])}
            try:
                lv = int(par.get("awareness_level", "1").split(";")[0])
            except ValueError:
                continue
            if lv < 2:                      # 1 = verde, nessun avviso
                continue
            fine = inf.get("expires")
            if fine and dt.datetime.fromisoformat(fine) < adesso:
                continue
            tipo = par.get("awareness_type", "").split(";")[-1].strip()
            chiave = (tipo, lv, inf.get("onset"), fine)
            if chiave in visti:
                continue
            visti.add(chiave)
            out.append({"tipo": tipo, "evento": inf.get("event"), "livello": lv - 1,   # 1 gialla, 2 arancione, 3 rossa
                        "inizio": inf.get("onset"), "fine": fine})
    out.sort(key=lambda x: (-x["livello"], x["inizio"] or ""))
    return out


def main():
    dati = {"comune": COMUNE, "fonti": "Protezione Civile (Bollettino di criticità) · MeteoAlarm · CC BY 4.0"}
    try:
        dati["protezione_civile"] = protezione_civile()
    except Exception as e:  # una fonte che non risponde non deve cancellare l'altra
        print("Protezione Civile non disponibile:", e, file=sys.stderr)
    try:
        dati["meteoalarm"] = meteoalarm()
    except Exception as e:
        print("MeteoAlarm non disponibile:", e, file=sys.stderr)
    if "protezione_civile" not in dati and "meteoalarm" not in dati:
        sys.exit("Nessuna fonte disponibile: lascio il file com'è")
    # se una fonte manca, tengo l'ultimo dato buono di quella fonte
    try:
        with open(OUT, encoding="utf-8") as f:
            vecchio = json.load(f)
        for k in ("protezione_civile", "meteoalarm"):
            if k not in dati and k in vecchio:
                dati[k] = vecchio[k]
    except (OSError, ValueError):
        vecchio = None
    if vecchio == dati:
        print("Nessun cambiamento")
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("allerte.json aggiornato")


if __name__ == "__main__":
    main()
