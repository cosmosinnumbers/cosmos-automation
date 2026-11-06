---
name: jev-pipeline
description: >-
  Filtro semantico Jev (TypeSafe) sulla pipeline contenuti di Cosmos in Numbers: dopo l'ingest dei feed
  (NASA/ESA/ESO/APOD, ricerca settimanale) e la generazione dei post, classifica, ordina, dà un punteggio e
  controlla il brand voice con i tool mcp__jev__*, poi lascia pubblicare la coda di GitHub Actions.
  Usala con /jev-pipeline, o quando si chiede di scegliere, filtrare o controllare post e news prima che escano.
---

# jev-pipeline

Aggiunge un giudizio semantico (Jev, System One di TypeSafe) ai controlli che il repo fa già senza LLM.
**Non sostituisce `tools/post_qc.py`**: le regole esatte (COSMOS9 e mai LAUNCH9, limiti di lunghezza, regole
TikTok, numeri presenti nella fonte, duplicati, menu copiati) restano nel codice. Jev decide solo ciò che una
regex non sa decidere: che tipo di contenuto è, quanto è rilevante oggi, quanto è buono, se il tono è giusto.

Riferimento dei tool e dei payload: `.claude/skills/jev/references/tools.md` (skill installata da jev-code).

## Prerequisiti (controlla prima di tutto)

1. `npx -y @french-castle/jev-code@0.5.0 doctor` → deve vedere una chiave (`TYPESAFE_API_KEY`, oppure
   `OPENROUTER_API_KEY` / `AI_GATEWAY_API_KEY`). La chiave sta **solo** nell'ambiente (variabile dell'ambiente
   cloud o segreto GitHub), mai in file, log, memoria o commit.
2. Se i tool `mcp__jev__*` non sono registrati nella sessione, usa la CLI con gli stessi payload:
   `npx -y @french-castle/jev-code@0.5.0 classify --input payload.json` (anche `rank`, `score`, `check`).
   **Thread cloud di Claude:** la chiave è un *network secret* dell'ambiente: il proxy la inserisce da solo
   nell'header `Authorization` verso api.typesafe.ai. Servono comunque `TYPESAFE_API_KEY` con un valore
   segnaposto qualsiasi (la CLI rifiuta di partire senza) e `NODE_USE_ENV_PROXY=1` (il fetch di Node non
   usa il proxy da solo). Se non sono già nell'ambiente, esportali nel comando:
   `TYPESAFE_API_KEY=placeholder NODE_USE_ENV_PROXY=1 npx -y @french-castle/jev-code@0.5.0 doctor --live`.
3. Se manca la chiave o l'host non risponde (proxy 403, timeout): **non bloccare la pipeline**. Segnalalo una
   volta e lascia decidere `post_qc.py` come oggi. Non inventare mai risultati Jev.

## Flusso

```
ingest feed → genera/adatta → jev_classify → jev_rank → jev_score → jev_check → coda → publish.yml
```

### 1. Ingest
Fonti reali del progetto (niente feed nuovi senza motivo):
- feed delle agenzie usati da `tools/threads_build.py` (NASA, JPL, ESA, ESA/Webb, ESA/Hubble, ESO, NOIRLab,
  APOD), ultimi 3 giorni;
- `research/cosmos/<settimana>.json` (virali YouTube, Reddit RSS, Instagram) da `tools/research.py`;
- voci future già in `queues/*.json` (`threads`, `meta`, `x`, `tiktok`, `youtube`).

### 2. Genera / adatta
Con i generatori interni, senza riscrivere i fatti: `threads_build.py --dry-run`, `carousel_build.py`,
`day_short.py`, `queue_short_reel.py`, poi `post_qc.clean()`. Un candidato che `post_qc.check()` blocca è
già scartato: non mandarlo a Jev.

### 3. jev_classify: che cosa è
Un item per candidato (`id` = `ref` della coda, `text` = testo del post). Classi:
- `breaking`: notizia nuova di un'agenzia (ultimi 3 giorni), con data o scoperta precisa;
- `evergreen`: dato o curiosità valida sempre (fact sheet, quiz, clip dei lunghi);
- `promo`: il messaggio principale è vendere (LOOK UP, Gumroad, COSMOS9);
- `skip`: fuori nicchia, testo rotto, clickbait senza dato, nulla da dire.

