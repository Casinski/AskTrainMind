# 👋 AskTrainMind — Guida per il nuovo utente

Benvenuto! Questa guida spiega, passo per passo, come **aprire**, **consultare** e **fare domande** ad AskTrainMind, la pagina che mostra il **DB Flotte ETR1000**: le funzioni, i requisiti e i documenti FRS di ogni configurazione del treno, più un'AI che risponde alle domande tecniche.

> **Non devi installare niente.** Ti serve solo un browser (Microsoft Edge, già presente su Windows, oppure Chrome o Firefox). Per il file Excel ti serve Excel o un visualizzatore. Non servono Python, programmi aggiuntivi, diritti di amministratore né Internet.

> **Accesso in sola consultazione.** Puoi consultare tutto e fare domande all'AI. I dati, l'addestramento dell'AI e gli aggiornamenti sono gestiti dal **developer**: la pagina non modifica nessun file e il file Excel è in sola lettura.

---

## 1. Cosa hai ricevuto

Una cartella **`User`** (o la cartella completa del programma che la contiene):

```
User/
├── AskTrainMind.html                        ← la pagina da aprire (doppio clic)
├── DB Flotte ETR1000 Ver_1.9 Gabriele.xlsx  ← il file Excel completo (sola lettura)
├── docs/                                    ← i PDF dei documenti FRS (li apre la pagina)
├── LEGGIMI.txt                              ← promemoria rapido
└── NEWUSER.md                               ← questa guida
```

⚠️ **Tieni sempre insieme `AskTrainMind.html` e la cartella `docs`.** Se sposti la pagina da sola, i PDF non si aprono più.

---

## 2. Primo avvio (2 minuti)

1. **Copia la cartella sul tuo PC**, per esempio in `Documenti\AskTrainMind`.
   - Se l'hai ricevuta come **file ZIP**, clic destro → **Estrai tutto…**, poi lavora sulla cartella estratta. Se apri la pagina dall'interno dello ZIP, i PDF non si aprono.
   - Evita di aprirla direttamente da una cartella di rete lenta: copiarla in locale è più veloce.
2. Apri la cartella **User** e fai **doppio clic su `AskTrainMind.html`**.
   - Se si apre con un programma sbagliato: clic destro → **Apri con** → **Microsoft Edge** (o Chrome/Firefox).
   - In alternativa, nella cartella del programma, doppio clic su **`AVVIA_WEB.bat`**. Se il PC aziendale blocca i file `.bat`, usa il doppio clic sulla pagina: funziona allo stesso modo.
3. Controlla in alto a destra la **data dei dati**, per esempio *«Dati del … · aggiornati il … · AI: N concetti»*. È la data dell'ultimo aggiornamento del developer.
4. Se il browser mostra un avviso sui **contenuti locali**, consentili: la pagina funziona **offline** e **non invia dati** a nessuno.

Per consultare il file Excel: doppio clic su **`DB Flotte ….xlsx`**. Excel lo apre in **sola lettura** (oppure in *Visualizzazione protetta*): va bene così, non serve abilitare la modifica.

---

## 3. Cosa puoi fare

In alto ci sono tre pulsanti:

| Pulsante | A cosa serve |
|---|---|
| **🧭 Esplora** | sfogliare configurazioni → FRS → funzioni; leggere i PDF affiancati; confrontare i requisiti |
| **💬 Chiedi** | fare una domanda in italiano all'AI |
| **❔ Guida** | la guida completa di ogni pulsante (la trovi sempre nella pagina) |

### 3.1 🧭 Esplora — un percorso tipico

1. **① Configurazioni**: clicca una o più configurazioni, per esempio **VZI_Base**, **VZI_New14** e **VZ_FR**. Tutto il resto verrà mostrato affiancato per quelle configurazioni.
2. **② FRS**: scegli un documento, per esempio *FRS_Air Supply*.
3. **③ Funzioni**: scegli una funzione, per esempio *AIR_Control_of_Main_Compressor*.
4. **④ Dettaglio**: si apre un pannello con tre schede:
   - **🧠 Funzioni AI**: la sintesi della funzione per ogni configurazione e quanto è simile alla base;
   - **📄 PDF affiancati**: i PDF delle configurazioni scelte, già alla pagina della funzione;
   - **📋 Requisiti**: la tabella dei requisiti (vedi sotto).

### 3.2 📋 Requisiti — come leggere la tabella

Ogni riga mostra **sempre l'ID e la Description** del requisito. Così capisci subito cosa dice, per ogni configurazione scelta. La colonna **Esito** dice se il requisito è condiviso fra le configurazioni che hai scelto:

| Esito | Significato |
|---|---|
| **✔ MATCHED** | il requisito c'è in **tutte** le configurazioni scelte, con lo **stesso testo** |
| **✖ NOT MATCHED** · *solo in una* | c'è in **una sola** configurazione |
| **✖ NOT MATCHED** · *manca in alcune* | è condiviso solo da una parte delle configurazioni, **anche se è la maggioranza** |
| **✖ NOT MATCHED** · *testo diverso* | c'è in tutte, ma alcune configurazioni hanno un **testo diverso** |
| **? DA VERIFICARE** | c'è in tutte, ma per qualche configurazione il testo non è disponibile nel file |

Nelle celle delle configurazioni:

