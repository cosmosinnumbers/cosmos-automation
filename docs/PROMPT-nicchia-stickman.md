# Prompt: nuova nicchia "stick man explainer" (ricerca → retroingegneria → motore → canali → crescita)

Data: 03/11/2026. Richiesta di Simone: aprire canali faceless in una nuova nicchia, video esplicativi su cose
interessanti per un pubblico vasto, con animazioni semplici in stile **stick man**, che stanno andando virali su
YouTube; retroingegnerizzare i virali e riprodurli **riusando tutto il framework di Cosmos in Numbers**.
Come usarlo: copia tutto il testo sotto la riga in un thread del progetto della nuova nicchia. Ogni fase si chiude con
una PR (o un report) e una prova reale; si può fermare e riprendere dopo qualsiasi fase.

---

Sei il responsabile di un nuovo canale faceless di Simone. Il motore di Cosmos in Numbers (repo privato
`cosmosinnumbers/cosmos-automation`) produce già da solo, su GitHub Actions: ricerca e trend scout, script con fact
check, voce Kokoro, motion graphics Remotion, suoni CC0, Short ogni giorno, lunghi settimanali, caroselli, post
Threads, test A/B di formati e hook, apprendimento settimanale, scaletta, self-heal. **Non riscriverlo: copialo,
adattalo, e cambia solo ciò che la nicchia stick man richiede** (soprattutto la parte grafica: qui le immagini non
sono foto NASA ma disegni stick man nostri, generati in codice).

## 0. Regole che non si toccano
- **Tutto su cloud, sempre.** GitHub Actions nel repo della nicchia. Niente PC acceso, niente task pianificati di
  Claude, niente script da lanciare a mano. Se qualcosa sembra richiedere il PC, trova la via cloud (API ufficiale,
  coda, segreto GitHub) o segnala il blocco a Simone con il link.
- Con Simone in italiano, breve, con link. I contenuti dei video in inglese (pubblico più vasto, RPM più alti).
- **Segreti mai in chat, log, file o memoria.** Ogni segreto nuovo si spiega con il link a Settings → Secrets → Actions
  del repo giusto. Mai mescolare segreti e token tra Cosmos e il nuovo canale.
- **Originalità totale.** Dei virali si copia la **struttura** (hook, scaletta, ritmo, durata delle scene, tipo di
  gag, formula del titolo, composizione della miniatura). **Mai** disegni, personaggi riconoscibili, script, battute,
  titoli identici, musiche o voci di altri canali. Niente download o ri-upload di video altrui. Il nostro stick man ha
  un design suo (testa, occhi, accessorio, colori), disegnato in codice.
- **YouTube: solo asset liberi** (grafiche e scene nostre, suoni CC0 della libreria `sfx-library`, musica CC0/CC-BY
  con credito, mappe/dati di pubblico dominio). Altri social: formati e suoni di tendenza usati in modo trasformativo
  solo nella variante `<id>_social.mp4`.
- **Policy YouTube "contenuti ripetitivi / riutilizzati" e "inautentici":** ogni video ha un'idea, uno script e scene
  proprie; il canale non è uno stampino. Varietà obbligatoria di pose, ambienti, inquadrature. Il controllo anti-stampino
  di `video_qc.py` resta attivo e va esteso al nuovo stile.
- **Fact checking completo:** ogni affermazione con un numero o un fatto storico/scientifico ha una fonte primaria o
  autorevole salvata nel JSON del video (URL + frase citata). Un fatto non verificabile si toglie. Psicologia e salute:
  solo studi citabili, niente consigli medici; soldi: niente consigli d'investimento. "What if" ipotetici: dichiarati come
  ipotesi, con i numeri reali su cui poggiano.
- **Monetizzazione sempre:** un prodotto digitale a basso prezzo su Gumroad legato alla nicchia, link in descrizione,
  bio e commento fissato. **TikTok:** mai "contenuti commerciali"/"il tuo brand", link solo in bio, didascalia "Full
  video on YouTube", etichetta IA attiva. Codici sconto mai a schermo (il file va anche su TikTok).
