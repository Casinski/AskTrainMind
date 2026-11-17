# 📘 Guida unica di AskTrainMind

AskTrainMind trasforma il file **DB Flotte ETR1000** e i documenti FRS in un'applicazione web **semplice, colorata e veloce**. Con questa guida impari in pochi minuti a:

| Voglio… | Vai a |
|---|---|
| vedere a colpo d'occhio configurazioni, FRS, funzioni e requisiti | **🧭 Esplora** |
| lavorare sul file come in Excel (filtri, ordinamento, copia, CSV) | **📊 Fogli** |
| fare domande in italiano o cercare una parola in tutti i PDF | **💬 Chiedi** |
| insegnare all'AI cosa significano sigle, sensori e centraline | **🧠 Conoscenza** |
| lanciare le opzioni del programma e modificare la CONFIG | **🛠️ Strumenti** (riservata) |
| rileggere questa guida | **❔ Guida** |

Tutto funziona **sul tuo computer**: nessun dato viene inviato in Internet.

---

## 1. 🚀 Avvio

1. Doppio clic su **AVVIA_WEB.bat** nella cartella del programma (oppure, dal Prompt dei comandi: `python asktrainmind_web.py`).
2. Il browser si apre da solo su **http://127.0.0.1:8765**. Se non succede, copia l'indirizzo in Edge, Chrome o Firefox.
3. Lascia aperta la finestra nera: chiudendola (o con Ctrl+C) la pagina smette di funzionare.

```
python asktrainmind_web.py --port 8800        (usa un'altra porta)
python asktrainmind_web.py --no-browser       (non aprire il browser)
```

Se compare «mancano pacchetti», esegui una volta `python -m pip install -r requirements.txt`.

In alto a destra un **pallino** indica lo stato: 🟢 file caricato, 🟡 caricamento in corso, 🔴 errore. Quando il file Excel cambia (perché lo salvi tu o perché lo aggiorna il programma) la pagina se ne accorge e si ricarica da sola.

### I colori e i simboli usati ovunque

Ogni **configurazione** (VZI_Base, VZ_FR, VZI_New14, …) ha sempre **lo stesso colore** in tutte le schede. Gli esiti del confronto con la configurazione base sono indicati così:

| Simbolo | Significato |
|---|---|
| ★ blu | riferimento: la configurazione ha la propria descrizione (di solito la base) |
| ✔ verde | simile alla base (≥ 90 %) |
| ≈ arancione | differenze moderate |
| ≠ rosso | differenze rilevanti |
| ○ grigio | documento collegato, funzione non ancora analizzata |
| – | funzione non trattata nella configurazione |

---

## 2. 🧭 Esplora: la vista a blocchi (pagina iniziale)

Esplora mostra il file come una **mappa a blocchi che si apre verso il basso**, livello dopo livello, come nei software documentali e di analisi dei requisiti: nessun blocco si sovrappone agli altri, e i blocchi si dispongono da soli in righe e colonne in base alla larghezza dello schermo.

```
① 🚆 Configurazioni      VZI_Base  ·  VZ_FR  ·  VZI_New14 …     (clic = apri)
        ▼
② 📘 FRS / DOC ID        FRS_Line Voltage · FRS_Teledia · FRS_Hotbox …
        ▼
③ ⚙️ Funzioni            BOG_Hotbox_Detection · AIR_Control_of_Main_Compressor …
        ▼
④ 🗂 Dettaglio           Funzioni AI · Requisiti · Reqs not matched · Index
```

### Come si usa

