---
name: vendita
description: >-
  Revisione di vendita di Cosmos in Numbers: legge il funnel (visualizzazioni, clic veri verso Gumroad, download
  del gratuito, vendite), trova il collo di bottiglia della settimana, propone alternative e le fa valutare a Jev,
  poi cambia inviti all'acquisto, argomenti dei video e pagine prodotto. Usala con /vendita, o quando si chiede
  perché non si vende, come vendere di più, o di rivedere offerte, link, titoli e prodotti Gumroad.
---

# vendita

Una procedura sola per ogni revisione di vendita. Il prompt completo e le decisioni prese finora sono in
`docs/PROMPT-vendere.md`.

## 1. Leggi i numeri

- `reports/funnel.md`: il funnel degli ultimi 7 giorni, riscritto ogni mattina da `tools/funnel_report.py`
  (dentro `metrics.yml`). Storico in `07-analytics/metrics/funnel.jsonl`.
- `07-analytics/metrics/gumroad-utm.jsonl`: clic per link tracciato. I clic del link in bio di Instagram sono
  quasi tutti robot: il rapporto li confronta con i tocchi contati da Instagram e toglie la differenza.
- `07-analytics/metrics/gumroad.jsonl`: vendite e download per prodotto. Le visite alla pagina non sono esposte
  dall'API: "non misurato".
- Dal cloud dei thread gumroad.com e nasa.gov non si raggiungono: tutto ciò che legge o scrive Gumroad passa da
  un workflow (`gumroad-audit`, `gumroad-apply`, `gumroad-utm`, `sky-calendar`).

## 2. Trova il collo di bottiglia (uno solo)

| Segnale | Collo di bottiglia | Dove si lavora |
|---|---|---|
| Clic veri sotto lo 0,3% delle visualizzazioni | il clic | `tools/cta.py`, `config/sales-topics.json`, `config/sky-calendar.json`, link del canale e delle bio |
| Più di 30 clic a settimana, nessun download | la pagina | `products/*/description.html`, copertine, `tools/gumroad_apply.py` |
| Più di 20 download, nessuna vendita | da gratis a pagamento | ultima pagina del PDF (`products/sky-30-nights/build.mjs`), ricevuta, email Gumroad |
| Vendite, ma poche | il volume | altri posti dove i compratori cercano già: Amazon KDP, Etsy, Pinterest |

Regola pratica: una vendita ogni 50-100 clic veri di persone interessate al cielo. Sotto quella soglia zero
vendite è il risultato atteso, non un problema di prezzo.

## 3. Dove i link si cliccano

Cliccabili: descrizione e commento fissato dei video lunghi di YouTube, pagina del canale YouTube, bio di
Instagram e TikTok, post Facebook, risposte su Threads. Non cliccabili: descrizione e commenti degli Short,
didascalie di Instagram e TikTok. Ogni link passa da `tools/links.py` (`link(prodotto, canale, posto)`), che
restituisce il link tracciato di `config/gumroad-utm.json`.

## 4. Decidi con Jev

Per titoli, inviti all'acquisto, offerte e priorità: almeno 8 candidati, una domanda sola, livelli scritti per
esteso (0 = nessun effetto ... 4 = fortissimo). Payload e limiti: `.claude/skills/jev/references/tools.md`.

```bash
TYPESAFE_API_KEY=placeholder NODE_USE_ENV_PROXY=1 NODE_NO_WARNINGS=1 \
  npx -y @french-castle/jev-code@0.5.0 score --input candidati.json
```

Nello stato metti i numeri veri del funnel, mai la tua conclusione. Riporta i punteggi nel commento del codice
o del file di configurazione che cambi, con la data. Jev rompe i pareggi: dopo 7 giorni decidono i clic.

## 5. Cambia, misura, scrivi

- Contenuti da acquirente: `config/sales-topics.json` (video lunghi, in ordine), `tools/sky.py calendar`
  (eventi del cielo per gli Short `sky_tonight`), `tools/cta.py` (prima risposta su Threads).
- Prodotto gratuito: "The Next 30 Nights", calendario del cielo ricostruito ogni lunedì da `sky-calendar.yml`
  (calcolo PyEphem, nessun LLM). Stesso link per sempre: `cosmosinnumbers.gumroad.com/l/sky-30-nights`.
- Regole che non cambiano: TikTok mai contenuti commerciali e link solo in bio; COSMOS9 = $7,41 fino al 30/11/2026
  (codice universale, non modificabile via API); YouTube solo materiale libero; nessuna chiave in file o log.
- Alla fine: cosa è cambiato, cosa aspettarsi in numeri e quando si rilegge il funnel, cosa serve da simone.
