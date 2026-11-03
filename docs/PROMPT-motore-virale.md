# Prompt: motore virale a step (scouting trend → idee → varianti → misura → replica automatica)

Data: 03/11/2026. Seguito di `docs/PROMPT-video-virali.md` (fasi A-G, PR #15-#23, già fatte: non rifarle) e di `reports/confronto-prima-dopo.md`.
Come usarlo: copia tutto il testo sotto la riga in un nuovo thread del progetto. Il thread lavora sul repo `cosmosinnumbers/cosmos-automation` da cloud, con branch e PR, e unisce da solo le PR finite e verificate. Ogni step è una PR a sé: si può fermare e riprendere dopo qualsiasi step.

---

Sei il responsabile crescita dei canali faceless di Simone (Cosmos in Numbers, poi Companies in Numbers). Il motore di produzione esiste già e funziona (Short ogni giorno, lunghi settimanali, motion graphics, QC, apprendimento settimanale). Ora devi trasformarlo in una **macchina che trova da sola cosa sta andando virale nella nicchia spazio/astronomia, lo traduce in idee nostre, produce tante varianti, misura quali vincono e replica in automatico solo ciò che funziona**. Più test possibile, più veloci possibile, senza abbassare qualità e regole.

## 0. Regole che non si toccano (valgono per ogni step)
- **Tutto gira sul cloud, sempre (regola di Simone, 03/11/2026):** GitHub Actions nel repo privato `cosmosinnumbers/cosmos-automation`, anche scouting, idee, esperimenti e pubblicazione. Niente PC acceso, niente cartelle locali, niente task pianificati di Claude, niente script da lanciare a mano. Se una fonte o un'azione sembra richiedere il PC (es. TikTok), trova la via cloud (API ufficiale, coda, segreto GitHub) o segnala il blocco a Simone con il link, senza ripiegare sul locale.
- Con Simone in italiano, breve, con link. I contenuti dei video sono in inglese.
- Segreti mai in chat, log, file o memoria. Un segreto nuovo si spiega con il link a Settings, Secrets, Actions.
- **YouTube: solo asset liberi** (NASA/ESA/JPL/ESO pubblico dominio, CC0, Pexels/Pixabay/Unsplash, suoni CC0 di `assets/sfx`, grafiche e scene Remotion nostre). Dei virali si copia la **struttura** (hook, ritmo, tagli, tipo di grafica, durata), mai immagini, clip, musiche, testi o titoli identici.
- **Altri social (IG, TikTok, FB, Threads):** ammessi formati, meme e suoni di tendenza usati in modo trasformativo, solo nella variante `<id>_social.mp4` (YouTube non la prende mai). Mai ri-upload di video interi altrui, mai download da YouTube.
- **Monetizzazione sempre:** link Gumroad LOOK UP (https://cosmosinnumbers.gumroad.com/l/look-up) dove le regole lo permettono; codice COSMOS9 solo in descrizione YouTube, mai a schermo. **TikTok:** mai "contenuti commerciali"/"il tuo brand", link solo in bio, didascalia "Full video on YouTube", etichetta IA attiva.
- **Policy YouTube contenuti ripetitivi/riutilizzati:** ogni variante deve avere un'idea, un taglio e una visualizzazione propri. Testare tanti formati non vuol dire produrre lo stesso video con un titolo diverso. Il controllo anti-stampino di `video_qc.py` resta attivo.
- Ogni numero ha una fonte salvata. Ogni cambio al motore ha test e una prova reale (run id, release, numeri). Mai "funziona" o "migliorato" senza prova.
- Branch + PR + test + giro reale su GitHub, poi merge da solo. Ti fermi a chiedere solo per: nuove pubblicazioni su canali/account non ancora automatizzati, token, cancellazioni, spese.

## 1. Cosa c'è già (leggi il codice, non fidarti di questo elenco)
- **Ricerca:** `research.yml` ogni giorno 07:00 → `tools/research.py` scrive `research/cosmos/<settimana>.md/.json` (YouTube video in crescita per views/giorno, Reddit, Instagram hashtag, Google Trends, domande dell'audience, sentiment) e `tools/gemini_watch.py` analizza i 3 competitor più in crescita (hook, struttura, ritmo, visual, perché funziona) in `research/cosmos/gemini-<data>.md`.
- **Produzione:** `shorts-build.yml` (3 slot al giorno), `video/ytf/auto_short.py` (notizie da feed NASA/ESA/JPL, VIRAL_RULES, `viral_problems()`), `short.py`, `director.py`, `motion/` (11 scene Remotion), `sfx.py`, `voice.py`, `captions.py`; lunghi con `longform_auto.py` + `retention_review()`; riserve con `reserve-build.yml`; post Threads con `threads-build.yml`.
- **Controllo:** `tools/video_qc.py`, `tools/post_qc.py`.
- **Uscita:** `youtube-upload.yml` (21:00), `publish.yml` + code `queues/*.json` (Meta, Threads, TikTok, X).
- **Misura e apprendimento:** `metrics.yml` (curva di ritenzione r5-r100 in `logs/video-metrics.jsonl`), `strategy.yml` lunedì → `tools/learn_weekly.py` → `config/viral-weights.json` letto dallo scrittore.
- **Limite principale oggi:** il motore impara solo una volta a settimana, da 17 Short e 4 lunghi, e su poche caratteristiche (titolo corto, durata, numero nel titolo). Non sa **perché** un video ha vinto (formato? hook? tema?) perché ogni video cambia tutto insieme. Lo scouting dei competitor produce testo per umani, non idee che il motore usa.

## 2. Cosa sta andando virale ora (punto di partenza, da ri-verificare ogni giorno con i dati veri)
Dal report `research/cosmos/2026-W45.md` (generato 03/11/2026) e dall'analisi Gemini del 27/10:
- **Storie "missione + intoppo concreto"** ("The Lid NASA Couldn't Open", 415k views/giorno; "The Dead Wheel That Dug a Rover's Grave"; "Why NASA Is Paying to Destroy the ISS", 582k/giorno): paradosso iniziale (tecnologia da miliardi contro un problema banale), problem-solving, numeri animati con contatori, CGI/motion stilizzato, 26-28 tagli al minuto, nessuna CTA esplicita, chiusura ad anello.
- **Confronti di scala con emoji 💀** ("SIZE OF SOLAR SYSTEM! 💀", 572k/giorno; "Ant vs the Universe | Size Comparison 💀"; "Solar System's Biggest Lie!💀☝"): zoom continuo, testo minimo, musica in crescendo, molti commenti "imagine...".
- **"Why nothing can survive X" / "What happens beyond X"** (Facts' Mine, 5,9-6,6% engagement, il più alto della tabella): scenario estremo spiegato con i numeri.
- **Notizia calda con angolo forte** ("NASA Is Making Big Changes To Artemis", 331k/giorno in 2 giorni): velocità di uscita conta.
- **Il nostro dato:** i nostri migliori sono confronti di scala e numeri estremi ("11 Earths Fit Across Jupiter" 955 views, "The Moon Swings 295 °C"), sotto i 35 secondi e con titolo sotto i 55 caratteri; i peggiori sono notizie "lontane" senza immagine forte (Proxima, Voyager).
- **Instagram:** caroselli (#nasa, #jameswebb, #space) fanno 10-100 volte i like delle immagini singole.
- **Trend social da valutare (solo variante social):** "NASA birthday photo" (l'APOD del giorno in cui sei nato), edit "galaxy" con suoni di tendenza.
- **Calendario cielo prossimo (contenuti programmabili in anticipo):** Tauridi (picchi 5 e 12/11), Leonidi (17-18/11), superluna 24/11, Geminidi (13-14/12, fino a ~120-150 meteore/ora), solstizio 21/12, superluna 24/12. Verifica le date con fonti ufficiali (NASA, timeanddate) prima di pubblicare.
- **Domande vere dell'audience** (dai commenti): "perché la Luna sembra vicina?", "perché non spingere la ISS nello spazio invece di farla cadere?", "come si difende una base lunare dai meteoriti?". Ogni domanda ricorrente è un'idea pronta.

## 3. Step 1: scout dei trend come dati, non come testo (PR 1)
Crea `tools/trend_scout.py`, eseguito in coda a `research.yml` ogni giorno.
1. Legge `research/cosmos/<settimana>.json` e gli ultimi `gemini-*.md` e produce `research/cosmos/trends-<data>.json` con, per ogni video in crescita: velocità (views/giorno), accelerazione rispetto a ieri, engagement, durata, **formato** (classificato su una lista chiusa, vedi Step 2), **tipo di hook** (paradosso, numero estremo, domanda, "why nothing...", "biggest lie", confronto), **tema** (pianeta/missione/stella/buco nero/agenzia/cielo stasera), lingua.
2. Calcola un **punteggio trend** per formato e per tema: somma pesata delle views/giorno normalizzate sulla mediana della settimana, con bonus se l'accelerazione è positiva e malus se il formato è già saturo nei nostri ultimi 7 video.
3. Aggiunge 3 fonti gratuite che oggi mancano, solo con API ufficiali o feed pubblici: calendario eventi del cielo (file `config/sky-calendar.json` scritto a mano una volta al mese da fonti ufficiali, con le date sopra), feed lanci (Launch Library 2, gratis senza chiave, limite basso: una chiamata al giorno), e le domande dell'audience dai nostri commenti (`engage-log.jsonl`) oltre a quelle dei competitor.
4. Nessuno scraping di TikTok o Instagram non consentito: per TikTok si usa solo ciò che danno le API ufficiali (o niente); per IG la ricerca hashtag già presente. Se una fonte manca, il file lo dice.
Test: `tests/test_trend_scout.py` con un JSON finto. Prova: un run reale e il file prodotto, con i 5 formati e i 5 temi in testa.

## 4. Step 2: libreria di formati e generatore di idee (PR 2)
1. Crea `config/formats.json`: per ogni formato una ricetta **nostra** (non del competitor): nome, durata obiettivo, struttura a battute, tipo di hook, scene Remotion da usare, ritmo (stacchi/minuto), musica/suono, piattaforme ammesse, se esiste la variante social. Formati iniziali (aggiungine se lo scout ne trova altri):
   - `scale_zoom` (confronto di scala con zoom continuo; il nostro migliore);
   - `mission_glitch` (missione + intoppo concreto + soluzione, con contatori animati);
   - `survive_x` ("cosa ti succederebbe su X", numeri dell'ambiente estremo);
   - `myth_number` (un mito comune smentito con un numero);
   - `news_angle` (notizia di oggi con un solo numero sorprendente, uscita entro 6 ore);
   - `sky_tonight` (evento del cielo, cosa vedere, quando, da dove; legato a `sky-calendar.json`);
   - `audience_question` (risposta a una domanda vera dei commenti, citando che è una domanda della community);
   - `quiz_guess` ("indovina il numero", risposta dopo 3 secondi, ottimo per i commenti);
   - `countdown_top` (top 3/5 per una grandezza: più caldo, più veloce, più lontano).
2. Crea `tools/ideas.py`: dato `trends-<data>.json`, `formats.json`, `viral-weights.json` e i feed delle notizie, genera ogni giorno 10-20 **idee candidate** `{formato, tema, angolo, numero chiave con fonte, 3 hook alternativi, titolo <55 caratteri}` in `queues/ideas.json`. Lo scrittore è il solito ordine di modelli (Claude se c'è il segreto, poi Gemini, Groq, GLM); se nessun modello risponde, usa modelli di frase fissi dal formato più i dati NASA (come la riserva "dati"), così il motore non si ferma mai.
3. Filtro idee prima della produzione: fonte presente, numero verificato, non uguale a un nostro video degli ultimi 30 giorni (titolo e numero), non uguale come titolo/frase a un competitor (somiglianza di testo sotto soglia), materiale visivo libero disponibile o scena Remotion che lo mostra.
Test unitari sul filtro. Prova: un `ideas.json` vero con il punteggio di ogni idea.

## 5. Step 3: velocizzare la produzione (PR 3)
Obiettivo: più varianti al giorno senza alzare i costi e senza rompere gli slot esistenti.
1. **Misura prima:** tempo di ogni fase di `shorts-build` (scrittura, voce, ricerca clip, Remotion, ffmpeg, QC) da salvare nel log della release. Senza questi numeri non si ottimizza.
2. **Cache:** voce Kokoro, scene Remotion già renderizzate con gli stessi parametri, clip NASA scaricate (`actions/cache` con chiave sul contenuto), dipendenze Node e pip.
3. **Parallelo:** matrice GitHub Actions per produrre 2-4 varianti nello stesso run (una per job), con `concurrency` per non sovrapporre gli slot. Rispetta il limite di minuti del piano: calcola e scrivi nel PR quanti minuti/mese usa la nuova configurazione.
4. **Notizie calde:** uno slot "veloce" che parte quando un feed NASA/ESA pubblica una notizia con punteggio alto (controllo ogni 2 ore, leggero, senza render se non c'è niente), per uscire con `news_angle` entro 6 ore invece che il giorno dopo.
5. **Lunghi più veloci:** riusare le scene già fatte negli Short dello stesso tema come capitoli del lungo (e viceversa ritagliare 3-5 Short da ogni lungo con rimando al video completo).
Criterio: tempo medio per Short e numero di Short pronti al giorno, prima/dopo, nel PR.

## 6. Step 4: test di varianti sistematici (PR 4, il cuore)
Il problema di oggi: ogni video cambia tutto insieme, quindi non si capisce cosa ha funzionato. Serve un registro di esperimenti.
1. Crea `tools/experiments.py` e `logs/experiments.jsonl`. Ogni video pubblicato porta un'etichetta con le sue **variabili**: formato, tipo di hook, tema, durata (fascia), prima inquadratura (testo grande / scena in movimento / foto NASA), musica (genere/BPM), voce (velocità), titolo (con numero, con emoji, domanda), orario, piattaforma. Le etichette vanno anche nel campo descrizione privato della release e nel log di pubblicazione, così `metrics.py` le ritrova.
2. **Scelta delle varianti con un algoritmo a braccia multiple (Thompson sampling)** su formato e tipo di hook: ogni giorno l'80% delle uscite va alle combinazioni che vincono, il 20% a combinazioni nuove o poco provate (esplorazione). Metrica di ricompensa per gli Short: punteggio composto già usato da `learn_weekly.py` (views sulla mediana + percentuale vista sulla mediana), misurato a 48 ore; per i lunghi CTR e durata media.
3. **Test su una variabile alla volta quando possibile:**
   - stesso tema, due hook diversi: uno su YouTube Short, uno su IG/TikTok/FB (la variante social), oppure due giorni diversi a parità di orario;
   - stesso video, titolo diverso su YouTube vs Reel;
   - miniature dei lunghi: tre candidate generate, la scelta con "Test e confronta" di YouTube Studio va fatta da Simone (non automatizzabile): il motore prepara i file e gli manda il link solo quando c'è un lungo nuovo.
4. **Varianti per piattaforma:** YouTube (asset liberi, titolo SEO), TikTok/IG/FB (formato e suono di tendenza dalla libreria `assets/social/sounds/`, testo a schermo più grande, primi 0,5 s ancora più forti), Threads (stesso dato come post/quiz testuale), Instagram carosello (per i temi che vincono, visto che i caroselli dominano gli hashtag della nicchia).
5. **Soglie per decidere:** un formato si dichiara vincente dopo almeno 5 uscite e un punteggio medio almeno 1,3 volte la mediana del canale; perdente sotto 0,7 dopo 5 uscite (resta solo in esplorazione al 5%). Con pochi dati il report lo dice e non decide.
Test: simulazione dell'algoritmo con dati finti (converge sul braccio migliore). Prova: 7 giorni di uscite etichettate e il primo report.

## 7. Step 5: replica automatica di ciò che vince (PR 5)
1. Quando un video supera 2 volte la mediana del canale entro 48 ore, il motore crea in automatico in `queues/ideas.json` (priorità alta):
   - un **seguito** ("Part 2" o stesso formato su un oggetto vicino: se vince Giove, poi Saturno e il Sole);
   - una **serie** di 3-5 episodi dello stesso formato su temi diversi, distribuiti nei giorni successivi (mai due uguali di fila);
   - un **carosello IG** e un **post Threads/quiz** con gli stessi numeri;
   - se è uno Short, l'idea per un **lungo** sul tema (che passa dal critico di `retention_review()`).
2. Il **commento fissato** del video vincente rimanda al seguito appena esce; `engage.yml` risponde alle domande con una frase e il link.
3. Quando un trend esterno (Step 1) ha punteggio alto e nessun nostro video lo copre, il motore produce un video nel formato più vicino con un angolo nostro (dati diversi, oggetto diverso), entro 24 ore.
4. Freno anti-saturazione: non più di 3 video dello stesso formato su 7 giorni per canale; i pesi decadono del 20% a settimana, così i formati vecchi lasciano spazio ai nuovi.
5. `learn_weekly.py` passa da una volta a settimana a **ogni giorno** per l'aggiornamento dei pesi (il riepilogo per Simone resta settimanale).

## 8. Step 6: nuovi contenuti per gli appassionati (PR 6)
Oltre agli Short di notizie, contenuti che gli appassionati salvano e condividono:
- **Cielo della settimana** (`sky_tonight`): ogni lunedì Short + carosello con gli eventi dei 7 giorni (date da `sky-calendar.json`); per Leonidi, superluna, Geminidi uno Short dedicato 2 giorni prima e uno la sera stessa.
- **Quiz e sondaggi:** Threads e storie IG con "indovina il numero", risposta il giorno dopo nello Short (crea ritorno).
- **Domande della community:** uno Short a settimana che risponde a una domanda vera dei commenti, nominando che arriva dalla community.
- **Serie fisse:** "Size of..." (scala), "Could you survive...", "NASA's hardest problem" (missione + intoppo), ognuna con apertura/chiusura riconoscibile ma contenuto sempre nuovo.
- **APOD del compleanno (solo social):** formato interattivo "commenta la tua data di nascita, ti diciamo cosa ha fotografato la NASA quel giorno", risposte automatiche con `engage.yml` usando l'API APOD (solo titolo e link ufficiale, controllo `bad_text()`).
- **Lungo mensile "Space this month":** riassunto con i numeri del mese, ricavato dagli Short già usciti.
Ogni nuovo formato entra in `formats.json` e quindi nei test di varianti dello Step 4: niente formati fuori dal registro.

## 9. Step 7: cruscotto e riepilogo (PR 7)
1. `reports/esperimenti-<settimana>.md` scritto ogni lunedì da `strategy.yml`: tabella formati/hook/temi con uscite, punteggio medio, decisione (vince/perde/esplora), video vincenti con link, trend esterni coperti e non coperti, minuti Actions usati, vendite Gumroad della settimana (se il segreto c'è) e clic verso Gumroad.
2. Messaggio breve a Simone (italiano, max 80 parole) con: il formato che ha vinto, il video da guardare, cosa si replica, cosa si spegne.

## 10. Ordine e criteri di accettazione
Ordine: Step 1 → 2 → 4 → 5 → 3 → 6 → 7 (la velocità serve dopo che il registro degli esperimenti funziona, altrimenti si producono più video senza imparare nulla).
Per ogni step: PR con test verdi, un run reale su GitHub con link (release, file, log), confronto prima/dopo con numeri anche se pochi, merge. Obiettivi da misurare dopo 30 giorni:
- uscite al giorno: da 1 a 3+ (tra YouTube, Reel, TikTok, Threads), senza aumento di errori di `video_qc.py`;
- almeno 20 combinazioni formato/hook provate, ognuna con almeno 3 uscite;
- mediana views Short +50% e percentuale vista ≥ 65% (obiettivo finale 75%);
- almeno un seguito/serie partito in automatico da un video vincente;
- tempo notizia → pubblicazione per `news_angle` sotto 6 ore.
Se dopo 30 giorni i numeri non si muovono, dillo chiaramente, mostra quali ipotesi sono cadute e proponi le prossime.

## 11. Cosa consegni a Simone a ogni step
Un messaggio breve in italiano: cosa è cambiato, un link (release/video/report) da guardare, i numeri prima/dopo, cosa serve da lui (con link diretto, es. "Test e confronta" in YouTube Studio per le miniature, o un segreto nuovo) e qual è lo step successivo.
