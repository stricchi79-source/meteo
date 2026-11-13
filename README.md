# Stazione Meteo

Una piccola web app meteo in un unico file (`index.html`), pensata soprattutto per lo smartphone.
Mostra le condizioni attuali, le previsioni ora per ora (24 ore) e quelle dei prossimi 7 giorni
per la località scelta. I dati arrivano da [Open-Meteo](https://open-meteo.com), gratuito e senza chiave API.

## Funzionalità

- **Condizioni attuali**: temperatura, percepita, descrizione del tempo, umidità, punto di rugiada,
  vento (velocità, direzione e raffiche), pressione, nuvolosità, pioggia di oggi e probabilità,
  indice UV massimo, alba e tramonto.
- **Prossime 24 ore**: temperatura, icona e probabilità di pioggia per ogni ora.
- **Prossimi 7 giorni**: minime e massime e probabilità di pioggia.
- **Ricerca località** per nome (geocoding Open-Meteo, in italiano) oppure tramite **GPS**.
- **Località salvate**, ricordate nel browser.
- **Funziona anche offline**: mostra gli ultimi dati scaricati con l'indicazione di quando risalgono.
- **Aggiornamento automatico** quando si torna sull'app (al massimo ogni 10 minuti).
- **Tema chiaro/scuro** automatico, in base alle impostazioni del dispositivo.

La località predefinita è Castelnuovo Bormida (Piemonte).

## Come usarla

### Aprirla in locale

Non serve installare nulla: basta scaricare il repository e aprire `index.html` con un browser.

```bash
git clone https://github.com/stricchi79-source/meteo.git
cd meteo
# poi apri index.html con il browser (doppio clic sul file)
```

> Nota: alcuni browser bloccano la geolocalizzazione per i file aperti con `file://`.
> Se il pulsante "Usa la mia posizione" non funziona, avvia un piccolo server locale:
>
> ```bash
> python3 -m http.server 8000
> ```
>
> e apri <http://localhost:8000> nel browser.

### Pubblicarla online con GitHub Pages

1. Su GitHub apri **Settings → Pages** del repository.
2. In **Build and deployment**, scegli **Source: Deploy from a branch**.
3. Seleziona il branch `main` e la cartella `/ (root)`, poi **Save**.
4. Dopo un paio di minuti l'app sarà disponibile su
   `https://stricchi79-source.github.io/meteo/`.

### Installarla sul telefono

L'app va aperta dall'indirizzo online (GitHub Pages, `https://...`): **non si installa
aprendo il file `index.html` scaricato sul telefono**.

- **Android (Chrome)**: apri `https://stricchi79-source.github.io/meteo/`, menu ⋮ →
  *Installa app* (o *Aggiungi a schermata Home* → *Installa*).
- **iPhone (Safari)**: apri il sito **con Safari** (non con Chrome o dall'anteprima di un'altra app),
  tocca *Condividi* → *Aggiungi alla schermata Home*.

L'app si aprirà a schermo intero come un'applicazione normale e si avvia anche senza rete.

## Uso quotidiano

- **Cambiare località**: tocca il nome della località in alto, cerca una città oppure usa
  "Usa la mia posizione". Le località scelte vengono salvate nell'elenco "Località salvate";
  toccando × si rimuovono.
- **Aggiornare i dati**: tocca il pulsante con la freccia circolare in alto a destra.

## Personalizzazione

Per cambiare la località predefinita, modifica la costante `HOME` in `index.html`:

```js
const HOME = {id:'3179533',name:'Castelnuovo Bormida',admin:'Piemonte, IT',lat:44.742,lon:8.551};
```

Inserisci nome, regione, latitudine e longitudine della tua località (l'`id` può essere
qualsiasi stringa univoca, ad esempio l'ID restituito dalla ricerca di Open-Meteo).

## Privacy

L'app non ha server propri: tutto avviene nel browser. Le località salvate e i dati in cache
restano nel `localStorage` del dispositivo. Le richieste esterne sono verso le API di
Open-Meteo (previsioni e ricerca località) e, se attivato,
GoatCounter (contatore visite).

## Statistiche visite

Il sito può contare le visite con [GoatCounter](https://www.goatcounter.com), un servizio
gratuito e rispettoso della privacy: non usa cookie e non raccoglie dati personali.

Per attivarlo:

1. Crea un account gratuito su <https://www.goatcounter.com> e scegli un nome per il sito
   (ad esempio `meteo`, che diventa `meteo.goatcounter.com`).
2. In `index.html` imposta quel nome nella costante `GOATCOUNTER`:

   ```js
   const GOATCOUNTER = 'meteo';
   ```

3. Le visite si vedono nella dashboard su `https://<nome>.goatcounter.com`.

Le visite fatte aprendo il file in locale o da `localhost` non vengono contate.

## Crediti

- Dati meteo: [Open-Meteo](https://open-meteo.com) (licenza CC BY 4.0).
- Carattere: Space Grotesk (licenza SIL OFL), ospitato nella cartella `fonts/`, quindi niente richieste a Google e funziona anche offline.