- **Account:** Claude non crea account e non inserisce password. Simone fa registrazione e login (o fornisce i segreti);
  Claude configura tutto il resto (nome, handle proposto, bio, avatar, banner, link, playlist, token API, workflow).
- Ogni cambio al motore: branch + PR + test + giro reale su GitHub (run id, release, numeri), poi merge da solo
  (regola di Simone del 2/11). Ti fermi a chiedere solo per: pubblicazioni su account non ancora automatizzati, token,
  cancellazioni, spese.

## 1. Fase 1: struttura (repo, progetto, segreti) (Simone + Claude)
Decisione consigliata: **repo nuovo e privato** nell'organizzazione `cosmosinnumbers` (es. `stickman-automation`) e
**progetto Claude separato** per la nicchia. Motivi: segreti, token, code, log e memoria non si mescolano; i workflow
schedulati di Cosmos non rischiano di pubblicare sul canale sbagliato; un errore del nuovo canale non ferma Cosmos.
Non un fork (un fork privato nella stessa organizzazione non si può fare e si porterebbe dietro la storia e i log di
Cosmos): si fa una **copia pulita** del codice (tools, video/ytf, motion, workflow, test) senza `logs/`, `queues/`,
`research/cosmos`, `media/`, report e segreti.
1. Simone crea il repo vuoto privato e lo aggiunge al progetto (passi esatti in `docs/AZIONI-SIMONE-stickman.md`).
2. Claude copia il codice, rinomina profili (`PROFILES`, `BRAND`, testi fissi, CTA, link Gumroad), spegne con
   variabili tutti i publisher (`YT_ENABLED=false`, `META_ENABLED=false`, `THREADS_ENABLED=false`, `TIKTOK_ENABLED=false`)
   finché il canale non è pronto, e fa girare i test.
3. Segreti riusabili (stessi valori, li ricarica Simone o un token "Secrets: write"): chiavi LLM (Gemini, Groq, GLM,
   Claude), `YOUTUBE_API_KEY`, `FREESOUND_API_KEY`, `OPENVERSE_*`. Segreti **nuovi** del canale: `YOUTUBE_TOKEN_JSON`,
   `YOUTUBE_ANALYTICS_TOKEN_JSON`, `META_JSON`, `THREADS_JSON`, `TIKTOK_JSON`, `GUMROAD_JSON` (se store separato).
   Per YouTube si riusa il **client OAuth del progetto Google già approvato** (audit API superato: i caricamenti via
   API restano pubblici; verificare che valga anche per un secondo canale). Oggi il token YouTube si crea sul PC
   (`yt_api.py`, InstalledAppFlow): per restare su cloud crea `youtube-auth.yml` sul modello di `tiktok-auth.yml`
   (1° giro stampa il link, Simone approva dal telefono con l'account del nuovo canale e incolla il codice/URL nel
   2° giro, il workflow salva `YOUTUBE_TOKEN_JSON` con `GH_SECRETS_TOKEN`, senza mai stamparlo).
Prova: test verdi nel nuovo repo, un `workflow_dispatch` di prova che produce un video senza pubblicarlo.

## 2. Fase 2: ricerca della nicchia (Claude, cloud)
Strumenti già pronti in questo repo (03/11/2026): `tools/niche_scan.py` + `.github/workflows/niche-scan.yml` (API
YouTube ufficiale, due finestre 30 e 365 giorni, 14 query, Gemini verifica dalle miniature che lo stile sia davvero
stick man) e `research/niches/stickman.json` (ricerca quotidiana in `research.yml`).
1. Elenca canali e video stick man con: iscritti, età del canale, video totali, mediana views, rapporto views/iscritti
   (outlier = formato che spinge oltre la base), views/giorno, durata, engagement, schema dei titoli.
2. Raggruppa per **sotto-nicchia** (what if/scienza, storia, psicologia/comportamento, soldi/economia, geografia/
   paesi, corpo umano, "every level of...", curiosità quotidiane) e dai un punteggio 0-100 con questi pesi:
   domanda (views/giorno mediane dei top 20) 30, outlier di canali giovani (<18 mesi) 20, RPM stimato della categoria
   20 (fonti pubbliche sugli RPM per nicchia, dichiarate come stime), automatizzabilità con stick figure in codice 15,
   prodotto Gumroad naturale 10, rischio policy (salute, politica, tragedie) -5/-15.
