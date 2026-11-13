# Link nelle bio, controllo del 2026-11-13

Scritto da `tools/bio_links.py audit`: ogni testo di profilo letto con le API, ogni link aperto come farebbe un visitatore.

## YouTube (descrizione canale)

> 🆓 Free PDF, The Solar System in 20 Numbers: https://gum.co/u/7oa8ngql / 📘 LOOK UP, our beginner's stargazing guide: https://gum.co/u/bpy9bhug /  / Real space. Real data. /  / Cosmos in Numbers explains the universe using only real telescope and spacecraft images (NASA, ESA/Webb, ESA/Hubble) and public scientific data — the NASA Exoplanet Archive, JPL Horizons, NASA's planetary fact sheets — turned into our own charts. /  / No fake planets passed off as photos. Illustrations are always labelled "artist's concept". Every number has a source in the description, and if we get something wrong, we p

- `https://gum.co/u/7oa8ngql` → HTTP 200, arriva a `solar-system-20`, tracciato (solar-system-20/youtube/description), ATTENZIONE: pulsante d'acquisto non trovato
- `https://gum.co/u/bpy9bhug` → HTTP 200, arriva a `look-up`, tracciato (look-up/youtube/description), ATTENZIONE: pulsante d'acquisto non trovato
- Nota: i 'link del canale' sotto la descrizione non sono leggibili via API: vanno guardati in YouTube Studio

## Facebook (sito e informazioni)

> https://gum.co/u/olfuvkyy, https://gum.co/u/5lo91i50, https://cosmosinnumbers.github.io/, https://www.tiktok.com/@cosmosinnumbers, https://www.instagram.com/cosmos.innumbers/, https://cosmosinnumbers.github.io/links.html?src=fb, https://cosmosinnumbers.github.io/, https://www.tiktok.com/@cosmosinnumbers, https://www.instagram.com/cosmos.innumbers/, https://cosmosinnumbers.gumroad.com/l/look-up?layout=profile, https://cosmosinnumbers.gumroad.com/l/look-up?layout=profile | Real space. Real data. Space explainers from real NASA/ESA images and public data. Free PDF, The Solar System in 20 Numbers:

- `https://gum.co/u/olfuvkyy` → HTTP 200, arriva a `solar-system-20`, tracciato (solar-system-20/facebook/post), ATTENZIONE: pulsante d'acquisto non trovato
- `https://gum.co/u/5lo91i50` → HTTP 200, arriva a `look-up`, tracciato (look-up/facebook/post), ATTENZIONE: pulsante d'acquisto non trovato
- `https://cosmosinnumbers.github.io/` → HTTP 200, arriva a `https://cosmosinnumbers.github.io/`, NON tracciato
- `https://cosmosinnumbers.github.io/links.html?src=fb` → HTTP 200, arriva a `https://cosmosinnumbers.github.io/links.html?src=fb`, NON tracciato
- `https://cosmosinnumbers.gumroad.com/l/look-up?layout=profile` → HTTP 200, arriva a `look-up`, NON tracciato, ATTENZIONE: pulsante d'acquisto non trovato

## Instagram (bio e link)

> https://gum.co/u/ggvfi5il | Real space. Real data. 🔭 / Real NASA/ESA images + public data. / New videos every week. / Full videos on YouTube 👇 / youtube.com/@CosmosinNumbers

- `https://gum.co/u/ggvfi5il` → HTTP 200, arriva a `solar-system-20`, tracciato (solar-system-20/instagram/bio), ATTENZIONE: pulsante d'acquisto non trovato

## Threads (bio)

- NON LETTO: SystemExit: Missing credentials: secret THREADS_JSON or file /home/runner/work/cosmos-automation/Progetto-YouTube-Faceless/secrets/threads.json

## TikTok (bio e link)

> | Full videos on YouTube:CosmosinNumbers / https://youtube.com/@cosmosinnumbers /  / https://gum.co/u/8apaaidv

- `https://gum.co/u/8apaaidv` → HTTP 200, arriva a `solar-system-20`, tracciato (solar-system-20/tiktok/bio), ATTENZIONE: pulsante d'acquisto non trovato

## Sito: links.html

> (vuoto)

- **Nessun link Gumroad in questo testo.**

## Sito: home

> (vuoto)

- **Nessun link Gumroad in questo testo.**

## Tutti i link corti registrati

- PROBLEMA · look-up/youtube/description · https://gum.co/u/bpy9bhug → HTTP 200 `look-up`
- PROBLEMA · look-up/youtube/comment · https://gum.co/u/d4rfxslb → HTTP 200 `look-up`
- PROBLEMA · look-up/threads/reply · https://gum.co/u/ir34fzja → HTTP 200 `look-up`
- PROBLEMA · look-up/x/reply · https://gum.co/u/w8zoa3vp → HTTP 200 `look-up`
- PROBLEMA · look-up/instagram/bio · https://gum.co/u/6n4kmchn → HTTP 200 `look-up`
- PROBLEMA · look-up/tiktok/bio · https://gum.co/u/zyeqv1gx → HTTP 200 `look-up`
- PROBLEMA · look-up/facebook/post · https://gum.co/u/5lo91i50 → HTTP 200 `look-up`
- PROBLEMA · look-up/github-pages/site · https://gum.co/u/evqinpnd → HTTP 200 `look-up`
- PROBLEMA · solar-system-20/youtube/description · https://gum.co/u/7oa8ngql → HTTP 200 `solar-system-20`
- PROBLEMA · solar-system-20/youtube/comment · https://gum.co/u/vgs5fiqx → HTTP 200 `solar-system-20`
- PROBLEMA · solar-system-20/threads/reply · https://gum.co/u/5rztvjeu → HTTP 200 `solar-system-20`
- PROBLEMA · solar-system-20/x/reply · https://gum.co/u/gflpac3d → HTTP 200 `solar-system-20`
- PROBLEMA · solar-system-20/instagram/bio · https://gum.co/u/ggvfi5il → HTTP 200 `solar-system-20`
- PROBLEMA · solar-system-20/tiktok/bio · https://gum.co/u/8apaaidv → HTTP 200 `solar-system-20`
- PROBLEMA · solar-system-20/facebook/post · https://gum.co/u/olfuvkyy → HTTP 200 `solar-system-20`
- PROBLEMA · solar-system-20/github-pages/site · https://gum.co/u/i0meheaa → HTTP 200 `solar-system-20`
- PROBLEMA · sky-30-nights/youtube/description · https://gum.co/u/mqmpfhio → HTTP 200 `sky-30-nights`
- PROBLEMA · sky-30-nights/youtube/comment · https://gum.co/u/diur8ufn → HTTP 200 `sky-30-nights`
- PROBLEMA · sky-30-nights/threads/reply · https://gum.co/u/39bdcdob → HTTP 200 `sky-30-nights`
- PROBLEMA · sky-30-nights/x/reply · https://gum.co/u/wudzes1w → HTTP 200 `sky-30-nights`
- PROBLEMA · sky-30-nights/instagram/bio · https://gum.co/u/nhyrnvfl → HTTP 200 `sky-30-nights`
- PROBLEMA · sky-30-nights/tiktok/bio · https://gum.co/u/efbugyb1 → HTTP 200 `sky-30-nights`
- PROBLEMA · sky-30-nights/facebook/post · https://gum.co/u/p5up3vuy → HTTP 200 `sky-30-nights`
- PROBLEMA · sky-30-nights/github-pages/site · https://gum.co/u/uuqdh665 → HTTP 200 `sky-30-nights`
