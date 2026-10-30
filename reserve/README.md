# Riserva di Short (shorts-build)

Se alle 15:00 lo Short del giorno non è uscito (Gemini e GitHub Models falliti), shorts-build pubblica come release
del giorno la prima cartella pronta di questa riserva (ordine alfabetico) e la toglie da qui.

Una cartella per Short, già controllato da una persona: `reserve/<id>/<id>.mp4`, `upload.md` (stesso formato di
shorts-build: `## Title`, `## Description`), `factcheck.md`, e facoltativo `expires` con la data AAAA-MM-GG
dopo la quale non va più usato. Meglio Short "dati" con numeri che non scadono.
