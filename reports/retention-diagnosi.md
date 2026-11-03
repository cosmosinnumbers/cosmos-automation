# Diagnosi ritenzione (Fase A) – 3/11/2026

Fonte: `07-analytics/metrics/youtube.jsonl` (YouTube Analytics, ultima lettura).

## Shorts (17 con analytics)
- Visualizzazioni mediane: 240. Percentuale media vista mediana: 60,7 %. Durata 30–41 s.
- Migliori: «Earth's fit across Jupiter» 955 views (59,3 %), «Roman Telescope» 927 (52,5 %), «Moon swings 295 °C» 744 (49,6 %).
- Peggiori: «Voyager 1 light-day» 16 (44 %), «Nearest Star» 22 (46 %).
- Lettura: vincono i titoli con una stranezza concreta o un confronto di scala (Terra/Giove, 295 °C). La ritenzione non spiega le views: la differenza sta nel gancio e nel titolo (scroll stop), non nella parte centrale.
- Obiettivo: «viewed» ≥ 75 % e durata media > 100 % con loop. Oggi siamo a ~60 %.

## Lunghi (4, 8–9 min)
- Views 17–89, percentuale media vista 13,6–30,9 %. Obiettivo ≥ 40 % e CTR ≥ 5 %.
- Lettura: perdita grossa nei primi minuti; servono hook forte, capitoli con micro-gancio e cambio visivo ogni 3–5 s.

## Iscritti
- Guadagno trascurabile: nessuna call-to-action legata al contenuto.

## Cosa mancava
Non esisteva la curva di ritenzione per video. Dal 3/11 `metrics.py` la legge (`audienceWatchRatio`) e salva:
- in `07-analytics/metrics/youtube.jsonl`: r5, r25, r50, r75, r100, worst_drop, worst_drop_at_pct;
- in `logs/video-metrics.jsonl`: curva completa (100 punti) per video.
Richiede lo scope yt-analytics già in uso (secret YOUTUBE_ANALYTICS_TOKEN_JSON).

## Azioni per le fasi successive
1. B: Short con una sola idea, max 2 numeri, hook ≤ 12 parole, loop aperto e ultima riga che chiude il loop.
2. C: immagini pertinenti al tema (niente clip NASA generiche) e scene motion di riserva.
3. D: QC automatico prima della pubblicazione.
4. E/F: critico dei lunghi, capitoli, ciclo di apprendimento settimanale basato sulle curve.
