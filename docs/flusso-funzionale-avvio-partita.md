# Flusso Funzionale Dell'Applicazione

## Scopo Del Documento

Questo documento descrive il comportamento dell'applicazione dal momento in cui viene aperta fino all'inizio della partita.

Non e' un documento tecnico di dettaglio e non sostituisce il contratto architetturale del frontend. Serve a spiegare, in modo comprensibile anche a livello business o prodotto, che cosa fa il sistema, in quale ordine e con quali regole principali.

## Perimetro

Il documento copre:

- avvio dell'applicazione
- verifica di disponibilita' del backend
- recupero del contesto locale salvato sul dispositivo
- identificazione del giocatore
- creazione o ingresso in una stanza
- gestione della sala d'attesa
- passaggio dalla lobby alla partita

Non copre il dettaglio del gameplay dopo l'avvio della partita.

## Glossario Minimo

- Backend: il servizio server che gestisce login, stanze, partita e riconnessioni.
- Memoria locale: i dati salvati nel browser per ricordare il giocatore e, quando ha senso, la stanza in cui stava giocando.
- UUID: identificativo della sessione del giocatore lato backend.
- Room ID: codice stanza condivisibile per entrare in una partita.
- Owner: il proprietario della stanza, cioe' il giocatore che puo' avviare la partita e gestire alcuni comandi di lobby.

## Dati Che L'Applicazione Tiene In Memoria Locale

L'applicazione salva nel browser tre informazioni principali:

- `playerName`: il nome del giocatore
- `uuid`: l'identita' della sessione attiva
- `roomId`: la stanza a cui il giocatore stava partecipando

Questi dati non hanno tutti lo stesso significato:

- il nome serve soprattutto per migliorare la continuita' dell'esperienza utente
- lo uuid rappresenta una sessione valida lato server solo per un certo periodo o finche' il backend la considera attiva
- il roomId serve solo se l'applicazione deve provare a rientrare automaticamente nella stanza corretta

## Vista D'Insieme Del Flusso

In termini semplici, il percorso e' questo:

1. L'utente apre l'app.
2. L'app verifica che il backend sia raggiungibile.
3. Se il backend non risponde, mostra una schermata di caricamento e continua a riprovare.
4. Quando il backend torna disponibile, l'app controlla se esiste un contesto locale utilizzabile.
5. Se trova una sessione completa, prova a ripristinare il collegamento alla stanza.
6. Se non trova una sessione completa, ottiene una nuova identita' dal backend.
7. L'utente puo' creare una nuova stanza oppure entrare in una stanza esistente.
8. Una volta entrato, vede la lobby e attende l'avvio della partita.
9. Solo l'owner puo' far partire la partita.
10. All'avvio, i posti liberi vengono completati con bot e l'app passa alla schermata di gioco.

## 1. Avvio Dell'Applicazione

Quando l'applicazione viene aperta, non mostra subito un flusso interattivo completo. Prima verifica se il backend e' vivo e pronto a rispondere.

Dal punto di vista dell'utente questo significa:

- se il backend e' disponibile, il flusso prosegue quasi subito
- se il backend non e' disponibile, l'app rimane in una schermata di attesa
- durante questa attesa l'interfaccia principale resta disattivata per evitare azioni incoerenti

La schermata iniziale di caricamento quindi non e' una semplice animazione estetica: rappresenta lo stato reale di disponibilita' del sistema.

## 2. Verifica Di Disponibilita' Del Backend

La verifica viene fatta tramite un controllo leggero di raggiungibilita'. In pratica l'app effettua un ping al backend.

Il comportamento funzionale e' il seguente:

- se il ping ha successo, il backend viene considerato pronto
- se il ping fallisce, l'app non entra nel flusso di gioco
- invece di andare in errore definitivo, continua a riprovare periodicamente

Questo approccio evita due problemi:

- mostrare schermate che dipendono dal server quando il server non e' raggiungibile
- costringere l'utente a ricaricare manualmente la pagina in caso di avvio lento del backend

## 3. Recupero Del Contesto Locale

Quando il backend risulta pronto, l'app controlla cosa era stato salvato localmente sul dispositivo.

Qui il comportamento e' intenzionalmente differenziato tra tre casi.

### Caso A: Esistono `uuid` E `roomId`

Questo e' il caso di una sessione considerata completa. L'app assume che il giocatore stesse partecipando a una stanza e prova a ricostruire quel contesto.

In pratica:

