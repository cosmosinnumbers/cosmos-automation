# Memoria iniziale del progetto "stick man" (dal progetto Cosmos, 03/11/2026)

Da importare nella memoria del nuovo progetto Claude (il coordinatore la legge al primo avvio). Solo regole e fatti
validi per tutti i canali di Simone; i dettagli tecnici di Cosmos restano nel repo `cosmos-automation`.

## Chi è Simone e come lavora
- Owner: simone (GitHub Redwraith). Scrive in italiano; risposte brevi, con link. Lavora dal telefono.
- Obiettivo dichiarato: 10.000 €/mese dai canali faceless; vuole velocità e il massimo dell'autonomia.
- **Tutto su cloud (GitHub Actions)**, mai PC acceso, mai attività pianificate di Claude.
- **Autonomia:** non aspettare il suo ok su script e video; adeguarsi da soli al framework dei virali della nicchia
  (struttura, ritmo, tagli, stile), mai copiare immagini, clip, musiche, testi di altri.
- **Merge:** i thread possono unire da soli le PR finite e verificate (test e giro reale ok), salvo cose rischiose
  (publisher, token, cancellazioni).
- Il 03/11/2026 Simone ha dato il permesso di creare in autonomia tutto il motore della nicchia stick man (repo,
  progetto, copia del motore e dei segreti), nei limiti di ciò che Claude può fare.
- Account: Claude non crea account né inserisce password. Simone registra e fa login (o dà i segreti), Claude configura
  il resto (nome, bio, grafica, link, playlist, token, workflow).

## Regole di contenuto (valgono per ogni canale)
- YouTube: solo asset liberi (CC0/CC-BY con credito, pubblico dominio, grafiche nostre). Altri social: formati, meme e
  suoni di tendenza ammessi in modo trasformativo, solo nella variante social; mai ri-upload di video interi altrui.
- Fact checking completo, ogni numero con fonte salvata. Video lunghi di qualità alta, motion graphics, intrattenere
  per tutto il video. Sottotitoli .srt multilingua (italiano incluso) su tutti i video YouTube.
- Caricamento YouTube sempre via API (il progetto Google di Cosmos ha superato l'audit: gli upload via API sono pubblici).
- **Monetizzazione sempre:** prodotto Gumroad a pagamento in bio, descrizioni, post. Threads spinto di più (video, quiz,
  news, post a catena).
- **TikTok:** MAI "contenuti commerciali"/"il tuo brand"; didascalia solo "Full video on YouTube"; link prodotto solo in
  bio; etichetta IA attiva; niente codici sconto a schermo.
- Mai due publisher sullo stesso canale (una sola coda, su GitHub).
- Segreti mai in chat, log, file o memoria.

## Contesto tecnico ereditato
- Motore copiato da `cosmosinnumbers/cosmos-automation` (tools/, video/ytf/, motion/ Remotion, workflow, test):
  ricerca + trend scout, scrittore con fact check, voce Kokoro, 11 scene motion, suoni CC0 (Freesound + Openverse),
  QC video e post, esperimenti 80/20, apprendimento settimanale, scaletta della domenica (issue a Redwraith), self-heal.
- LLM: Gemini spesso in quota (429/503), Groq di riserva (`GROK_API_KEY`), GLM senza saldo, Claude solo con
  `CLAUDE_CODE_OAUTH_TOKEN`/`ANTHROPIC_API_KEY`.
- YPP: i ricavi vengono dai video lunghi; Short/TikTok/Reels servono alla scoperta.
- Piano della nicchia: `docs/PROMPT-nicchia-stickman.md`; azioni di Simone: `docs/AZIONI-SIMONE-stickman.md`.
