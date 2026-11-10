# AskTrainMind — Guida al funzionamento

## Cos'è AskTrainMind

AskTrainMind è uno script Python che compila automaticamente le celle
**"Funzioni AI"** nel foglio Excel ETR1000, analizzando i documenti tecnici
PDF/DOCX presenti su OneDrive e confrontando le configurazioni di flotta.

All'avvio di `python funzioni_ai_filter.py` compare un menu:

```
  1) Esegui Funzioni AI e Requisiti
  2) Ricerca Funzioni
```

- **1** compila le celle "Funzioni AI" del foglio **Funzioni** e il foglio
  **Requisiti** (vedi [Opzione 1 — cosa succede nel file Excel](#opzione-1--cosa-succede-nel-file-excel)).
- **2** crea/aggiorna il foglio **Index Funzioni** con l'elenco delle funzioni
  dei documenti FRS di ogni configurazione (vedi [Opzione 2 — Ricerca Funzioni](#opzione-2--ricerca-funzioni-foglio-index-funzioni)).

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
| `config.py` | Parametri globali (percorsi, modello AI, soglie) |

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
Non usa Ollama: legge solo gli indici dei PDF.

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

| Riga | Col A | Col B | Col C, D, … (una per configurazione) |
|---|---|---|---|
| 1 | `DOC ID / Funzione` | `Paragrafo` | nome configurazione |
| titolo blocco | DOC ID (es. `FRS_Drive Control`) | — | documento di riferimento (es. `3EST000225-7909`) |
| righe sotto | titolo funzione | paragrafo dell'indice (es. `3.1`, `3.2.1`) | `MATCHED` / `NOT FOUND` / `N/A` |

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
6. **Salvataggio** del file Excel (stessa logica dell'opzione 1).

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

## Parametri configurabili (`config.py`)

| Parametro | Default | Descrizione |
|---|---|---|
| `OLLAMA_MODEL` | `"llama3:8b"` | Modello AI locale |
| `OLLAMA_NUM_PREDICT` | `300` | Token **minimi** in uscita. Le risposte lunghe (riassunto, paragrafo di differenze) calcolano da sole il budget necessario |
| `OLLAMA_NUM_PREDICT_MAX` | `1536` | Tetto al budget di token calcolato automaticamente |
| `SIMILARITY_THRESHOLD` | `0.26` | Soglia similarità Strategia B |
| `LLM_SCORE_THRESHOLD_RED` | `75` | Score sotto cui → ROSSO |
| `LLM_SCORE_THRESHOLD_YELLOW` | `55` | Score sotto cui → borderline |
| `MAX_CELLS_PER_RUN` | `0` | Limite celle per run (0 = illimitato) |
| `AI_CALL_DELAY_SECONDS` | `2` | Pausa tra gruppi |
| `START_FROM_FUNC_ID` | `""` | Riprendi da una funzione specifica |
| `SHEET_INDEX_FUNZIONI` | `"Index Funzioni"` | Foglio creato dall'opzione 2 |
| `INDEX_FUNC_FIRST_DOC_ID` / `INDEX_FUNC_LAST_DOC_ID` | `"FRS_Drive Control"` / `"FRS_EMS"` | Righe di CONFIG analizzate dall'opzione 2 |
| `INDEX_FUNC_MAX_DEPTH` | `2` | 1 = solo funzioni, 2 = anche sotto-funzioni |
| `INDEX_FUNC_GENERIC_TITLES` | `Function Design`, `Requirements`, … | Sotto-titoli da non considerare funzioni |
| `INDEX_FUNC_FUZZY_MATCH` | `0.92` | Somiglianza minima tra titoli |

---

## Come eseguire

```bash
# Menu interattivo (1 = Funzioni AI e Requisiti, 2 = Ricerca Funzioni)
python funzioni_ai_filter.py

# Senza menu
python funzioni_ai_filter.py --mode 1    # Funzioni AI e Requisiti
python funzioni_ai_filter.py --mode 2    # Ricerca Funzioni -> foglio "Index Funzioni"

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