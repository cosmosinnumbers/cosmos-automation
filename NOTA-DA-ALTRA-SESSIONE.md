# Nota per la sessione che costruisce cosmos-automation (26/10/2026)

Un'altra sessione Claude ha lavorato in questa cartella senza sapere che esisteva già. Prima di pubblicare:

1. **`tools/threads_api.py` è stato sovrascritto** con la versione di `Progetto-YouTube-Faceless/tools/threads_api.py`. Se l'avevi modificato (es. percorsi `queues/` e `logs/`), rifai le modifiche.
2. **`.gitignore` è stato riscritto**: ora esclude `secrets/`, `__pycache__/`, `*.pyc`, `.env`. Ricontrolla che basti e che `docs/segreti.md` non contenga token.
3. I doppioni (`.github/workflows/threads.yml` e `07-analytics/`) sono già stati cancellati.
4. Simone **non vuole più usare X** (costa): niente post su X.
5. Una sola sessione di pubblicazione per canale: quando GitHub Actions pubblica su Threads, va sospesa l'attività `cosmos-threads-daily` sul PC.

Cancella questa nota quando hai finito.
