# FUNCT-REQS — Come vengono calcolati MATCHED (Requisiti) e % SIMILARITY (Funzioni)

Pipeline per ogni funzione (orchestrata da `funzioni_ai_filter.py`).
**Ordine obbligatorio: prima i Requisiti, poi le Funzioni.**

---

## 1. Estrazione del testo della sezione (`document_handler._extract_pdf`)

1. Si apre il PDF alla pagina indicata nel foglio Excel (`Rif. Pagina`).
2. Si cerca l'**indice di sezione** della funzione (es. `3.2.1`) confrontandolo con `FUNC ID` / descrizione.
   - **Strategia A** (indice trovato): il testo prima dell'indice viene scartato; si leggono le pagine
     successive finché compare un indice fratello o superiore (es. `3.2.2`), poi STOP. Le pagine senza
     indice sono continuazioni della sezione. L'ultima pagina viene troncata all'inizio della nuova sezione.
   - **Strategia B** (indice non trovato): si prosegue finché la sovrapposizione di parole chiave con la
     pagina iniziale resta ≥ `SIMILARITY_THRESHOLD` (0.26).
3. Massimo `MAX_SECTION_PAGES` (25) pagine aggiuntive. Il risultato è il testo della sezione con i marker
   `[Pagina N]`.

## 2. Estrazione dei requisiti (`requirements_extractor.py`)

Due strategie **fuse** (non alternative):

1. **Matrice di celle** (`extract_from_tables`, PyMuPDF `find_tables()`), con ritaglio verticale sulla
   sezione per non prendere requisiti della funzione successiva:
   - **Orizzontale**: testata `Nr | Description | Type/ApplicabilityDetails | Derived to | User Interface | SIL`,
     una riga per requisito.
   - **Verticale**: blocchi `ID / Description / Safety level`.
2. **Testo lineare** (`extract`): recupera i requisiti non rilevati da `find_tables()` (blocchi senza cornice).
3. Classificazione: **accettati** gli ID della colonna `Nr`/`ID` (contenenti `Zefiro`); **scartati** gli ID
   della colonna `Derived to` (sono la provenienza, non requisiti).
4. Deduplica per ID → lista di `Requirement` per configurazione.

**Casi particolari gestiti** (necessari perché un requisito presente in due configurazioni non risulti
«solo in una» nel foglio *Reqs not matched*):

- **Sezione che continua su più pagine**: il ritaglio verticale usa il titolo della funzione come bordo
  superiore **solo sulla pagina in cui la sezione inizia**. Sulle pagine successive un titolo discendente
  (es. `3.1.2.1` dentro `3.1`) è un sotto-paragrafo: le tabelle sopra di esso appartengono ancora alla funzione.
  Prima venivano perse, per esempio `2F_06.03.Zefiro-Europe.CONCEPT.165` (pag. 9 di `3EST000225-7915`,
  AIR_Control_of_Main_Compressor, VZI_Base) e `2F_03.Zefiro-Europe.CONCEPT.213` / `CONCEPT.80`
  (pag. 25-26 di `3EST000225-7906`, VZI_Base).
- **ID spezzato su più righe della tabella** (`2F_03.Zefiro-` / `Europe.CONCEPT.` / `80`): le righe vengono
  ricomposte in un unico ID. Un ID troncato (`2F_06.03.Zefiro`) non viene mai accettato come requisito.
- **Blocco verticale `ID | 2F_…` dentro una tabella orizzontale**: riconosciuto come inizio di un nuovo requisito.
- **Parole incollate** nel testo delle celle (`Ifthepressuredecreasesbelowlimit4`): il testo viene riletto dal
  livello di testo della pagina, che conserva gli spazi.

## 3. Requisiti → MATCHED (`requisiti_writer.py` + `req_ai_comparator.py`)

1. I requisiti di tutte le configurazioni vengono uniti per ID (una riga per requisito nel foglio `Requisiti`).
2. Si confronta **solo la Description** (gli altri campi sono contesto e non generano mai differenze).
   Normalizzazione: minuscole, spazi compattati, punteggiatura rimossa (cifre, `% . / -` conservati).
