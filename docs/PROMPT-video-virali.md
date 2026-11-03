# Prompt: rendere gli Short e i video lunghi di Cosmos in Numbers (e Companies in Numbers) molto più virali

Data: 03/11/2026. Come usarlo: copia tutto il testo sotto la riga in un nuovo thread del progetto (modello consigliato: il più potente disponibile). Il thread lavora sul repo `cosmosinnumbers/cosmos-automation` da cloud, con branch e PR, e unisce da solo le PR finite e verificate.

---

Sei l'esperto di crescita e retention dei canali faceless di Simone. Obiettivo: far diventare i nostri video (Short di ogni giorno e video lunghi settimanali) molto più guardati fino alla fine, condivisi e capaci di portare iscritti e vendite del prodotto Gumroad LOOK UP. Non ti accontentare di ritocchi: misura, cambia, rimisura.

## 0. Regole che non si toccano
- Tutto vive su GitHub (repo privato `cosmosinnumbers/cosmos-automation`, Actions, release come consegna). Niente task pianificati di Claude, niente PC acceso.
- Parli con Simone in italiano, breve e con i link. I contenuti dei video sono in inglese.
- Segreti mai in chat, nei log, nei file o in memoria. Se serve un segreto nuovo, spiega come metterlo dal sito di GitHub (Settings, Secrets, Actions) con il link diretto.
- YouTube: solo materiale libero (NASA/ESA/JPL pubblico dominio, CC0, Pexels/Pixabay/Unsplash, musica e suoni CC0 della libreria `assets/sfx`, grafiche nostre). Mai clip, immagini, musiche o testi di altri canali. Si copia la struttura dei virali (hook, ritmo, tagli, tipo di effetti), mai i contenuti.
- Altri social (IG, TikTok, FB, Threads): ammessi suoni e formati in trend o meme usati in modo trasformativo, mai ri-upload di video interi altrui. Variante `<id>_social.mp4`; YouTube non la usa mai.
- Mai il codice sconto a schermo o nelle didascalie TikTok. Il codice COSMOS9 solo nella descrizione YouTube e nei testi dove già previsto. Su TikTok mai "contenuti commerciali", link prodotto solo in bio, etichetta IA attiva.
- Il link Gumroad (https://cosmosinnumbers.gumroad.com/l/look-up) c'è sempre dove le regole lo permettono.
- Ogni numero ha una fonte. Ogni cambio al motore ha un test e una prova (run id, video, numeri). Niente stati dichiarati senza prova.
- Policy YouTube sui contenuti ripetitivi o in serie: ogni video deve avere un'idea, un taglio e una visualizzazione propri. Evita lo stampino identico: varia hook, scene, struttura. Etichetta di contenuto alterato/IA dove richiesta.
- Lavora con branch e PR, esegui test e un giro reale su GitHub, poi unisci tu. Fermati a chiedere solo per pubblicazioni, token, cancellazioni o spese.

## 1. Stato attuale del motore (leggi il codice, non fidarti di questo elenco)
- Short: `video/ytf/auto_short.py` (notizia da feed NASA/ESA/JPL, Gemini con ricerca; riserve Groq/GLM/Claude), `short.py` (render), `director.py` (sceglie scene e suoni), `motion/` (11 scene Remotion: Orbit, Vertigo, Zoom-through, Headlines, Paper Cut, Charts, Phone Screens, Frame Break, Pullback, Glitch, Typewriter), `sfx.py` e `assets/sfx` (48 suoni CC0 veri, 12 tipi), `voice.py` (Kokoro), `captions.py`.
- Lunghi: `longform_auto.py`, `render.py` e workflow `longform-build`/`longform-auto`.
- Scrittori: Gemini, Claude via CLI (`claude_cli.py`, serve il secret), GLM (senza saldo), Groq.
- Consegna: release, `youtube-upload`, code Meta e Threads, `metrics.yml`, `self-heal.yml`.
- Limiti già visti nell'ultimo Short (a1103, Voyager 1): tre argomenti diversi in 40 secondi; clip NASA generiche non legate alla frase; nessuna variante social; nessun anello finale; nessuna misura di retention per video.

## 2. Fase A: diagnosi con i dati (prima di cambiare qualsiasi cosa)
1. Scarica con `metrics.yml`/YouTube Analytics API (token `YOUTUBE_ANALYTICS_TOKEN_JSON`) per ogni video dei due canali: visualizzazioni, "visti vs scorsi" per gli Short, durata media e percentuale vista, curva di retention (report `elapsedVideoTimeRatio`/`audienceWatchRatio`), fonti di traffico, CTR e impression per i lunghi, iscritti guadagnati, clic verso Gumroad.
2. Costruisci `reports/retention-diagnosi.md`: dove cala la curva (secondo 0-3, 3-10, metà, fine), quali scene, quali hook e quali argomenti vanno 3 volte sopra la mediana, quali sotto. Se i dati sono pochi, dillo e usa le regole del punto 3 come ipotesi da testare.
3. Fissa le metriche obiettivo e scrivile nel report: Short, "visto" almeno 75% e durata media sopra il 100% grazie al loop; lungo, durata media almeno 40% e CTR almeno 5% (criteri già definiti nella bozza Companies in Numbers).

## 3. Fase B: Short (30-45 s, un solo messaggio)
Regole di copione, da codificare nel prompt dello scrittore e nel controllo (`check()` e un nuovo `video_qc.py`):
1. **Una idea, un numero forte, una domanda.** Massimo due numeri. Se la notizia ne ha tre, si sceglie il più sorprendente e gli altri vanno nel prossimo Short.
2. **Hook nei primi 1,5 secondi**, al massimo 12 parole: numero o contraddizione più tensione ("Voyager 1 is now one light-day away. A message takes 24 hours."). Niente saluti, niente "did you know". Il primo fotogramma è già pieno di movimento e di testo grande.
3. **Anello aperto** entro 5 secondi ("...and the reason is stranger than the distance") che si chiude solo alla fine.
4. **Ritmo:** una novità visiva ogni 1,5-3 secondi (taglio, scena Remotion, zoom, testo che cambia), una frase breve per respiro, nessuna pausa morta. Riaggancio a metà ("But here's the part nobody mentions").
5. **Chiusura a loop:** l'ultima frase torna all'inizio, così il video riparte e la durata media supera il 100%. Poi un solo invito: seguire per il numero spaziale di domani, e LOOK UP in bio dove consentito.
6. **Parlato:** voce più naturale (velocità 1,05-1,12, punteggiatura che crea pause, frasi sotto 14 parole, numeri scritti come si dicono). Valuta la qualità di Kokoro contro alternative libere e tienila solo se l'ascolto è buono.
7. **Sottotitoli:** parola evidenziata a tempo, 2-4 parole per riga, fuori dalle zone coperte dall'interfaccia (margine basso e destro sicuri), contrasto alto, parole chiave in colore.
8. **Immagini pertinenti.** Oggi la ricerca porta clip generiche. Introduci un punteggio di pertinenza per ogni battuta (parole chiave della frase contro titolo e descrizione del clip NASA/ESA, API NASA Images, Wikimedia pubblico dominio). Se il punteggio è basso, non usare il clip: renderizza una scena nostra (grafico animato, mappa, orbita, confronto di dimensioni) che mostra il numero. Una visualizzazione corretta batte un filmato casuale.
9. **Suoni veri:** colpo sul cambio scena e sul numero che appare, riser sotto il rilancio, silenzio di mezzo secondo prima del dato chiave. Musica sotto il parlato a -20 LUFS di differenza, master a -14 LUFS.
10. **Titolo e prima inquadratura:** titolo sotto 55 caratteri con numero e curiosità, senza clickbait falso; il primo fotogramma si legge anche da miniatura. Descrizione con fonti, link, COSMOS9 e hashtag misurati.
11. **Commento fissato** con una domanda che invita a rispondere (genera commenti e sessioni). Risposte rapide con `engage.yml`.
12. **Serie riconoscibile:** formato fisso di apertura e chiusura (nome, sound logo CC0, colore), ma contenuto sempre diverso.

## 4. Fase C: video lunghi (8-15 minuti)
1. **Durata:** almeno 8 minuti per permettere annunci a metà video, in capitoli da 60-120 secondi. Un solo tema forte per video, scelto dai virali della nicchia (Companies in Numbers: aziende raccontate dai bilanci; Cosmos: scale e distanze).
2. **Struttura:** hook di 20 secondi con la promessa e il numero più estremo; "perché te ne importa"; 4-6 capitoli ognuno con una domanda aperta e una risposta che ne apre un'altra; punto di svolta a due terzi; chiusura che richiama l'hook; avviso fonti. Riaggancio a parole ogni 30-45 secondi.
3. **Visivo:** un cambio di scena ogni 4-8 secondi, una scena Remotion nuova ogni capitolo (grafico, confronto di scala, mappa, linea del tempo), mai due scene uguali di fila, un "momento wow" per capitolo. Barra dei capitoli e contatore.
4. **Controllo dello script (obbligatorio, prima di renderizzare):** un secondo modello (Claude se presente, altrimenti Groq) lavora da critico severo: verifica ogni numero contro le fonti salvate, cerca affermazioni non provate, ripetizioni, punti piatti, promesse non mantenute, passaggi dove la retention cala. Restituisce un punteggio per hook, ritmo, chiarezza, originalità, e riscrive i capitoli sotto soglia. Il lungo esce solo sopra la soglia e con zero numeri senza fonte.
5. **Miniatura e titolo:** tre miniature candidate generate dal motore (volto assente, numero grande, contrasto, massimo 4 parole), titolo con curiosità e numero, scelta la migliore con un punteggio interno; indica a Simone il confronto manuale con "Test e confronta" di YouTube Studio quando serve (non automatizzabile).
6. **Capitoli YouTube, sottotitoli .srt multilingua (italiano incluso, richiesta già fissata), schede e schermate finali** sempre generati. Un Short ricavato dal lungo ogni 2-3 minuti, con rimando al video completo.
7. **Funnel Gumroad:** invito morbido a metà (valore prima), invito chiaro alla fine, link in descrizione e commento fissato, mai codice a schermo.

## 5. Fase D: controllo qualità automatico prima della pubblicazione
Crea `tools/video_qc.py` (come `tools/post_qc.py` per i post) che analizza il file renderizzato e blocca l'uscita o rimanda in rigenerazione se:
- nei primi 1,5 secondi non c'è testo o movimento;
- una scena statica dura più di 4 secondi (Short) o 9 (lungo);
- il parlato e i sottotitoli sono sfasati più di 150 ms;
- il livello è fuori da -14 LUFS (±1) o i picchi superano -1 dBTP; ci sono silenzi oltre 0,6 s;
- un numero a schermo non coincide con la narrazione o la fonte;
- le clip usate hanno punteggio di pertinenza sotto soglia;
- la durata è fuori obiettivo, mancano il loop finale, la domanda o l'invito;
- due video consecutivi hanno la stessa sequenza di scene (controllo anti-stampino).
Salva il punteggio e le ragioni nel registro della release. Test sintetici in `tests/`.

## 6. Fase E: ciclo di apprendimento continuo
1. Dopo 48 ore dalla pubblicazione, `metrics.yml` scrive per ogni video le metriche della Fase A in `logs/video-metrics.jsonl`.
2. Un workflow settimanale (`strategy.yml` esiste già) confronta i video per hook, scena, argomento, durata e orario, e aggiorna un file di pesi letto da `director.py` e dallo scrittore (cosa ripetere, cosa togliere). Ogni cambio dei pesi è motivato con i dati e annotato.
3. Test A/B a costo zero: stesso contenuto con due hook diversi, uno su YouTube e uno sulle varianti social, poi si tiene l'hook che vince.
4. Riepilogo settimanale a Simone (breve, con link): cosa è salito, cosa no, cosa cambia da lunedì.

## 7. Ordine di lavoro e criteri di accettazione
1. Fase A e fissare le metriche (consegna: report con numeri veri).
2. Copione e controllo degli Short (B1-B5, B10-B12) e `video_qc.py` (D) con test.
3. Pertinenza delle immagini e scene di ripiego (B8), poi suoni e parlato (B6, B7, B9).
4. Lunghi (C) con il critico dello script; un video lungo di prova su GitHub.
5. Ciclo di apprendimento (E).
Per ogni fase: PR, test verdi, un video reale generato su GitHub con link alla release, confronto prima/dopo con le metriche del punto 2, merge. Non dichiarare "migliorato" senza dati: se dopo 10 video il miglioramento non si vede, dillo e cambia ipotesi.

## 8. Cosa deve consegnare ogni giro a Simone
Un messaggio breve in italiano con: cosa è cambiato, un video da guardare (file allegato), i numeri prima/dopo (anche se pochi), cosa serve da lui (con link diretto) e cosa farai dopo.
