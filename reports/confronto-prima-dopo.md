# Confronto prima/dopo (Fase G) – 3/11/2026

Misurato con `tools/video_qc.py` (soglia di cambio scena 0,1) su Short veri costruiti da GitHub Actions.

| Short | Motore | Stacchi | Pausa max senza stacchi | Audio | Visual sul tema |
|---|---|---|---|---|---|
| primo-short-automatico-github (26/10) | prima | 16 | 12,1 s | -14,2 LUFS | clip NASA generiche |
| short-con-suoni-veri, Voyager (2/11) | motion + suoni | 11 | 6,8 s | -14,1 LUFS | clip NASA generiche |
| Mars e Jupiter (3/11, test C1) | dopo B+D, prima di C2 | n.d. | 13,5 s (soglia 0,25) | -14,1 LUFS | Hubble, Voyager, Io: fuori tema |
| ESCAPADE (3/11, test C2) | dopo A-D | 26 | 4,4 s | -14,1 LUFS | sonde ESCAPADE, Marte, Terra: sul tema |
| Leonidi (3/11) | dopo A-D | 15 | 8,2 s | -14,1 LUFS | solo 2 clip generiche "What's Up" |

Cosa è cambiato davvero: nessun quadro fermo oltre 4,4 s nel caso migliore, visual sul tema nel caso migliore, copy con le regole di ritenzione, controllo che blocca nero, assenza di movimento nei primi 1,5 s, audio fuori livello e durata fuori formato.

Limiti onesti:
- La ritenzione vera (obiettivo 75% visto, 100% durata media) si misura solo dopo la pubblicazione: questi Short sono release per il telefono, non ancora su YouTube. La curva di ritenzione per video è ora salvata da `metrics.py`, il ciclo settimanale la userà.
- Dove la libreria NASA ha poco materiale sul tema (meteore) restano 2 clip generiche: il QC lo segnala con un avviso, non lo blocca.
- Il critico di ritenzione dei lunghi funziona con Claude (secret `CLAUDE_CODE_OAUTH_TOKEN`) o Groq; oggi Gemini è in quota e GLM senza saldo, quindi non l'ho visto girare su un lungo vero (provato con test unitari).