3. Confronto base (`VZI_Base`) vs ciascuna altra configurazione:

   | Condizione | Esito | LLM |
   |---|---|---|
   | Description identica dopo normalizzazione | **MATCHED** | no |
   | Similarità (`SequenceMatcher`) ≥ `REQ_DESC_SIMILARITY_MATCH` (0.94) | **MATCHED** | no |
   | Description assente in una sola config | DIFF "verifica manuale" | no |
   | Similarità < `REQ_DESC_SIMILARITY_DIFF` (0.55) | DIFF + frammenti divergenti | no |
   | 0.55 ≤ sim < 0.94 | il modello restituisce `score` + `differenze` | sì |

4. Con LLM: **MATCHED** se `differenze` è vuoto (o contiene solo frasi "identico/uguale…", post-filtro)
   **e** `score ≥ REQ_LLM_SCORE_MATCH` (80). Altrimenti DIFF con paragrafo + confronto testuale.
5. Scrittura cella:
   - `VZI_Base` → dump dei campi in nero; altre config → `MATCHED` verde grassetto o differenze in rosso.
   - Base assente, più config: tutte simili → `MISS VZI_BASE REQ, MATCHED`, altrimenti `MISS VZI_BASE REQ, FOUND DIFF`.
   - Base assente, una sola config → `MISS VZI_BASE REQ` + Description.
   - In **ogni** cella, dopo l'esito (MATCHED, differenze o MISS…), segue sempre il separatore e il
     dump della configurazione con la **Description**: così Esplora mostra il testo di ogni configurazione.
     Per i file scritti prima di questa regola: `python req_desc_backfill.py` (voce 18 del terminale).
6. L'esito (`last_verdict`: n. requisiti, n. divergenti, config divergenti) viene passato alle Funzioni.

## 3b. Esito dei requisiti in Esplora (`reqs_not_matched.row_view` + `explore.js → reqStatus`)

La pagina web ricalcola l'esito **fra le configurazioni scelte dall'utente** (non solo base vs altre):

1. Per ogni configurazione si ricava la Description dalla cella (`description_from_cell`) e si raggruppano
   le configurazioni con **lo stesso testo** (gruppi A, B, C…; il gruppo 0 è quello di VZI_Base, se presente).
   Le celle MATCHED senza testo ereditano il testo della base; le celle senza testo ricavabile sono `?`.
2. Riferimento: **VZI_Base** (★) se mostrata e presente; altrimenti la prima configurazione che contiene il
   requisito (☆, riferimento sostitutivo).
3. Esito:

   | Esito | Condizione |
   |---|---|
   | ✔ MATCHED | presente in tutte le configurazioni mostrate, un solo testo |
   | ✖ NOT MATCHED · solo in una | presente in una sola configurazione (con ≥ 2 mostrate) |
   | ✖ NOT MATCHED · manca in alcune | presente in più di una ma non in tutte (anche se nella maggioranza) |
   | ✖ NOT MATCHED · testo diverso | presente in tutte, più di un testo |
   | ? DA VERIFICARE | presente in tutte, un solo testo noto ma qualche testo non ricavabile |

## 4. Funzioni → % SIMILARITY (`funzioni_ai_filter.py` + `func_ai_comparator.functional_similarity`)

Due funzioni sono **analoghe se il loro significato è analogo**. Impaginazione, intestazioni e piè di pagina
del PDF, righe spezzate e tabelle riformattate non sono differenze. Le **grandi differenze funzionali o
d'impianto**, invece, abbassano la percentuale e vengono **marcate** in cella. Il calcolo è deterministico e
**non richiede chiamate LLM**.

1. **Pulizia**: vengono rimossi `[Pagina N]`, codici documento, intestazioni e piè di pagina ripetuti
   (`Document state`, `Revision`, copyright, intestazioni VSI «Progetto / Titolo / Codice documento / Pagina
   N di M»).
2. **Similarità di significato** (0-100), media pesata (`FUNC_SIM_WEIGHTS`, default 0.45 / 0.25 / 0.30) di:
   - **sequenza** delle parole di contenuto (stesso discorso nello stesso ordine; stopword e suffissi
     rimossi);
   - **lessico** di contenuto (stessi concetti, anche se riordinati; coseno sulle frequenze);
   - **requisiti in comune** (Jaccard sugli ID `2F_…`; ignorato se nessuna delle due sezioni ha requisiti).
