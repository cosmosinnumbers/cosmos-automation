# Segreti del repo: comandi pronti (li lancia Simone)

PowerShell, dalla cartella del progetto. Ogni comando legge il file e lo passa a GitHub senza mostrarlo.

```powershell
cd C:\Users\Simon\progetti_claude\Progetto-YouTube-Faceless
Get-Content -Raw secrets\meta.json    | gh secret set META_JSON    --repo cosmosinnumbers/cosmos-automation
Get-Content -Raw secrets\threads.json | gh secret set THREADS_JSON --repo cosmosinnumbers/cosmos-automation
```

Quando esisteranno i file (oggi non ci sono):

```powershell
Get-Content -Raw secrets\x.json      | gh secret set X_JSON      --repo cosmosinnumbers/cosmos-automation
Get-Content -Raw secrets\tiktok.json | gh secret set TIKTOK_JSON --repo cosmosinnumbers/cosmos-automation
```
- `x.json`: le 4 chiavi X in `secrets\api.env` sono vuote. Guida `guide\x-api-setup.md`, poi
  `C:\cctk\Scripts\python.exe -I tools\env_to_secrets.py`, poi il comando sopra e `gh variable set X_ENABLED --body true --repo cosmosinnumbers/cosmos-automation`.
- `tiktok.json`: solo dopo l'app TikTok (vedi `docs/tiktok.md`).

## Rinnovo automatico dei token (metodo consigliato)
| Token | Durata (verificata) | Chi lo rinnova |
|---|---|---|
| Meta Page token | non scade, ma ha una data di fine "accesso ai dati" (`data_access_expires_at`) | `tokens.yml` ogni lunedì avvisa 21 giorni prima; si rigenera dal PC (SOP 15.7) |
| Threads long-lived | 60 giorni, rinnovabile se ha più di 24 h | `tokens.yml` ogni lunedì (`threads_api.py refresh`) |
| TikTok access token | 24 h; refresh token 365 giorni, a volte ruota (doc TikTok, aggiornata il 4/08/2026) | ogni pubblicazione, e `tokens.yml` |
| X OAuth 1.0a | non scade | nessuno |

Il token rinnovato va salvato nel secret. Metodo più sicuro: un **token GitHub fine-grained** limitato a questo solo
repo con il solo permesso "Secrets: read and write". Se trapelasse, permetterebbe solo di riscrivere i secret di
questo repo (non leggerli: GitHub non restituisce mai i valori), e scade da solo.

1. Apri https://github.com/settings/personal-access-tokens/new (loggato come cosmosinnumbers).
2. Token name `cosmos-automation-secrets`; Expiration **366 days** (o "Custom" al 24/10/2027).
3. Repository access → **Only select repositories** → `cosmosinnumbers/cosmos-automation`.
4. Permissions → Repository permissions → **Secrets → Read and write** (Metadata: Read-only si aggiunge da solo).
5. **Generate token**, copialo, poi in PowerShell:
   ```powershell
   gh secret set GH_SECRETS_TOKEN --repo cosmosinnumbers/cosmos-automation
   ```
   e incollalo quando chiede "Paste your secret" (non si vede mentre lo incolli).
6. Promemoria: rigenerarlo entro il 24/10/2027.

Senza questo token il workflow pubblica lo stesso, ma il rinnovo di Threads fallisce con un messaggio chiaro
("GH_SECRETS_TOKEN not configured") e il token andrebbe rinnovato a mano dal PC entro il 15/12/2026.

- `GLM_API_KEY` (+ facoltativi `GLM_BASE_URL`, `GLM_MODELS`): modello GLM di Z.ai come scrittore/revisore/regista, vedi docs/glm.md
