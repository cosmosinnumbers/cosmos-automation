# Scorecard settimanale (16/11/2026)

**Periodo delle letture:** youtube 2026-11-07→2026-11-15; instagram 2026-11-07→2026-11-15; facebook 2026-11-07→2026-11-15; threads 2026-11-07→2026-11-15; gumroad 2026-11-07→2026-11-15. **Fonti:** `07-analytics/metrics/*.jsonl` (metrics.yml), `research/cosmos/`. Fatti calcolati dal codice (`tools/strategy_weekly.py`); l'analisi è un'ipotesi, non una conclusione. Campioni piccoli: tutto esplorativo.

## Distribuzione, attenzione e coinvolgimento (per canale e formato)
| Canale | Formato | Post (nuovi 7 gg) | Visualizzazioni cumulate | + nella settimana | Mediana per post | Like | Commenti | Condivisioni | Salvataggi | Visione media |
|---|---|---|---|---|---|---|---|---|---|---|
| youtube | long | 7 (0) | 254 | 28 | 35 | 12 | 8 | 1 | – | – |
| youtube | short | 35 (9) | 7.688 | 991 | 164 | 191 | 38 | 7 | – | – |
| instagram | carousel | 6 (0) | 38 | 0 | 6 | 18 | 0 | 0 | 0 | – |
| instagram | reel | 19 (4) | 3.781 | 556 | 135 | 85 | 0 | 1 | 6 | 6,9 s mediana |
| facebook | carousel | 6 (0) | 21 | 0 | 2 | 4 | 0 | 0 | – | – |
| facebook | photo | 1 (0) | 7 | 0 | 7 | 0 | 0 | 0 | – | – |
| facebook | reel | 21 (5) | 86 | 5 | 3 | 17 | 0 | – | – | 1,9 s mediana |
| threads | text_post | 26 (11) | 2.555 | 1.949 | 40 | 30 | 53 | 0 | – | – |
| threads | video | 10 (5) | 795 | 707 | 47 | 18 | 24 | 0 | – | – |

Visualizzazioni come definite da ogni piattaforma (07-analytics/metrics/DEFINIZIONI.md); valori cumulati all'ultima lettura, "+ nella settimana" = differenza con la lettura di 7 giorni prima.

## Account
- youtube @CosmosinNumbers: subscribers 11 (era 8 il 2026-11-07), views 7.720 (era 6.561 il 2026-11-07), videos 42 (era 31 il 2026-11-07)
- instagram @cosmos.innumbers: acct_profile_views 3 (era 1 il 2026-11-07), acct_website_clicks 1 (era 0 il 2026-11-07), acct_reach 126 (era 111 il 2026-11-07), acct_followers 5 (era 5 il 2026-11-07)
- facebook Cosmos in Numbers (Pagina): acct_page_views 0 (era 0 il 2026-11-07), acct_post_engagements 0 (era 1 il 2026-11-07), acct_followers 2 (era 1 il 2026-11-07)

## Traffico e risultati di business
- tiktok: nessuna lettura (non misurato)
- gumroad 2026-11-15: vendite e visite non misurate (visits (non esposte dall'API))

## Non misurato
- gumroad: visits (non esposte dall'API)
- instagram: reach (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"Au3_XYnqyfgVKg_8BmaDVoG"}}); replies (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"APoAM3Z34Ihv5-RTXBltxmj"}}); shares (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"A2reCwtR65imU8_amtUDWSP"}}); total_interactions (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"AHz7AagczJT4zf5mP7zBUIE"}}); views (Meta API error 400: {"error":{"message":"(#10) Not enough viewers for the media to show insights","code":10,"type":"OAuthException","fbtrace_id":"AjXErkf0eQZmaJVMx-W8OFU"}})
- youtube: link_clicks (non esposto dalle API)

## Threads Insights (ultimo file inviato da Simone)

Fonte: schermate degli Insight di Threads inviate da Simone il 03/11/2026 (periodo come mostrato dall'app; i valori sono quelli dell'app, non verificati via API).

## Community principali dei follower
| Community | Account |
|---|---|
| Science Threads | 502 |
| Book Threads | 273 |
| History Threads | 156 |
| Space Threads | 143 |
| Cats of Threads | 132 |

## Paesi
- Australia 4,4%
- un altro paese 5,6% (nome non riportato)

## Momenti più attivi (ora italiana, CET)
| Giorno | Fascia | Account attivi |
|---|---|---|
| Venerdì | 19-22 | 2,1K |
| Giovedì | 22-01 | 2K |
| Mercoledì | 19-22 | 2K |

## Cosa ne fa l'automazione (ipotesi da misurare, non conclusioni)
- Il video delle 21:00 è già nella fascia migliore: resta alle 21:00 (stesso video su tutti i canali).
- Mercoledì-venerdì il quiz passa dalle 16:00 alle 17:55: è l'orario più tardo che rispetta le 3 ore prima del video delle 21:00 (massimo 3 post al giorno). Metrica: visualizzazioni e voti dei quiz mer-ven contro quelli degli altri giorni, su 3 settimane.
- I quiz usano il topic tag "Science" (la community più grande); news e video restano con il tag dell'argomento (Mars, Moon, JWST...) o "Space".
- Libri e storia dell'astronomia: idee per post futuri solo da fonti verificabili (es. ricorrenze NASA con pagina ufficiale), non ancora automatizzati.

## Analisi (Gemini, controllata dal codice)
### Interpretazione
- Dal 2026-11-07 al 2026-11-15, i YouTube Short guidano la distribuzione con 991 visualizzazioni nella settimana su 35 post totali (mediana 164 visualizzazioni).
- Su Threads, i post di testo hanno generato 1.949 visualizzazioni nella settimana con 11 nuovi post (mediana 40), superando i video che hanno ottenuto 707 visualizzazioni con 5 nuovi post (mediana 47).
- Su Instagram, i Reel registrano 556 visualizzazioni nella settimana su 19 post totali (mediana 135, tempo di visione mediano 6,9 s), ma gli acct_website_clicks sono passati solo da 0 a 1.
- Su Facebook la distribuzione è limitata (Reel con mediana 3 visualizzazioni e tempo di visione mediano 1,9 s); il formato photo rappresenta un campione troppo piccolo per trarre conclusioni (1 solo post totalizzato).
- L'impatto reale sul business resta ignoto: visite e vendite su Gumroad al 2026-11-15 non sono misurate dall'API, e i clic sui link di YouTube non sono esposti.

### Decisioni (ipotesi da testare)
- Nessuna decisione: Le visite e le vendite su Gumroad non sono misurate dall'API e i clic sui link di YouTube non sono esposti. Con un solo clic sul sito registrato da Instagram tra il 2026-11-07 e il 2026-11-15, i dati sul comportamento d'acquisto sono insufficienti per definire decisioni di business validate.

### Prossimo test utile
- Inserire un link tracciato UTM per LOOK UP nei commenti in evidenza dei YouTube Short e nella bio di Instagram per misurare i clic reali generati al prodotto per 14 giorni.

### Idee dai competitor
- Short su confronti numerici veloci tra corpi celesti (es. dati sul numero di lune per pianeta), ispirato ai video di comparazione più visti nella nicchia.
- Post di testo su Threads focalizzati su eventi astronomici del mese corrente sintetizzati in numeri, adattati al format essenziale del canale.
