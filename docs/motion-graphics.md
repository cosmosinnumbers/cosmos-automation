# Motion graphics e sound design dei video (02/11/2026)

Richiesta di simone: video "bellissimi", con gli 11 effetti del reel, tutto su GitHub Actions; poi sound design
automatico (Openverse → suoni al frame giusto → sintesi in codice) e una variante per gli altri social.

## Cosa cambia nei video
- **Short (1080x1920)**: hook animato nel primo secondo e mezzo, sfondo con il video sfocato al posto delle bande
  blu vuote, titolo che entra, sottotitoli grandi con la parola detta in arancione, barra di avanzamento,
  1-3 scene animate a metà scelte dal contenuto, transizioni tra le clip, chiusura con il telefono che mostra
  LOOK UP e una riga digitata ("follow + LOOK UP in bio"). A schermo **nessun codice sconto** (lo stesso file
  va su TikTok); COSMOS9 resta nella descrizione YouTube/Meta come prima.
- **Video lunghi (1920x1080)**: hook animato, contatori trasformati in dashboard Charts, frasi brevi in Paper Cut,
  frasi-shock con numero in Vertigo, colpo di scena a metà con Frame Break, quadro d'insieme con Pullback, titoli
  delle fonti in Headlines, glitch/zoom-through ai cambi capitolo, telefono con LOOK UP sulla chiusura.
  I clip verticali presi dai lunghi (clip.py) ereditano tutto.

## Gli 11 effetti (`motion/src/scenes/`, Remotion 4.0.536)
| # | Effetto | Quando lo usa il regista (`video/ytf/director.py`) |
|---|---|---|
| 01 | Orbit | primo 1,8 s di ogni video (hook), etichetta con l'agenzia della fonte |
| 02 | Vertigo | frase con numero e parola "shock" (times, record, largest, billion...) |
| 03 | Zoom-through | tagli tra clip e cambi capitolo |
| 04 | Headlines | 2+ fonti primarie e niente altro adatto a metà video: i titoli veri delle fonti |
| 05 | Paper Cut | frase breve a metà video, parole a tempo con la voce |
| 06 | Charts | la prima frase con un numero vero (no anni, no nomi tipo X-59) |
| 07 | Phone Screens | chiusura: il prodotto Gumroad su un telefono, etichette ai lati |
| 08 | Frame Break | frase di contrasto (but, however, actually, turns out...) |
| 09 | Pullback | frase "quadro d'insieme" (whole, entire, total, system...) |
| 10 | Glitch | taglio prima di una frase di contrasto |
| 11 | Typewriter | ultima riga, invito a seguire + link in bio |

Le card delle scene mostrano fotogrammi del nostro stesso materiale NASA/ESA; personaggi, telefono, copertina di
LOOK UP e grafiche sono disegnati in codice. Tema `brand: cosmos` o `brand: companies` (palette Companies in
Numbers) nello script.yaml / short.yaml; `motion: false` spegne gli effetti per un video.

Se Node o Chrome non partono in Actions, il video esce lo stesso senza scene (mai uno Short perso per un effetto).
Tempo in più per uno Short: circa 1 minuto.

## Suoni (`video/ytf/sfx.py`)
1. Libreria: `tools/sfx_library.py` (workflow `sfx-library`, mensile o a mano) cerca su Openverse **solo CC0**,
   scarica, normalizza in `assets/sfx/openverse/` e registra titolo, autore, pagina e licenza in `library.json`.
2. Posizionamento: ogni evento visivo diventa un suono al frame esatto (whoosh sull'entrata, impatto sul colpo,
   click per ogni tasto del Typewriter e per ogni parola del Paper Cut, vetri sul Frame Break, ding quando il
   contatore arriva...), con livelli per tipo sotto la voce.
3. Sintesi: i tipi senza file CC0 vengono generati in codice (whoosh, impact, riser, glitch, key, pop, slap,
   shatter, ding, shimmer, tick).
Volume finale -14 LUFS come prima.

## Variante social (`assets/social/`)
Suoni di tendenza per IG/FB/TikTok in `assets/social/sounds/`: lo Short esce anche come `<id>_social.mp4` con quel
suono al posto della musica generata. YouTube prende sempre e solo il file principale. Dettagli e rischi in
`assets/social/README.md`.

## Prova in locale
    cd motion && npm ci
    python video/ytf/short.py <cartella_short> --reuse-voice
Anteprima delle scene: `cd motion && npx remotion studio src/index.jsx` (serve `@remotion/cli`).
Licenza Remotion: gratuita per persone singole e aziende fino a 3 dipendenti.
