# Apprendimento da tutti i canali (2026-11-06)

Post letti: 65 (solo video: Short, Reel, video Threads/TikTok; almeno 12 ore di vita, ultimi 45 giorni), raggruppati in 33 contenuti (lo stesso video su più canali conta una volta).

Punteggio = volte la mediana del canale (1 = nella media). Instagram: views, tempo medio di visione, interazioni (salvataggi e condivisioni pesano di più); YouTube: views e % visto; Facebook, Threads, TikTok: views. Contenuto = media pesata dei canali (IG 30%, YT 30%, TikTok 15%, Threads 15%, FB 10%).

## Cosa ha funzionato
- **What a light-year really is**: 3.788x, 1184 views totali (instagram 4.85x, facebook 0.6x); temi: Luce, distanze e anni luce, Spiegone di un concetto; ore 21; 2026-11-03
- **NASA's Roman Telescope Got Sharper by Moving a Mirror**: 2.385x, 929 views totali (youtube 2.38x); temi: Telescopi; ore 20; 2026-10-22
- **The Moon Swings 295 °C in One Day. Here's Why**: 1.971x, 745 views totali (youtube 1.97x); temi: Estremi (temperatura, velocità), Pianeti e lune; ore 13; 2026-10-28
- **Why Is Venus Hotter Than Mercury?**: 1.808x, 404 views totali (facebook 1.6x, instagram 1.23x, threads 5.26x, youtube 0.73x); temi: Estremi (temperatura, velocità), Pianeti e lune, Spiegone di un concetto; ore 13; 2026-10-15
- **Every Type of Planet We've Actually Found Beyond Our Solar System**: 1.756x, 94 views totali (youtube 1.76x); temi: Pianeti e lune; ore 20; 2026-10-14
- **Webb Found the Home of the Farthest Radio Burst Ever Seen**: 1.646x, 492 views totali (facebook 1.6x, instagram 0.82x, threads 4.37x, youtube 1.12x); temi: Luce, distanze e anni luce, Galassie, nebulose, stelle, Telescopi; ore 12; 2026-10-15

## Cosa no
- The Nearest Star to the Sun Is Invisible to the Naked Eye: 0.423x, 23 views (Luce, distanze e anni luce, Galassie, nebulose, stelle)
- The 10 Largest Moons, Ranked by JPL's Real Measurements: 0.56x, 32 views (Scala e dimensioni, Pianeti e lune)
- NASA's Perseverance rover has now driven 45.22 km on Mars: the longest drive ever on anoth: 0.6x, 3 views (Record e missioni, Pianeti e lune)
- The Moon you see is 1.3 seconds old: 0.608x, 230 views (Luce, distanze e anni luce, Pianeti e lune)

## Regole dai dati (almeno 3 contenuti, differenza almeno 20%)
- SI: Spiegone di un concetto (theme, +40%, n 4)
- SI: Domanda (hook, +27%, n 3)
- SI: headline di 40 caratteri o meno (short_headline, +27%, n 7)
- SI: ore 20 (hour, +23%, n 7)
- NO: Paradosso (hook, -21%, n 3)
- NO: headline lunga (short_headline, -21%, n 26)
- NO: Record e missioni (theme, -20%, n 6)
- SI: Confronto di scala (format, +20%, n 7)

## Temi (media ridotta verso 1 finché i dati sono pochi)
- Spiegone di un concetto: 1.551x su 4 contenuti
- Estremi (temperatura, velocità): 1.318x su 4 contenuti
- Telescopi: 1.284x su 6 contenuti
- Notizia del giorno: 1.176x su 6 contenuti
- Luce, distanze e anni luce: 1.165x su 10 contenuti
- Scala e dimensioni: 1.09x su 4 contenuti
- Pianeti e lune: 1.059x su 18 contenuti
- Galassie, nebulose, stelle: 1.03x su 7 contenuti
- Record e missioni: 0.981x su 6 contenuti

## Decisioni automatiche
- Prossimo video lungo: sulla scia di "What a light-year really is" (3.788x). longform-auto lo usa come indicazione di argomento quando non ne riceve una.
- Clip del giorno: tools/day_clip.py sceglie la clip non usata con il punteggio previsto più alto (1 giorno su 5 prova il tema meno testato).
- Clip dei nuovi video lunghi: tools/auto_clips.py ordina i capitoli con gli stessi pesi.
- Lo scrittore dei video lunghi riceve i temi che vanno e quelli da evitare.

## Medie per canale

- youtube:short: 24 post, mediana views 237.5
- youtube:long: 5 post, mediana views 33
- instagram:reel: 14 post, mediana views 129.5
- facebook:reel: 15 post, mediana views 5
- threads:video: 7 post, mediana views 19
