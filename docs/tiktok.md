# TikTok: Content Posting API (Direct Post), verifica del 24/10/2026

Fonti (tutte con "Last updated August 4, 2026"):
- https://developers.tiktok.com/doc/content-posting-api-get-started
- https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- https://developers.tiktok.com/doc/content-sharing-guidelines
- https://developers.tiktok.com/doc/oauth-user-access-token-management

## Cosa dice la documentazione
| Tema | Fatto verificato |
|---|---|
| Requisiti | app registrata, prodotto Content Posting API con Direct Post attivo, scope `video.publish` approvato e autorizzato dall'utente (OAuth con Login Kit per ottenere token e open_id) |
| Client non revisionati | tutti i post sono **privati** (SELF_ONLY); su account pubblici l'init risponde 403 `unaudited_client_can_only_post_to_private_accounts`; massimo 5 utenti in 24 h |
| Token | access token 24 h; refresh token 365 giorni; il refresh può restituire un refresh token nuovo da usare al posto del vecchio |
| Limiti | 6 richieste/minuto per token sull'init; tetto giornaliero per creator (`spam_risk_too_many_posts`, circa 15 post/giorno indicato nelle linee guida) e quota del client (`reached_active_user_cap`) |
| Privacy via API | `post_info.privacy_level` = `PUBLIC_TO_EVERYONE` (deve essere fra le `privacy_level_options` di creator_info) |
| "Il tuo brand" | `post_info.brand_organic_toggle: true` (`brand_content_toggle` = contenuto sponsorizzato di terzi, per noi false) |
| Etichetta IA | supportata: `post_info.is_aigc` (predefinito false). Da noi resta false (decisione del 24/10/2026) |
| PULL_FROM_URL | solo da dominio o prefisso URL verificato nel portale (Media Transfer Guide); altrimenti FILE_UPLOAD |

## Il punto critico: la revisione
Le linee guida (content-sharing-guidelines) chiedono che, **a ogni post**, l'utente scelga a mano la privacy da un
menu senza valore predefinito, attivi a mano commenti/duetti/stitch (nessuno spuntato di default), veda l'anteprima
e dia il consenso prima dell'invio. Nell'elenco degli usi **non accettabili** c'è testualmente:
"A utility tool to help upload contents to the account(s) you or your team manages", e le app devono essere
"intended for a wide audience, not limited to internal groups/private use".

Conseguenza: il nostro caso d'uso onesto (pubblicazione programmata dei contenuti originali di @cosmosinnumbers,
un solo account, nessun clic per post) è esattamente quello che le linee guida escludono. Una richiesta onesta ha
probabilità molto alte di essere rifiutata; una richiesta che descrivesse un'app per il pubblico generale non sarebbe
vera, e non la preparo. Per questo non ho costruito la pagina di pubblicazione "conforme" né il video dimostrativo:
dimostrerebbero un flusso con un clic per post, che non è quello che useremmo.

Cosa è comunque pronto:
- `tools/tiktok_api.py` (auth-url, setup, refresh, check, post, next) con privacy pubblica, "Il tuo brand",
  etichetta IA da config (`TIKTOK_AIGC_LABEL`, predefinito false). Nel workflow `TIKTOK_ENABLED=false`.
- Privacy Policy e Terms già online: https://cosmosinnumbers.github.io/privacy.html e /terms.html (risposta 200 il 24/10/2026).
- Se vuoi provare lo stesso: crei l'account su https://developers.tiktok.com (Log in → "Manage apps" → "Connect an app"),
  e mi scrivi "tiktok prova": preparo scheda, icona, redirect URI (https://cosmosinnumbers.github.io/tiktok-callback.html)
  e testo della richiesta con il caso d'uso vero. Il clic su "Submit for review" resta tuo.

## Piano B: servizi già approvati da TikTok (confronto, nessun account creato, nessuna spesa)
| Servizio | Prezzo attuale (fonte) | API | "Il tuo brand" via API | Limiti |
|---|---|---|---|---|
| Ayrshare | Premium $149/mese ($129 annuale), 1 profilo (pagina prezzi ayrshare.com, modificata l'8/07/2026) | sì, REST | sì: `tikTokOptions.isBrandOrganic` (anche `isAIGenerated`, `visibility`) | 6 video/min, 15/giorno; riautorizzare TikTok ogni anno |
| Publer | Business $10/mese ($8 annuale) per il primo account (prezzi da siti terzi di giugno 2026, da ricontrollare su publer.com/plans) | sì, solo piani Business ed Enterprise (docs Publer) | non documentato nella pagina API | non documentati |
| Buffer | Essentials $6/canale/mese, Team $12 (recensioni 2026) | API GraphQL in beta con chiave personale; nuove app non accettate (fonte: blog di un concorrente) | non trovato | non documentati |

Lettura: Ayrshare è l'unico dei tre con il campo "Il tuo brand" documentato, ma costa $129–149 al mese. Publer è
economico ma il supporto alla divulgazione del brand non è verificato. Buffer oggi non è un'API utilizzabile.
Alternativa a costo zero: restare con TikTok Studio da Chrome (come oggi), con avviso immediato se Chrome non è collegato.
