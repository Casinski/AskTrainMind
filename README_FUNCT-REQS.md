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
6. L'esito (`last_verdict`: n. requisiti, n. divergenti, config divergenti) viene passato alle Funzioni.

## 4. Funzioni → % SIMILARITY (`funzioni_ai_filter.py` + `func_ai_comparator.text_similarity`)

1. Normalizzazione del testo di sezione: rimossi `[Pagina N]`, codici documento, `Revision`, `Page`,
   `Document state`, punteggiatura; minuscole.
2. `% SIMILARITY = SequenceMatcher(base, altra).ratio() × 100` — deterministica, **nessuna chiamata LLM**.
3. Scrittura cella `Funzioni AI`:
   - `VZI_Base` → riassunto LLM della funzione, in nero.
   - Altre config → `RIFERIMENTO VZI_BASE, % SIMILARITY = X, X>90%` (verde grassetto se X ≥ 90)
     oppure `... X<90%` con colore: verde ≥ 80, arancione ≥ 50, rosso grassetto < 50.
   - Base assente → `MISS VZI_BASE` + riassunto di ogni configurazione.

Tutte le soglie sono in `config.py`.

---

## Debug delle tabelle requisito

Script: **`debug/debug_requisiti.py`** (stessa logica di `requirements_extractor.py`, output su console e in
`debug_requisiti.log` nella cartella di lancio). Dalla root del progetto:

```bash
# Scansione completa: elenca le pagine che contengono requisiti
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf"

# Analisi dettagliata delle pagine 7–8 (tabelle, campi, accettati/scartati)
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf" 7 8

# Come sopra + dump delle celle grezze di find_tables()
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf" 7 8 -raw
```

Requisito: `pip install pymupdf`.
