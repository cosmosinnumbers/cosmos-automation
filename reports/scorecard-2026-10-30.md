# Scorecard settimanale (30/10/2026)

**Periodo delle letture:** youtube 2026-10-27→2026-10-30; instagram 2026-10-27→2026-10-30; facebook 2026-10-27→2026-10-30; threads 2026-10-27→2026-10-30; gumroad 2026-10-27→2026-10-30. **Fonti:** `07-analytics/metrics/*.jsonl` (metrics.yml), `research/cosmos/`. Fatti calcolati dal codice (`tools/strategy_weekly.py`); l'analisi è un'ipotesi, non una conclusione. Campioni piccoli: tutto esplorativo.

## Distribuzione, attenzione e coinvolgimento (per canale e formato)
| Canale | Formato | Post (nuovi 7 gg) | Visualizzazioni cumulate | + nella settimana | Mediana per post | Like | Commenti | Condivisioni | Salvataggi | Visione media |
|---|---|---|---|---|---|---|---|---|---|---|
| youtube | long | 4 (1) | 172 | 23 | 36 | 8 | 5 | – | – | – |
| youtube | short | 15 (11) | 4.348 | 890 | 212 | 95 | 13 | – | – | – |
| instagram | carousel | 6 (4) | 31 | 8 | 4,5 | 14 | 0 | 0 | 0 | – |
| instagram | reel | 9 (3) | 1.302 | 488 | 126 | 30 | 0 | 0 | 0 | 6,0 s mediana |
| facebook | carousel | 6 (4) | 20 | 1 | 1,5 | 3 | 0 | 0 | – | – |
| facebook | photo | 1 (0) | 7 | 0 | 7 | 0 | 0 | 0 | – | – |
| facebook | reel | 11 (5) | 54 | 2 | 6 | 7 | 0 | – | – | 2,2 s mediana |
| threads | text_post | 14 (8) | 5.454 | 272 | 50,5 | 107 | 37 | 0 | – | – |
| threads | video | 3 (1) | 243 | 2 | 79 | 7 | 5 | 0 | – | – |

Visualizzazioni come definite da ogni piattaforma (07-analytics/metrics/DEFINIZIONI.md); valori cumulati all'ultima lettura, "+ nella settimana" = differenza con la lettura di 7 giorni prima.

## Account
- youtube @CosmosinNumbers: subscribers 7 (era 7 il 2026-10-27), views 4.437 (era 3.559 il 2026-10-27), videos 19 (era 15 il 2026-10-27)
- instagram @cosmos.innumbers: acct_profile_views 1 (era 0 il 2026-10-27), acct_website_clicks 0 (era 0 il 2026-10-27), acct_reach 110 (era 8 il 2026-10-27), acct_followers 4 (era 4 il 2026-10-27)
- facebook Cosmos in Numbers (Pagina): acct_page_views 0 (era 2 il 2026-10-27), acct_post_engagements 0 (era 0 il 2026-10-27), acct_followers 1 (era 1 il 2026-10-27)

## Traffico e risultati di business
- tiktok: nessuna lettura (non misurato)
- gumroad 2026-10-30: vendite e visite non misurate (revenue_usd (idem); sales (manca secrets/gumroad.json (token di Gumroad)); visits (non esposte dall'API))

## Non misurato
- gumroad: revenue_usd (idem); sales (manca secrets/gumroad.json (token di Gumroad)); visits (non esposte dall'API)
- youtube: avg_view_duration_s (manca il consenso yt-analytics.readonly (metrics.py yt-auth)); avg_view_pct (manca il consenso yt-analytics.readonly (metrics.py yt-auth)); link_clicks (non esposto dalle API); shares (manca il consenso yt-analytics.readonly (metrics.py yt-auth)); subs_gained (manca il consenso yt-analytics.readonly (metrics.py yt-auth))

## Analisi (Gemini, controllata dal codice)
### Interpretazione
- I risultati di business non sono misurabili: al 2026-10-30 le vendite e i ricavi di LOOK UP su Gumroad non sono misurati per mancanza di token, le visite non sono esposte dalle API e i click al sito da Instagram sono fermi a 0 sia il 2026-10-27 sia il 2026-10-30.
- Su YouTube, il formato Short registra 4.348 visualizzazioni cumulate (+890 tra il 2026-10-27 e il 2026-10-30) su 15 post, mentre il formato Long si ferma a 172 visualizzazioni (+23 nella settimana) su un campione piccolo di 4 post; tempo medio di visione e click ai link restano però non misurati.
- Threads ottiene la distribuzione più alta con 5.454 visualizzazioni cumulate (+272 nella settimana), 107 like e 37 commenti su 14 post di testo, mentre i video su Threads contano solo 3 post (campione piccolo) con 243 visualizzazioni cumulate.
- Su Instagram, i Reel mostrano una trazione maggiore rispetto ai caroselli con 1.302 visualizzazioni cumulate (+488 nella settimana) e 6,0 secondi di visione media mediana su un campione piccolo di 9 post, contro le 31 visualizzazioni su 6 post carosello.

### Decisioni (ipotesi da testare)
- Nessuna decisione: Le prove a supporto delle decisioni di business non bastano: al 2026-10-30 vendite, ricavi e visite su Gumroad non sono misurati, e i click al sito da Instagram sono pari a 0. Senza tracciamento del traffico verso LOOK UP è impossibile valutare l'impatto economico di qualsiasi cambio editoriale.

### Prossimo test utile
- Configurare la chiave API di Gumroad per misurare vendite e ricavi, e pubblicare per 7 giorni nei prossimi YouTube Short un link tracciato a LOOK UP nel primo commento per verificare se genera click e conversioni.

### Idee dai competitor
- Breve video Short basato sul confronto di distanze astronomiche reali: mostrare visivamente quanti chilometri separano Terra e Luna calcolando quali pianeti possono entrare in quello spazio.
- Video Short focalizzato su un contrasto numerico estremo: spiegare la missione OSIRIS-REx confrontando i 6 miliardi di chilometri percorsi con le sole 2 viti bloccate e i 121,6 grammi di campione raccolto.