1. **① Configurazioni**: ogni blocco mostra il treno, il numero di FRS e di funzioni, i **veicoli** (dal foglio Flotte) e una barra colorata con la distribuzione degli esiti. Clicca uno o **più** blocchi (selezione multipla); **☑ Tutte** le seleziona tutte.
2. **② FRS**: compaiono i documenti FRS delle configurazioni scelte, con il DOC ID. I **pallini colorati** indicano in quali configurazioni l'FRS è collegato; un **pallino tratteggiato** significa *link documentale mancante* nel foglio Funzioni. Clicca uno o più FRS (**☑ Tutti** / **☐ Nessuno**).
3. **③ Funzioni**: per ogni FRS le sue funzioni, con le **pillole di esito** per configurazione (★ ✔ ≈ ≠ ○), il numero di requisiti 📋 e di righe in Reqs not matched ⚠️. Clicca una o più funzioni.
4. **④ Dettaglio**: per ogni funzione selezionata si apre un pannello con quattro schede:
   - **🧠 Funzioni AI**: una scheda per configurazione con la sintesi AI, la percentuale di somiglianza e il documento (📄 apri alla pagina);
   - **📋 Requisiti**: matrice requisito × configurazione — **★** testo della base, **=** uguale, **≠** diverso, **➕** presente solo lì, vuoto = assente. Filtri **Tutti / ≠ Diversi / = Uguali**, casella *Filtra requisiti…*; clic su una cella per leggere il testo completo;
   - **⚠️ Reqs not matched**: le righe della funzione con le note;
   - **🗂 Index**: l'esito della ricerca funzioni (opzione 2).

   In alto nel pannello: **Selezionate / Tutte** (configurazioni scelte al livello ① oppure tutte quelle che trattano la funzione), **💬 Chiedi** (apre Chiedi con una domanda già pronta), **📊 Foglio** (apre la funzione nel foglio Funzioni), **✕** chiude.

### Filtri di Esplora

| Comando | Effetto |
|---|---|
| 🔎 *Cerca funzione, descrizione o FRS…* | filtra i blocchi mentre scrivi; anche **senza selezionare nulla** mostra subito tutte le funzioni che corrispondono |
| ✔ ≈ ≠ ○ (chip *Esito*) | solo le funzioni con quell'esito in almeno una configurazione selezionata |
| 📋 Con requisiti | solo funzioni presenti nel foglio Requisiti |
| ⚠️ In Reqs not matched | solo funzioni con requisiti non MATCHED |
| ✖ Azzera | toglie selezioni e filtri |

La **barra di navigazione** (🧭 Esplora › 🚆 configurazioni › FRS › funzioni) permette di tornare a un livello con un clic. La pagina ricorda le tue selezioni.

---

## 3. 📊 Fogli: il file Excel nel browser

In basso trovi le linguette **Index Funzioni**, **Funzioni**, **Requisiti** e **Reqs not matched**, come in Excel. La prima apertura richiede un paio di secondi, poi ogni operazione è istantanea anche con migliaia di righe.

### Filtri per colonna (come Excel)

- Clicca la **freccetta ▾** nell'intestazione: elenco dei valori con conteggio, **Filtro testo: contiene…**, **Ordina A→Z / Z→A**, **(Seleziona tutto)**.
- **Doppio clic** su una cella = filtra subito la colonna per quel valore.
- Le colonne filtrate hanno la freccetta colorata; i filtri si combinano.

### ⚡ Filtri rapidi (un clic)

Sopra la griglia compaiono i pulsanti adatti al foglio aperto:

| Foglio | Filtri rapidi |
|---|---|
| Funzioni | 🧠 Solo Funzioni AI · 🔗 Solo link documenti · 📝 Approfondimenti · 🔌 Componenti |
| Requisiti | ≠ Con differenze · ➕ Non presenti nella base |
| Reqs not matched | 🔗 Link documentale mancante · ≈ Requisiti simili · ⏳ Nota AI da generare |
| Index Funzioni | ❌ NOT FOUND · ➖ N/A |

### Filtri attivi sempre visibili

Ogni filtro, ricerca o filtro rapido attivo compare come **etichetta colorata** nella barra dei filtri: clicca **✕** sull'etichetta per toglierlo, oppure **Rimuovi tutti i filtri**.

### Come mostrare i risultati

Nei fogli organizzati per funzione scegli con i tre pulsanti:

| Pulsante | Cosa vedi |
|---|---|
| ▤ Righe + funzione | le righe trovate precedute dalla riga della loro funzione (consigliato) |
| ☰ Solo righe | esattamente come il filtro di Excel |
| ▣ Funzione intera | tutto il blocco delle funzioni che contengono almeno una riga trovata |

L'ordinamento mantiene unite le righe della stessa funzione.

### Ricerca, colonne, dettagli, copia