- rimette in memoria applicativa il nome, lo uuid e il roomId
- prova a riaprire la connessione WebSocket verso quella stanza

Questo e' il meccanismo che consente la continuita' tra un refresh della pagina e il rientro automatico.

### Caso B: Manca Il `roomId`, Ma Esiste Il Nome

In questo caso l'app non prova a rientrare in una stanza, perche' non avrebbe abbastanza contesto per farlo in modo affidabile.

Fa invece una cosa piu' semplice:

- recupera il nome del giocatore
- chiede al backend una nuova identita' valida

Dal punto di vista dell'esperienza utente, il nome viene ricordato ma la partecipazione a una stanza no.

### Caso C: La Sessione Salvata Non E' Piu' Valida

Questo e' il caso piu' delicato ed e' quello che in passato poteva bloccare l'app.

Se il backend comunica che la sessione non e' piu' valida:

- l'app considera non riutilizzabili lo uuid e il roomId salvati
- cancella il contesto locale ormai obsoleto
- mantiene il nome del giocatore
- torna a uno stato pulito di home
- chiede immediatamente al backend una nuova identita'

Il risultato business e' che l'utente non resta intrappolato in un loop di riconnessione fallita. Perde il legame con la vecchia stanza, ma torna operativo.

## 4. Identificazione Del Giocatore

L'identificazione avviene tramite una chiamata di login al backend.

Il backend restituisce:

- uno uuid valido
- il nome effettivo assegnato al giocatore

Da quel momento l'app salva localmente la nuova identita'.

Questa fase serve a distinguere due concetti:

- il nome, che e' una preferenza utente o un'etichetta visibile
- l'identita' di sessione, che e' il vero riferimento usato dal server per considerare la presenza del giocatore valida oppure no

## 5. Home: Creare O Cercare Un Tavolo

Una volta pronto il backend e ottenuta o recuperata un'identita' valida, l'utente si trova nella schermata iniziale.

Qui il flusso e' volutamente semplice.

L'utente inserisce il proprio nome e puo' scegliere tra due azioni:

- `Nuova partita`
- `Cerca un tavolo`

Se il nome non e' stato inserito, l'app non prosegue e richiama l'attenzione sull'input. Questo impedisce di creare o cercare una stanza senza un'identita' comprensibile agli altri partecipanti.

### Nuova partita

Se l'utente sceglie di creare una nuova partita:

- l'app chiede al backend un nuovo codice stanza
- salva localmente il roomId insieme a uuid e nome
- apre la connessione alla stanza appena creata

### Cerca un tavolo

Se l'utente vuole entrare in una stanza esistente:

- inserisce il codice stanza
- l'app salva localmente il roomId selezionato
- prova a collegarsi a quella stanza usando il proprio nome e la propria sessione

In entrambi i casi, il passaggio successivo non e' ancora la partita ma la sala d'attesa.

## 6. Ingresso In Stanza E Assegnazione Del Posto

Quando la connessione verso la stanza va a buon fine, il backend decide se il giocatore puo' entrare, rientrare oppure no.

Le regole principali sono queste.

### Se La Partita Non E' Ancora Iniziata

Il backend verifica che la sessione sia ancora valida. Se lo e', assegna al giocatore il primo posto libero disponibile al tavolo.

Il primo giocatore umano che entra diventa owner della stanza.

L'app riceve quindi le informazioni necessarie per mostrare la lobby:

- il posto assegnato al giocatore
- la lista attuale dei partecipanti
- il posto del proprietario della stanza

### Se La Partita E' Gia' In Corso

Il backend non tratta l'ingresso come un nuovo join. Prova invece a riconoscere il giocatore come rientrante.

Prima prova a identificarlo tramite uuid. Se non basta, usa un fallback sul nome per compatibilita'.

Se il giocatore viene riconosciuto correttamente:

- viene riattaccato al proprio posto
- l'app passa direttamente alla schermata di gioco
- il server invia subito lo stato corrente della partita

Se invece il giocatore non puo' essere riconosciuto, l'ingresso non viene autorizzato.

## 7. Funzionamento Della Sala D'Attesa

La lobby e' lo spazio in cui i giocatori si raccolgono prima dell'avvio effettivo della partita.

Da un punto di vista business, la lobby ha quattro funzioni:

- mostrare il codice stanza da condividere
- mostrare chi e' seduto ai quattro posti del tavolo
- indicare chiaramente chi e' l'owner
- consentire all'owner di preparare il tavolo prima dell'inizio

