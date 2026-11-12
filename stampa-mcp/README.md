# Stampa da ovunque – server MCP per la stampante di casa

Un piccolo server MCP che gira sul **PC Windows di casa**, quello collegato alla stampante.
Dal telefono chiedi a Claude cose come *"stampa questo PDF"* e lui stampa a casa.
Prima di ogni stampa ti chiede **conferma sul telefono**.

## Cosa sa fare

| Strumento | Cosa fa |
|---|---|
| `elenca_stampanti` | Stampanti installate, predefinita e stato (pronta/offline…) |
| `stampa_file` | Stampa un file presente sul PC (PDF, TXT, immagini, Word…) |
| `stampa_da_url` | Scarica un file da un link e lo stampa |
| `stampa_testo` | Stampa del testo (una nota, una lista…) |
| `coda_di_stampa` | Mostra i lavori in coda |
| `annulla_stampe` | Svuota la coda |

Opzioni: stampante (anche solo parte del nome; se manca usa la predefinita), copie (1–20),
fronte/retro e bianco/nero (questi due solo per i PDF stampati con SumatraPDF).

## Installazione sul PC di casa (una volta sola)

1. **Python 3.10+** da <https://www.python.org/downloads/>. Durante l'installazione spunta
   **"Add python.exe to PATH"**.
2. **SumatraPDF** (gratuito, consigliato) da <https://www.sumatrapdfreader.org>: con questo i PDF
   si stampano in modo silenzioso e affidabile e funzionano copie, fronte/retro e bianco/nero.
3. **Claude Code**: apri PowerShell e lancia
   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```
   poi scrivi `claude` una volta per fare l'accesso con il tuo account.
4. **Scarica questa cartella** (`stampa-mcp`) sul PC, ad esempio in `C:\stampa-mcp`.
5. Fai doppio clic su **`installa.bat`**. Installa le dipendenze e mostra le stampanti trovate.
6. Evita che il PC vada in sospensione (da PowerShell come amministratore):
   ```powershell
   powercfg /change standby-timeout-ac 0
   ```

## Uso dal telefono

1. Sul PC fai doppio clic su **`avvia-da-telefono.bat`** e lascia aperta la finestra. Avvia
   `claude remote-control` in questa cartella e carica in automatico il server `stampante`
   (lo dichiara il file `.mcp.json`). La prima volta Claude ti chiede di approvare il server: rispondi sì.
2. Sul telefono apri l'app **Claude** → sezione **Code**: trovi la sessione del PC.
3. Scrivi, ad esempio:
   - *"Che stampanti ho?"*
   - *"Stampa C:\Users\Io\Documents\bolletta.pdf, 2 copie fronte/retro"*
   - *"Stampa il PDF a questo link: https://…"*
   - *"Stampa la lista della spesa: latte, pane, uova"*
   - *"Annulla tutto quello che è in coda"*
4. Claude ti chiede conferma prima di usare lo strumento: **confermi dal telefono** e la stampa parte.

> Per stampare un allegato ricevuto via email: salvalo in una cartella sincronizzata sul PC
> (OneDrive o Google Drive) e chiedi di stampare quel percorso, oppure inoltra il link al file.

### In alternativa: Claude Desktop

Se usi l'app Claude Desktop sul PC, aggiungi il server in
`%APPDATA%\Claude\claude_desktop_config.json` (sostituisci il percorso con il tuo):

```json
{
  "mcpServers": {
    "stampante": {
      "command": "python",
      "args": ["C:\\stampa-mcp\\server.py"]
    }
  }
}
```

e riavvia Claude Desktop.

## Sicurezza

- Il server **non apre porte** su Internet: comunica solo con Claude sul PC (stdio). Il
  collegamento al telefono passa dal tuo account Claude.
- Ogni stampa richiede la tua conferma, a meno che tu non scelga di approvare lo strumento per sempre.
- Nomi e percorsi passano a PowerShell tramite variabili d'ambiente, mai inseriti nel comando:
  così non si possono iniettare comandi.
- I file scaricati da link (max 50 MB) finiscono in `%TEMP%\stampa-mcp`. Per cambiare cartella
  imposta la variabile `STAMPA_CARTELLA`.

## Problemi comuni

- **"Stampante non trovata"**: chiedi prima *"che stampanti ho?"* e usa quel nome.
- **I PDF non escono**: installa SumatraPDF, oppure indica dove si trova con la variabile
  d'ambiente `SUMATRA_PATH`.
- **Word/immagini non escono**: questi file li stampa l'app associata (Word, Foto…). Deve
  supportare la stampa diretta; in caso contrario convertili in PDF.
- **La sessione non compare sul telefono**: controlla che la finestra di `avvia-da-telefono.bat`
  sia aperta e che il PC sia acceso e connesso.