- **★** è il riferimento, cioè la configurazione base **VZI_Base**;
- **☆** è il riferimento sostitutivo: VZI_Base non è fra le configurazioni scelte, o non contiene il requisito, quindi si confronta con la prima configurazione che lo contiene. **L'esito resta valido anche senza VZI_Base**;
- **=** significa stesso testo del riferimento; **≠B** significa testo diverso. **Configurazioni con la stessa lettera (A, B, C…) hanno lo stesso testo**, così vedi subito quali condividono la stessa variante;
- **✖** significa requisito assente.

Sotto l'esito una riga spiega il motivo, per esempio *«manca in VZ_FR»* oppure *«testo A: VZI_Base, VZI_New14 · testo B: VZ_FR»*.

- **Clicca su un requisito** per leggere i testi completi, raggruppati per variante. Le parole diverse dal riferimento sono evidenziate: verdi quelle aggiunte, rosse barrate quelle tolte. La tabella **resta ferma sul requisito aperto**: per muoverti usa la barra di scorrimento verticale della tabella. Un altro clic lo richiude.
- Usa i filtri **✔ MATCHED / ✖ NOT MATCHED** (e *solo in una*, *manca in alcune*, *testo diverso*) e la casella **Filtra requisiti** per trovare subito quello che ti serve.
- La legenda **«Come leggere la tabella»** è sempre disponibile sopra la tabella.

### 3.3 💬 Chiedi — fare domande all'AI

Scrivi la domanda in italiano e premi **Invio**. Esempi:

- *Come funziona il loop DNRA sul VZI_Base?*
- *Cos'è il TCMS?*
- *Quali sono le differenze di BOG_Hotbox_Detection tra VZI_Base e VZ_FR?*
- *Quali requisiti di AIR_Control_of_Main_Compressor sono diversi?*
- *Nel documento FRS Air Supply, nel VZI_New14, a che valore di pressione devono attivarsi i compressori?*

La risposta mette insieme:

- **📄 Dai documenti**: l'AI **legge il testo dei documenti** e cita il requisito o il paragrafo che risponde, con documento, pagina e configurazioni. Per esempio: *il requisito 2F_06.03.Zefiro-Europe.CONCEPT.46 stabilisce che «All main compressors shall be ordered to run during start up of the train when MR pressure is less than 800 kPa…»*. **Clicca sui passaggi** per aprire il PDF alla pagina giusta;
- **🧠 Cosa so di «…»**: i concetti tecnici che l'AI ha imparato dal developer e dai documenti;
- **i dati del DB Flotte**: differenze, requisiti e documenti della funzione citata, con i link per aprirla in Esplora.

Consigli per risposte migliori:
- nomina la **configurazione** (*VZI_New14*, *VZ_FR*…) e, se lo conosci, il **documento** o la **funzione**;
- usa parole tecniche (*pressione*, *compressore*, *porte*, *sabbiatura*…): l'AI le traduce nei termini inglesi dei documenti;
- la risposta «Dai documenti» è una **prima risposta basata sul testo**: verifica sempre nel PDF.

Se l'AI risponde **«🤔 Non conosco ancora…»**, usa **⧉ Copia la domanda** e inviala al developer: la insegnerà all'AI e ti manderà la pagina aggiornata.

---

## 4. Cosa NON devi fare

- **Non usare `AVVIA_DEVELOPER.bat`** né i file `.py`, se li trovi nella cartella: sono strumenti del developer (analisi, addestramento dell'AI, aggiornamento dei dati).
- **Non modificare né rinominare** i file della cartella `User`: vengono rigenerati dal developer a ogni aggiornamento.
- **Non separare** `AskTrainMind.html` dalla cartella `docs`.

---

## 5. Problemi frequenti

| Problema | Soluzione |
|---|---|
| La pagina si apre in Blocco note o in un altro programma | Clic destro su `AskTrainMind.html` → **Apri con** → **Microsoft Edge** |
| `AVVIA_WEB.bat` non parte (bloccato dai criteri aziendali) | Apri direttamente `User\AskTrainMind.html` con doppio clic |
| Un PDF non si apre o resta bianco | La cartella `docs` deve essere accanto alla pagina; se hai uno ZIP, estrai tutto. Con ↗ puoi aprire il PDF in una nuova scheda |
| Pagina bianca o pulsanti che non rispondono | Usa una versione recente di Edge, Chrome o Firefox (non Internet Explorer); ricarica con **F5** |
| La pagina è lenta ad aprirsi la prima volta | È normale: contiene tutti i dati e il testo dei documenti. Attendi qualche secondo |
| Excel chiede di «Abilitare la modifica» | Non serve: il file è in sola consultazione |
| I dati sembrano vecchi | Guarda la data in alto a destra e chiedi al developer la cartella aggiornata |
| L'AI non conosce un termine o la risposta non convince | **⧉ Copia la domanda** e inviala al developer |

---

*Per il developer: prima di consegnare la cartella aggiorna la pagina con `AVVIA_DEVELOPER.bat` → voce **13** («Aggiorna la cartella User»), dopo aver eseguito le analisi e l'addestramento dell'AI. Con la voce **17** verifichi che Chiedi usi la conoscenza appresa e legga i documenti. Basta consegnare la cartella `User`, che contiene pagina, Excel, PDF e questa guida.*