- **Cerca in tutto il foglio** (**Ctrl+F**): cerca in tutte le colonne, compresi FUNC ID e nomi dei documenti; le parole sono evidenziate.
- **🚆 Configurazioni**: mostra/nasconde tutte le colonne di una configurazione; **▥ Colonne**: singole colonne e **Blocca prime N col.**; trascina il bordo dell'intestazione per allargare.
- Selezionando una cella, il pannello **🗎 Dettagli** mostra testo completo, commenti e azioni: **apri il PDF alla pagina**, **SharePoint**, **copia**, **filtra per questo valore**, **solo questa funzione**, **chiedi su questa funzione**.
- **Maiusc+clic/frecce** seleziona più celle, **Ctrl+C** copia (si incolla in Excel), la barra in basso mostra conteggio/somma/media; **⇩ CSV** esporta le righe visibili.

---

## 4. 💬 Chiedi: domande e ricerca nei documenti

In alto scegli la modalità: **💬 Fai una domanda** oppure **🔎 Cerca nei documenti del computer**.

### Fai una domanda

Scrivi in italiano e premi **Invio** (Maiusc+Invio = a capo). Mentre scrivi un FUNC ID compare l'autocompletamento. A sinistra trovi esempi e domande recenti.

| Tipo di domanda | Esempio |
|---|---|
| Differenze fra configurazioni | Puoi trovare tutte le differenze tra le varie configurazioni per le funzioni AIR_Control_of_Main_Compressor, BOG_Hotbox_Detection |
| Confronto su tutte le configurazioni | Confronta la funzione BOG_Hotbox_Detection per tutte le configurazioni |
| Funzionamento | Come funziona la funzione BOG_Hotbox_Detection nella configurazione VZI_Base? |
| Spiegazione semplice | Potresti descrivere in modo semplice come funziona a livello tecnico la funzione BOG_Hotbox_Detection |
| Componenti | Quali componenti sono trattati all'interno della funzione BOG_Hotbox_Detection? |
| Documenti | Mostrami i documenti relativi alla funzione BOG_Hotbox_Detection per le configurazioni VZI_Base e VZ_FR |
| Requisiti uguali/diversi | Quali requisiti differiscono e quali sono uguali tra le varie configurazioni per la funzione BOG_Hotbox_Detection |
| Figure e tabelle | Mostrami se sono presenti le eventuali figure e tabelle presenti nella configurazione base per la funzione BOG_Hotbox_Detection |
| Per argomento | Quali funzioni parlano di pantografo? |

Suggerimenti:

- Configurazioni abbreviate: «base» = VZI_Base, «FR» = VZ_FR, «New14» = VZI_New14…; senza indicazioni vengono considerate **tutte**.
- Con «**per tutte le configurazioni**», «tra le varie configurazioni», «ogni configurazione» le risposte su funzionamento e differenze mostrano il badge **🚆 tutte le configurazioni** e **un blocco colorato per ogni configurazione** (esito, somiglianza, documento, sintesi) con i **treni/veicoli impattati**.
- La riga **Interpretazione** mostra come è stata capita la domanda; sotto la risposta compaiono **domande successive** cliccabili.
- I termini del glossario (🧠 Conoscenza) sono **sottolineati**: passa sopra con il mouse per leggerne il significato.

### Le risposte

Riepiloghi con numeri chiave, tabelle (ordinabili, filtrabili, **⧉ Copia**), figure e tabelle in miniatura (clic per ingrandire) e l'elenco dei documenti. Per ogni documento c'è **un solo pulsante principale** — **📄 Apri alla pagina** della funzione — più due piccole icone: **🖼** anteprima delle sole pagine della funzione e **🌐** SharePoint. Le risposte arrivano in pochi millisecondi e le domande ripetute escono dalla cache.

### 🔎 Cerca nei documenti del computer

Scrivi una o più parole: i risultati compaiono **mentre scrivi**, raggruppati **per documento**, con nome del file, numero di pagina, **estratto evidenziato** e **miniatura della pagina**. Clic sul risultato = PDF aperto alla pagina.

- Usa le **virgolette** per la frase esatta: `"hot box"`.
- L'indice dei PDF viene costruito in background all'avvio (`WEB_PDF_INDEX_AT_START`) e poi aggiornato solo per i file nuovi o modificati: la ricerca richiede pochi millisecondi.
- Cartelle analizzate: `ONEDRIVE_DOCS_ROOT`, la cartella `docs` del programma e quelle in `WEB_EXTRA_DOC_DIRS`.
- In modalità domanda puoi anche spuntare **Cerca anche nei documenti del computer** per aggiungere i passaggi trovati alla risposta.

