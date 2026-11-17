# Guida all'interfaccia web di AskTrainMind

L'interfaccia web mostra il file **DB Flotte ETR1000** in modo dinamico, permette di fare **domande in italiano** su funzioni, requisiti e documenti e, per chi ha installato tutto il necessario, di **lanciare le opzioni** del programma e modificare la **CONFIG**. Funziona interamente sul tuo computer: nessun dato viene inviato in Internet.

## Avvio

1. Fai doppio clic su **AVVIA_WEB.bat** nella cartella del programma (oppure, dal Prompt dei comandi: `python asktrainmind_web.py`).
2. Il browser si apre da solo su **http://127.0.0.1:8765**. Se non si apre, copia l'indirizzo nella barra del browser (Edge, Chrome o Firefox).
3. Lascia aperta la finestra nera: chiudendola (o premendo Ctrl+C) la pagina smette di funzionare.

Opzioni utili da riga di comando:

```
python asktrainmind_web.py --port 8800        (usa un'altra porta)
python asktrainmind_web.py --no-browser       (non aprire il browser)
```

Se compare il messaggio «mancano pacchetti», esegui una volta `python -m pip install -r requirements.txt`.

La pagina ha quattro schede in alto: **📊 Fogli**, **💬 Chiedi**, **🛠️ Strumenti** (solo sul PC dove gira il programma) e **❔ Guida** (questa pagina). In alto a destra un pallino indica lo stato: verde = file caricato, giallo = caricamento in corso, rosso = errore.

## Fogli: consultare il file Excel

In basso trovi le linguette dei fogli **Index Funzioni**, **Funzioni**, **Requisiti** e **Reqs not matched**, proprio come in Excel. La prima apertura richiede un paio di secondi; poi il foglio è in memoria e ogni operazione è istantanea anche con migliaia di righe.

### Filtri e ordinamento (come i filtri di Excel)

- Clicca la **freccetta ▾** nell'intestazione di una colonna: si apre un menu con l'elenco dei valori (con conteggio), una casella **Filtro testo: contiene…**, i comandi **Ordina dalla A alla Z / dalla Z alla A** e **(Seleziona tutto)**.
- Le colonne filtrate hanno la freccetta colorata; puoi combinare filtri su più colonne.
- **Doppio clic** su una cella = filtra subito la colonna per quel valore.
- **✖ Rimuovi filtri** azzera filtri, ricerca e ordinamento.

Nei fogli organizzati per funzione (Funzioni, Requisiti, Reqs not matched) il menu **Filtro** decide cosa mostrare:

| Modalità | Cosa vedi |
|---|---|
| righe + intestazione funzione | le righe che soddisfano i filtri, precedute dalla riga della funzione a cui appartengono (consigliata) |
| solo righe (come Excel) | esattamente come il filtro di Excel |
| blocco funzione intero | tutte le righe delle funzioni che contengono almeno una riga trovata |

L'ordinamento mantiene unite le righe della stessa funzione.

### Ricerca

La casella **Cerca in tutto il foglio** (scorciatoia **Ctrl+F**) trova il testo in qualunque colonna, compresi FUNC ID, descrizione della funzione e nome dei documenti collegati. Le parole trovate sono evidenziate in giallo.

### Configurazioni, colonne e righe

- **🚆 Configurazioni**: mostra o nasconde in un colpo tutte le colonne di una configurazione (VZI_Base, VZ_FR, …), ciascuna con il suo colore.
- **▥ Colonne**: mostra o nasconde le singole colonne e con **Blocca prime N col.** sceglie quante colonne tenere ferme a sinistra (come «Blocca riquadri»).
- Trascina il bordo destro dell'intestazione per **allargare/stringere** una colonna.
- Menu **Righe compatte / medie / alte** per leggere più testo senza aprire la cella.

### Pannello Dettagli e collegamenti ai documenti

Selezionando una cella, il pannello **🗎 Dettagli** a destra mostra il testo completo, i commenti e le azioni disponibili: **apri il PDF alla pagina giusta** (se il documento è presente sul PC), **apri su SharePoint**, **copia**, **filtra per questo valore**, **mostra solo questa funzione**, **chiedi informazioni su questa funzione**. La barra **fx** sopra la griglia mostra il contenuto della cella come in Excel.

### Selezione, copia ed esportazione

- **Maiusc+clic** o **Maiusc+frecce** selezionano più celle; **Ctrl+C** le copia (si incollano in Excel mantenendo righe e colonne).
- Nella barra in basso vedi **conteggio, somma e media** delle celle selezionate e quante righe sono visibili.
- **⇩ CSV** esporta le righe visibili (con i filtri applicati) in un file apribile con Excel.

La pagina ricorda per ogni foglio filtri, colonne e larghezze. Quando il file Excel viene aggiornato (da te o dal programma) la pagina se ne accorge e si ricarica da sola, con un avviso.

## Chiedi: fare domande

