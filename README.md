# cosmos-automation (privato)

Pubblicazione automatica di **Cosmos in Numbers** su GitHub Actions: non dipende dal PC acceso né da Claude in Chrome
per i canali che hanno un'API (Instagram, Facebook Storie, Threads, X; TikTok dopo l'approvazione).

## Come funziona
- `queues/*.json`: cosa uscirà e quando (`at` = ora italiana `AAAA-MM-GG HH:MM`). Le scrive il task Claude
  `cosmos-daily-content` dal PC, poi `git push`.
- `.github/workflows/publish.yml`: parte alle 10:55, 11:55, 14:55, 17:55 e 19:55 UTC (= 11:55, 12:55, 15:55, 18:55,
  20:55 ora solare italiana), aspetta il minuto esatto di ogni voce e pubblica con `tools/run_slot.py`.
- `logs/*.jsonl`: **unica fonte di verità** per pacing anti-ban e spesa X. Il workflow fa commit dei log dopo ogni
  voce; il PC fa `git pull` prima di ogni controllo o programmazione.
- Idempotente: una voce già nel log si salta. Al massimo 1 nuovo tentativo, poi il workflow fallisce con l'elenco dei
  problemi (GitHub manda una e-mail). Le voci partite con più di 2 ore di ritardo finiscono in `logs/missed-log.jsonl`.
- Facebook (carosello e Reel) **non** passa dal workflow: si programma in anticipo via API (`scheduled_publish_time`)
  dal task delle 10:00 (`meta_api.py fb-carousel`, `fb-reel`).

| Ora | Canale | Voce in coda |
|---|---|---|
| 12:00 | Threads news, X news | `threads-queue`, `x-queue` |
| 13:00 | TikTok Short "dati" | `tiktok-queue` (solo con `TIKTOK_ENABLED=true`) |
| 16:00 | Threads quiz/sondaggio, X | `threads-queue`, `x-queue` |
| 19:00 | Carosello Instagram | `meta-queue` (`ig-carousel`) |
| 21:00 | Reel IG, Storia IG, Storia FB, Threads video, X, TikTok news | `meta-queue` (`ig-reel`, `ig-story`, `fb-story`), `threads-queue`, `x-queue`, `tiktok-queue` |

Media: `https://cosmosinnumbers.github.io/media/<AAAA-MM-GG>/` (repo pubblico del sito). Ogni URL va verificato con
risposta 200 prima di metterlo in coda (lo ricontrolla anche il workflow).

## Controllo qualità dei post (`tools/post_qc.py`, dal 1/11/2026)
Ogni post passa due controlli, senza LLM: quando entra in coda (`threads_build.py`) e un attimo prima di uscire
(`run_slot.py`, tutti i canali con testo).
- **Blocca:** testo di menu dei siti, frasi tagliate, HTML o segnaposto rimasti, limiti di lunghezza, LAUNCH9 (il
  codice giusto è COSMOS9), link Gumroad senza COSMOS9 fino al 30/11, fonte mancante, numeri che non sono nella fonte,
  doppioni recenti, hashtag nei post Threads, TikTok con prodotto/link/codice o senza "Full video on YouTube".
- **Punteggio 0-100:** hook della prima riga, chiarezza, numeri, parole dei trend della settimana
  (`research/cosmos/<settimana>.json`), fonte, invito all'azione. La news delle 12:00 è la candidata pulita con il
  punteggio più alto (minimo 55).
- **Se un post non passa:** pulizia automatica sicura; altrimenti non esce e, su Threads, al suo posto esce un post
  "dati" dalla NASA Planetary Fact Sheet. Ogni decisione è in `logs/qc-log.jsonl`.
- Controllo a mano della coda: `python tools/post_qc.py` (solo i post futuri) o `--all`.

## Interruttori (Settings → Secrets and variables → Actions → Variables)
`META_ENABLED`, `THREADS_ENABLED`, `X_ENABLED` (predefinito true), `TIKTOK_ENABLED` (false finché TikTok non approva
l'app e un post pubblico di prova non è verificato), `TIKTOK_AIGC_LABEL` (false: decisione del 24/10/2026),
`YT_ENABLED` (false finché Google non approva l'audit API).

## Segreti
`META_JSON`, `THREADS_JSON`, `X_JSON`, `TIKTOK_JSON` (il contenuto dei file `secrets/*.json`), `GH_SECRETS_TOKEN`
(token fine-grained solo per questo repo, permesso "Secrets: read and write", serve a salvare i token rinnovati).
Mai stampati: il workflow non fa echo e GitHub li maschera nei log. Istruzioni in `docs/segreti.md`.

## Auto-riparazione (self-heal.yml)
Se un workflow automatico fallisce, `self-heal.yml` lo rilancia (solo i job falliti, 0-2 volte dopo 2 e 6 minuti,
vedi `config/self-heal.json`). Se fallisce ancora, `tools/self_heal.py` legge il log e chiede una correzione a un
LLM gratuito (Gemini, Groq, GLM, GitHub Models) e, solo se esiste il segreto `ANTHROPIC_API_KEY` o
`CLAUDE_CODE_OAUTH_TOKEN`, a Claude. La correzione deve compilare e non far fallire nuovi test: diventa una PR, unita
da sola solo se non tocca publisher, token, code, log, cancellazioni o workflow; poi il run viene rilanciato per
verifica. Issue con etichetta `alert` solo se non si ripara. Niente doppi post: i rilanci leggono i log dalla cima di
main. Limiti: 1 autofix per workflow ogni 20 ore, 4 al giorno (`logs/autofix-log.jsonl`). Spegnere: variabile
`SELF_HEAL=false` (tutto) o `AUTOFIX=false` (solo la correzione con LLM).

## Spegnere tutto (reversibile)
Actions → publish → "Disable workflow" (oppure `gh workflow disable publish --repo cosmosinnumbers/cosmos-automation`).

## Sul PC
```
git -C C:\Users\Simon\progetti_claude\cosmos-automation pull
C:\cctk\Scripts\python.exe -I tools\run_slot.py --dry-run
C:\cctk\Scripts\python.exe -I tools\meta_api.py fb-carousel "<didascalia>" <unix> <url1> <url2> ...
```
Gli strumenti leggono le credenziali da `..\Progetto-YouTube-Faceless\secrets\` quando non trovano le variabili
d'ambiente (cartella cambiabile con `COSMOS_SECRETS`).
