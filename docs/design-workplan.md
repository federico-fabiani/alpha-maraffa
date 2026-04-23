# Piano di lavoro — Redesign visivo Marafone

Sequenza di task ordinata per dipendenze. Ogni fase è autonoma e testabile prima di passare alla successiva.

---

## Stato attuale

Il frontend funziona. Il backend non si tocca. Il redesign è **solo CSS + layout React** — nessuna logica di gioco viene modificata.

Problema principale da risolvere: la palette `felt-*` (verde) va eliminata e sostituita con la palette osteria (ruggine + crema + legno). Il GameScreen usa un tavolo verde che evoca il poker.

---

## Fase 1 — CSS Foundation (1 sessione)

**Obiettivo**: rimpiazzare i token di colore, standardizzare la tipografia, tenere le animazioni esistenti.

### 1.1 — Pulire i token in `index.css`

Rimuovere da `@theme`:

```css
/* RIMUOVERE */
--color-felt-950 … --color-felt-500   /* tutti i verde-feltro */
--color-team-b: #1d4ed8;              /* blu squadra, fuori palette */
```

Aggiungere in `@theme`:

```css
--color-rust: #5c1a0a;
--color-rust-hover: #7a2210;
--color-cream: #f5e6c4;
--color-parchment: rgba(255, 248, 218, 0.62);
--color-border: rgba(120, 48, 18, 0.42);
--color-wood: #2a1a0e;
--color-gold: #c8922a;
--color-gold-dark: #9a6e1a;
--color-ink: #1a0f0a;
--color-team-a: #c8922a;
--color-team-b: #8b3a1a;
--font-display: "Cinzel", serif;
--font-body: "IM Fell English", serif;
--font-ui: "Outfit", sans-serif;
```

### 1.2 — Aggiornare gli stili globali

- `body` background: `var(--color-wood)` invece del gradiente verde
- Rimuovere la texture griglia verde (`body::before` con `ambient-pan`) — sostituire con texture legno o lasciare scuro uniforme
- `.screen-content`: cross-fade 380ms — invariato

### 1.3 — Verificare che home e lobby mantengano l'aspetto

Tutto ciò che usa classi `felt-*` va rimappato a variabili nuove. Grep: `felt-` nel codice.

**Deliverable**: Home e Lobby visivamente corrette, nessun verde.

---

## Fase 2 — HomeScreen (1 sessione)

**Obiettivo**: home pulita, stile osteria, nessuna regressione funzionale.

### Componenti da toccare

- `HomeScreen.tsx` (layout JSX)
- Sezione home in `index.css`

### Specifiche

- Background: `background.png` fullscreen, `object-fit: cover`
- Titolo: `title.png`, max-width 380px, centrato, `animate-float`
- Input nome:
  - font: `var(--font-body)`, italic
  - background: `var(--color-parchment)`
  - bordo: `1px solid var(--color-border)`
  - colore testo: `var(--color-ink)`
  - placeholder: IM Fell English, opacità 0.5
  - `input-shake` su submit vuoto — già implementato, verificare
- Menu voci (Crea / Unisciti):
  - font: `var(--font-display)`, peso 700, size ~1.4rem
  - colore: `var(--color-rust)`
  - hover: `var(--color-rust-hover)`, sottolienato
  - Frecce `arrow.png`: opacity 0 → 1 su hover, `scaleX(-1)` per sinistra
  - Nessun `<button>` con bordo visibile — stile `background: none`
- Input codice stanza (join):
  - stessa palette dell'input nome
  - appare/sparisce con fade se si clicca "Unisciti"

**Deliverable**: screenshot home corrispondente al design.

---

## Fase 3 — LobbyScreen (1 sessione)

**Obiettivo**: i posti al tavolo sembrano sedie, non celle di una griglia.

### Layout fisico del tavolo

```
         [ Posto 2 — avversario ]
[ Posto 3 ]   [ TAVOLO ]   [ Posto 1 ]
         [ Posto 0 — io    ]
```

Implementazione CSS:

```css
.lobby-table {
  display: grid;
  grid-template-areas:
    ". top ."
    "left . right"
    ". bottom .";
  grid-template-columns: 1fr 2fr 1fr;
  grid-template-rows: auto 8rem auto;
}
```

### Posto occupato

- Avatar placeholder: cerchio 56px, sfondo crema, bordo colore team
- Nome: Cinzel, rust o cream a seconda del background
- Badge team: piccolo rettangolo colorato con lettera (A / B)
- Indicatore "Pronto": checkmark oro se ready

### Posto libero

- Cerchio tratteggiato, opacità 0.4
- Testo "Attesa..." IM Fell English italic, rust 0.5

### Codice stanza

- Cinzel, size 2rem, lettera-spacing ampio
- Bordo ruggine, background parchment
- Click-to-copy: tooltip "Copiato!" che appare 1.5s

### Bottoni host (kick/start)

- Cinzel, sfondo rust, testo cream, bordo rust-dark
- hover: rust-hover
- Start: appare solo quando tutti i posti occupati

**Deliverable**: lobby con layout fisico, palette corretta.

---

## Fase 4 — GameScreen — layout base (1 sessione)

**Obiettivo**: rimpiazzare il tavolo verde con il tavolo osteria. Funziona anche con `background.png` come placeholder mentre `table-perspective.png` non è disponibile.

### 4.1 — Background

```css
.game-screen {
  background-image: url("/assets/table-perspective.png"); /* o background.png come fallback */
  background-size: cover;
  background-position: center;
}
```

Overlay per leggibilità:

```css
.game-screen::after {
  content: "";
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.15);
  pointer-events: none;
}
```

### 4.2 — `.piano-gioco` (TableArea)