### ✨ Spiegazione con l'AI locale (facoltativa)

Con **Ollama** installato compare **✨ Spiegazione discorsiva con l'AI locale**: il testo viene scritto in tempo reale, in italiano, usando solo i dati del file, dei documenti e del glossario. Senza Ollama tutto il resto funziona. Verifica sempre sulle fonti quanto scritto dall'AI.

---

## 5. 🧠 Conoscenza: insegnare all'AI

L'AI conosce l'italiano tecnico ma non le sigle del tuo progetto. In questa scheda **lei legge un documento e ti fa domande**; le tue risposte formano un **glossario** che verrà usato nelle analisi.

1. **Scegli la fonte** a sinistra:
   - **⚙️ Da una funzione**: scrivi il FUNC ID (es. `BOG_Hotbox_Detection`) e la configurazione; l'AI legge le pagine dell'FRS che trattano la funzione;
   - **📄 Da un PDF del computer**: cerca il PDF per nome o codice e, se vuoi, indica l'intervallo di pagine (*auto* = tutto, fino a `KNOWLEDGE_MAX_PAGES`).
2. Premi **🎓 Inizia la lezione**. L'AI individua sigle, sensori, centraline, attuatori, segnali e termini ricorrenti non ancora noti (al massimo `KNOWLEDGE_MAX_QUESTIONS`).
3. Per ogni termine vedi la **frase del documento** in cui compare (📄 pag. N apre il PDF) e rispondi:
   - scrivi il **significato** con parole tue, scegli la **categoria** (🌡️ sensore, 🖥️ centralina, ⚙️ attuatore, 🔀 relè, 📶 segnale, 🏗️ sottosistema, 🔩 componente, 🔤 sigla, 💡 concetto) e, se vuoi, delle note;
   - **✔ Salva e continua** (Ctrl+Invio) · **✨ Proposta AI** (l'AI suggerisce una definizione da correggere) · **⏭ Salta** · **🚫 Ignora sempre**.
4. A destra il **Glossario**: ricerca, filtro per categoria, ➕ aggiunta manuale, ✏️ modifica, 🗑 eliminazione, ⬇ esportazione JSON.

**Come viene usato**: con `KNOWLEDGE_USE_IN_ANALYSIS = True`, in tutti i prompt inviati a Ollama (opzioni del programma e spiegazioni di Chiedi) vengono aggiunte le definizioni dei soli termini presenti nel testo analizzato (al massimo `KNOWLEDGE_MAX_TERMS_IN_PROMPT`). Il glossario è salvato in `KNOWLEDGE_FILE` (cartella della cronologia) e puoi copiarlo su un altro PC. La proposta AI richiede Ollama; il quiz e il glossario funzionano anche senza.

---

## 6. ⚠️ Il foglio Reqs not matched (opzione 5)

Il foglio contiene **tutti** i requisiti non MATCHED fra le configurazioni scelte (nessun limite che interrompe l'analisi: con `REQS_NOT_MATCHED_AI_MAX_CALLS = 0` le note AI sono calcolate per tutte le righe; se imposti un limite, le righe restanti vengono comunque scritte con «[Nota AI non generata …]» e completate alla successiva esecuzione).

Nella colonna **Note** trovi inoltre:

- **«Mancanza link documentale per l'FRS *<nome FRS>* nella configurazione *<configurazione>* (inserire il link nel foglio Funzioni).»** quando una configurazione non ha il link al documento: il requisito non è “assente”, manca solo il collegamento. La cella della configurazione è colorata in **arancio chiaro** con un commento.
- **«Requisito simile a *<ID>* (somiglianza della Description NN %; presente in …).»** quando un requisito con ID diverso ha una descrizione simile (stesso requisito rinumerato). Le due righe vengono messe **una accanto all'altra** e l'ID è evidenziato in **giallo chiaro**. La soglia è `REQS_NOT_MATCHED_SIMILAR_MIN` (0.80 = 80 %; 1.0 = solo testo identico; 0 = disattivato).

Per vedere le nuove note rigenera il foglio con l'opzione 5 (menu del programma o 🛠️ Strumenti). In 📊 Fogli usa i filtri rapidi **🔗 Link documentale mancante** e **≈ Requisiti simili**.

---

## 7. 🛠️ Strumenti e CONFIG (sezione riservata)

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

### Le opzioni del programma in breve

| Opzione | Cosa fa |
|---|---|
| 1 | Sintesi AI delle funzioni per configurazione (righe «Funzioni AI» del foglio Funzioni) |
| 2 | Ricerca delle funzioni nei documenti (foglio Index Funzioni) |
| 3 | Ricerca del riferimento di pagina nei documenti |
| 4 | Confronto specifico Funzioni-Requisiti (foglio Confronto Reqs) |
| 5 | Requisiti non MATCHED tra configurazioni (foglio Reqs not matched) |

I dettagli completi sono nel [README](README.md).

---

## 8. ⚡ Prestazioni

- Ogni foglio è letto una sola volta e conservato compresso in `WEB_CACHE_DIR`; viene riletto solo se il file Excel cambia.
- Esplora carica un unico riepilogo compatto e scarica i dettagli di una funzione solo quando la apri (poi restano in memoria).
- Indice full-text dei PDF, pagine delle funzioni, miniature, figure e risposte sono in cache; le miniature vengono caricate solo quando diventano visibili.
- La griglia disegna solo le righe visibili.
- Per liberare spazio cancella la cartella `WEB_CACHE_DIR`: verrà ricostruita.

## 9. ❓ Domande frequenti e problemi

| Problema | Soluzione |
|---|---|
| La pagina non si apre | Controlla che la finestra di AVVIA_WEB.bat sia aperta e vai su http://127.0.0.1:8765 |
| «La porta … è già usata» | `python asktrainmind_web.py --port 8800` (se la pagina è già attiva il browser si apre direttamente) |
| File Excel non trovato | Imposta `EXCEL_PATH` (Strumenti → Percorsi, oppure `config.py`) |
| In Esplora un FRS ha un pallino tratteggiato | Manca il link al documento nel foglio Funzioni per quella configurazione |
| «PDF non presente sul PC» | Sincronizza DOC_FLOTTE con OneDrive e verifica `ONEDRIVE_DOCS_ROOT`; resta disponibile 🌐 SharePoint |
| La ricerca nei documenti non trova nulla | Attendi la fine dell'indicizzazione (prima volta) o premi Strumenti → ↻ Aggiorna indice documenti |
| Nessuna spiegazione / proposta AI | Avvia Ollama e scarica il modello (`ollama pull …`); controlla `WEB_QA_USE_AI` |
| Reqs not matched senza le nuove note | Rigenera il foglio con l'opzione 5 |
| Scheda Strumenti assente | La pagina è aperta da un altro PC: Strumenti è disponibile solo sul PC del programma |
| Dati non aggiornati | Premi F5; la pagina si aggiorna comunque da sola quando il file cambia |

## 10. ⚙️ Variabili di config.py usate dalla pagina web

| Variabile | Significato |
|---|---|
| `WEB_HOST` / `WEB_PORT` | indirizzo e porta (predefinito 127.0.0.1:8765, solo questo PC) |
| `WEB_OPEN_BROWSER` | apre il browser all'avvio |
| `WEB_CACHE_DIR` | cartella della cache della pagina web |
| `WEB_EXTRA_DOC_DIRS` | altre cartelle con PDF per risposte e ricerca |
| `WEB_PDF_INDEX_MAX_PAGES` | pagine massime indicizzate per PDF (0 = tutte) |
| `WEB_PDF_INDEX_AT_START` | costruisce/aggiorna l'indice dei PDF in background all'avvio |
| `WEB_QA_USE_AI` | abilita la spiegazione con l'AI locale in Chiedi |
| `WEB_QA_MAX_SECTION_PAGES` | pagine massime analizzate per funzione |
| `KNOWLEDGE_FILE` | file JSON del glossario |
| `KNOWLEDGE_USE_IN_ANALYSIS` | usa il glossario nei prompt di analisi e in Chiedi |
| `KNOWLEDGE_MAX_TERMS_IN_PROMPT` | termini massimi aggiunti a un prompt |
| `KNOWLEDGE_MAX_QUESTIONS` | domande massime per lezione |
| `KNOWLEDGE_MAX_PAGES` | pagine massime lette per lezione |
| `REQS_NOT_MATCHED_SIMILAR_MIN` | soglia dei requisiti simili nell'opzione 5 |
| `CONFIG_OVERRIDES_FILE` | file con i valori forzati dalla sezione CONFIG |
