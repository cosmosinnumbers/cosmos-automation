# Prompt: prossime implementazioni Cosmos su GitHub Actions (30/10/2026)

Copia tutto il testo sotto la riga in una nuova sessione (modello consigliato: Opus 5.5).

---

Lavori sul PC di Simone, in `C:\Users\Simon\progetti_claude`. Leggi prima `CLAUDE.md` (regole: italiano con Simone,
contenuti in inglese, Gumroad LOOK UP in ogni post tranne TikTok, anti-ban Meta, segreti mai letti né stampati,
Python `C:\cctk\Scripts\python.exe -I`), poi `Progetto-YouTube-Faceless/governance/regole-operative.md` (ogni stato
con prova, ogni numero con fonte, ogni modifica in `governance/registro-modifiche.md`) e le ultime 30 righe di
`Progetto-YouTube-Faceless/governance/stato.md`.

Obiettivo: Simone non vuole più task pianificati di Claude. Tutto deve girare su GitHub Actions nel repo privato
`cosmosinnumbers/cosmos-automation` (clone locale `C:\Users\Simon\progetti_claude\cosmos-automation`), senza token
Claude, con Gemini (segreto `GEMINI_API_KEY`/`GEMINIAPIKEY3`) e Groq come riserva (segreto `GROK_API_KEY`, già
gestito da `backup_llm()` in `video/ytf/auto_short.py`). Un'implementazione alla volta, nell'ordine sotto: per ognuna
prova a secco, poi un solo giro reale se serve, poi commit con messaggio in italiano, push su main, riga nel registro
modifiche e in stato.md con la prova (run id, link). Se un passo fallisce due volte fermati e scrivilo.

## Stato al 30/10/2026 sera (già fatto, non rifare)
- `shorts-build.yml`: Short news del giorno alle 06:30, ritentativi 11:00 e 15:00 solo se manca la release
  `a<MMDD>-*`; Gemini, poi Groq; stesso controllo dei numeri (`check()`); a fine giornata Short di riserva da
  `reserve/` (`tools/reserve_short.py`) o issue "Short non uscito". Note della release pronte per il telefono
  (`tools/phone_notes.py`).
- `reserve-build.yml`: mercoledì e sabato 16:00 uno Short "dati" evergreen dalle schede NASA (`auto_short.py
  --reserve`, max 5 in riserva).
- `youtube-upload.yml` + `tools/yt_short_upload.py`: lo Short del giorno su YouTube via API, pubblico alle 21:00, mai
  doppioni (`logs/youtube-publish-log.jsonl` + titoli del canale), issue se fallisce. Test: C-BKdHUodpE pubblico.
- `queue-short-reel.yml` + `tools/queue_short_reel.py`: lo Short del giorno diventa Reel IG in `queues/meta-queue.json`
  (slot 20:48-21:10, almeno 24 h + 2 min dal Reel precedente). `publish.yml` (cron 10:45, 14:45, 17:45, 19:45 UTC) e
  `tools/run_slot.py` pubblicano le code all'ora esatta; media anche come file del repo (`media/...`).
- `engage.yml`: risposte ai commenti YT/IG/FB/Threads ogni 2 h e commento LOOK UP sotto i nuovi video (cta).
- Altri: `metrics.yml` (08:30), `research.yml` (07:00), `tokens.yml` (lunedì), `launch9.yml` (30/11, manca il
  segreto `GUMROAD_JSON`), `backup-llm-check.yml` (verifica Groq).
- Task Claude ancora accesi: `cosmos-daily-content` (10:08, ora solo Reel IG in coda), `cosmos-comment-replies`
  (22:38, TikTok + fissare il commento YouTube), `cosmos-strategy-weekly` (lunedì), `lookup-launch9-fine` (30/11).
- Limiti fissi: TikTok non ha API approvata (resta da telefono, didascalia senza LOOK UP/LAUNCH9/Gumroad, etichetta IA
  attiva, mai "Il tuo brand"); X spento (`X_ENABLED=false`, costa); fissare commenti YouTube solo a mano.

## Da implementare, in ordine

1. **Threads automatico (urgente: coda vuota dall'1/11).** Nuovo workflow giornaliero (es. `threads-build.yml`,
   mattina) che aggiunge a `queues/threads-queue.json`: news delle 12:00 (vera e recente, fonte NASA/ESA/arXiv, testo
   dalla pagina, numeri controllati con lo stesso `check()`), quiz o sondaggio delle 16:00 (chiavi come gli elementi
   esistenti: `ref`, `at`, `tag`, `poll`, `text`, `replies`; risposta del quiz precedente nel testo), video delle
   21:00 = Short del giorno. Un topic tag pertinente per post, 1-2 risposte a catena con dato e fonte, link LOOK UP
   nella prima risposta con testi a rotazione (`cosmosinnumbers.gumroad.com/l/look-up`, LAUNCH9 fino al 30/11), max 3
   post al giorno distanziati di almeno 3 h. Leggi `tools/threads_api.py` per formato e pacing. Il video Threads
   richiede un URL pubblico: vedi punto 2; finché manca, solo testo.