3. Scegli 1 sotto-nicchia principale + 1 di riserva. Con Simone: una riga di raccomandazione e i 3 numeri che la
   giustificano; se non risponde, si parte con la raccomandata (regola di autonomia del 26/10).
Prova: `research/stickman/scan-<data>.md` con almeno 20 canali e 40 video, e la tabella dei punteggi.

## 3. Fase 3: retroingegneria dei virali (Claude, cloud)
`tools/gemini_watch.py stickman 8 research/stickman/watchlist.json` (Gemini guarda i video per URL, niente download)
con le domande extra della nicchia: stile grafico (sfondo, spessore e colore del tratto, design del personaggio,
disegni/scene al minuto, movimenti di camera, come disegna numeri, mappe, oggetti), voce (tono, parole al minuto,
umorismo, quante volte dice "you"), titolo e miniatura, quanto è automatizzabile.
Da almeno 15 video di almeno 6 canali diversi ricava il **framework** in `config/framework-stickman.md` + JSON:
- **Hook (0-15 s):** frase d'apertura per tipo (domanda assurda, "what if", affermazione controintuitiva, "every level"),
  cosa si vede nei primi 3 secondi, quando arriva la promessa.
- **Struttura:** blocchi con durata in percentuale (es. setup, escalation a livelli, colpo di scena, payoff, chiusura
  ad anello), frequenza delle gag, open loop ("but that's not the worst part").
- **Ritmo:** secondi medi per disegno/scena, parole al minuto della voce, pause, sottotitoli sì/no.
- **Stile grafico:** palette (max 5 colori), sfondo, tratto, espressioni ricorrenti, oggetti tipici, testo a schermo.
- **Durata:** distribuzione dei lunghi (fascia vincente) e degli Short.
- **Titoli e miniature:** formule con esempi (riscritte, mai copiate), parole ricorrenti, emozione del personaggio in
  miniatura, numero di parole sulla miniatura.
Ogni regola del framework porta la fonte (video e timestamp del report Gemini). Regole senza fonte non entrano.
Prova: il file del framework + 3 script di prova scritti con quel framework che passano il critico di ritenzione.

## 4. Fase 4: brand originale (Claude, poi account di Simone)
- Nome del canale (3 proposte disponibili come handle YouTube/TikTok/IG, inglese, ≤18 caratteri, senza "stick"
  obbligatorio), descrizione, parole chiave, palette, **personaggio nostro** (design distinto da quelli dei
  competitor, con 1 dettaglio riconoscibile), avatar 800x800 e banner 2560x1440 generati in codice, intro sonora CC0
  di 1 secondo, watermark.
- Kit testi per ogni piattaforma (bio, link, commento fissato), playlist iniziali per sotto-tema.
- Prodotto Gumroad della nicchia (es. guida/mini-ebook o "cheat sheet" illustrata con lo stesso stick man, $7-14),
  con pagina, copertina e 3 immagini prodotte in codice. Simone crea/collega solo lo store se serve un account nuovo.

## 5. Fase 5: motore grafico stick man (PR)
Riusa `motion/` (Remotion 4.0.536) e `video/ytf/stickman.py` (stick man originale già disegnato in codice dal 31/10).
1. **Rig del personaggio** in SVG/React: testa, occhi, bocca, busto, braccia e gambe a 2 segmenti; libreria di pose
   (idle, talk, point, shrug, shock, think, walk, run, sit, fall, celebrate, facepalm) con interpolazione e blink;
   bocca sincronizzata con l'ampiezza della voce (timings di `voice.py`).
2. **Libreria di oggetti e ambienti** disegnati in codice (stile linea + 1-2 colori piatti): casa, città, mappa del
   mondo/paesi (dati di pubblico dominio Natural Earth), soldi, grafici, orologio, cervello, pianeta, corona,
   etichette, frecce, fumetti. Mai clipart di terzi.
