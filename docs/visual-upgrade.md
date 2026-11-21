# Video più visual: analisi e scelte (15-16/11/2026)

Richiesta di simone: video prima di tutto virali, "più visual subito", guardare tool/repo e cosa fa la nicchia.

## Cosa non andava (misurato sui nostri Short)
- Il filmato occupava 900 px su 1920: metà schermo era fascia scura. Le foto quadrate ancora meno.
- Primo fotogramma = una scheda grafica (telefono) o una clip generica NASA, non il soggetto della storia.
- Clip fuori tema: "This Week @NASA" e "What's Up" portano sigle, loghi e persone che parlano.
- Scene grafiche su fondo blu piatto: ogni scena "usciva" dal filmato.
- Fino a 10,8 s senza uno stacco (obiettivo del QC: 6 s).

## Cosa fanno i canali che funzionano nella nicchia (fonti: guide e analisi pubbliche, numeri indicativi)
- Immagine a tutto schermo dal primo fotogramma; voce + testo + immagine insieme nell'aggancio.
- Decisione di restare o scorrere in circa 2 secondi: l'aggancio deve mostrare il soggetto, non un'introduzione.
- Nuovo materiale visivo ogni 3-5 s, tagli a tempo con la musica; sottotitoli sempre (molti guardano senza audio).
- Durata corta (15-45 s): non allungare uno script che regge in 25 s.
- Lo spazio funziona perché le immagini sono "impossibili da filmare": telescopi (Webb, Hubble, Chandra) e confronti
  di scala battono il filmato generico.
Limite: sono blog di chi vende strumenti video, non dati di YouTube. La verifica vera è la nostra ritenzione
(`reports/retention-diagnosi.md`, `reports/esperimenti-*.md`) nelle prossime 2 settimane.

## Tool e repo guardati
| Progetto | Cosa fa | Decisione |
|---|---|---|
| Remotion | video in React, già il nostro motore (16 scene) | resta la base |
| OpenMontage, OpenReels, short-video-maker, OpenCut | pipeline "argomento -> Short" con Remotion e sottotitoli a parola | stessa architettura della nostra: presi i pattern (sottotitoli a parola, tutto schermo), non il codice |
| DepthFlow | parallasse 2.5D da una foto (mappa di profondità) | no per ora: AGPL e serve GPU, i runner GitHub non ce l'hanno |
| Modelli video IA (text-to-video) | filmati generati | no: a pagamento, e su YouTube vogliamo solo materiale libero e vero |
Il collo di bottiglia non era lo strumento ma l'impaginazione e la scelta del materiale: corretti nel nostro codice.

## Fatto in questa PR
Vedi `docs/motion-graphics.md`, sezione "Short a tutto schermo". Esempio prima/dopo sullo stesso Short
(a1114, stessa voce): QC 92 -> 100, stacchi 44 -> 58, pausa massima 10,8 -> 5,4 s.

## Prossimi passi possibili
1. Clip dei lunghi (Reel IG/FB delle 21:00): riquadro più grande o ritaglio 4:5 quando la scena non ha grafiche ai bordi.
2. Clip NASA a 1080p (ora 720p: a tutto schermo sono un po' morbide) e più fonti libere (ESA/Webb, ESO, NOIRLab).
3. Altre scene "in numeri": righello delle distanze, confronto di dimensioni in scala, orbite.
4. Misurare: ritenzione a 3 s e media degli Short dal 16/11 contro i 14 giorni prima.

## 21/11/2026: Short puliti, niente testo fisso

Richiesta di simone (screenshot della scheda Short): "I like more clean thumbnails like the purple one, full screen
video, and don't put any label that stays in the video".

- Clip dai lunghi (`video/ytf/clip.py` → `clip_full.py`, layout predefinito): immagine a tutto schermo 9:16, niente
  titolo fisso in alto, niente riquadro 16:9 né fascia di testo. Le schermate grafiche del lungo (card navy, grafici
  a punti) sono coperte dalle foto/filmati NASA del lungo (`assets.yaml`, solo soggetti nominati nella clip). Il
  sottopancia "CHAPTER" e i crediti del lungo restano fuori dall'inquadratura. Il titolo compare solo nell'apertura
  di 1,7 s; poi solo sottotitoli a ritmo con la voce e la barra di avanzamento. `CLIP_LAYOUT=box` = vecchio look.
- Short notizia (`fullbleed.py`): il titolo e il badge "NASA · NEW" spariscono dopo ~2,5 s; "ARTIST'S CONCEPT" e
  crediti solo nei primi secondi della loro immagine.
- Copertina Reel (`tools/reel_cover.py`): fotogramma nitido a tutto schermo + solo il titolo.
- Bug corretto: `caption_chunks` univa male l'ultima parola (`groups[-2] = groups[-2] + groups.pop()` scrive sul
  gruppo sbagliato), negli Short notizia uscivano parole doppie o mancanti nei sottotitoli.
- Le clip già tagliate nelle release restano col vecchio look finché non si rilancia `long-clips` con `recut: all`.
