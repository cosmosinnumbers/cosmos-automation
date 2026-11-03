# Prompt: video lunghi coinvolgenti (03/11/2026)

Richiesta di simone del 03/11/2026: il video lungo deve intrattenere ed essere coinvolgente per chi guarda. Niente
capitoli: non servono allo spettatore. Più immagini per ogni parte. La voce parla a chi guarda: fa domande, chiede
di commentare e di seguire, e presenta la guida LOOK UP su Gumroad, anche con uno spot a metà video. Titoli e hook
sono specifici e chiari, scritti come copywriting o nello stile dei video in trend della nicchia. Tutto gira su
GitHub Actions, mai sul PC.

Valgono le regole già fissate: solo asset liberi su YouTube (NASA/ESA, CC0), ogni numero viene dalle fonti, mai un
codice sconto a schermo (COSMOS9 solo in descrizione), caricamento solo via API YouTube, nessun ok umano su script e
video (contano i controlli automatici).

Ogni step si fa in ordine, si verifica con test o con un controllo su Actions e solo dopo si passa al successivo.

## Step 1. Una storia sola, senza capitoli a schermo

- Lo script resta diviso in "atti" (6-8) solo per il ritmo interno: ogni atto apre rispondendo alla domanda lasciata
  da quello prima e chiude con una nuova domanda o una svolta.
- La voce non annuncia mai un capitolo o una parte ("Chapter 2", "Part three", "In this section"). I passaggi tra
  atti sono frasi che tirano avanti ("So if that is true, why does NASA…?").
- A schermo: niente cartelli "CHAPTER 01", niente titoli di capitolo, niente Typewriter di capitolo.
- In descrizione: niente elenco di capitoli con i minuti.
- Il QC non chiede più "almeno 3 capitoli" quando lo script dice `chapters: false`.
- Tra un atto e l'altro restano la transizione (glitch o zoom-through) e il riser, che fanno ritmo senza nominare
  niente.

## Step 2. Parlare a chi guarda

Nella narrazione:
- "you" in tutto il video: almeno una frase su cinque si rivolge allo spettatore ("Picture yourself standing on…").
- Almeno 4 domande dirette allo spettatore, sparse. La prima entro il primo minuto, dove si chiede di scommettere
  ("Before I tell you, guess: closer to 10 or to 100? Write it in the comments.").
- 2 battute "ask": una domanda breve, al massimo 12 parole, a cui si risponde nei commenti. Compare a schermo con il
  Typewriter ("> your turn" + domanda). Una nella prima metà, una nel finale.
- 1 invito a seguire il canale, una sola volta e subito dopo il momento "wow" più forte, mai all'inizio:
  "If numbers like this make your day, follow: there is a new one every day."
- Mai "smash the like", "in this video", "did you know" o saluti.

## Step 3. Lo spot della guida a metà video

- Una battuta "spot" tra il 35% e il 65% del video, subito dopo aver dato valore e mai mentre una domanda è aperta
  da meno di 20 secondi. Sono 2 frasi, al massimo 40 parole: cos'è LOOK UP (la guida per principianti per trovare
  in cielo quello di cui parliamo) e dove si trova ("link in the description"). Mai prezzo o codice.
- A schermo c'è la scena Phone Screens con la copertina della guida ("LOOK UP · Link in description").
- Alla fine c'è un secondo richiamo a LOOK UP nelle ultime 3 battute, più un'ultima domanda per i commenti.
- LOOK UP compare quindi esattamente 2 volte: nello spot e nel finale.

## Step 4. Più immagini, mai una foto ferma

- Ogni battuta (1-2 frasi, circa 5 s) ha il suo visual. Almeno 30% foto o clip vere e almeno 40% grafica dati,
  mai tre dello stesso tipo di fila (regole già presenti).
- Ogni atto ha almeno 3 query di immagini diverse: niente stessa query due volte nello stesso atto.
- Il montaggio taglia comunque ogni inquadratura sopra gli 8 s e trasforma in testo animato i numeri detti (PR #35).

## Step 5. Titolo e hook da copywriter

Il titolo:
- specifico: il soggetto concreto più un numero vero o un contrasto preciso ("Why NASA Will Fly Past Europa 49
  Times", non "The Secret of Europa");
- chiaro in 2 secondi, al massimo 60 caratteri, con una sola promessa e senza parole vaghe da sole (secret,
  mystery, amazing, insane, shocking, truth, crazy);
- nello stile dei titoli che crescono questa settimana nella nicchia (research/cosmos/trends-*.json: formati, hook ed
  esempi): si copia la struttura, mai il titolo.

L'hook (prima frase, entro 5 s, al massimo 14 parole):
- è la promessa del titolo detta con altre parole, con il numero o il contrasto subito;
- nelle prime 75 parole ci sono la posta in gioco, la promessa del finale e la prima domanda allo spettatore.

Ci sono 2 titoli alternativi per il test A/B, con hook diversi (paradox, extreme_number, comparison, question, you).
Il critico di ritenzione dà un voto anche a "engagement", cioè quanto il video parla a chi guarda: deve essere
almeno 7.

## Step 6. Controlli automatici (script_check)

Bloccano lo script e lo rimandano allo scrittore:
- parole che annunciano un capitolo o una parte;
- meno di 4 domande con "you" o "your";
- battute "ask" diverse da 2, battuta "spot" diversa da 1 o fuori dal 35-65%;
- LOOK UP diverso da 2 volte (spot + ultime 3 battute), oppure un codice sconto o un prezzo nella narrazione;
- un titolo senza numero o contrasto, più lungo di 60-70 caratteri o con parole vaghe da sole;
- un atto con meno di 3 query di immagini diverse.

## Step 7. Misurare e correggere

- Dopo 7 giorni da ogni lungo, metrics.yml legge la ritenzione (r25/r50/r75) e i commenti. Il report del lunedì
  confronta lo spot (calo di ritenzione nei 20 s dello spot), le battute ask (commenti arrivati) e i titoli A/B.
- Se lo spot fa perdere più di 5 punti di ritenzione, va spostato più tardi o accorciato. Se le domande non portano
  commenti, vanno cambiate in domande a scelta (A o B).