```css
.piano-gioco {
  transform: perspective(900px) rotateX(28deg);
  transform-origin: center bottom;
  /* calibrare il valore di rotateX visivamente sul background definitivo */
}
```

Drop shadow direzionale (luce dall'alto-sinistra):

```css
.card-face {
  filter: drop-shadow(3px 5px 4px rgba(0, 0, 0, 0.55));
}
```

### 4.3 — Rimuovere il verde dalla TableArea

In `TableArea.tsx` e `index.css`:

- Rimuovere classi con `felt` e `green`
- Background `.table-area`: `transparent` — il background del GameScreen fa il lavoro

### 4.4 — PlayerArea avversari

- Nomi: Outfit 0.75rem, sfondo `rgba(42,26,14,0.75)`, bordo oro sottile, bordo-radius 4px
- Carte impilate: mantenere `opponent-float`
- Indicatore turno: `animate-pulse-ring` in oro — invariato, solo verificare i colori

### 4.5 — Mano giocatore (bottom)

- Layout fan: invariato (margin-left negativo + rotazione per indice)
- `playable`: lift -5px, gold glow — verificare che il glow usi `var(--color-gold)`
- `selected`: lift -12px

**Deliverable**: GameScreen senza verde, carte appoggiate visivamente sul tavolo inclinato.

---

## Fase 5 — Animazioni carta giocata (1 sessione)

**Obiettivo**: le carte "atterrano" sul tavolo invece di apparire.

### Animazione attuale

`card-appear`: 350ms, overshoot springy. Buona ma non ha il senso fisico del "lancio".

### Nuova animazione `card-land`

```css
@keyframes card-land {
  0% {
    transform: translateY(60px) scale(0.85) rotate(-3deg);
    opacity: 0;
    filter: drop-shadow(2px 2px 2px rgba(0, 0, 0, 0.3));
  }
  65% {
    transform: translateY(-4px) scale(1.02) rotate(0.5deg);
    filter: drop-shadow(6px 8px 8px rgba(0, 0, 0, 0.6));
  }
  80% {
    transform: translateY(2px) scale(0.99) rotate(0deg);
    filter: drop-shadow(3px 5px 4px rgba(0, 0, 0, 0.55));
  }
  100% {
    transform: translateY(0) scale(1) rotate(var(--card-rotation));
    filter: drop-shadow(3px 5px 4px rgba(0, 0, 0, 0.55));
  }
}
```

### Bussata — variante impatto forte

Aggiungere classe `.bussata` alla carta con:

```css
@keyframes card-slam {
  /* come card-land ma con vibrazione finale */
  80% {
    transform: translateY(3px) scale(0.97);
  }
  90% {
    transform: translateY(-2px) scale(1.01);
  }
  95% {
    transform: translateY(1px);
  }
  100% {
    transform: translateY(0) scale(1);
  }
}
```

Come sapere quando applicare `.bussata`: la carta ha declaration `busso` nel payload WebSocket → `TableArea.tsx` già riceve questa informazione.

**Deliverable**: carte che atterrano con peso fisico; bussata distinta.

---

## Fase 6 — Video di transizione (asincrono — dipende da asset esterni)

**Obiettivo**: la transizione lobby→game diventa il "sedersi al tavolo".

### Quando disponibile `intro.webm`

In `App.tsx` (o nel componente che gestisce il cambio schermata):

```tsx
// Prima di mostrare GameScreen
setScreen("transition");
// Mostra <video> fullscreen con autoplay
// Al termine dell'evento 'ended': setScreen('game')
```

CSS:

```css
.transition-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  animation: fade-in 300ms ease;
}
.transition-overlay video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
```

### Senza video (fallback attuale)

Cross-fade 600ms diretto lobby→game.

**Deliverable**: transizione fluida quando il video è disponibile; fallback silenzioso senza video.

---

## Fase 7 — GameOverScreen e dettagli finali (1 sessione)

- Background: `background.png` (ritorno alla tovaglia)
- Testo vincitore: Cinzel, colore team vincente
- Punteggi: IM Fell English
- Bottone "Nuova partita": stile menu home

**Nota**: il layout attuale di GameOverScreen è funzionale. Fase 7 è principalmente palette + font.

---

## Dipendenze asset

| Asset                   | Necessario per                            | Come generarlo                                          |
| ----------------------- | ----------------------------------------- | ------------------------------------------------------- |
| `table-perspective.png` | Fase 4 (GameScreen background definitivo) | Frame 2 già pronto — rinominare e aggiungere agli asset |
| `card-back.png`         | Dorso carte avversari                     | Asset già generato — da integrare in `Card.tsx`         |
| `intro.webm`            | Fase 6                                    | Veo 3 o Kling AI — interpolare tra frame 1 e frame 2    |

**La Fase 4 può partire subito** usando `background.png` come placeholder nel GameScreen. `table-perspective.png` si aggiunge come drop-in quando pronto.

---

## Ordine consigliato

```
Fase 1 (CSS tokens)  →  Fase 2 (Home)  →  Fase 3 (Lobby)
       ↓
Fase 4 (GameScreen layout)  →  Fase 5 (animazioni carte)
       ↓
Fase 6 (video — async)   +   Fase 7 (GameOver + polish)
```

Ogni fase lascia l'app in uno stato funzionante e visivamente migliorato. Non ci sono fasi "rotte a metà".

---

## Checklist pre-merge per ogni fase

- [ ] Nessuna classe `felt-*` nei file modificati
- [ ] Nessun colore hardcoded al di fuori delle variabili CSS
- [ ] Animazioni: timing non lineare (cubic-bezier o spring)
- [ ] Font: Cinzel per titoli/bottoni, IM Fell English per testo narrato, Outfit per HUD
- [ ] Testato su viewport 1280×800 (desktop minimo) e 1920×1080
