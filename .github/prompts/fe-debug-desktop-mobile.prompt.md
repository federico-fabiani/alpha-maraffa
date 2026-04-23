---
name: fe-debug-desktop-mobile
description: Debugga il frontend locale con confronto desktop vs mobile landscape, screenshot e controlli UI.
argument-hint: "Opzionale: route, schermata o problema da controllare"
agent: agent
tools:
  - mcp_chrome-devtoo/*
---

Analizza il frontend locale su `http://localhost:5173/`.

Contesto opzionale dell'utente: ${input:focus:homepage, route, schermata o problema specifico}

Segui questo workflow:

1. Apri `http://localhost:5173/` con i tool DevTools.
2. Se la pagina non risponde, fermati e spiega con precisione il blocco.
3. Esegui un controllo desktop con viewport `1440x1024`.
4. Esegui un controllo mobile in `landscape`, invertendo width e height rispetto al portrait. Usa come default `844x390,mobile,touch,landscape`.
5. Per ogni viewport:
   - attendi che il rendering sia stabile
   - cattura almeno uno screenshot utile
   - verifica overflow orizzontale, clipping, contenuti fuori viewport, CTA nascoste, z-index errati, font troppo piccoli, tap target stretti, immagini deformate, modali o overlay rotti, elementi fixed o sticky che coprono contenuti
   - raccogli solo errori console o network rilevanti per il problema osservato
6. Se serve, percorri il minimo flusso necessario per raggiungere la schermata indicata nel contesto opzionale.
7. Confronta desktop e mobile landscape e segnala solo problemi concreti, riproducibili e visibili.

Formato output richiesto:

- Desktop: esito sintetico e problemi trovati
- Mobile landscape: esito sintetico e problemi trovati
- Delta responsive: cosa peggiora o si rompe passando da desktop a mobile landscape
- Screenshot: riepilogo degli screenshot catturati
- Console/network: solo segnali utili
- Fix consigliati: massimo 3, ordinati per impatto

Regole operative:

- Non modificare codice salvo richiesta esplicita.
- Non fare un audit generico: concentrati su layout, leggibilita', interazione e stabilita' visiva.
- Se l'utente chiede "mobile" senza specificare altro, assumi sempre `landscape`.
- Se l'utente indica una route o una feature specifica, dai priorita' a quella, ma includi comunque il confronto desktop vs mobile landscape.