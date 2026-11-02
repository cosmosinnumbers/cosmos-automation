# Scorecard settimanale (02/11/2026)

**Periodo delle letture:** youtube 2026-10-27→2026-11-02; instagram 2026-10-27→2026-11-02; facebook 2026-10-27→2026-11-02; threads 2026-10-27→2026-11-02; gumroad 2026-10-27→2026-11-02. **Fonti:** `07-analytics/metrics/*.jsonl` (metrics.yml), `research/cosmos/`. Fatti calcolati dal codice (`tools/strategy_weekly.py`); l'analisi è un'ipotesi, non una conclusione. Campioni piccoli: tutto esplorativo.

## Distribuzione, attenzione e coinvolgimento (per canale e formato)
| Canale | Formato | Post (nuovi 7 gg) | Visualizzazioni cumulate | + nella settimana | Mediana per post | Like | Commenti | Condivisioni | Salvataggi | Visione media |
|---|---|---|---|---|---|---|---|---|---|---|
| youtube | long | 5 (1) | 186 | 37 | 30 | 9 | 6 | 1 | – | – |
| youtube | short | 19 (8) | 5.200 | 1.742 | 233 | 120 | 20 | 6 | – | – |
| instagram | carousel | 6 (1) | 31 | 8 | 4,5 | 14 | 0 | 0 | 0 | – |
| instagram | reel | 11 (4) | 1.637 | 823 | 129 | 36 | 0 | 0 | 1 | 7,0 s mediana |
| facebook | carousel | 6 (1) | 20 | 1 | 1,5 | 3 | 0 | 0 | – | – |
| facebook | photo | 1 (0) | 7 | 0 | 7 | 0 | 0 | 0 | – | – |
| facebook | reel | 12 (1) | 62 | 10 | 4,5 | 9 | 0 | – | – | 1,9 s mediana |
| threads | text_post | 19 (9) | 5.647 | 465 | 38 | 110 | 47 | 0 | – | – |
| threads | video | 4 (1) | 255 | 14 | 73,5 | 8 | 7 | 0 | – | – |

Visualizzazioni come definite da ogni piattaforma (07-analytics/metrics/DEFINIZIONI.md); valori cumulati all'ultima lettura, "+ nella settimana" = differenza con la lettura di 7 giorni prima.

## Account
- youtube @CosmosinNumbers: subscribers 7 (era 7 il 2026-10-27), views 5.127 (era 3.559 il 2026-10-27), videos 24 (era 15 il 2026-10-27)
- instagram @cosmos.innumbers: acct_profile_views 1 (era 0 il 2026-10-27), acct_website_clicks 0 (era 0 il 2026-10-27), acct_reach 172 (era 8 il 2026-10-27), acct_followers 4 (era 4 il 2026-10-27)
- facebook Cosmos in Numbers (Pagina): acct_page_views 0 (era 2 il 2026-10-27), acct_post_engagements 1 (era 0 il 2026-10-27), acct_followers 1 (era 1 il 2026-10-27)

## Traffico e risultati di business
- tiktok: nessuna lettura (non misurato)
- gumroad 2026-11-02: vendite e visite non misurate (visits (non esposte dall'API))

## Non misurato
- gumroad: visits (non esposte dall'API)
- instagram: reach (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"AhtJLYmIOqA523haevMuuP7"}}); replies (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"AeI-w12wfvGTNnMs-ftGjZ7"}}); shares (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"AWZcdAQFF5YPQ2qMWSSTBRI"}}); total_interactions (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"AAvVfzD-e-vQRCZzBjvFcdY"}}); views (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"AxLmIO599SoOvzUa2nnoriF"}})
- youtube: link_clicks (non esposto dalle API)

## Analisi (Gemini, controllata dal codice)
### Interpretazione
- Dal 2026-10-27 al 2026-11-02, le visite e le vendite su Gumroad per il prodotto LOOK UP non sono state misurate.
- I clic sul sito web da Instagram sono stati 0 tra il 2026-10-27 e il 2026-11-02, su un campione piccolo di 4 follower e 172 di copertura dell'account.
- Su YouTube, i video Short hanno generato 1.742 visualizzazioni nella settimana (su 5.200 totali), ma i clic verso link esterni non sono esposti dalle API.
- Su Threads, i post di testo hanno ottenuto 465 visualizzazioni nella settimana su un totale di 19 post pubblicati, ma la conversione verso il prodotto non è tracciata.

### Decisioni (ipotesi da testare)
- Nessuna decisione: Le visite e le vendite di LOOK UP su Gumroad non sono misurate e i clic sul sito da Instagram sono stati 0 dal 2026-10-27 al 2026-11-02. Non ci sono dati di traffico o conversione sufficienti per guidare decisioni di business.

### Prossimo test utile
- Inserire un link per il prodotto LOOK UP nei commenti in evidenza dei prossimi 5 YouTube Shorts per verificare se genera almeno 1 visita o vendita su Gumroad entro 7 giorni.

### Idee dai competitor
- Aprire uno Short nei primi 3 secondi con un confronto grafico di dimensioni o distanze spaziali basato su dati numerici per fermare lo scorrimento.
- Strutturare un contenuto breve attorno a un paradosso ingegneristico dello spazio (come una sonda o un contenitore bloccato) usando solo animazioni di dati e testo a schermo.
