# 📘 Guida di AskTrainMind

AskTrainMind mostra il **DB Flotte ETR1000** (funzioni, requisiti e documenti FRS di ogni configurazione del treno) e risponde a domande tecniche usando ciò che l'AI ha imparato dai documenti ferroviari.

| Voglio… | Pulsante |
|---|---|
| sfogliare configurazioni, FRS e funzioni, leggere i PDF affiancati e confrontare i requisiti | **🧭 Esplora** |
| fare una domanda in italiano su una funzione o su un concetto tecnico | **💬 Chiedi** |
| leggere questa guida | **❔ Guida** |

## 1. 🚀 Come si apre

- Apri la cartella **User** e fai **doppio clic su `AskTrainMind.html`**, oppure fai doppio clic su **`AVVIA_WEB.bat`** nella cartella del programma. La pagina si apre nel browser (Edge, Chrome o Firefox). **Non serve installare nulla e non serve Internet.**
- Nella stessa cartella trovi il **file Excel** DB Flotte all'ultimo aggiornamento.
- In alto a destra c'è la data dei dati, per esempio *«Dati del 18/11/2026 · aggiornati il 18/11/2026 · AI: 206 concetti»*. Il developer rigenera la pagina dopo ogni aggiornamento.
- I PDF si aprono dalla cartella **docs** che si trova dentro la cartella **User**: tieni sempre insieme `AskTrainMind.html` e `docs`.

### Colori e simboli

| Simbolo | Significato (funzioni) | | Simbolo | Significato (requisiti, vedi *📋 Requisiti*) |
|---|---|---|---|---|
| ★ | configurazione di riferimento (base) | | ★ / ☆ | riferimento VZI_Base / riferimento sostitutivo se VZI_Base manca |
| ✔ | simile alla base: verde (≥ 80 %, verde grassetto nel DB se ≥ 90 %) | | = | stesso testo del riferimento |
| ≈ | differenze moderate: arancione (50–80 %) | | ≠B | testo diverso (stessa lettera = stesso testo) |
| ≠ | differenze rilevanti: rosso (< 50 %) | | ✖ | requisito assente |
| ○ | collegata, non ancora analizzata | | ✔ MATCHED | presente in tutte con lo stesso testo |
| ⚠ | documento non disponibile: link mancante o da verificare | | ✖ NOT MATCHED | solo in una, manca in alcune o testo diverso |

Le parole sottolineate a puntini sono **concetti che l'AI conosce**. Cliccale per aprire la scheda: significato, come funziona, elementi del treno coinvolti, sensori, centraline, tarature, eventi TCMS, frasi tratte dai documenti e funzioni collegate. Una sottolineatura più chiara indica un significato ricavato dai documenti e non ancora confermato dal developer.

## 2. 🧭 Esplora

Esplora mostra il DB come una **mappa a blocchi che si apre verso il basso**, livello dopo livello:

```
① 🚆 Configurazioni   VZI_Base · VZ_FR · VZ_ES …        (clic = seleziona, anche più di una)
        ▼
② 📘 FRS / DOC ID     FRS_Brake Control · FRS_Air Supply …
        ▼
③ ⚙️ Funzioni         BRK_Detection_of_Non-Rotating_Axle_(DNRA) …
        ▼
④ 🗂 Dettaglio funzioni   🧠 Funzioni AI · 📄 PDF affiancati · 📋 Requisiti
```

1. **① Configurazioni**: ogni blocco mostra il treno, la baseline, il numero di FRS 📚, di funzioni ⚙️ e di veicoli 🚆. Puoi cliccare **più configurazioni**, per esempio VZI_Base, VZ_FR e VZ_ES: tutto il resto verrà mostrato **affiancato** per quelle configurazioni. **☑ Tutte** le seleziona tutte.
2. **② FRS**: i documenti FRS delle configurazioni scelte. I pallini colorati indicano in quali configurazioni ogni documento è collegato.
3. **③ Funzioni**: le funzioni dei documenti scelti, con l'esito per configurazione (★ ✔ ≈ ≠ ○ ⚠) e il numero di requisiti 📋.
4. **④ Dettaglio funzioni**: per ogni funzione selezionata si apre un pannello. In alto trovi:
   - **Selezionate / Tutte**: mostra solo le configurazioni scelte al punto ① oppure tutte quelle che trattano la funzione;
   - i badge colorati delle configurazioni mostrate;
   - **💬 Chiedi**: apre Chiedi con una domanda già pronta;
   - **✕**: chiude il pannello.

   Il pannello ha tre schede. La pagina ricorda l'ultima scheda aperta.