`auto_accept: 0.8`, `min_margin: 0.4`. Esempio con dati reali: `examples/classify.json`.
Uso: `skip` in `auto` → fuori. `promo` → mai nel post: il link prodotto va come prima risposta (`cta.py`) su
Threads e solo in bio su TikTok. `decision: review` → vale il giudizio di `post_qc`.

### 4. jev_rank: cosa esce prima
`query`: "Quale post interessa di più oggi al pubblico di Cosmos in Numbers (spazio spiegato con numeri
verificati), dando precedenza alle notizie nuove?". `candidates` = i non-skip, `top_k` = posti liberi nello slot.
Controlla `any_relevant`: se è sotto 0.5 nessun candidato merita lo slot, quindi usa il post di riserva dal
Fact Sheet (come fa già `run_slot.py`).

### 5. jev_score: qualità
Livelli (dal peggiore al migliore):
1. "Debole: nessun dato chiaro, hook assente, frasi lunghe o confuse"
2. "Discreto: un dato c'è ma è sepolto, l'apertura non incuriosisce"
3. "Buono: numero chiaro in apertura, un solo messaggio, fonte citata"
4. "Ottimo: numero sorprendente nella prima riga, frasi brevi, fa venire voglia di vedere il video"

`level` va da 0 (Debole) a 3 (Ottimo). Scarta solo `level 0` con `decision: auto`. Per il resto il punteggio
serve a scegliere tra candidati dello stesso slot e si somma allo score 0-100 di `post_qc`, non lo sostituisce
(test del 6/11: news APOD e quiz del giorno sono usciti a livello 1 con confidenza bassa, la clip a livello 3).

### 6. jev_check: brand voice
`state`: `{ "post": <testo>, "source": <testo della pagina fonte>, "platform": <threads|ig|fb|tiktok|x> }`.
Checks:
- `tone_ok`: "Il tono di `post` è divulgativo e professionale, senza sensazionalismo, allarmismo o slang?"
- `claims_supported`: "Ogni affermazione di `post` è sostenuta da `source`, senza claim non verificati?"
- `one_message`: "`post` comunica un solo messaggio chiaro?"
- `no_hard_sell`: "`post` evita di spingere un acquisto nel corpo del testo?"

`yes_at: 0.75`, `no_at: 0.25`. Un `no` su `claims_supported` o `tone_ok` scarta il post. `uncertain` → si
tiene solo se `post_qc` lo approva con score >= 70, altrimenti riserva.

### 7. Pubblicazione
**Non c'è Blotato in questo progetto.** Si pubblica così:
1. scrivi o aggiorna la voce in `queues/<canale>-queue.json` (`at` in ora italiana);
2. `python tools/post_qc.py` deve uscire con 0;
3. commit e push su `main` (o PR unita): `publish.yml`, `youtube-upload.yml`, `youtube-long-upload.yml` pubblicano
   all'ora giusta. Facebook si programma via API da `meta_api.py`.
Se un giorno il proprietario collega Blotato MCP, solo allora il passo 7 può usare i suoi tool.

## Regole del progetto (sempre)
- Niente attesa dell'ok del proprietario su script, post o video: decide la pipeline con questi criteri.
- TikTok: mai attivare "contenuti commerciali"/"il tuo brand"; didascalia "Full video on YouTube", niente
  link, prodotto o codice sconto nel testo.
- Codice sconto: solo COSMOS9.
- YouTube/Cosmos: solo asset liberi (CC0/CC-BY con credito).
- Registra ogni decisione Jev in `logs/jev-log.jsonl` (una riga: data, ref, label, rank, score, verdetti,
  decisione finale). Nessuna chiave nei log.
- Ogni chiamata costa credito TypeSafe: un solo batch per passo (fino a 64 item), niente chiamate per item.

## Risultato da riportare
Tabella breve: ref, classe, rank, livello, verdetti check, esito (in coda / riserva / scartato) e il motivo.