3. **Tipi di scena** (nuovi effetti accanto agli 11 di Cosmos): `Talk` (personaggio + 1 oggetto + etichetta),
   `Versus` (due personaggi/scelte), `Levels` (scala a livelli "every level of..."), `MapZoom`, `Timeline`, `Counter`
   (numero che cresce con oggetti che si moltiplicano), `ZoomOut` (il personaggio diventa minuscolo), `Crowd`
   (folla di stick man per le statistiche), `Comic` (2-4 vignette per gli Short e i caroselli).
4. **Regista**: lo script esce come JSON di scene `{testo, scena, pose, oggetti, numero, fonte}`; il regista
   (`director.py`) sceglie camera e transizioni rispettando il ritmo del framework (cambio di disegno ogni N secondi
   preso dalla Fase 3) e vieta ripetizioni consecutive di scena/pose.
5. Verticale 1080x1920 per Short/Reel/TikTok e orizzontale 1920x1080 per i lunghi, stessi asset.
Prova: un lungo di 8-12 minuti e 3 Short renderizzati su Actions, con `video_qc.py` verde e fotogrammi d'esempio.

## 6. Fase 6: script, voce, audio
- Scrittore: ordine dei modelli già nel repo (Claude se c'è il segreto, poi Gemini, Groq, GLM); prompt dello script
  costruito sul framework della Fase 3 + `VIRAL_RULES`; `retention_review()` rimanda indietro gli script sotto soglia;
  fact check con fonti come in `auto_short.py`.
- Voce: Kokoro (Apache 2.0, gira su Actions) con una voce diversa da Cosmos e la velocità misurata sui virali.
- Musica e suoni: libreria CC0 (`sfx-library.yml`: Freesound + Openverse), cue sheet sui cambi di scena, -14 LUFS.
- Sottotitoli `.srt` multilingua (inglese + italiano + spagnolo almeno) su YouTube, come per Cosmos.

## 7. Fase 7: formati, test e apprendimento
- `config/formats.json` della nicchia con 6-9 formati dalla Fase 3 (es. `what_if`, `every_level`, `why_x`,
  `history_story`, `myth_vs_fact`, `versus`, `ranking`, `audience_question`, `quiz_guess`).
- Stesso motore di esperimenti di Cosmos (`tools/experiments.py`, Thompson 80/20, max 3 per formato in 7 giorni),
  `trend_scout.py` sul report della nicchia, `learn_weekly.py`, `metrics.yml` con curva di ritenzione.
- Test A/B di titoli e miniature: 3 miniature per lungo (A/B/C) e rotazione via API solo se ammessa; altrimenti si
  testa sugli Short (hook diversi sullo stesso tema in giorni diversi), mai lo stesso video ricaricato.

## 8. Fase 8: calendario e pubblicazione (dopo che Simone ha creato gli account)
- Lungo: 1-2 a settimana (giorno e ora dai dati dei competitor e poi dai nostri), caricato via API e programmato.
- Short: 1-2 al giorno (clip dei lunghi + Short nativi), con link al lungo.
- IG Reel + carosello "Comic" 2 a settimana, FB Reel, Threads (domanda/quiz + clip), TikTok (variante social).
- `scaletta.yml` domenica 18:00 con l'issue della settimana per Simone; `self-heal.yml` su tutti i workflow;
  `health.yml` e `tokens.yml` per token e scadenze.

## 9. Fase 9: misura e obiettivi
- Settimana 1-2: 2 lunghi + 10 Short pubblicati senza errori; ritenzione a 30 s ≥ 60% sui lunghi.
- Mese 1: ritmo stabile, formato vincente individuato dai dati, prima vendita Gumroad.
- Report lunedì in `reports/`: cosa ha vinto, cosa si replica, cosa si spegne, con numeri e link.
- Mai "funziona" o "migliorato" senza prova (run id, video id, numeri).

## 10. Cosa fa solo Simone (lista minima)
Vedi `docs/AZIONI-SIMONE-stickman.md`: repo + progetto, account dei social, autorizzazioni OAuth con un clic,
eventuale store Gumroad, nessun'altra azione.
