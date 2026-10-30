# Video lunghi su GitHub Actions

Una cartella per video: `longform/<id>/` con `script.yaml`, `assets.yaml`, `assets/`, `charts/`, e se servono
`thumbs.yaml` e `clips.yaml`. Il workflow `longform-build` fa voce, montaggio, sottotitoli, miniature, descrizione,
QC e le clip verticali, poi crea la release `lf-<id>` da scaricare sul telefono. Non carica niente.

- Approvazione (una volta a settimana, a mano): aggiungi `approved: true` a `script.yaml` e fai il push, oppure
  Actions → longform-build → Run workflow con l'id.
- Clip per Reel e TikTok, `clips.yaml`: `- {id: clip-a, start: 12.5, end: 48.0, headline: "..."}` (secondi del
  video finito, presi dal `.srt`).
- `p6-europa-clipper` è la prova del 30/10/2026 (stesso materiale di `Progetto-YouTube-Faceless/04-produzione`).
