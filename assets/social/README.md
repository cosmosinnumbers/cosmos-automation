# Libreria "social" (Instagram, Facebook, TikTok): separata da YouTube

Regola di simone (02/11/2026): sugli altri social si possono usare materiali in trend, virali e meme; su YouTube
resta solo materiale libero (NASA/ESA pubblico dominio, CC0, musica e suoni generati in codice).

Come funziona:
- `sounds/`: metti qui (da PC o telefono, con un commit) i suoni o le basi in tendenza da usare sui social
  (mp3, m4a, wav, ogg, aac). `video/ytf/short.py` crea allora anche `<id>_social.mp4`: stesso video, con il
  suono di questa cartella al posto della musica generata (a rotazione per giorno, oppure `social_sound:` nello
  short.yaml). La voce e gli effetti restano uguali.
- `tools/queue_short_reel.py` manda ai Reel IG/FB e a TikTok il file `_social` quando c'è; YouTube
  (`tools/yt_short_upload.py`) prende sempre e solo il file principale.
- Cartella vuota = nessuna variante: i social ricevono il file di YouTube, come prima.

Da sapere prima di caricare un suono:
- Le API di Instagram e TikTok non possono agganciare i "suoni in tendenza" delle loro librerie interne: il suono
  viene incollato nel file. Se è musica protetta, Meta e TikTok possono silenziare il video o limitarne la
  diffusione (succede in automatico, anche mesi dopo). Spezzoni brevi e rimontati (meme, effetti, voce sopra)
  rischiano molto meno di un brano intero.
- Non si caricano video interi di altri, né spezzoni scaricati da YouTube per essere ripubblicati così come sono.
- Ogni file qui dentro non va MAI in un video YouTube: la pipeline lo garantisce, non spostarlo in `assets/sfx/`.
