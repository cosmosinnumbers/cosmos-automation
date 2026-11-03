# Definizioni delle metriche (07-analytics/metrics/)

Generato da `tools/ytf/metrics.py defs`. Ogni riga dei file `.jsonl` porta `read_at` (ora UTC di lettura) e `date`.
Una metrica rifiutata dall'API va in `missing` con il motivo: nei rapporti si scrive "non misurato", mai una stima.

## youtube

- `views`: Visualizzazioni totali dalla pubblicazione (Data API videos.statistics.viewCount; per gli Short YouTube conta ogni avvio, dal 31/03/2025).
- `likes`: Mi piace totali (Data API).
- `comments`: Commenti totali (Data API).
- `an_views`: Visualizzazioni dal 01/10/2026 a oggi secondo YouTube Analytics (possono differire da views per ritardo e filtri antispam).
- `minutes_watched`: Minuti di visione stimati (Analytics estimatedMinutesWatched).
- `avg_view_duration_s`: Durata media di visione in secondi (Analytics averageViewDuration).
- `avg_view_pct`: Percentuale media visualizzata (Analytics averageViewPercentage; per gli Short può superare 100 con le ripetizioni).
- `r5`: Quota di spettatori ancora presenti al 5% del video (curva di ritenzione, audienceWatchRatio; solo organico).
- `r25`: Quota ancora presente al 25% del video.
- `r50`: Quota ancora presente al 50% del video.
- `r75`: Quota ancora presente al 75% del video.
- `r100`: Quota ancora presente alla fine (per gli Short può superare 1 se si rivede).
- `worst_drop`: Calo massimo tra due punti consecutivi della curva (1% del video).
- `worst_drop_at_pct`: A che % del video avviene il calo massimo.
- `subs_gained`: Iscritti guadagnati dal video (Analytics subscribersGained).
- `shares`: Condivisioni (Analytics shares).
- `link_clicks`: Non esposti dalle API: i clic sui link in descrizione non sono misurati.

## instagram

- `views`: Visualizzazioni (Graph API insights 'views': volte in cui il contenuto è stato riprodotto o mostrato).
- `reach`: Account unici che hanno visto il contenuto (stima di Meta).
- `saved`: Salvataggi.
- `shares`: Condivisioni.
- `likes`: Mi piace.
- `comments`: Commenti.
- `total_interactions`: Somma di mi piace, salvataggi, commenti e condivisioni meno quelli annullati.
- `avg_watch_ms`: Reel: tempo medio di visione in millisecondi (ig_reels_avg_watch_time).
- `watch_total_ms`: Reel: tempo totale di visione in millisecondi (ig_reels_video_view_total_time).
- `replies`: Storie: risposte.
- `acct_profile_views`: Account: visite al profilo nel giorno precedente (profile_views, period=day).
- `acct_website_clicks`: Account: clic sul link del profilo nel giorno precedente (website_clicks).
- `acct_reach`: Account: copertura del giorno precedente.
- `acct_followers`: Account: follower totali (followers_count).

## facebook

- `views`: Reel: riproduzioni iniziali (blue_reels_play_count). Post e caroselli: visualizzazioni (post_media_view).
- `plays_total`: Reel: riproduzioni totali, ripetizioni incluse (fb_reels_total_plays).
- `reach`: Post e caroselli: persone uniche (post_total_media_view_unique). Per i Reel non esposta (post_impressions_unique non più valida).
- `clicks`: Post: clic sul post (post_clicks).
- `avg_watch_ms`: Reel: tempo medio di visione in millisecondi (post_video_avg_time_watched).
- `likes`: Mi piace.
- `comments`: Commenti.
- `shares`: Condivisioni.
- `acct_followers`: Pagina: follower totali (followers_count).
- `acct_page_views`: Pagina: visualizzazioni della Pagina del giorno precedente (page_views_total).

## threads

- `views`: Visualizzazioni del post (Threads insights 'views').
- `likes`: Mi piace.
- `replies`: Risposte.
- `reposts`: Repost.
- `quotes`: Citazioni.
- `shares`: Condivisioni.

## gumroad

- `sales`: Vendite totali del prodotto (Gumroad API products.sales_count).
- `revenue_usd`: Incasso lordo in dollari (products.sales_usd_cents / 100).
- `visits`: Visite alla pagina prodotto: non esposte dall'API, si leggono da Gumroad → Analytics (pagina, a mano o con Chrome).

## x

- Non letto: l'account è vuoto per scelta e la lettura via API è a pagamento.

## tiktok

- Non letto via API (nessuna app approvata): lettura settimanale da TikTok Studio, in `tiktok.jsonl` a mano.