### 🧠 Funzioni AI
Le schede, una per configurazione, sono **centrate nel pannello** e affiancate. Ogni scheda contiene la sintesi AI della funzione, la somiglianza con la base e il documento di riferimento (📄 apre il PDF alla pagina della funzione).

- **★ Riferimento** (configurazione base): la sintesi della funzione.
- **Varianti**: la **similarità funzionale** con la base (barra e percentuale con il colore dell'esito ✔ ≈ ≠). La similarità misura quanto le due funzioni **hanno lo stesso significato**: non conta l'impaginazione del PDF. Quando ci sono **differenze funzionali o d'impianto grandi**, la scheda le elenca nel riquadro rosso **«Differenze rilevanti rispetto a …»**:
  - *Valori/soglie diversi*: tensioni, tempi, correnti… che cambiano (per esempio `VZI_Base 18.5 kV → VZ_FR 30 kV`);
  - *Requisiti diversi*: requisiti presenti in una sola delle due configurazioni;
  - *Contenuto molto diverso*: una configurazione descrive la funzione con molto più testo;
  - *Componenti/sigle d'impianto diversi*: centraline, apparecchiature o segnali citati solo da una configurazione.

  Con differenze rilevanti la funzione non risulta mai «uguale» alla base (niente verde grassetto).

**Documento non disponibile (⚠).** Se per una configurazione manca il documento, la scheda mostra in **nero grassetto**:

| Messaggio | Cosa significa | Cosa fare |
|---|---|---|
| **LINK DOCUMENTALE NON INSERITO** | nel foglio *Funzioni* non c'è il link al documento per quella configurazione | chiedi al developer di inserire il link |
| **RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO** | il link c'è ma non porta a nessun documento (link errato, `#N/A`, PDF assente) | segnala il link al developer perché lo verifichi |

In questi casi la configurazione è **esclusa dal confronto** con le altre: non ha percentuale di similarità e i suoi requisiti non vengono confrontati.

### 📄 PDF affiancati
I PDF delle configurazioni scelte si aprono **uno accanto all'altro**, ognuno già alla **pagina in cui inizia la funzione**. Così puoi leggerli in parallelo senza aprire e chiudere un documento alla volta.

| Comando | Effetto |
|---|---|
| chip delle configurazioni (barra *Documenti*) | mostra o nasconde il PDF di quella configurazione |
| **Auto · 1 · 2 · 3 · 4** | numero di colonne (*Auto* le adatta alla larghezza dello schermo) |
| **⟲ Pagina funzione** | riporta tutti i PDF alla pagina della funzione |
| **⛶ Schermo intero** | i PDF affiancati occupano tutto lo schermo (Esc per uscire) |
| ◀ ▶ e casella numero (su ogni PDF) | pagina precedente o successiva, oppure vai alla pagina indicata |
| ↗ | apre il PDF in una nuova scheda del browser |

Dentro ogni PDF puoi usare anche i comandi del browser (zoom, ricerca con Ctrl+F, scorrimento).

### 📋 Requisiti
È una tabella **requisito × configurazione** per le configurazioni scelte al punto ①. Ogni riga mostra **sempre l'ID e la Description del requisito**: si capisce subito cosa dice il requisito, senza aprirlo.

**In alto** trovi:
- il **riepilogo**: per ogni configurazione, quanti requisiti contiene e quanti ne ha *solo lei* (*«3 solo qui»*);
- il **riferimento**: ★ **VZI_Base** (configurazione base). Se VZI_Base **non è fra le configurazioni scelte**, o non contiene quel requisito, il riferimento diventa la **prima configurazione che lo contiene (☆)**: l'esito resta comunque chiaro per le configurazioni scelte;
- i **filtri**: **Tutti · ✔ MATCHED · ✖ NOT MATCHED**, il dettaglio dei NOT MATCHED (**① solo in una · ◐ manca in alcune · ≠ testo diverso · ? da verificare**), la casella *Filtra requisiti (ID o testo)…* e **▾ Espandi tutti / ▴ Comprimi tutti**;
- la **legenda** *«Come leggere la tabella»* (si apre e chiude con un clic; la pagina ricorda la scelta).

**Colonna «Esito»** — vale fra le configurazioni **mostrate**:

| Esito | Quando | Esempio con VZI_Base, VZ_FR, VZ_ES |
|---|---|---|
| **✔ MATCHED** (verde) | il requisito c'è in **tutte** le configurazioni, con lo **stesso testo** | ★ = = |
| **✖ NOT MATCHED** · *solo in una* | c'è in **una sola** configurazione | ✖ ☆ ✖ → *presente solo in VZ_FR* |
| **✖ NOT MATCHED** · *manca in alcune* | è condiviso da una parte delle configurazioni, **anche se è la maggioranza** | ★ = ✖ → *presente in 2 di 3 · manca in VZ_ES* |
| **✖ NOT MATCHED** · *testo diverso* | c'è in tutte, ma **alcune hanno un testo diverso** | ★A =A ≠B → *testo A: VZI_Base, VZ_FR · testo B: VZ_ES* |
| **? DA VERIFICARE** | c'è in tutte, ma per qualche configurazione il file Excel non riporta il testo | ★ = ? |
| **• PRESENTE** | è mostrata una sola configurazione: scegline altre per il confronto | |

Sotto l'esito una riga spiega il motivo (*«manca in VZ_ES»*, *«testo A: …, testo B: …»*). Se un requisito è condiviso solo da alcune configurazioni **e** ha testi diversi, l'esito li riporta entrambi.

**Simboli nelle celle delle configurazioni:**

| Simbolo | Significato |
|---|---|
| ★ | riferimento: VZI_Base |
| ☆ | riferimento sostitutivo: VZI_Base non c'è (o non è mostrata), si confronta con questa configurazione |
| = | stesso testo del riferimento |
| ≠B | testo diverso dal riferimento. **Le configurazioni con la stessa lettera (A, B, C…) hanno lo stesso testo**: così vedi quali sotto-configurazioni condividono la stessa variante |
| ✖ | requisito assente in questa configurazione |
| ? | requisito presente, testo non verificabile |

**Clicca su un requisito** per aprire sotto la riga i **testi completi raggruppati per variante**: un riquadro per ogni testo diverso, con le configurazioni che lo usano; le parole aggiunte rispetto al riferimento sono **evidenziate in verde** e quelle tolte **barrate in rosso**. Un riquadro elenca anche le configurazioni in cui il requisito **manca**. **I requisiti restano sempre al loro posto**: il dettaglio si apre solo sotto la riga cliccata, senza far scorrere la tabella. Clicca di nuovo sul requisito per richiuderlo; puoi tenere aperti più requisiti insieme.

### Filtri di Esplora (barra in alto)

| Comando | Effetto |
|---|---|
| 🔎 *Cerca funzione, descrizione o FRS…* | filtra i blocchi mentre scrivi; anche senza selezionare nulla mostra subito le funzioni che corrispondono |
| ✔ ≈ ≠ ○ ⚠ (chip *Esito*) | mostra solo le funzioni con quell'esito in almeno una configurazione selezionata |
| 📋 Con requisiti | mostra solo le funzioni che hanno requisiti |
| ✖ Azzera | toglie selezioni e filtri |

La barra di navigazione (🧭 Esplora › configurazioni › FRS › funzioni) ti riporta a un livello con un clic. La pagina ricorda le tue selezioni anche quando la riapri.

## 3. 💬 Chiedi

Scrivi una domanda in italiano e premi **Invio**. Alcuni esempi:

- *Come funziona il loop DNRA sul VZI_Base?*
- *Cos'è il TCMS?* · *Cos'è una configurazione dell'ETR1000?* · *Cos'è un pantografo?*
- *Quali sono le differenze di BOG_Hotbox_Detection tra VZI_Base e VZ_FR?*
- *Quali requisiti di AIR_Control_of_Main_Compressor sono diversi?*
- *In quali documenti è descritta CON_DNRA_Alarm?*
- *Nel documento FRS Air Supply, nel VZI_New14, a che valore di pressione devono attivarsi i compressori?*

La risposta mette insieme:

- **📄 Dai documenti**: l'AI **legge il testo dei documenti** (requisiti e paragrafi dei PDF di ogni funzione) e cita il passaggio che risponde alla domanda, per esempio: *nel documento FRS_Air Supply (3ECP413719-0603), pag. 7 — il requisito 2F_06.03.Zefiro-Europe.CONCEPT.46 stabilisce che «All main compressors shall be ordered to run during start up of the train when MR pressure is less than 800 kPa…»*. Se nomini una configurazione viene citato il **PDF di quella configurazione**. Sotto trovi gli altri passaggi pertinenti: **cliccali per aprire il PDF alla pagina**. È una prima risposta basata sull'analisi del testo: verifica sempre nel documento. Le parole italiane della domanda sono tradotte nei termini inglesi dei documenti (es. *pressione → pressure*, *attivarsi → run/start*);

- **🧠 Cosa so di «…»**: la scheda di ogni concetto citato, con il significato, il funzionamento, gli elementi del treno coinvolti, i sensori, le centraline, le tarature, gli eventi TCMS e le frasi tratte dai documenti tecnici (con documento e pagina);
- **💬 Spiegazioni dell'esperto**: le risposte libere che il developer ha dato alle domande dell'AI (questionario *questionAI*). Chiedi le usa anche quando la domanda non nomina una sigla, ma ne descrive il funzionamento;
- **le funzioni collegate**: cliccale per aprirle subito in 🧭 Esplora, con PDF affiancati e requisiti;
- **i dati del DB Flotte**: sintesi per configurazione, differenze, requisiti e documenti, quando la domanda riguarda una funzione;
- **🤔 Non conosco ancora…**: le parole che l'AI non ha ancora imparato. Con **⧉ Copia la domanda** puoi inviarla al developer, che la insegnerà all'AI e aggiornerà la pagina.

A sinistra trovi le **domande suggerite** e la **cronologia** delle tue domande (🗑 per cancellarla).

## 4. ❓ Problemi frequenti

| Problema | Soluzione |
|---|---|
| Un PDF non si apre o resta bianco | La cartella **docs** deve trovarsi accanto a `AskTrainMind.html` (dentro **User**). Se il file è dentro uno ZIP, estrai prima tutto. Se il documento manca, chiedilo al developer. |
| I PDF non si vedono affiancati | Allarga la finestra oppure scegli 1 o 2 colonne; con ↗ apri il PDF in una nuova scheda |
| Il browser mostra un avviso sui contenuti locali | Consenti il contenuto: la pagina funziona senza Internet e non invia dati |
| I dati sembrano vecchi | Controlla la data in alto a destra e chiedi al developer di aggiornare la cartella User |
| L'AI non conosce un termine | Usa **⧉ Copia la domanda** e invia il testo al developer |
| Una scheda dice «LINK DOCUMENTALE NON INSERITO» o «RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO» | Il documento di quella configurazione manca o il link è errato: segnalalo al developer (vedi *🧠 Funzioni AI*) |

---

*Primo utilizzo: vedi **NEWUSER.md**. Per il developer: le analisi, l'addestramento dell'AI e la CONFIG si gestiscono da **AVVIA_DEVELOPER.bat**. Vedi README.md e TRAINING_AI.md.*
