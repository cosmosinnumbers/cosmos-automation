# Apprendimento da tutti i canali (2026-11-10)

Post letti: 72 (solo video: Short, Reel, video Threads/TikTok; almeno 12 ore di vita, ultimi 45 giorni), raggruppati in 36 contenuti (lo stesso video su più canali conta una volta).

Punteggio = volte la mediana del canale (1 = nella media). Instagram: views, tempo medio di visione, interazioni (salvataggi e condivisioni pesano di più); YouTube: views e % visto; Facebook, Threads, TikTok: views. Contenuto = media pesata dei canali (IG 30%, YT 30%, TikTok 15%, Threads 15%, FB 10%).

## Cosa ha funzionato
- **What a light-year really is**: 3.797x, 1187 views totali (instagram 4.84x, facebook 0.67x); temi: Luce, distanze e anni luce, Spiegone di un concetto; ore 21; 2026-11-03
- **NASA's Roman Telescope Got Sharper by Moving a Mirror**: 2.481x, 930 views totali (youtube 2.48x); temi: Telescopi; ore 20; 2026-10-22
- **The Moon Swings 295 °C in One Day. Here's Why**: 2.049x, 746 views totali (youtube 2.05x); temi: Estremi (temperatura, velocità), Pianeti e lune; ore 13; 2026-10-28
- **The Sun you see is 8 minutes old**: 2.034x, 371 views totali (threads 3.84x, youtube 1.13x); temi: Luce, distanze e anni luce; ore 21; 2026-11-06
- **Every Type of Planet We've Actually Found Beyond Our Solar System**: 1.924x, 94 views totali (youtube 1.92x); temi: Pianeti e lune; ore 20; 2026-10-14
- **The 5 Spacecraft Leaving Our Solar System — Where Are They Right Now?**: 1.852x, 45 views totali (youtube 1.85x); temi: Record e missioni; ore 20; 2026-10-21

## Cosa no
- The Sun Will Swell 200 Times Wider: How It All Ends: 0.155x, 6 views (Scala e dimensioni)
- The Nearest Star to the Sun Is Invisible to the Naked Eye: 0.442x, 25 views (Luce, distanze e anni luce, Galassie, nebulose, stelle)
- Why NASA Will Fly Past Europa 49 Times: 0.534x, 4 views (Record e missioni, Pianeti e lune, Spiegone di un concetto)
- The 10 Largest Moons, Ranked by JPL's Real Measurements: 0.614x, 34 views (Scala e dimensioni, Pianeti e lune)

## Regole dai dati (almeno 3 contenuti, differenza almeno 20%)
- NO: ore 16 (hour, -44%, n 3)
- SI: Domanda (hook, +34%, n 3)
- SI: Confronto di scala (format, +31%, n 8)
- SI: ore 20 (hour, +29%, n 8)
- NO: Scala e dimensioni (theme, -24%, n 5)
- SI: headline di 40 caratteri o meno (short_headline, +24%, n 9)
- NO: Galassie, nebulose, stelle (theme, -23%, n 7)
- NO: Notizia con un numero forte (format, -21%, n 4)
- NO: Numero estremo (hook, -21%, n 24)

## Temi (media ridotta verso 1 finché i dati sono pochi)
- Spiegone di un concetto: 1.357x su 5 contenuti
- Estremi (temperatura, velocità): 1.297x su 4 contenuti
- Luce, distanze e anni luce: 1.257x su 11 contenuti
- Telescopi: 1.237x su 6 contenuti
- Notizia del giorno: 1.179x su 6 contenuti
- Pianeti e lune: 1.071x su 19 contenuti
- Record e missioni: 1.004x su 7 contenuti
- Galassie, nebulose, stelle: 0.956x su 7 contenuti
- Scala e dimensioni: 0.931x su 5 contenuti

## Decisioni automatiche
- Prossimo video lungo: sulla scia di "The Sun you see is 8 minutes old" (2.034x). longform-auto lo usa come indicazione di argomento quando non ne riceve una.
- Clip del giorno: tools/day_clip.py sceglie la clip non usata con il punteggio previsto più alto (1 giorno su 5 prova il tema meno testato).
- Clip dei nuovi video lunghi: tools/auto_clips.py ordina i capitoli con gli stessi pesi.
- Lo scrittore dei video lunghi riceve i temi che vanno e quelli da evitare.

## Medie per canale

- youtube:short: 26 post, mediana views 226.0
- youtube:long: 7 post, mediana views 33
- instagram:reel: 15 post, mediana views 130
- facebook:reel: 16 post, mediana views 4.5
- threads:video: 8 post, mediana views 43.5