Scrivi la domanda in italiano e premi **Invio** (Maiusc+Invio per andare a capo). Mentre scrivi un FUNC ID compare l'**autocompletamento** (frecce + Tab/Invio). A sinistra trovi gli **esempi di domande** e le **domande recenti**: cliccale per riproporle.

### Che cosa puoi chiedere

| Tipo di domanda | Esempio |
|---|---|
| Differenze fra configurazioni | Puoi trovare tutte le differenze tra le varie configurazioni per le funzioni AIR_Control_of_Main_Compressor, BOG_Hotbox_Detection |
| Funzionamento | Come funziona la funzione BOG_Hotbox_Detection nella configurazione VZI_Base? |
| Spiegazione semplice | Potresti descrivere in modo semplice come funziona a livello tecnico la funzione BOG_Hotbox_Detection |
| Componenti | Quali componenti sono trattati all'interno della funzione BOG_Hotbox_Detection? |
| Documenti | Mostrami i documenti relativi alla funzione BOG_Hotbox_Detection per le configurazioni VZI_Base e VZ_FR |
| Requisiti uguali/diversi | Quali requisiti differiscono e quali sono uguali tra le varie configurazioni per la funzione BOG_Hotbox_Detection |
| Figure e tabelle | Mostrami se sono presenti le eventuali figure e tabelle presenti nella configurazione base per la funzione BOG_Hotbox_Detection |
| Ricerca per argomento | Quali funzioni parlano di pantografo? (propone le funzioni pertinenti: clic per approfondire) |

Suggerimenti:

- Puoi indicare le funzioni con il FUNC ID completo o con parole della descrizione; se la scelta è ambigua la risposta propone dei pulsanti con le funzioni candidate.
- Le configurazioni si possono scrivere in forma abbreviata: «base» = VZI_Base, «FR» = VZ_FR, «New14» = VZI_New14, ecc. Senza indicazioni vengono considerate tutte.
- La riga **Interpretazione** in cima alla risposta mostra come è stata capita la domanda (funzioni, configurazioni, tipo di richiesta).

### Le risposte