2. **Hosting pubblico dei media.** `cosmosinnumbers.github.io` rifiuta il push (Redwraith ha solo lettura). Prepara a
   Simone il clic esatto (account cosmosinnumbers → repo cosmosinnumbers.github.io → Settings → Collaborators →
   Redwraith con Write) oppure un token fine-grained come segreto per far pubblicare i media dal workflow; poi pubblica
   i 2 commit fermi del clone locale (36e62fd, 2522290) e collega lo Short del giorno a `media/` del sito per Threads.
   Formato video Threads in CLAUDE.md (H.264 High, 1080x1920, 30 fps, ≤ 8 Mbps, AAC 48 kHz, +faststart).
3. **Short del giorno anche su Facebook e Storie.** Collegare la release del giorno a: Reel FB (`meta_api.fb_reel`
   con `scheduled_publish_time` 21:00, programmato nativamente da Meta), Storia IG e Storia FB alle 21:00 (`ig-story`,
   `fb-story` in meta-queue, taglio 19 s con `story_cut`). Rispettare `guard()` e i limiti in `tools/meta_api.py`
   (warm-up fino al 15/11). Prova a secco con `publish.yml -f dry_run=true -f only=meta -f ref=<ref>`.
4. **Spegnere i task Claude doppi**, uno alla volta e solo con prova che l'equivalente GitHub ha funzionato:
   `cosmos-daily-content` dopo il Reel IG del 31/10 21:00 (controlla `logs/meta-publish-log.jsonl` e la run publish);
   cancella `cosmos-weekly-shorts` e `cosmos-thursday-shorts` (solo manuali, inutili); `lookup-launch9-fine` solo dopo
   una prova a secco riuscita di `launch9.yml` (serve `GUMROAD_JSON`, lo carica Simone). `cosmos-strategy-weekly`:
   portarlo su GitHub con Gemini (dati in `07-analytics/metrics/*.jsonl`, `research/cosmos/*`, formato da imitare
   `Progetto-YouTube-Faceless/03-strategia/scorecard-2026-10-26.md` e `07-analytics/decisioni-settimanali.md`; il
   rapporto va in un file del repo o in una issue, non come Artifact).
5. **Controllo di salute settimanale** (lunedì 08:00): issue con esito degli ultimi 7 giorni di ogni workflow
   (`gh run list`), elementi futuri per coda, scadenze (token Threads entro il 15/12, accesso dati Meta da `meta_api
   check`, LAUNCH9 il 30/11, riserva Short), Short usciti per piattaforma. Nessun segreto nel testo.
6. **Manutenzione.** (a) Ora legale: dal 28/03/2027 i cron UTC slittano di un'ora; rendere gli orari in ora italiana
   (doppio cron con controllo dell'ora locale nello script, o finestra con attesa). (b) Node 20 deprecato:
   aggiornare `actions/checkout`, `setup-python`, `cache` alle versioni attuali (verificare i tag esistenti).
   (c) I video in `media/` e `reserve/` fanno crescere il repo: preferire gli asset delle release e togliere i file
   già pubblicati.
7. **Metriche YouTube complete.** Manca il consenso `yt-analytics.readonly` (durata media e % visualizzata "non
   misurato"). Prepara il comando (`video/ytf/metrics.py yt-auth` o equivalente) e il clic esatto per Simone; poi
   il token nel segreto usato da `metrics.yml`.
8. **Più avanti (chiedi prima a Simone):** video lunghi su GitHub (voce, montaggio, clip, release da uno script
   approvato) e clip Reel da P5 e P6 (`video/ytf/clip.py` o `Progetto-YouTube-Faceless/tools/ytf/clip.py`, segmenti
   scelti da Gemini dal `.srt`).

## Regole di lavoro
- Un solo publisher per canale: non creare un secondo workflow che pubblica la stessa cosa (controlla `publish.yml`,
  `youtube-upload.yml`, `queue-short-reel.yml`).
- Account, login, consensi OAuth, segreti, pagamenti: li fa Simone. Preparagli link e clic esatti (scrive dall'iPhone).
- Mai leggere `secrets/` né stampare token; nei log solo nomi e stati.
- Alla fine di ogni punto: messaggio breve a Simone in italiano con esito, prova e cosa deve fare lui.
