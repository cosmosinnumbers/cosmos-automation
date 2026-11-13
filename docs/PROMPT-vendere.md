# Prompt di lavoro: far vendere i prodotti di Cosmos in Numbers

Versione ottimizzata (13/11/2026) della richiesta di simone: "usa Fable per migliorare il progetto e arrivare
finalmente a vendere i prodotti, rivedi tutto il piano, usa i trend, metti nuove skill, usa Jev per decidere".
Da incollare in un nuovo thread, oppure da richiamare con la skill `/vendita`.

## Il prompt

```
Obiettivo misurabile: prima vendita di LOOK UP, poi 5 vendite al mese. Non "più contenuti": più clic veri di
persone che vogliono guardare il cielo, e una pagina che li converte.

1. Parti dai numeri, non dalle idee. Leggi reports/funnel.md (visualizzazioni, clic veri verso Gumroad,
   download del gratuito, vendite) e dimmi in una riga qual è il collo di bottiglia di questa settimana.
   Un numero non misurato si scrive "non misurato": non stimarlo.
2. Lavora solo sul collo di bottiglia. Clic sotto lo 0,3% delle visualizzazioni: contenuti e link. Clic sopra
   30 a settimana senza download: pagine Gumroad. Download sopra 20 senza vendite: passaggio gratis -> pagamento.
3. Ogni contenuto deve avere una strada cliccabile verso il prodotto. Link cliccabili: descrizione e commento
   fissato dei video LUNGHI di YouTube, pagina del canale, bio, post Facebook, risposte su Threads. Non cliccabili:
   descrizione e commenti degli Short, didascalie Instagram e TikTok.
4. Scrivi per chi compra una guida al cielo: cosa si vede stasera, sciami di meteore, pianeti, primo binocolo o
   telescopio, eclissi del 2 agosto 2027. Le curiosità sullo spazio portano visualizzazioni, non acquirenti.
5. Usa i trend come FORMATO (struttura, ritmo, tipo di titolo, eventi del cielo dei prossimi giorni), mai
   ricaricando video altrui. YouTube: solo materiale libero (CC0, CC-BY con credito, NASA/ESA).
6. Quando ci sono alternative (titoli, inviti all'acquisto, offerte, priorità), scrivine almeno 8 e falle
   valutare a Jev (jev_score con livelli scritti per esteso). Riporta il punteggio e tieni solo le prime.
   Jev rompe i pareggi: la decisione finale la prendono i numeri veri dopo 7 giorni.
7. Regole fisse: testi pubblici in inglese, report a simone in italiano; link Gumroad tracciati
   (tools/links.py); codice COSMOS9 = $7,41 fino al 30/11; TikTok mai "contenuti commerciali", link solo in bio;
   tutto su GitHub Actions; nessuna chiave in chiaro; le PR le unisci tu, salvo cose rischiose.
8. Chiudi con tre cose: cosa hai cambiato (con link), cosa aspettarsi in numeri e quando lo verifichi, cosa
   serve da simone (account, login, incolla). Niente promesse di vendite: intervalli e condizioni.
```

## Perché è scritto così

| Prima | Adesso | Motivo |
|---|---|---|
| "arrivare a vendere" | prima vendita, poi 5 al mese, e un collo di bottiglia a settimana | senza un numero ogni thread rifaceva il piano da capo |
| "rivedi tutto il piano" | leggi `reports/funnel.md` e lavora su un solo passo | il 13/11 il piano era giusto ma i clic veri erano 1 in 7 giorni su 3.395 visualizzazioni |
| "usa i trend" | trend come formato + eventi del cielo dei prossimi giorni | i trend di intrattenimento portavano spettatori che non comprano una guida |
| "usa Jev per decidere" | almeno 8 alternative, livelli scritti, punteggio riportato | Jev è un classificatore: serve una rosa di candidati e una scala chiara |
| "metti nuove skill" | skill `/vendita` nel repo con la procedura | la procedura resta al prossimo thread |

## Cosa ha deciso Jev il 13/11/2026 (jev-1.14.0)

Priorità (probabilità di portare i primi clienti in 30 giorni, scala 0-4): Amazon KDP 2,22 · video lunghi che
rispondono a ricerche 2,18 · contenuti "cielo di stasera" 2,10 · sistemare i link 1,63 · Pinterest 1,39 ·
Etsy 1,34 · nuovo PDF gratuito 1,14 · Black Friday 1,09 · più post Threads 0,64 · abbassare il prezzo 0,52 ·
più Short di curiosità 0,51 · altri prodotti nuovi 0,46.

Titoli dei lunghi (intenzione d'acquisto, 0-4): Binoculars vs Telescope 3,21 · 5 Things in Tonight's Sky 3,02 ·
Jupiter Tonight 3,01 · Your First Night With a Telescope 3,00 · Night Sky December 2,77 · Geminids 2,66 ·
Supermoon 1,09. Stanno in `config/sales-topics.json`.

Inviti all'acquisto (spinta al clic, 0-4): calendario del cielo gratuito 2,94 · "Want to find this yourself
tonight?" 2,75 · "never shown where to look" 2,25. In fondo le frasi che usavamo: "If you like these numbers"
1,18 · PDF dei 20 numeri 1,23 · "173 pages, every number sourced" 1,40. Stanno in `tools/cta.py`.
