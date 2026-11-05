# AskTrainMind — Guida al funzionamento

## Cos'è AskTrainMind

AskTrainMind è uno script Python che compila automaticamente le celle
**"Funzioni AI"** nel foglio Excel ETR1000, analizzando i documenti tecnici
PDF/DOCX presenti su OneDrive e confrontando le configurazioni di flotta.

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

---

## Come eseguire

```bash
# Elabora tutto il foglio dall'inizio
python funzioni_ai_filter.py

# Riprendi da una funzione specifica
python funzioni_ai_filter.py --start "LV_Pantograph_Lifting"
python funzioni_ai_filter.py -s "LV_Pantograph_Lifting"
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