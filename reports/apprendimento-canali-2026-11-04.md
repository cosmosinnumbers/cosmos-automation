# Apprendimento da tutti i canali (2026-11-04)

Post letti: 60 (solo video: Short, Reel, video Threads/TikTok; almeno 12 ore di vita, ultimi 45 giorni), raggruppati in 31 contenuti (lo stesso video su più canali conta una volta).

Punteggio = volte la mediana del canale (1 = nella media). Instagram: views, tempo medio di visione, interazioni (salvataggi e condivisioni pesano di più); YouTube: views e % visto; Facebook, Threads, TikTok: views. Contenuto = media pesata dei canali (IG 30%, YT 30%, TikTok 15%, Threads 15%, FB 10%).

## Cosa ha funzionato
- **What a light-year really is**: 3.722x, 1174 views totali (instagram 4.84x, facebook 0.36x); temi: Luce, distanze e anni luce, Spiegone di un concetto; ore 21; 2026-11-03
- **NASA's Roman Telescope Got Sharper by Moving a Mirror**: 2.36x, 928 views totali (youtube 2.36x); temi: Telescopi; ore 20; 2026-10-22
- **The Moon Swings 295 °C in One Day. Here's Why**: 1.953x, 745 views totali (youtube 1.95x); temi: Estremi (temperatura, velocità), Pianeti e lune; ore 13; 2026-10-28
- **Every Type of Planet We've Actually Found Beyond Our Solar System**: 1.699x, 91 views totali (youtube 1.7x); temi: Pianeti e lune; ore 20; 2026-10-14
- **11 Earths Fit Across Jupiter**: 1.574x, 1086 views totali (youtube 2.47x, facebook 1.09x, instagram 0.84x); temi: Scala e dimensioni, Pianeti e lune, Notizia del giorno; ore 20; 2026-10-23
- **Perseverance Just Broke the Record for Driving on Another World**: 1.454x, 444 views totali (youtube 0.82x, instagram 2.09x); temi: Record e missioni, Notizia del giorno; ore 21; 2026-10-27

## Cosa no
- The Nearest Star to the Sun Is Invisible to the Naked Eye: 0.427x, 23 views (Luce, distanze e anni luce, Galassie, nebulose, stelle)
- The 10 Largest Moons, Ranked by JPL's Real Measurements: 0.46x, 28 views (Scala e dimensioni, Pianeti e lune)
- NASA's Perseverance rover has now driven 45.22 km on Mars: the longest drive ever on anoth: 0.545x, 3 views (Record e missioni, Pianeti e lune)
- 754 Giant Planets Circle Their Star in Under 10 Days: 0.677x, 34 views (Galassie, nebulose, stelle, Pianeti e lune)

## Regole dai dati (almeno 3 contenuti, differenza almeno 20%)
- SI: Spiegone di un concetto (theme, +53%, n 3)
- SI: headline di 40 caratteri o meno (short_headline, +34%, n 6)
- SI: ore 20 (hour, +32%, n 6)
- SI: Confronto di scala (format, +30%, n 6)
- NO: headline lunga (short_headline, -25%, n 25)
- NO: Numero estremo (hook, -22%, n 20)
- NO: Galassie, nebulose, stelle (theme, -22%, n 7)

## Temi (media ridotta verso 1 finché i dati sono pochi)
- Spiegone di un concetto: 1.62x su 3 contenuti
- Estremi (temperatura, velocità): 1.226x su 4 contenuti
- Luce, distanze e anni luce: 1.221x su 8 contenuti
- Telescopi: 1.157x su 6 contenuti
- Notizia del giorno: 1.104x su 6 contenuti
- Pianeti e lune: 1.037x su 16 contenuti
- Record e missioni: 1.016x su 5 contenuti
- Scala e dimensioni: 1.01x su 4 contenuti
- Galassie, nebulose, stelle: 0.943x su 7 contenuti

## Decisioni automatiche
- Prossimo video lungo: sulla scia di "What a light-year really is" (3.722x). longform-auto lo usa come indicazione di argomento quando non ne riceve una.
- Clip del giorno: tools/day_clip.py sceglie la clip non usata con il punteggio previsto più alto (1 giorno su 5 prova il tema meno testato).
- Clip dei nuovi video lunghi: tools/auto_clips.py ordina i capitoli con gli stessi pesi.
- Lo scrittore dei video lunghi riceve i temi che vanno e quelli da evitare.

## Medie per canale

- youtube:short: 22 post, mediana views 241.0
- youtube:long: 5 post, mediana views 33
- instagram:reel: 13 post, mediana views 130
- facebook:reel: 14 post, mediana views 5.5
- threads:video: 6 post, mediana views 40.5
