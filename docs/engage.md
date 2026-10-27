# Risposte automatiche stile ManyChat (engage.yml)

Dal 27/10/2026 le risposte ai commenti di Cosmos in Numbers girano su GitHub Actions, senza PC acceso e senza
token di Claude. Sostituiscono i task del PC `cosmos-sky-replies` (ogni 2 ore), `cosmos-cta-comments` (22:15) e la
parte via API di `cosmos-comment-replies`.

## Cosa fa (ogni 2 ore, 09:20–23:20 ora italiana)
1. Legge i commenti nuovi (ultimi 14 giorni) sotto i nostri post: YouTube, Instagram, Pagina Facebook, Threads.
2. Parole chiave (in `config/engage.json`, modificabili senza toccare il codice):
   - **SKY / chapter / free** → capitolo gratuito (`look-up.html`);
   - **GUIDE / book / buy / price / link** → LOOK UP su Gumroad + LAUNCH9 (fino al 30/11, poi sparisce da solo);
   - **VIDEO / full video / youtube** → l'ultimo video lungo pubblico su YouTube.
   Valgono nei commenti corti (fino a 3 parole) o scritte in maiuscolo ("comment SKY").
3. Tutto il resto lo legge **Gemini** (chiave già nei segreti): sceglie uno dei flussi sopra, oppure scrive una
   risposta breve in inglese (niente link, niente numeri inventati), oppure salta spam, insulti e provocazioni.
4. Dove va il link: Facebook e Threads nella risposta; Instagram "link in bio" (i link nei commenti IG non sono
   cliccabili e sembrano spam); YouTube rimanda al commento fissato (i link nelle risposte finiscono nello spam).
5. Sotto ogni nuovo video pubblico YouTube mette UN commento del canale con LOOK UP + "Comment SKY". **Fissarlo**
   resta manuale in Studio (l'API di YouTube non permette di fissare i commenti).

Limiti: Instagram max 5 risposte a giro e 20 al giorno, con 20–40 s fra una e l'altra (account sospeso il 15/10);
le altre piattaforme 8 a giro e 30 al giorno. Un commento non riceve mai due risposte (`logs/engage-log.jsonl`), e
quelli a cui ha già risposto Simone a mano si saltano. Mai like, follow o commenti sui post di altri.

## DM (messaggi privati): pronti ma spenti
Meta permette a un'app in **modalità sviluppo** di mandare DM solo a chi ha un ruolo nell'app (cioè a Simone stesso).
Per scrivere in DM ai follower serve l'**Advanced Access**, che si ottiene così (solo Simone può farlo):
1. **Verifica aziendale** in Meta Business Suite → Impostazioni → Centro sicurezza (documento e dati dell'attività).
2. developers.facebook.com → app Cosmos → **App Review → Permissions and Features**: chiedere Advanced Access per
   `instagram_manage_messages`, `instagram_manage_comments`, `pages_messaging`, `pages_read_engagement`,
   `pages_manage_metadata`, con un video dimostrativo (lo prepara Claude) e la privacy policy del sito.
3. App in modalità **Live**; nell'app Instagram: Impostazioni → Messaggi → "Consenti l'accesso ai messaggi" attivo.
4. Poi basta la variabile del repo `ENGAGE_DM=true`. Da quel momento:
   - commento con parola chiave su IG o FB → **DM privato** col link (uno per commento, entro 7 giorni) + risposta
     pubblica "ti ho scritto in DM";
   - messaggio in DM → risposta col flusso giusto o con il menu (SKY / GUIDE / VIDEO), solo entro le 24 ore di Meta.
   Se il DM viene rifiutato, il bot ripiega da solo sulla risposta pubblica.
Threads e YouTube non hanno DM via API: lì restano le risposte pubbliche.

## Interruttori (Settings → Secrets and variables → Actions → Variables)
- `ENGAGE_ENABLED=false` spegne tutto; `ENGAGE_DM=true` accende i DM (solo dopo l'App Review).
- Pausa di una sola piattaforma: file `logs/ENGAGE_PAUSE_IG` (o `FB`, `TH`, `YT`, `DM`). Il bot lo crea da solo se
  Meta risponde con un errore di blocco o limitazione e manda l'e-mail di GitHub; per ripartire si cancella il file.
- Prova senza inviare nulla: Actions → engage → Run workflow con "dry run" spuntato.

## Segreti usati
`META_JSON`, `THREADS_JSON`, `GEMINI_API_KEY` (o `GEMINIAPIKEY3`), `YOUTUBE_TOKEN_JSON` (contenuto di
`Progetto-YouTube-Faceless\secrets\token.json`):
```powershell
Get-Content -Raw C:\Users\Simon\progetti_claude\Progetto-YouTube-Faceless\secrets\token.json | gh secret set YOUTUBE_TOKEN_JSON --repo cosmosinnumbers/cosmos-automation
```