3. **Penalità per differenze funzionali/d'impianto** (massimo `FUNC_SIM_PENALTY_MAX` = 30 punti):

   | Differenza | Penalità | Marcata come rilevante |
   |---|---|---|
   | valore/soglia con unità diverso (`18.5 kV` → `30 kV`, `2 s` → `500 ms`) | 3 punti ciascuno (max 6) | sempre |
   | requisito presente in una sola configurazione | 1 punto ciascuno (max 10) | da `FUNC_SIM_MAJOR_MIN_REQS` (2) |
   | contenuto molto diverso (rapporto di lunghezza < 0.7 / < 0.5) | 5 / 10 punti | sempre |
   | sigla d'impianto (centralina, apparecchiatura) presente in una sola configurazione | 0.5 punti ciascuna (max 10) | da `FUNC_SIM_MAJOR_MIN_COMPONENTS` (3) |

   I rimandi agli hazard (`HRnn`), i nomi delle carrozze (`DM1`, `M3`), i connettivi (`AND`/`OR`) e i nomi delle
   configurazioni non contano come sigle d'impianto. Con almeno una **differenza rilevante** la percentuale
   resta sotto `FUNC_SIMILARITY_GREEN`: la funzione non risulta mai verde grassetto.
4. Scrittura cella `Funzioni AI` (colori del foglio, `FONT_*` in `funzioni_ai_filter.py`):
   - `VZI_Base` → riassunto LLM della funzione, in nero.
   - Altre config → `RIFERIMENTO VZI_BASE, % SIMILARITY = X, X>90%` oppure `... X<90%`:

     | X | Colore |
     |---|---|
     | ≥ `FUNC_SIMILARITY_GREEN` (90) | **verde grassetto** (funzione analoga) |
     | ≥ `FUNC_SIMILARITY_HIGH` (80) | verde |
     | ≥ `FUNC_SIMILARITY_MEDIUM` (50) | arancione |
     | ≥ `FUNC_SIMILARITY_DIFF` (25) | rosso |
     | < 25 | **rosso grassetto** |

     Se ci sono differenze rilevanti e `FUNC_APPEND_DIFF_DETAIL = True`, sotto la sigla compare
     `DIFFERENZE RILEVANTI:` con l'elenco puntato, per esempio:

     ```
     RIFERIMENTO VZI_BASE, % SIMILARITY = 54.2%, X<90%
     DIFFERENZE RILEVANTI:
     • Valori/soglie diversi: VZI_Base 18.5 kV → VZ_FR 2.05 kV, 30 kV, 34 kV, 4.5 kV
     • Requisiti diversi: 2 solo in VZI_Base, 9 solo in VZ_FR
     ```
   - Base assente → `MISS VZI_BASE` + riassunto di ogni configurazione.
   - **Documento della configurazione mancante** → in **nero grassetto** `LINK DOCUMENTALE NON INSERITO`
     (nessun link nel foglio *Funzioni*) oppure `RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO` (link presente
     ma `#N/A`, URL non costruibile o PDF non trovato). La configurazione è **esclusa dal confronto**:
     nessuna similarità, nessun requisito confrontato (`FUNC_MARK_LINK_ISSUES`).

L'interfaccia web usa gli stessi colori: ✔ verde (≥ 80), ≈ arancione (50-80), ≠ rosso (< 50), ⚠ documento non
disponibile. Mostra inoltre le differenze rilevanti nella scheda della configurazione.

Tutte le soglie sono in `config.py`.

---

## Debug delle tabelle requisito

Script: **`debug/debug_requisiti.py`** (stessa logica di `requirements_extractor.py`, output su console e in
nel log unico `asktrainmind.log`). Dalla root del progetto:

```bash
# Scansione completa: elenca le pagine che contengono requisiti
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf"

# Analisi dettagliata delle pagine 7–8 (tabelle, campi, accettati/scartati)
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf" 7 8

# Come sopra + dump delle celle grezze di find_tables()
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf" 7 8 -raw
```

Requisito: `pip install pymupdf`.