### Informazioni Visibili In Lobby

L'utente vede:

- il codice stanza, copiabile per invitare altri partecipanti
- i posti del tavolo occupati e quelli ancora in attesa
- il proprio posto
- l'indicazione dell'owner

### Poteri Dell'Owner

Solo l'owner puo':

- avviare la partita
- scambiare due posti al tavolo
- espellere un giocatore umano
- promuovere un altro giocatore umano a owner

Gli altri partecipanti vedono la lobby, ma non possono avviare la partita ne' usare i comandi di gestione della stanza.

### Se Un Giocatore Lascia La Lobby

Se un giocatore abbandona prima dell'inizio della partita:

- il suo posto viene liberato
- la lista dei partecipanti viene aggiornata per tutti

Se ad abbandonare e' l'owner, la proprieta' della stanza viene riassegnata a un altro partecipante umano ancora presente.

Se la stanza resta completamente vuota, il backend la elimina.

## 8. Avvio Della Partita

La partita parte solo quando l'owner invia il comando di avvio.

Non e' necessario che tutti e quattro i posti siano occupati da persone reali. Al momento dell'avvio, il backend completa automaticamente i posti vuoti con bot.

Questo passaggio ha tre effetti funzionali immediati:

1. lo stato della stanza passa da sala d'attesa a partita in corso
2. i posti liberi vengono riempiti con bot dotati di nome proprio
3. il server invia a tutti i partecipanti il messaggio di inizio partita

Quando l'app riceve questo evento:

- aggiorna l'elenco completo dei giocatori, inclusi gli eventuali bot
- cambia schermata dalla lobby al tavolo di gioco
- azzera i dati temporanei di lobby che non servono piu' come contesto di attesa

Da qui in poi inizia il flusso di partita vero e proprio.

## 9. Gestione Della Connessione Prima E All'Inizio Del Match

Durante il collegamento alla stanza e durante la partita, l'app mantiene una connessione persistente con il backend.

Dal punto di vista funzionale:

- la connessione viene aperta quando l'utente entra o rientra in una stanza
- l'app misura periodicamente la raggiungibilita' della sessione con messaggi di ping/pong
- se la connessione cade mentre la partita e' gia' in corso, l'app prova a riconnettersi automaticamente per un numero limitato di tentativi

Questa logica e' importante soprattutto in mobilita' o con rete instabile, perche' evita che una disconnessione breve venga percepita subito come abbandono definitivo.

## 10. Regole Funzionali Riassuntive

Le regole piu' importanti, dal punto di vista del prodotto, sono queste:

- l'app non entra nel flusso utente finche' il backend non risponde
- il nome del giocatore viene ricordato localmente per rendere il rientro piu' comodo
- la stanza viene riutilizzata automaticamente solo se esiste un contesto completo e coerente
- una sessione locale non piu' valida viene scartata, non riutilizzata a forza
- il primo giocatore umano che entra in stanza diventa owner
- solo l'owner puo' avviare la partita e gestire il tavolo in lobby
- i posti non occupati vengono riempiti con bot al momento dell'avvio della partita
- se la partita e' gia' iniziata, l'accesso viene trattato come riconnessione e non come nuovo ingresso

## 11. Casi Di Errore O Di Deviazione Dal Flusso Principale

Prima dell'inizio della partita, i casi principali che possono deviare dal percorso standard sono:

- backend non raggiungibile: l'app resta in caricamento e riprova
- stanza non trovata: l'ingresso non va a buon fine
- stanza piena: il backend rifiuta il join
- partita gia' iniziata senza riconoscimento del giocatore: l'utente non entra come nuovo partecipante
- sessione non valida: l'app scarta la vecchia sessione, mantiene il nome e si rigenera
- espulsione dalla lobby: l'utente torna a uno stato pulito con messaggio esplicativo

## 12. In Sintesi

Fino all'inizio della partita, l'applicazione si comporta come un orchestratore di continuita' e coerenza:

- prima verifica che il sistema centrale sia disponibile
- poi prova a ricostruire il contesto utente piu' sensato possibile
- se il contesto non e' valido, lo rigenera senza bloccare l'utente
- porta il giocatore in lobby con un ruolo chiaro
- fa partire il match solo quando il tavolo e' pronto e l'owner lo decide

Per questo motivo il flusso iniziale non e' solo una sequenza di schermate, ma una serie di controlli di consistenza tra dispositivo, backend, stanza e presenza del giocatore.
