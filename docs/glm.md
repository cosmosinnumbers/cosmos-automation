# GLM (Z.ai) come provider LLM

Aggiunto il 02/11/2026. Modello: GLM-5.3 (Zhipu / Z.ai, pesi aperti, annunciato ad agosto 2026) o il più recente
glm-5.x che la chiave elenca; modelli di ripiego glm-5.2. Endpoint OpenAI-compatibile
`https://api.z.ai/api/paas/v4/chat/completions` (chiavi "Coding Plan": `https://api.z.ai/api/coding/paas/v4`).

## Segreti (Settings → Secrets → Actions)
- `GLM_API_KEY` (obbligatorio per usarlo)
- `GLM_BASE_URL` (facoltativo: solo per il Coding Plan)
- `GLM_MODELS` (facoltativo: es. `glm-5.3,glm-5.2` per forzare i modelli)
- variabile di repo `LLM_FIRST=glm` (facoltativa): GLM scrive per primo, Gemini e Groq diventano il ripiego.

## Dove interviene (codice: `video/ytf/glm.py`)
- Scrittura Short/script/caption: dopo Gemini, prima di Groq (o per primo con `LLM_FIRST=glm`). Lo stesso fact check
  per numeri e fonti di prima si applica a ogni bozza, da qualunque modello.
- Revisore dei video lunghi: GLM con ragionamento attivo (`thinking`), un modello diverso dallo scrittore Gemini.
- Regista delle animazioni (`director.creative_pass`): sceglie etichetta dell'hook e parole da evidenziare; la
  risposta è validata (solo parole e numeri della narrazione, niente codici) e se qualcosa non torna resta la
  scelta deterministica.
Senza `GLM_API_KEY` non cambia nulla.
