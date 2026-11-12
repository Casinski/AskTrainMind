# AskTrainMind — Guida al funzionamento

## Cos'è AskTrainMind

AskTrainMind è uno script Python che compila automaticamente le celle
**"Funzioni AI"** nel foglio Excel ETR1000, analizzando i documenti tecnici
PDF/DOCX presenti su OneDrive e confrontando le configurazioni di flotta.

All'avvio di `python funzioni_ai_filter.py` compare un menu:

```
  1) Esegui Funzioni AI e Requisiti
  2) Ricerca Funzioni
  3) Cerca riferimento pagina
  4) CONFRONTO SPECIFICO FUNZIONI-REQUISITI
```

- **1** compila le celle "Funzioni AI" del foglio **Funzioni** e il foglio
  **Requisiti** (vedi [Opzione 1 — cosa succede nel file Excel](#opzione-1--cosa-succede-nel-file-excel)).
- **2** crea/aggiorna il foglio **Index Funzioni** con l'elenco delle funzioni
  dei documenti FRS di ogni configurazione e, per ognuna, il FUNC ID e la
  DESCRIZIONE FUNZIONE da usare nel foglio Funzioni (vedi [Opzione 2 — Ricerca Funzioni](#opzione-2--ricerca-funzioni-foglio-index-funzioni)).
- **3** compila solo le celle **Rif. Pagina** del foglio **Funzioni**
  (vedi [Opzione 3 — Cerca riferimento pagina](#opzione-3--cerca-riferimento-pagina)).
- **4** confronta per *Description* i requisiti dei documenti di un DOC ID
  (es. `FRS_Coupler`) in tutte le configurazioni e scrive l'esito nel foglio
  **Confronto Reqs** (vedi [Opzione 4 — Confronto specifico Funzioni-Requisiti](#opzione-4--confronto-specifico-funzioni-requisiti-foglio-confronto-reqs)).

### Flusso di lavoro consigliato

1. **Opzione 2** → foglio *Index Funzioni* con le funzioni dei documenti e
   i FUNC ID / DESCRIZIONE FUNZIONE proposti;
2. nel foglio **Funzioni** si inseriscono le funzioni (col A = FUNC ID,
   col B = DESCRIZIONE FUNZIONE) e i link dei documenti;
3. **Opzione 3** → le celle *Rif. Pagina* vengono compilate dall'indice
   dei PDF;
4. **Opzione 1** → generazione di *Funzioni AI* e *Requisiti*.

---

## Architettura dei file

| File | Ruolo |
|---|---|
| `funzioni_ai_filter.py` | Entry point e orchestratore principale |
| `excel_scanner.py` | Legge il foglio Excel e produce i `FillTarget` da compilare |
| `document_handler.py` | Scarica e estrae il testo dai PDF/DOCX |
| `ai_synthesizer.py` | Chiama Ollama e produce il testo per la cella |
| `llm_json.py` | Lettura tollerante del JSON prodotto dal modello (ripara le risposte troncate) |
| `requirements_extractor.py` | Estrae i requisiti dalle tabelle dei PDF (layout orizzontale e verticale) |
| `function_parser.py` | Parsing strutturato del testo estratto |
| `deterministic_comparator.py` | Confronto oggettivo (valori numerici, timer) senza LLM |
| `support_loader.py` | Carica i fogli di supporto Excel (Cartelle, Configurazioni) |
| `url_builder.py` | Costruisce gli URL SharePoint dai dati Excel |
| `index_funzioni.py` | Opzione 2 "Ricerca Funzioni": crea il foglio "Index Funzioni" |
| `func_id_proposer.py` | Opzione 2: FUNC ID e DESCRIZIONE FUNZIONE ricopiati o proposti per le funzioni dell'indice |
| `confronto_reqs.py` | Opzione 4 "Confronto specifico Funzioni-Requisiti": crea il foglio "Confronto Reqs" |
| `rif_pagina.py` | Calcolo del "Rif. Pagina" dall'indice dei PDF (opzione 3 e inizio opzione 1) |
| `interrupt_guard.py` | Salvataggio dei progressi su interruzione (Ctrl+C), salvataggi automatici e punti di ripresa |
| `config.py` | Parametri globali (percorsi, modello AI, soglie) — vedi [Opzioni di configurazione](#opzioni-di-configurazione-configpy) |

---

## Flusso di esecuzione

```
Excel (ws_write) ──► excel_scanner.scan() ──► FillTarget[]
                                                    │
                         ┌──────────────────────────┘
                         ▼
              document_handler.download()     ← cerca file su OneDrive
              document_handler.extract_page_text()  ← estrae testo PDF
                         │
                         ▼
              function_parser.parse_function_structure()   ← parsing regex
              deterministic_comparator.compare_all()       ← diff oggettive
                         │
                         ▼
              ai_synthesizer.synthesize_with_comparison()  ← Ollama (1 chiamata/gruppo)
                         │
                         ▼
              ws_write.cell().value = testo formattato
              colore cella (Verde/Rosso/Nero/Grigio)
```

---

## Opzione 1 — cosa succede nel file Excel

Passi eseguiti da `python funzioni_ai_filter.py` → scelta **1**, visti dal
punto di vista del file Excel (`EXCEL_PATH` in `config.py`).

1. **Controlli iniziali** — verifica che Ollama sia attivo e che il file
   Excel esista; altrimenti si ferma senza toccare nulla.
2. **Apertura del file** — il file viene aperto due volte: una copia in sola
   lettura dei *valori* (per leggere link e formule già calcolati) e una
   copia di *scrittura*, l'unica che verrà salvata.
3. **Lettura dei fogli di supporto**
   - **Cartelle** cella D5 → radice dei percorsi dei documenti;
   - **CONFIG** e **MAN_CPR** → per ogni DOC ID e configurazione, il codice
     del documento da aprire.
4. **Aggiornamento "Rif. Pagina"** (se `RIF_PAGINA_DYNAMIC = True`) — per
   ogni funzione del foglio **Funzioni** la pagina viene ricavata
   dall'indice del PDF e scritta nella riga "Rif. Pagina":
   - verde se coincide con quella scritta a mano o se la cella era vuota;
   - rossa nel formato `32 utente - 34 dinamico` se diverge;
   - non toccata se non è calcolabile.
5. **Scansione del foglio Funzioni** — riga per riga si riconoscono:
   - riga funzione (col A = FUNC ID, col B = descrizione);
   - riga documento (col C = cartella `CONFIG`/`MAN_CPR`/…, col D = DOC ID,
     una colonna per configurazione con il link);
   - righe di dettaglio (col E = "Rif. Pagina", "Funzioni AI", …).

   Diventa un *obiettivo* ogni cella "Funzioni AI" la cui configurazione ha un
   link valido nella riga documento. Gli obiettivi sono raggruppati per
   (FUNC ID, DOC ID) così ogni funzione si analizza una volta per tutte le
   configurazioni. Con `--start FUNC_ID` le funzioni precedenti sono saltate.
6. **Controllo incrementale** (`RECHECK_MODE`) — per ogni gruppo:
   - livello 1: dimensione e data del PDF uguali all'ultima esecuzione →
     gruppo saltato, celle invariate;
   - livello 2: impronta del testo della sezione e della lista requisiti
     uguale → gruppo saltato; diversa → riga in `storico_differenze.log` e
     rianalisi.
7. **Ricerca della sezione nel PDF** — partendo da "Rif. Pagina" si cerca il
   paragrafo della funzione nell'indice e se ne estrae il testo fino al
   paragrafo successivo.
8. **Estrazione dei requisiti** dalle tabelle e dal testo della sezione
   (gli ID citati dentro una Description non diventano nuovi requisiti).
9. **Foglio Requisiti**
   - cerca la riga della funzione (col A = FUNC ID, oppure col B =
     descrizione); se manca la crea;
   - sotto di essa, una riga per requisito: col C = numero requisito,
     col D = configurazioni in cui compare (colorate). I requisiti già
     presenti vengono aggiornati, i nuovi inseriti in coda al blocco;
   - colonne configurazione (da col E):
     - VZI_Base → testo completo del requisito, nero;
     - altre → `MATCHED` verde se identico alla base, altrimenti differenze
       in rosso;
     - VZI_Base assente → `MISS VZI_BASE REQ, MATCHED` (verde) o
       `MISS VZI_BASE REQ, FOUND DIFF` (rosso).
10. **Cella "Funzioni AI"** del foglio Funzioni:
    - VZI_Base → riassunto della funzione generato da Ollama, nero;
    - altre configurazioni → `RIFERIMENTO VZI_BASE, % SIMILARITY = X`,
      colorata in base alla percentuale (verde ≥ 90, verde ≥ 80,
      arancio ≥ 50, rosso sotto);
    - VZI_Base assente → `MISS VZI_BASE` + riassunto, nero;
    - in coda viene aggiunta la nota con la pagina usata.
11. **Salvataggio** — cache, storico e file Excel. Se il file è aperto in
    Excel si riprova ogni 5 s per 60 s, poi si salva
    `<nome>_backup.xlsx`. Log: `funzioni_ai_filter.log`.

Dettaglio di MATCHED e % SIMILARITY: [README_FUNCT-REQS.md](README_FUNCT-REQS.md).

---

## Opzione 2 — Ricerca Funzioni (foglio "Index Funzioni")

`python funzioni_ai_filter.py` → scelta **2** (oppure `--mode 2`).
Legge gli indici dei PDF; Ollama serve solo per proporre le descrizioni
delle funzioni nuove (`INDEX_FUNC_DESC_MODE = "ai"`, vedi punto 6).

1. **Lettura di CONFIG** — sezione *Functional Requirement Specification
   (FRS)*, righe da `FRS_Drive Control` a `FRS_EMS` (colonna B = DOC ID).
   Per ogni configurazione della riga 1 (VZI_Base, VZI_New14, VZ_FR, …) si
   legge:
   - il codice documento (prima colonna del gruppo);
   - la nota (terza colonna del gruppo, es. `manca`).

   Le celle `\` o `_` significano "nessun documento".
2. **Ricerca del file** in `ONEDRIVE_DOCS_ROOT`: prima nel percorso standard
   `<config>\CONFIG\FRS\<codice>.pdf`, poi per nome in tutte le
   sottocartelle (preferendo quelle con il nome della configurazione).
3. **Lettura delle funzioni** — nel sommario del PDF (prime pagine) si
   cerca il capitolo **Functional requirements**; sono funzioni:
   - i suoi figli diretti (es. `3.1 Coupling`, `3.2 Decoupling`);
   - i nipoti (es. `3.2.1 Pantograph - Lifting`) se
     `INDEX_FUNC_MAX_DEPTH = 2`.

   Le voci generiche (`Function Design`, `Requirements`, `Normal
   condition`, …) sono escluse. Se la numerazione non è gerarchica
   (documenti VSI) il livello si ricava dal rientro del titolo.
4. **Costruzione dell'elenco per DOC ID**:
   - prima tutte le funzioni di **VZI_Base**, nell'ordine dell'indice;
   - poi, configurazione per configurazione, si aggiungono in coda solo le
     funzioni **non già presenti**.

   Due titoli sono la stessa funzione se coincidono ignorando maiuscole,
   spazi e punteggiatura, oppure se la somiglianza è ≥
   `INDEX_FUNC_FUZZY_MATCH`.
5. **Scrittura del foglio** (rigenerato da zero a ogni esecuzione):

| Riga | Col A | Col B | Col C | Col D | Col E, F, … (una per configurazione) |
|---|---|---|---|---|---|
| 1 | `DOC ID / Funzione` | `Paragrafo` | `FUNC ID` | `DESCRIZIONE FUNZIONE` | nome configurazione |
| titolo blocco | DOC ID (es. `FRS_Air Supply`) | — | prefisso FUNC ID (es. `AIR`) | — | documento di riferimento (es. `3EST000225-7915`) |
| righe sotto | titolo funzione | paragrafo dell'indice (es. `3.1`, `3.2.1`) | FUNC ID | descrizione | `MATCHED` / `NOT FOUND` / `N/A` |

   Con `INDEX_FUNC_PROPOSE_IDS = False` le colonne C e D non vengono
   create e le configurazioni partono dalla colonna C (solo MATCHED,
   titolo e paragrafo).

   Il **Paragrafo** è quello del documento da cui la funzione è stata presa
   (VZI_Base se presente, altrimenti la prima configurazione che la
   contiene; il commento della cella indica configurazione, documento e
   pagina). Il paragrafo nelle altre configurazioni è nel commento della
   rispettiva cella `MATCHED`. Per i documenti VSI senza numerazione
   gerarchica il paragrafo è ricostruito dal rientro del sommario.

   Valori nella riga titolo:

| Valore | Significato |
|---|---|
| `codice` | documento trovato e letto (commento = percorso del file) |
| `codice (manca)` | documento segnato `manca` in CONFIG e non trovato |
| `codice (file non trovato)` | codice presente in CONFIG ma file assente |
| `codice (indice 'Functional requirements' non trovato)` | PDF senza quel capitolo nel sommario |
| `\` | nessun documento per quella configurazione |

   Valori nelle righe funzione:

| Valore | Significato |
|---|---|
| `MATCHED` (verde) | la funzione è presente nel documento della configurazione (commento = paragrafo e pagina) |
| `NOT FOUND` (rosso) | documento letto ma funzione assente |
| `N/A` (grigio) | documento non disponibile per la configurazione |

   Le sotto-funzioni sono rientrate e non in grassetto.
6. **FUNC ID e DESCRIZIONE FUNZIONE** (colonne C e D, se
   `INDEX_FUNC_PROPOSE_IDS = True`) — sono i valori da riportare nelle
   colonne A e B del foglio **Funzioni**:
   - funzione **già presente** nel foglio Funzioni (stesso DOC ID e FUNC ID
     corrispondente al titolo del paragrafo) → valori **ricopiati**, in nero;
   - funzione **nuova** → valori **proposti**, in blu corsivo. La
     convenzione è appresa dalle funzioni già presenti:
     - **FUNC ID** = `<PREFISSO>_<titolo del paragrafo>`: il prefisso è
       quello usato dalle funzioni dello stesso documento
       (`FRS_Air Supply` → `AIR`), il titolo ha spazi e ` - ` sostituiti da
       `_` (`Provision for Tilt system` → `AIR_Provision_for_Tilt_system`).
       Per le sotto-funzioni si antepone il titolo del **paragrafo padre**
       se le funzioni esistenti lo fanno, se il titolo è troppo generico
       (`Activation` → `BAT_Battery_Contactors_Activation`) o se il FUNC ID
       è già usato. Senza funzioni esistenti il prefisso si ricava dal
       titolo del documento (`INDEX_FUNC_ID_PREFIX_MAP` per imporlo);
     - **DESCRIZIONE** = una frase in italiano generata da Ollama nello
       stile delle descrizioni esistenti (passate come esempi), a partire
       dal titolo del documento, dal paragrafo padre e dal testo del
       paragrafo letto alla pagina dell'indice. Se Ollama non è disponibile
       si usa `INDEX_FUNC_DESC_TEMPLATE`. Le descrizioni generate sono
       salvate in `INDEX_FUNC_DESC_CACHE_FILE` e riusate alle esecuzioni
       successive.

   Il commento della cella FUNC ID indica l'origine (riga del foglio
   Funzioni, oppure prefisso, paragrafo padre e modalità della descrizione).
7. **Salvataggio** del file Excel (stessa logica dell'opzione 1).

---

## Opzione 3 — Cerca riferimento pagina

`python funzioni_ai_filter.py` → scelta **3** (oppure `--mode 3`).
Non usa Ollama.

Esegue da solo il passaggio "Rif. Pagina" che l'opzione 1 compie
all'inizio (punto 4 dell'opzione 1): per ogni funzione del foglio
**Funzioni** con un link documento valido, la pagina viene ricavata
dall'indice del PDF e scritta nella riga "Rif. Pagina" (verde se coincide
con il valore a mano o se la cella era vuota, rossa `32 utente - 34
dinamico` se diverge, non toccata se non calcolabile). Accetta `--start
FUNC_ID` per partire da una funzione. Si usa dopo aver inserito nel foglio
Funzioni le nuove funzioni e i link dei documenti, prima dell'opzione 1.

---

## Opzione 4 — Confronto specifico Funzioni-Requisiti (foglio "Confronto Reqs")

`python funzioni_ai_filter.py` → scelta **4** (oppure `--mode 4`, o
direttamente `--doc "FRS_Coupler"`). Non usa Ollama.

Serve a verificare se i requisiti di un documento sono presenti, con la
**stessa Description**, nei documenti di tutte le configurazioni.

1. **Scelta del DOC ID** — viene mostrato l'elenco numerato dei DOC ID del
   foglio **CONFIG** (col B). Si indicano, separati da virgola, numeri
   dell'elenco o DOC ID (anche solo una parte univoca, es. `FRS_Coup`).
   Con `--doc` la scelta si passa da riga di comando; con `--mode 4` fuori
   da un terminale si usa `CONFRONTO_REQS_DOC_IDS` di `config.py`.
2. **Documenti** — dalla riga del DOC ID in CONFIG si legge il codice del
   documento di ogni configurazione e lo si cerca in `ONEDRIVE_DOCS_ROOT`
   (stessa ricerca dell'opzione 2).
3. **Requisiti** — da ogni documento si estraggono tutti i requisiti
   (tabelle con colonna **Nr** e blocchi verticali con campo **ID**) con il
   campo **Description**.
4. **Confronto** — ogni requisito (partendo da VZI_Base) viene cercato negli
   altri documenti per Description (uguale ignorando maiuscole, spazi,
   virgolette e trattini). Le Description vuote o in
   `CONFRONTO_REQS_IGNORE_DESCRIPTIONS` (`DELETED`) si confrontano per Nr/ID.
5. **Foglio "Confronto Reqs"** — rigenerato a ogni esecuzione, subito dopo
   **Index Funzioni**. Per ogni DOC ID una riga titolo (codice del documento
   e numero di requisiti per configurazione), poi una riga per requisito:

| Colonna | Significato |
|---|---|
| `DOC ID / Requisito` | Nr/ID del requisito |
| `Nr / ID` | campo da cui è letto: `Nr` (tabella orizzontale) o `ID` (tabella verticale) |
| `Description` | testo confrontato |
| una per configurazione | `MATCHED` (verde) = stessa Description e stesso Nr/ID; `MATCHED DIFFERENT ID` (arancio) + Nr/ID della configurazione = stessa Description con Nr/ID diverso; `MISS` (rosso) = Description non trovata (commento se lo stesso Nr/ID esiste con Description diversa); `N/A` = la configurazione non ha il documento |

   Un requisito con `MATCHED` in tutte le configurazioni ha la stessa
   Description in tutti i documenti del DOC ID.
6. **Salvataggio** del file Excel (stessa logica dell'opzione 1).

---

## Interruzione e ripresa dell'esecuzione

Con `SAVE_PROGRESS = True` (predefinito) l'esecuzione può essere fermata in
qualsiasi momento con **Ctrl+C** (o Ctrl+Break) senza perdere il lavoro:

| Opzione | Cosa viene salvato all'interruzione | Alla ripartenza |
|---|---|---|
| 1 — Funzioni AI e Requisiti | Celle "Funzioni AI" e righe "Requisiti" già scritte, Rif. Pagina già calcolati, storico, cache dei confronti requisiti. Le righe requisito inserite ma non completate vengono tolte | Riparte dalla funzione interrotta; le celle già compilate e invariate vengono saltate (`RECHECK_MODE`) |
| 2 — Ricerca Funzioni | Foglio "Index Funzioni" con i DOC ID analizzati fino a quel momento (commento "Elenco PARZIALE" in A1), analisi dei PDF e descrizioni AI in cache | Rigenera il foglio completo; i PDF già analizzati e le descrizioni già generate vengono ripresi dalla cache |
| 3 — Cerca riferimento pagina | Celle "Rif. Pagina" già calcolate | Riparte dalla funzione interrotta |
| 4 — Confronto specifico Funzioni-Requisiti | Foglio "Confronto Reqs" con i DOC ID già confrontati | Rilanciare l'opzione |

Inoltre:

- nell'opzione 1 il file viene salvato anche ogni `AUTOSAVE_EVERY_N_GROUPS`
  funzioni, così anche una chiusura brusca (finestra chiusa, PC spento) perde al
  massimo le ultime funzioni;
- il file Excel viene scritto su un file temporaneo e poi sostituito: un
  secondo Ctrl+C durante il salvataggio viene rimandato alla sua conclusione;
- dal menu interattivo viene chiesto se riprendere dalla funzione interrotta;
  con `--mode` la ripresa è automatica, `--start` ha sempre la precedenza;
- nessuna colonna viene aggiunta ai fogli: i dati di ripresa stanno in
  `%LOCALAPPDATA%\FunzioniAI\progress_state.json`;
- il programma termina con codice di uscita `130` quando è stato interrotto.

Per disattivare tutto: `SAVE_PROGRESS = False`. Per ricominciare da capo
anziché riprendere, rispondere `n` alla domanda del menu oppure cancellare
`progress_state.json`.

---

## Struttura della cella "Funzioni AI"

Ogni cella compilata contiene **tre sezioni**:

### Sezione 1 — Descrizione funzionale
Breve descrizione in italiano (3-5 frasi) di cosa fa la funzione
in quella specifica configurazione, basata sul testo del documento.

```
Il sistema di alzamento pantografo gestisce la selezione e il sollevamento
del pantografo corretto in base al paese di operazione e al sistema di
tensione di linea selezionato dal conducente. Il TCMS invia il comando
al PCU tramite bus IP specificando il tipo di pantografo da alzare.
```

### Sezione 2 — Confronto con altre configurazioni
Testo leggibile in italiano che spiega se la configurazione è uguale
o diversa rispetto alle altre e **perché**, con motivazione tecnica esplicita.

Esempi:
```
CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_Base è equivalente a VZI_FR: entrambe le configurazioni implementano
la stessa logica di alzamento con gli stessi valori di soglia (750 kPa, 35 s).

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_ES è differente da VZI_Base a causa dei differenti valori parametrici
nel funzionamento nominale: la soglia di pressione è 800 kPa invece di
750 kPa e il timeout di rilevamento guasto è 40 s invece di 35 s.
```

### Sezione 3 — Dettaglio tecnico
Checklist delle categorie funzionali analizzate, differenze parametriche
rilevate automaticamente, score di equivalenza (0-100).

```
ANALISI FUNZIONALE:
  • Scopo funzionale: IDENTICAL
  • Logica operativa: IDENTICAL
  • Prestazioni: DIFFERENT
  • Comportamento in guasto: IDENTICAL

DIFFERENZE PARAMETRICHE (rilevate automaticamente):
  • parametri numerici: soglia pressione 800 vs 750 kPa

Score equivalenza funzionale: 68/100
```

---

## Colorazione celle

| Colore | Significato | Condizione |
|---|---|---|
| 🟢 **Verde** | Configurazioni equivalenti | Score ≥ 75, nessuna diff. funzionale critica |
| 🔴 **Rosso** | Differenze funzionali reali | Score < 75 o ≥ 2 categorie DIFFERENT o ≥ 3 diff. parametriche |
| ⚫ **Nero** | Incerto o unica configurazione | Score borderline, o unica config disponibile |
| ⬜ **Grigio** | Errore | Documento non trovato, PDF scansionato, errore LLM |

---

## Logica di estrazione testo dal PDF

### Strategia A — Indice trovato (caso normale)
1. Cerca tutti gli indici numerici nella pagina iniziale (es. `3.2.1`)
2. Abbina l'indice al `func_id` tramite confronto parole chiave
3. Legge le pagine successive includendo tutti i figli (`3.2.1.x`)
4. Si ferma al primo indice fratello o superiore (`3.2.2`, `3.3`)

### Strategia B — Nessun indice abbinabile (fallback)
Usata quando il titolo del documento è in una lingua diversa
dal `func_id` e non c'è corrispondenza testuale.
Calcola la similarità keyword tra pagine successive e la pagina
iniziale. Si ferma sotto la soglia `SIMILARITY_THRESHOLD`.

### Pagine parziali
- **Pagina iniziale parziale**: la pagina inizia con un'altra sezione
  prima della nostra funzione → il testo prima dell'indice viene escluso
- **Pagina finale parziale**: l'ultima pagina contiene sia la nostra
  funzione sia l'inizio della successiva → il testo viene troncato
  all'inizio della nuova sezione

La nota pagina nella cella riflette questi casi:
```
Pag. iniziale: parte di pag.8 — Pag. finale: parte di pag.14.
Pag. iniziale: pag.8 — Pag. finale: pag.14.
Pag. di riferimento: pag.8.
```

---

## Casistiche possibili nelle celle

### Caso 1 — Funzione identica in tutte le configurazioni 🟢
```
[Descrizione funzionale...]

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_Base è equivalente a VZI_FR e VZI_ES: tutte le configurazioni
implementano la stessa logica con gli stessi parametri operativi.

ANALISI FUNZIONALE:
  • Scopo funzionale: IDENTICAL
  • Logica operativa: IDENTICAL
  • Prestazioni: IDENTICAL
  ...
Score equivalenza funzionale: 92/100
Pag. iniziale: pag.8 — Pag. finale: pag.14.
```

### Caso 2 — Differenze parametriche tra configurazioni 🔴
```
[Descrizione funzionale...]

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_ES è differente da VZI_Base a causa dei differenti valori parametrici:
la soglia di pressione è 800 kPa invece di 750 kPa.

ANALISI FUNZIONALE:
  • Prestazioni: DIFFERENT
  ...
DIFFERENZE PARAMETRICHE (rilevate automaticamente):
  • parametri numerici: 800 kPa vs 750 kPa
Score equivalenza funzionale: 62/100
Pag. iniziale: pag.13 — Pag. finale: parte di pag.19.
```

### Caso 3 — Caso borderline (revisione manuale) ⚫
```
[Descrizione funzionale...]

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_FR presenta una differenza parziale rispetto a VZI_Base nella
gestione del guasto: il comportamento è simile ma con una sequenza
di reset leggermente diversa.

⚪ Caso non classificabile con certezza: revisione manuale raccomandata.
Score equivalenza funzionale: 67/100
Pag. di riferimento: pag.8.
```

### Caso 4 — Unica configurazione disponibile ⚫
```
[Descrizione funzionale...]

Unica configurazione disponibile — nessun confronto effettuato.
Pag. iniziale: pag.5 — Pag. finale: pag.9.
```

### Caso 5 — Documento non trovato ⬜ (grigio)
```
[Testo non estratto: pag.13 di FA020022045]
```

### Caso 6 — PDF scansionato (immagine senza testo) ⬜ (grigio)
```
[Testo non disponibile nel documento per questa pagina]
```

---

## Opzioni di configurazione (`config.py`)

Tutte le impostazioni stanno in **`config.py`**: è l'unico file da modificare.
Ogni opzione è una normale assegnazione Python; per cambiarla si modifica il
valore e si salva il file, che verrà riletto all'esecuzione successiva.

```python
# Esempi di modifica
MAX_CELLS_PER_RUN  = 0                    # numero  → nessun limite
START_FROM_FUNC_ID = ""                   # testo   → parti dall'inizio
SAVE_PROGRESS      = False                # booleano: True / False
INDEX_FUNC_ID_PREFIX_MAP = {"FRS_Drive Control": "DRV"}   # dizionario
EXCEL_PATH = Path(r"D:\Dati\DB Flotte ETR1000.xlsx")      # percorso (r"..." per i \)
```

Regole generali: i testi vanno tra virgolette, i booleani sono `True`/`False`
(maiuscola iniziale), le soglie 0–1 sono frazioni (`0.9` = 90 %), le soglie
0–100 sono percentuali. Se un'opzione viene cancellata, i moduli che la
leggono con `getattr` usano il valore predefinito indicato qui sotto.

### Percorsi e fogli

| Opzione | Valore | Significato |
|---|---|---|
| `EXCEL_PATH` | `C:\__SCRIPTS\AskTrainMind\DB Flotte ETR1000 Ver_1.8.xlsx` | File Excel da compilare |
| `ONEDRIVE_DOCS_ROOT` | cartella `DOC_FLOTTE` di OneDrive | Radice dei documenti PDF sincronizzati |
| `SHEET_FUNZIONI` / `SHEET_REQUISITI` / `SHEET_CONFIG` / `SHEET_CARTELLE` / `SHEET_MAN_CPR` / `SHEET_INDEX_FUNZIONI` | `"Funzioni"`, `"Requisiti"`, `"CONFIG"`, `"Cartelle"`, `"MAN_CPR"`, `"Index Funzioni"` | Nomi dei fogli (cambiarli solo se si rinominano i fogli nel file) |
| `FUNZIONI_AI_LABEL` | `"Funzioni AI"` | Etichetta (colonna E) delle righe da compilare |
| `CARTELLE_BASE_URL_ROW` / `_COL` | `5` / `4` | Cella del foglio Cartelle con l'URL SharePoint di base |

### Modello AI (Ollama)

| Opzione | Valore | Significato |
|---|---|---|
| `OLLAMA_MODEL` | `"qwen2.5:7b-instruct"` | Modello locale; es. `"qwen2.5:14b-instruct"` se c'è RAM/VRAM sufficiente |
| `OLLAMA_KEEP_ALIVE` | `"30m"` | Tempo per cui il modello resta caricato fra due chiamate |
| `OLLAMA_NUM_CTX` | `8192` | Finestra di contesto (token) |
| `OLLAMA_NUM_PREDICT` / `OLLAMA_NUM_PREDICT_MAX` | `300` / `1536` | Token minimi in uscita / tetto del budget calcolato automaticamente |
| `LLM_PARALLEL_WORKERS` | `3` | Chiamate contemporanee (1 = sequenziale; GPU 3–4, CPU 2) |

### Esecuzione

| Opzione | Valore | Significato |
|---|---|---|
| `MAX_CELLS_PER_RUN` | `4` | Celle "Funzioni AI" per esecuzione (0 = nessun limite) |
| `AI_CALL_DELAY_SECONDS` | `0.0` | Pausa fra un gruppo e l'altro |
| `START_FROM_FUNC_ID` | `"BOG_Hotbox_Detection"` | FUNC ID da cui partono le opzioni 1 e 3 (`""` = inizio foglio); `--start` ha la precedenza |
| `SIMILARITY_THRESHOLD` | `0.26` | Soglia della Strategia B (sezione trovata per somiglianza testuale) |
| `MAX_SECTION_PAGES` | `25` | Pagine lette al massimo dopo l'inizio di una sezione |
| `LLM_SCORE_GREEN` / `LLM_SCORE_RED` | `80` / `60` | Score del vecchio percorso di sintesi: ≥ verde, < rosso |

### Salvataggio dei progressi e ripresa

| Opzione | Valore | Significato |
|---|---|---|
| `SAVE_PROGRESS` | `True` | Salva il lavoro su interruzione, scrittura atomica del file Excel, punti di ripresa. `False` = comportamento originale |
| `AUTOSAVE_EVERY_N_GROUPS` | `5` | Opzione 1: salva il file Excel ogni N funzioni (0 = mai) |
| `RESUME_FROM_CHECKPOINT` | `True` | Opzioni 1 e 3: ripartono dalla funzione interrotta |
| `PROGRESS_STATE_FILE` | `%LOCALAPPDATA%\FunzioniAI\progress_state.json` | File dei punti di ripresa |
| `INDEX_FUNC_DOC_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\index_doc_cache.json` | Opzione 2: analisi dei PDF già lette |

Esempio: per salvare ogni funzione `AUTOSAVE_EVERY_N_GROUPS = 1` (più sicuro ma
più lento: ogni salvataggio riscrive l'intero file).

### Storico e controllo incrementale

| Opzione | Valore | Significato |
|---|---|---|
| `RECHECK_MODE` | `"fast"` | Celle già compilate: `"off"` = saltate; `"fast"` = rianalizzate solo se il PDF è cambiato (dimensione/data); `"deep"` = confronta anche il testo |
| `RECHECK_DEEP_EVERY_DAYS` | `30` | In `"fast"`, ogni quanti giorni forzare un controllo `"deep"` |
| `HISTORY_DIR` / `HISTORY_STATE_FILE` / `HISTORY_LOG_FILE` | `%LOCALAPPDATA%\FunzioniAI\…` | Impronte dei documenti e storico delle differenze |
| `HISTORY_READABLE_LOG` | `storico_differenze.log` | Storico leggibile accanto allo script |

### Rif. Pagina

| Opzione | Valore | Significato |
|---|---|---|
| `RIF_PAGINA_DYNAMIC` | `True` | Opzione 1: ricalcola il Rif. Pagina dall'indice dei PDF prima dell'analisi (`False` = usa i valori manuali). L'opzione 3 lo esegue sempre |

### Cella "Funzioni AI" (confronto funzioni)

| Opzione | Valore | Significato |
|---|---|---|
| `FUNC_SIMILARITY_GREEN` / `_HIGH` / `_MEDIUM` | `90` / `80` / `50` | Soglie % di similarità con VZI_Base: verde grassetto / verde / arancione; sotto = rosso |
| `FUNC_SIMILARITY_DECIMALS` | `1` | Decimali della percentuale in cella |
| `FUNC_TXT_REF_BASE_OK` / `FUNC_TXT_REF_BASE_DIFF` / `FUNC_TXT_MISS_BASE` | `"RIFERIMENTO VZI_BASE, % SIMILARITY = {pct}, …"`, `"MISS VZI_BASE"` | Testi della cella (`{pct}` = percentuale) |
| `FUNC_SUMMARY_SENTENCES` / `FUNC_SUMMARY_INPUT_CHARS` / `FUNC_SUMMARY_MAX_CHARS` | `5` / `6000` / `1200` | Frasi del riassunto, testo inviato al modello, lunghezza massima in cella |
| `FUNC_LLM_SCORE_MATCH` / `FUNC_TEXT_SIMILARITY_MATCH` | `80` / `0.95` | Soglie di MATCHED del confronto di funzione |
| `FUNC_USE_REQ_VERDICT` / `FUNC_REQ_DIFF_FORCES_DIFF` | `True` / `True` | L'esito dei requisiti forza MATCHED / DIFF della funzione |
| `FUNC_DIFF_MAX_CHARS` | `900` | Lunghezza massima del testo di differenze |

### Foglio Requisiti

| Opzione | Valore | Significato |
|---|---|---|
| `REQ_HEADER_ROW` | `1` | Riga di intestazione |
| `REQ_FUNC_ID_COL` / `REQ_DESC_COL` / `REQ_NUMBER_COL` / `REQ_CONFIG_COL` | `1` / `2` / `3` / `4` | Colonne A–D (FUNC ID, descrizione, Nr requisito, configurazione) |
| `REQ_CONFIG_COLS_START` | `5` | Prima colonna delle configurazioni (E) |
| `REQ_BASE_CONFIG` | `"VZI_Base"` | Configurazione di riferimento (usata anche dalle opzioni 1 e 2) |
| `REQ_TXT_MATCHED` / `REQ_TXT_MISS_MATCHED` / `REQ_TXT_MISS_DIFF` / `REQ_TXT_MISS_ONLY` | `"MATCHED"`, … | Testi scritti nelle celle |
| `REQ_COLOR_GREEN` / `_RED` / `_BLACK` | `"FF008000"`, … | Colori ARGB del testo |
| `REQ_FIELD_SEP` / `REQ_FIELD_LABEL` / `REQ_FIELD_LABEL_V` | — | Separatore ed etichette dei campi riportati in cella |
| `REQ_PRIMARY_FIELD` | `"description"` | Campo che decide se due requisiti differiscono |
| `REQ_DESC_SIMILARITY_MATCH` / `REQ_DESC_SIMILARITY_DIFF` | `0.94` / `0.55` | Sopra = MATCHED senza AI; sotto = DIFF senza AI; in mezzo decide Ollama |
| `REQ_LLM_SCORE_MATCH` | `80` | Score di Ollama oltre cui il requisito è MATCHED |
| `REQ_NO_DIFF_MARKERS` | elenco di frasi | Risposte del modello che significano "nessuna differenza" |
| `REQ_DIFF_STYLE` | `"narrativo"` | Differenze come paragrafo (`"narrativo"`) o elenco (`"puntuale"`) |
| `REQ_DIFF_MAX_CHARS` / `REQ_DIFF_DETAIL_MAX` / `REQ_DIFF_SNIPPET_LEN` | `700` / `3` / `160` | Lunghezza e dettaglio delle differenze |
| `REQ_ONE_ROW_PER_CONFIG` | `False` | `True` = una riga per (ID, configurazione) |
| `REQ_PROGRESSIVE_NUMBER` | `False` | Antepone "1) ", "2) " al Nr requisito |
| `REQ_CREATE_MISSING_FUNCTION` | `True` | Crea la riga funzione se manca nel foglio |

### Estrazione dei requisiti dai PDF

| Opzione | Valore | Significato |
|---|---|---|
| `REQ_ID_MARKER` | `"zefiro"` | Testo obbligatorio in un ID requisito reale |
| `REQ_USE_MATRIX_PARSER` | `True` | Lettura delle tabelle con `find_tables` (`False` = solo testo) |
| `REQ_H_HEADER_MIN_MATCH` | `2` | Intestazioni minime per riconoscere una tabella orizzontale |
| `REQ_PROSE_PREFIXES` / `REQ_MAX_ALPHA_RUN` | elenco / `24` | Filtri che scartano frasi scambiate per ID |
| `REQ_DEBUG_DUMP_VERTICAL` / `REQ_DEBUG_LOG_EACH` | `False` | Log diagnostici dettagliati |

### Colori delle configurazioni

| Opzione | Valore | Significato |
|---|---|---|
| `CONFIG_COLOR_MAP` | `{"VZI_Base": "1F4E79", …}` | Colore (RGB esadecimale) di ogni configurazione nota |
| `CONFIG_COLOR_PALETTE` | elenco di colori | Colori assegnati alle configurazioni non in mappa |

Esempio: `CONFIG_COLOR_MAP["VZ_NEW"] = "FF8C00"` dà l'arancione alla nuova configurazione.

### Ricerca Funzioni (opzione 2, foglio "Index Funzioni")

| Opzione | Valore | Significato |
|---|---|---|
| `INDEX_FUNC_FIRST_DOC_ID` / `INDEX_FUNC_LAST_DOC_ID` | `"FRS_Drive Control"` / `"FRS_EMS"` | Righe di CONFIG analizzate (estremi inclusi) |
| `INDEX_FUNC_CHAPTER_TITLES` | `["Functional requirements", …]` | Capitolo dell'indice che contiene le funzioni |
| `INDEX_FUNC_MAX_DEPTH` | `2` | 1 = solo funzioni, 2 = anche sotto-funzioni |
| `INDEX_FUNC_GENERIC_TITLES` | `Function Design`, `Requirements`, … | Sotto-titoli da non considerare funzioni |
| `INDEX_FUNC_FUZZY_MATCH` | `0.92` | Somiglianza minima tra titoli per dire "stessa funzione" |
| `INDEX_FUNC_TOC_MAX_PAGES` | `12` | Pagine iniziali in cui cercare il sommario |
| `INDEX_FUNC_MISSING_NOTE` | `"manca"` | Nota di CONFIG che indica un documento mancante |
| `INDEX_FUNC_PROPOSE_IDS` | `True` | Colonne FUNC ID e DESCRIZIONE FUNZIONE (`False` = solo MATCHED, titolo e paragrafo) |
| `INDEX_FUNC_ID_LEARN_FROM_SHEET` | `True` | Prefisso FUNC ID appreso dalle funzioni esistenti dello stesso DOC ID |
| `INDEX_FUNC_ID_PREFIX_MAP` | `{}` | Prefissi imposti, es. `{"FRS_Drive Control": "DRV"}` |
| `INDEX_FUNC_ID_PARENT_MODE` | `"auto"` | Padre nel FUNC ID delle sotto-funzioni: `auto` / `always` / `never` |
| `INDEX_FUNC_ID_SHORT_TITLE_WORDS` | `1` | In `auto`, titoli con al massimo N parole ricevono il padre |
| `INDEX_FUNC_ID_EXISTING_FUZZY` | `0.9` | Somiglianza titolo/FUNC ID per riconoscere una funzione esistente |
| `INDEX_FUNC_DESC_MODE` | `"ai"` | Descrizione delle funzioni nuove: `ai` / `template` / `off` |
| `INDEX_FUNC_DESC_TEMPLATE` | `"Funzione per gestire {title} ({doc_title}, §{paragraph})"` | Modello di riserva (segnaposto `{title} {doc_title} {doc_id} {paragraph} {parent}`) |
| `INDEX_FUNC_DESC_EXAMPLES` / `_MAX_CHARS` / `_INPUT_CHARS` | `6` / `300` / `3000` | Esempi di stile, lunghezza massima, testo del paragrafo inviato |
| `INDEX_FUNC_DESC_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\index_desc_cache.json` | Cache delle descrizioni AI |

### Confronto specifico Funzioni-Requisiti (opzione 4, foglio "Confronto Reqs")

| Opzione | Valore | Significato |
|---|---|---|
| `SHEET_CONFRONTO_REQS` | `"Confronto Reqs"` | Nome del foglio generato |
| `CONFRONTO_REQS_DOC_IDS` | `[]` | DOC ID proposti di default (es. `["FRS_Coupler"]`): usati premendo Invio nella scelta o con `--mode 4` fuori da un terminale |
| `CONFRONTO_REQS_IGNORE_DESCRIPTIONS` | `["DELETED"]` | Description che non identificano un requisito: confronto per Nr/ID |

### Parametri presenti ma non più usati

Restano in `config.py` per compatibilità, ma modificarli non ha effetto:
`OLLAMA_TIMEOUT`, `CACHE_DIR`, `MS_CLIENT_ID`, `MS_SCOPES`, `CRITICAL_CHECKLIST_KEYS`,
`RIF_PAGINA_LABEL`, `FUNC_TXT_MATCHED`, `FUNC_TXT_MISS_*`, `FUNC_SIMILARITY_DIFF`,
`FUNC_APPEND_DIFF_DETAIL`, `REQ_SECONDARY_FIELDS`, `REQ_WRITE_EXTRA_FIELDS`,
`REQ_EXTRA_FIELDS_START_COL`, `REQ_ACCEPT_LOOSE_IDS`, `REQ_ID_MIN_SEGMENTS`,
`REQ_ID_FALLBACK_PATTERNS`, `REQ_ID_BLACKLIST_SUBSTR`, `REQ_ID_ANCHORED_FALLBACK`,
`REQ_H_HEADER_*` (tranne `REQ_H_HEADER_MIN_MATCH`), `REQ_V_HEADER_*`, `REQ_V_LOOKAHEAD`,
`REQ_H_MAX_BLANK_LINES`, `REQ_H_SKIP_REPEATED_HEADER`, `REQ_TABLE_END_PATTERNS`.

---

## Come eseguire

```bash
# Menu interattivo (1 = Funzioni AI e Requisiti, 2 = Ricerca Funzioni,
#                  3 = Cerca riferimento pagina,
#                  4 = Confronto specifico Funzioni-Requisiti)
python funzioni_ai_filter.py

# Senza menu
python funzioni_ai_filter.py --mode 1    # Funzioni AI e Requisiti
python funzioni_ai_filter.py --mode 2    # Ricerca Funzioni -> foglio "Index Funzioni"
python funzioni_ai_filter.py --mode 3    # Cerca riferimento pagina -> celle "Rif. Pagina"
python funzioni_ai_filter.py --mode 3 --start "AIR_Air_Dryer"
python funzioni_ai_filter.py --mode 4    # Confronto Funzioni-Requisiti -> foglio "Confronto Reqs"

# Opzione 4: DOC ID indicati da riga di comando (foglio CONFIG, col B)
python funzioni_ai_filter.py --doc "FRS_Coupler"
python funzioni_ai_filter.py -m 4 -d "FRS_Coupler, FRS_Horn"

# Opzione 1: riprendi da una funzione specifica
python funzioni_ai_filter.py --mode 1 --start "LV_Pantograph_Lifting"
python funzioni_ai_filter.py -m 1 -s "LV_Pantograph_Lifting"
```

---

## Diagnostica problemi comuni

### Il codice usa Strategia B invece di A
**Causa**: `func_id` non passato o titolo del documento in lingua diversa.
**Soluzione**: Verifica che `target.func_id` sia valorizzato in `excel_scanner.py`
e che venga passato a `extract_page_text(func_id=...)`.

### Gli indici del PDF non vengono rilevati
**Causa più comune**: gli indici si trovano oltre riga 60 della pagina.
**Debug**: esegui `debug_pdf_indexes.py <file.pdf> <pag_inizio> <pag_fine>`.
Cerca le righe `>>>` nell'output per vedere come fitz estrae il testo.

### Riferimenti incrociati trattati come nuovi indici
**Esempio**: `"see chapter 3.2.5"` viene erroneamente interpretato come
l'inizio della sezione 3.2.5.
**Gestione**: `_is_section_heading_line()` e `_filter_progressive_indexes()`
in `document_handler.py` filtrano questi casi controllando:
- L'indice deve essere all'inizio della riga
- La riga precedente non deve contenere parole come "see", "chapter"
- La riga successiva non deve iniziare con virgolette `"`
- La sequenza degli indici deve essere progressiva (gap ≤ 3 tra fratelli)

### Il testo viene troncato troppo presto
**Causa**: un indice estraneo viene trovato prima della fine reale della sezione.
**Debug**: aggiungi log a `_truncate_at_new_section()` per vedere quale
indice causa il troncamento.

### File Excel bloccato
Lo script attende fino a 60 secondi che il file venga chiuso.

---

## WARNING ed ERROR nel log: come vanno letti

`funzioni_ai_filter.log` non deve contenere WARNING in condizioni normali.
Di seguito le cause storiche, tutte risolte, e il comportamento atteso oggi.

### `[Requisiti] Errore estrazione tabelle: 'req_id'`
**Causa**: `realign_header()` scartava la colonna "Nr" quando risultava
vuota nelle righe dati (ID scivolato sotto l'intestazione adiacente, o
tabella fatta di sole righe di continuazione). La testata perdeva il campo
`req_id` e `_parse_horizontal()` sollevava `KeyError`.
L'eccezione risaliva fino al ciclo sulle pagine di `extract_from_tables()`,
interrompendo la scansione di **tutte le pagine successive** della sezione.

**Oggi**: la colonna degli ID non si perde mai — se la testata non la
espone viene dedotta dai dati (colonna di soli ID, con `Derived to`
esclusa perché contiene ID per definizione). Gli errori sono inoltre
isolati per singola tabella e per singola pagina: la scansione prosegue
sempre fino all'ultima pagina della sezione.

### `[Summary] parsing fallito su <funzione>: Unterminated string ...`
**Causa**: `OLLAMA_NUM_PREDICT` valeva 300 token a fronte di riassunti da
1200 caratteri (`FUNC_SUMMARY_MAX_CHARS`). Ollama interrompeva la
generazione a metà stringa e il JSON risultava illeggibile, così **ogni**
riassunto degradava a semplice estratto testuale
(`riassunto LLM non disponibile, usato estratto testuale`).

**Oggi**: ogni chiamata dichiara il budget di token di cui ha bisogno
(`_token_budget()`) e le risposte eventualmente troncate vengono
recuperate da `llm_json.parse_json_relaxed()`, che chiude la stringa e le
parentesi aperte conservando il testo già prodotto dal modello. Il
troncamento viene segnalato a livello INFO, non WARNING.

### `Errore Ollama: prediction aborted, token repeat limit reached`
**Causa**: con `temperature=0` e `repeat_penalty=1.05` il modello poteva
entrare in ripetizione e Ollama abortiva la generazione con HTTP 500.

**Oggi**: `_call_ollama()` ritenta automaticamente fino a tre volte
alzando la penalità di ripetizione (1.05 → 1.25 → 1.40). L'ERROR compare
solo se tutti i tentativi falliscono.

### `STORICO — differenza rilevata`
Non è un'anomalia ma la notifica attesa di una differenza rispetto
all'esecuzione precedente: viene registrata a livello INFO.
Se il timeout scade, salva un backup con suffisso `_backup`.