Le risposte combinano: riepiloghi con numeri chiave, tabelle (filtrabili, ordinabili cliccando l'intestazione e copiabili con **⧉ Copia**), schede dei documenti con **📄 Apri alla pagina**, **🖼 Pagine della funzione** (anteprima delle sole pagine che trattano la funzione) e **🌐 SharePoint**, e le miniature di **figure e tabelle** (clic per ingrandire). Sono costruite dal file Excel e dai PDF presenti sul PC e arrivano in pochi millisecondi; la stessa domanda ripetuta viene servita dalla cache.

### Cercare nei documenti del computer

Spuntando **Cerca anche nei documenti del computer** la domanda viene cercata anche nel testo di tutti i PDF delle cartelle documenti, con i passaggi trovati evidenziati: clic su un risultato per aprire il PDF alla pagina. La prima volta il programma costruisce un **indice** dei PDF (alcuni minuti, in background); poi la ricerca è immediata e l'indice si aggiorna solo per i file nuovi o modificati. Le cartelle analizzate sono quella di `ONEDRIVE_DOCS_ROOT`, la cartella `docs` del programma e quelle aggiunte in `WEB_EXTRA_DOC_DIRS`.

### Spiegazione con l'AI locale (facoltativa)

Se sul PC è installato **Ollama** con il modello indicato in CONFIG, sotto le risposte compare il pulsante **✨ Spiegazione discorsiva con l'AI locale**: il testo viene scritto in tempo reale, in italiano, partendo solo dai dati del file e dei documenti. Con **Spiegazione AI automatica** spuntata parte da sola. Senza Ollama tutte le altre funzioni restano disponibili. Verifica sempre sulle fonti quanto scritto dall'AI.

## Strumenti: lanciare le opzioni (sezione riservata)

La scheda **🛠️ Strumenti** compare solo aprendo la pagina **dallo stesso PC** su cui gira il programma ed è pensata per chi ha installato l'intero ambiente. Finché manca qualcosa resta **bloccata 🔒** e mostra la guida di installazione con l'elenco dei controlli:

1. **Python 3.10+** da [python.org](https://www.python.org/downloads/), spuntando «Add python.exe to PATH».
2. **Pacchetti del programma**: nel Prompt dei comandi, nella cartella del programma, `python -m pip install -r requirements.txt`.
3. **Ollama** da [ollama.com/download](https://ollama.com/download): installalo e avvialo (icona del lama vicino all'orologio).
4. **Modello AI**: `ollama pull qwen2.5:7b-instruct` (o il modello scelto in `OLLAMA_MODEL`); il download è di alcuni GB.
5. **Percorsi**: nel riquadro «Percorsi e modello» imposta `EXCEL_PATH` (file DB Flotte) e `ONEDRIVE_DOCS_ROOT` (cartella DOC_FLOTTE sincronizzata con OneDrive).

Premi **↻ Ricontrolla**: quando tutti i controlli sono ✅ la sezione si sblocca 🔓.

### Lancia opzioni

Clicca la scheda dell'opzione (1–5): compare un modulo con gli stessi parametri del menu del programma (FRS da elaborare, FUNC ID di partenza, numero massimo di celle, gestione delle celle già compilate, configurazioni da confrontare, DOC ID…). Premi **▶ Avvia**.

- Chiudi il file Excel prima di avviare: il programma lo aggiorna e archivia la versione precedente in `_OLD`.
- Spuntando **Non modificare il DB Flotte** i risultati vengono scritti in `RESULTS\RESULTS_<data>_Opzione_N.xlsx` e il file principale resta intatto.
- Il riquadro **Esecuzione** mostra il log in tempo reale; **■ Interrompi (salva e termina)** ferma l'opzione salvando i progressi come nel programma.
- Al termine la pagina ricarica automaticamente il file aggiornato.

### CONFIG

Elenca tutte le variabili di `config.py`, raggruppate per sezione, ognuna con la sua **descrizione** e il valore originale. Puoi cercarle per nome o descrizione e filtrare **Solo valori forzati**.

- **Salva** forza un valore; i sì/no hanno un interruttore. I valori forzati sono evidenziati con l'etichetta **FORZATO**.
- **↺ Ripristina** (o **Ripristina tutti**) torna al valore di `config.py`.
- I valori forzati sono salvati in `config_overrides.json` nella cartella del programma: `config.py` **non viene modificato**. Valgono sia per la pagina web sia per le opzioni lanciate dopo (anche dal menu classico).
- Le variabili marcate come **calcolate** derivano da altre variabili: forzale direttamente solo se sai cosa stai facendo.

### Indice documenti

Mostra quanti PDF sono stati trovati e indicizzati per la ricerca nei documenti e con **↻ Aggiorna indice documenti** permette di aggiornarlo dopo aver aggiunto nuovi file.

## Reqs not matched: correzione

Il foglio **Reqs not matched** ora contiene **tutti** i requisiti non MATCHED fra le configurazioni scelte. In passato il calcolo delle Note AI si fermava dopo 200 chiamate (`REQS_NOT_MATCHED_AI_MAX_CALLS = 200`) e l'opzione terminava con il foglio incompleto. Ora il limite predefinito è **0 = nessun limite**, le note identiche vengono calcolate una sola volta e, se imposti comunque un limite, le righe restanti vengono scritte lo stesso con la nota «[Nota AI non generata: limite REQS_NOT_MATCHED_AI_MAX_CALLS raggiunto, rieseguire l'opzione 5]» invece di essere perse.

## Prestazioni e cache

- Ogni foglio viene letto una sola volta e conservato già pronto (compresso) in `WEB_CACHE_DIR`; viene riletto solo se il file Excel cambia.
- Indice dei PDF, rilevamento delle pagine, figure e risposte sono memorizzati in cache e riutilizzati.
- La griglia disegna solo le righe visibili: scorrimento fluido anche con decine di migliaia di righe.
- Per liberare spazio puoi cancellare la cartella indicata da `WEB_CACHE_DIR`: verrà ricostruita.

## Risoluzione dei problemi

| Problema | Soluzione |
|---|---|
| La pagina non si apre | Controlla che la finestra di AVVIA_WEB.bat sia aperta e vai su http://127.0.0.1:8765 |
| «La porta … è già usata da un altro programma» | Avvia con un'altra porta: `python asktrainmind_web.py --port 8800` (se invece la pagina è già attiva, il programma apre direttamente il browser) |
| File Excel non trovato | Imposta `EXCEL_PATH` (Strumenti → Percorsi, oppure `config.py`) |
| «PDF non presente sul PC» | Sincronizza la libreria DOC_FLOTTE con OneDrive e verifica `ONEDRIVE_DOCS_ROOT`; resta disponibile il link SharePoint |
| Nessuna spiegazione AI | Avvia Ollama e scarica il modello (`ollama pull …`); controlla `WEB_QA_USE_AI` |
| Scheda Strumenti assente | La pagina è aperta da un altro PC: Strumenti è disponibile solo sul PC del programma |
| Dati non aggiornati | Premi F5; la pagina si aggiorna comunque da sola quando il file cambia |

## Impostazioni della pagina web (config.py)

| Variabile | Significato |
|---|---|
| `WEB_HOST` / `WEB_PORT` | indirizzo e porta del server (predefinito 127.0.0.1:8765, solo questo PC) |
| `WEB_OPEN_BROWSER` | apre il browser all'avvio |
| `WEB_CACHE_DIR` | cartella della cache della pagina web |
| `WEB_EXTRA_DOC_DIRS` | altre cartelle con PDF da usare per le risposte e la ricerca |
| `WEB_PDF_INDEX_MAX_PAGES` | pagine massime indicizzate per ogni PDF (0 = tutte) |
| `WEB_QA_USE_AI` | abilita la spiegazione con l'AI locale in Chiedi |
| `WEB_QA_MAX_SECTION_PAGES` | pagine massime analizzate per funzione (figure, testo) |
| `CONFIG_OVERRIDES_FILE` | file con i valori forzati dalla sezione CONFIG |
