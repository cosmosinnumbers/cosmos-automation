# Apprendimento da tutti i canali (2026-11-05)

Post letti: 61 (solo video: Short, Reel, video Threads/TikTok; almeno 12 ore di vita, ultimi 45 giorni), raggruppati in 32 contenuti (lo stesso video su più canali conta una volta).

Punteggio = volte la mediana del canale (1 = nella media). Instagram: views, tempo medio di visione, interazioni (salvataggi e condivisioni pesano di più); YouTube: views e % visto; Facebook, Threads, TikTok: views. Contenuto = media pesata dei canali (IG 30%, YT 30%, TikTok 15%, Threads 15%, FB 10%).

## Cosa ha funzionato
- **What a light-year really is**: 3.723x, 1179 views totali (instagram 4.84x, facebook 0.36x); temi: Luce, distanze e anni luce, Spiegone di un concetto; ore 21; 2026-11-03
- **NASA's Roman Telescope Got Sharper by Moving a Mirror**: 2.368x, 928 views totali (youtube 2.37x); temi: Telescopi; ore 20; 2026-10-22
- **The Moon Swings 295 °C in One Day. Here's Why**: 1.96x, 745 views totali (youtube 1.96x); temi: Estremi (temperatura, velocità), Pianeti e lune; ore 13; 2026-10-28
- **Every Type of Planet We've Actually Found Beyond Our Solar System**: 1.73x, 93 views totali (youtube 1.73x); temi: Pianeti e lune; ore 20; 2026-10-14
- **11 Earths Fit Across Jupiter**: 1.577x, 1086 views totali (youtube 2.48x, facebook 1.09x, instagram 0.84x); temi: Scala e dimensioni, Pianeti e lune, Notizia del giorno; ore 20; 2026-10-23
- **Perseverance Just Broke the Record for Driving on Another World**: 1.454x, 444 views totali (youtube 0.82x, instagram 2.09x); temi: Record e missioni, Notizia del giorno; ore 21; 2026-10-27

## Cosa no
- The Moon you see is 1.3 seconds old: 0.362x, 87 views (Luce, distanze e anni luce, Pianeti e lune)
- The Nearest Star to the Sun Is Invisible to the Naked Eye: 0.428x, 23 views (Luce, distanze e anni luce, Galassie, nebulose, stelle)
- The 10 Largest Moons, Ranked by JPL's Real Measurements: 0.49x, 30 views (Scala e dimensioni, Pianeti e lune)
- NASA's Perseverance rover has now driven 45.22 km on Mars: the longest drive ever on anoth: 0.545x, 3 views (Record e missioni, Pianeti e lune)

## Regole dai dati (almeno 3 contenuti, differenza almeno 20%)
- SI: Spiegone di un concetto (theme, +56%, n 3)
- SI: ore 20 (hour, +36%, n 6)
- SI: Confronto di scala (format, +33%, n 6)
- NO: Numero estremo (hook, -24%, n 21)
- SI: headline di 40 caratteri o meno (short_headline, +22%, n 7)
- NO: Galassie, nebulose, stelle (theme, -20%, n 7)

## Temi (media ridotta verso 1 finché i dati sono pochi)
- Spiegone di un concetto: 1.619x su 3 contenuti
- Estremi (temperatura, velocità): 1.226x su 4 contenuti
- Telescopi: 1.16x su 6 contenuti
- Luce, distanze e anni luce: 1.143x su 9 contenuti
- Notizia del giorno: 1.108x su 6 contenuti
- Record e missioni: 1.016x su 5 contenuti
- Scala e dimensioni: 1.015x su 4 contenuti
- Pianeti e lune: 1.004x su 17 contenuti
- Galassie, nebulose, stelle: 0.942x su 7 contenuti

## Decisioni automatiche
- Prossimo video lungo: sulla scia di "What a light-year really is" (3.723x). longform-auto lo usa come indicazione di argomento quando non ne riceve una.
- Clip del giorno: tools/day_clip.py sceglie la clip non usata con il punteggio previsto più alto (1 giorno su 5 prova il tema meno testato).
- Clip dei nuovi video lunghi: tools/auto_clips.py ordina i capitoli con gli stessi pesi.
- Lo scrittore dei video lunghi riceve i temi che vanno e quelli da evitare.

## Medie per canale

- youtube:short: 23 post, mediana views 240
- youtube:long: 5 post, mediana views 33
- instagram:reel: 13 post, mediana views 130
- facebook:reel: 14 post, mediana views 5.5
- threads:video: 6 post, mediana views 41.5
