# Nicchia stick man: le sole cose che deve fare Simone

Tutto il resto (codice, video, grafica, testi, bio, playlist, workflow, pubblicazioni) lo fa Claude su GitHub Actions.
Nessuna password o chiave va scritta in chat: le chiavi si incollano solo in GitHub, Settings → Secrets → Actions.

## Subito (5 minuti, anche dal telefono)
1. **Repo nuovo:** su https://github.com/organizations/cosmosinnumbers/repositories/new crea un repo **privato**
   vuoto (nessun README) chiamato `stickman-automation` (il nome del canale arriva dopo, il repo si può rinominare).
2. **Progetto Claude nuovo** per la nicchia (consigliato), con quel repo tra i repository. Se preferisci restare in
   questo progetto, aggiungi il repo in Project settings → Resources.
3. **Segreti condivisi** nel nuovo repo (stessi valori di Cosmos): `GEMINI_API_KEY`, `GROK_API_KEY`, `YOUTUBE_API_KEY`,
   `FREESOUND_API_KEY`, e se li vuoi `CLAUDE_CODE_OAUTH_TOKEN`/`GLM_API_KEY`; più un token `GH_SECRETS_TOKEN` per il
   nuovo repo (stessa procedura di `docs/segreti.md`, scegliendo il nuovo repo), così i token rinnovati si salvano da soli.

## Quando Claude ha scelto il nome (dopo la ricerca)
4. **Account:** crea un account Google/brand per il canale YouTube, poi Instagram (professionale), pagina Facebook,
   Threads (dall'Instagram), TikTok, con il nome e l'handle che Claude propone. Solo registrazione e login.
5. **Autorizzazioni con un clic:** apri i link che Claude prepara (YouTube, Meta, TikTok) dal telefono, loggato col
   nuovo account, e premi "Consenti". I token li salva il workflow.
6. **Gumroad:** se vuoi uno store separato, crealo e collega il payout; altrimenti il prodotto va sullo store attuale.

Tutto qui. Su TikTok non attivare mai "contenuti commerciali"/"il tuo brand".
