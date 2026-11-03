# Nicchia stick man: le sole cose che deve fare Simone

Tutto il resto lo fa Claude su GitHub Actions: copia del motore, copia dei segreti condivisi, video, grafica, testi,
bio, playlist, workflow, pubblicazioni. Nessuna password o chiave va scritta in chat.

Perché servono queste azioni: le regole di sicurezza di Claude e di GitHub non gli permettono di creare repository,
progetti Claude o account, né di leggere i valori dei segreti. Gli script però fanno tutto il resto da soli.

## Adesso (circa 3 minuti, dal telefono)
1. **Crea il repo vuoto:** apri
   https://github.com/new (Owner cosmosinnumbers, nome stickman-automation, Private)
   lascia tutto com'è (niente README) e premi **Create repository**.
2. **Allarga il token dei segreti al nuovo repo:** apri https://github.com/settings/personal-access-tokens
   (loggato come cosmosinnumbers), apri il token `cosmos-automation-secrets` → **Edit** → Repository access: aggiungi
   `stickman-automation` → in Repository permissions metti **Secrets: Read and write** e **Contents: Read and write**
   → **Update**. Il valore del token non cambia, non va copiato da nessuna parte.
3. **Se richiesto,** dai all'app Claude l'accesso al nuovo repo:
   https://github.com/apps/claude/installations/select_target → cosmosinnumbers → aggiungi `stickman-automation`.
4. **Progetto Claude nuovo:** crea un progetto (es. "Stick man channel"), aggiungi il repo
   `cosmosinnumbers/stickman-automation` e scrivi nella chat del progetto: "Leggi docs/MEMORIA-stickman.md e
   docs/PROMPT-nicchia-stickman.md nel repo, salvale in memoria e parti dalla fase in corso".

Poi Claude, da solo: copia il motore (con tutti i publisher spenti), copia i segreti condivisi (chiavi LLM, chiave
YouTube, librerie suoni, client OAuth Google; mai i token di Cosmos) e continua con ricerca, brand e motore grafico.

## Più avanti (quando Claude ha scelto il nome del canale)
5. **Account:** crea l'account Google/brand del canale YouTube, Instagram professionale, pagina Facebook, Threads,
   TikTok, con il nome e l'handle che Claude propone. Solo registrazione e login.
6. **Autorizzazioni con un clic:** apri dal telefono i link che Claude prepara (YouTube, Meta, TikTok), loggato con il
   nuovo account, e premi "Consenti". I token li salva il workflow.
7. **Gumroad:** il prodotto va sullo store attuale; uno store separato solo se lo vuoi tu.

Su TikTok non attivare mai "contenuti commerciali"/"il tuo brand".
