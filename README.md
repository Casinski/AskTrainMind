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
  5) REQUISITI NON MATCHED TRA CONFIGURAZIONI
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
- **5** elenca nel foglio **Reqs not matched** i requisiti del foglio
  Requisiti non MATCHED fra le configurazioni scelte (es. `VZI_Base`,
  `VZI_New14`, `VZ_FR`) con una nota che spiega la differenza (vedi
  [Opzione 5 — Requisiti non MATCHED](#opzione-5--requisiti-non-matched-tra-configurazioni-foglio-reqs-not-matched)).
  Viene eseguita automaticamente, su tutte le configurazioni, al termine
  dell'opzione 1.

Ogni opzione **cancella e ricrea** (o riscrive) i fogli che produce, così
contengono sempre l'ultimo aggiornamento (nessun testo vecchio accanto al
nuovo); prima di salvare, la versione precedente del file viene archiviata
in **`_OLD`** (vedi
[Archivio _OLD](#archivio-_old-versioni-precedenti-del-file-excel)).

All'avvio di ogni opzione viene chiesto se **aggiornare direttamente il
file DB Flotte** (default) oppure creare solo un **file RESULTS** (vedi
[File RESULTS](#file-results-db-flotte-non-modificato)).

### Flusso di lavoro consigliato

1. **Opzione 2** → foglio *Index Funzioni* con le funzioni dei documenti e
   i FUNC ID / DESCRIZIONE FUNZIONE proposti;
2. nel foglio **Funzioni** si inseriscono le funzioni (col A = FUNC ID,
   col B = DESCRIZIONE FUNZIONE) e i link dei documenti;
3. **Opzione 3** → le celle *Rif. Pagina* vengono compilate dall'indice
   dei PDF;
4. **Opzione 1** → generazione di *Funzioni AI* e *Requisiti*.

## Utente e developer

AskTrainMind distingue due ruoli.

### 👤 Utente (sola consultazione, non installa nulla)

All'utente si consegna la cartella **`User/`** (autonoma: pagina, Excel, PDF in `User/docs/`
e guida). Il primo utilizzo è spiegato passo per passo in **[`NEWUSER.md`](NEWUSER.md)**
(copiata anche in `User/`). Nella cartella **`User/`** trova:

- **`AskTrainMind.html`**: doppio clic e si apre nel browser una pagina **completa e
  offline**, popolata all'ultimo aggiornamento del developer, senza Python, server o
  Internet. Lo stesso fa **`AVVIA_WEB.bat`**. La pagina ha tre pulsanti:
  - **🧭 Esplora**: configurazioni → FRS/DOC ID → funzioni → *Dettaglio funzioni* con
    🧠 Funzioni AI, **📄 PDF affiancati** delle configurazioni scelte (già alla pagina
    della funzione) e **📋 Requisiti**: Description sempre visibile, esito **✔ MATCHED /
    ✖ NOT MATCHED** fra le configurazioni scelte (*solo in una*, *manca in alcune*, *testo
    diverso*, con lettere A/B/C per le varianti di testo e riferimento sostitutivo ☆ se manca
    VZI_Base); clic sul requisito = testi affiancati per variante, la tabella resta sul
    requisito aperto;
  - **💬 Chiedi**: domande in italiano. Le risposte uniscono **📄 il testo dei documenti**
    (requisito o paragrafo citato con documento e pagina, es. CONCEPT.46 per la pressione di
    avvio dei compressori), il DB Flotte e la conoscenza tecnica appresa dall'AI (schede 🧠);
  - **❔ Guida**: [`GUIDA_WEB.md`](GUIDA_WEB.md).
- **`DB Flotte ETR1000 Ver_1.9 Gabriele.xlsx`**: copia del file Excel aggiornato (in sola lettura).
- `LEGGIMI.txt` e `NEWUSER.md`.

I PDF vengono aperti dalla cartella `User/docs/`, accanto alla pagina.

### 🛠️ Developer

Doppio clic su **`AVVIA_DEVELOPER.bat`** (oppure `python asktrainmind_dev.py`) apre il
**terminale developer**:

```
  ── ANALISI DEL DB FLOTTE (aggiornano il file Excel)
    1) Analisi completa FRS: sintesi AI delle funzioni + estrazione e confronto requisiti
    2) Ricostruisci l'indice delle funzioni dai PDF FRS
    3) Ricalcola il riferimento di pagina di ogni funzione nei PDF
    4) Confronto mirato dei requisiti per uno o più DOC ID
    5) Elenca i requisiti diversi fra configurazioni, con note AI
   18) Completa le Description mancanti nel foglio «Requisiti» (rilegge i PDF)
  ── INTELLIGENZA ARTIFICIALE (addestramento e conoscenza)
    6) Addestra l'AI: leggi i documenti tecnici (PDF/DOCX/TXT) e impara sigle e concetti
    7) Rispondi alle domande dell'AI (conferma, correggi o completa ciò che ha capito)
   15) Genera il foglio Excel «questionAI» con le domande dell'AI (da compilare con calma)
   16) Carica il foglio «questionAI» compilato: l'AI legge, cataloga e impara le tue risposte
    8) Insegna o correggi un concetto (sigla, loop, sensore, centralina, configurazione…)
    9) Consulta la conoscenza dell'AI (cerca, conferma le proposte, verifica i file)
   10) Prova la sezione «Chiedi» con la conoscenza aggiornata
   17) Verifica l'AI: la conoscenza appresa e la lettura dei documenti arrivano in «Chiedi»?
  ── CONFIGURAZIONE E PUBBLICAZIONE
   11) CONFIG: visualizza e modifica i parametri del programma (config.py)
   12) Verifica i prerequisiti (Python, pacchetti, Ollama, modello AI, Excel, documenti)
   13) Aggiorna la cartella User (pagina web offline + Excel per gli utenti)
   14) Apri l'anteprima web developer (server locale, con AI Ollama e ricerca nei PDF)
```

- `h N` descrive la voce N; `python asktrainmind_dev.py --run N` la esegue direttamente.
- Le voci 1-5 eseguono `funzioni_ai_filter.py --mode N --ask`, descritto sotto. Dopo la scelta vengono
  elencati e poi chiesti i parametri dell'opzione, come nel menu originale: aggiornamento del DB Flotte o solo
  file RESULTS e **ambito dell'analisi** — FRS, funzioni degli FRS scelti, configurazioni di treno — (tutte,
  vedi [Ambito dell'analisi](#ambito-dellanalisi-opzioni-1-5)); ripresa da interruzione, numero massimo di
  celle, sovrascrittura A/S/N, FUNC ID di partenza e Reqs not matched (opzione 1); ripresa da interruzione
  (opzione 3). I valori proposti con Invio sono quelli di CONFIG.
- **L'addestramento dell'AI** (voci 6-10, 15 e 16) è spiegato in **[`TRAINING_AI.md`](TRAINING_AI.md)**.
  Il modo più veloce per rispondere alle domande dell'AI è il **questionario Excel «questionAI»**:
  voce 15 per crearlo, compilazione libera della colonna gialla *LA TUA RISPOSTA*, voce 16 per caricarlo
  (`python asktrainmind_dev.py --questionai-export` / `--questionai-import "percorso.xlsx" [--from-id N]`).
  Se il caricamento si interrompe, quanto appreso resta salvato e il programma indica l'ID da cui ricaricare.
  La conoscenza è salvata in `knowledge/` (file JSON modificabili anche a mano) ed è usata
  in Chiedi, in Esplora e nei prompt delle analisi 1-5.
- **Voce 18** (`python req_desc_backfill.py [--dry-run]`): le celle del foglio *Requisiti* che riportano solo
  l'etichetta (`MISS VZI_BASE REQ…`, differenze) senza il testo ricevono la *Description* riletta dal PDF della
  configurazione; il file originale viene archiviato in `_OLD/`. Le nuove analisi (opzione 1) scrivono già sempre
  la Description nelle celle.
- **Voce 17** (`python verify_ai.py`): verifica che Chiedi mostri i concetti appresi (risposte del developer) e che
  le domande sul contenuto dei documenti citino il requisito atteso; rapporto in `RESULTS/verify_ai.txt`.
- **CONFIG** (voce 11): le modifiche vengono salvate in `config_overrides.json` e
  `config.py` non viene modificato.
- Dopo ogni voce che modifica dati o conoscenza la cartella `User/` viene rigenerata
  (`USER_AUTO_EXPORT`). Si può rigenerare anche a mano con la voce 13 o con `python export_user.py`.
- La voce 14 (`python asktrainmind_web.py --port 8765`) avvia il server web
  locale con le stesse pagine e in più la spiegazione AI con Ollama e la ricerca full-text nei PDF.

Dipendenze: `python -m pip install -r requirements.txt`.

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
| `reqs_not_matched.py` | Opzione 5 (e fine opzione 1): ricrea il foglio "Reqs not matched" |
| `requisiti_sorter.py` | Ordina i blocchi del foglio Requisiti come i FUNC ID del foglio Funzioni |
| `old_archive.py` | Copia la versione precedente del file Excel in `_OLD/<data>_Opzione_<N>/` con `RICHIESTA.txt` |
| `run_options.py` | Parametri dell'opzione 1, file RESULTS (DB non modificato), elenco celle aggiornate, commenti "Not updated" |
| `rif_pagina.py` | Calcolo del "Rif. Pagina" dall'indice dei PDF (opzione 3 e inizio opzione 1) |
| `app_logging.py` | Log unico `asktrainmind.log` condiviso da tutto il codice (anche storico e script di debug), troncato automaticamente |
| `interrupt_guard.py` | Salvataggio dei progressi su interruzione (Ctrl+C), salvataggi automatici e punti di ripresa |
| `config.py` | Parametri globali (percorsi, modello AI, soglie) — vedi [Opzioni di configurazione](#opzioni-di-configurazione-configpy); in fondo applica i valori forzati di `config_overrides.json` |
| `AVVIA_WEB.bat` | Utente: apre `User/AskTrainMind.html` (pagina offline) |
| `asktrainmind_dev.py`, `AVVIA_DEVELOPER.bat` | Terminale developer: opzioni 1-5, addestramento AI, CONFIG, pubblicazione |
| `export_user.py` | Genera la cartella `User/` (pagina HTML autonoma con dati, conoscenza e guida + copia dell'Excel) |
| `asktrainmind_web.py` | Server web locale per il developer (anteprima con AI Ollama) |
| `webapp/server.py` | Server locale (Flask/waitress) e API della pagina web |
| `webapp/workbook.py` | Lettura del file Excel per la pagina web, con cache compressa e ricarica automatica quando il file cambia |
| `webapp/documents.py` | Ricerca dei PDF locali, pagine della funzione, anteprime, figure/tabelle, indice full-text SQLite |
| `webapp/qa.py` | Sezione "Chiedi": interpretazione delle domande, risposte (anche per tutte le configurazioni), ricerca veloce nei documenti e spiegazione AI in streaming |
| `webapp/explorer.py` | Sezione "Esplora": riepilogo compatto configurazioni → FRS → funzioni e dettaglio della singola funzione |
| `docsearch.py` | Lettura dei documenti per Chiedi: indice del testo di requisiti e paragrafi dei PDF di ogni funzione (incluso nella pagina offline come `dx`) e ricerca BM25 con traduzione italiano → termini inglesi dei documenti; replicata in JavaScript in `offline.js` |
| `req_desc_backfill.py` | Voce 18: completa le Description mancanti nel foglio Requisiti rileggendo i PDF |
| `verify_ai.py` | Voce 17: verifica automatica della conoscenza e della lettura dei documenti in Chiedi |
| `NEWUSER.md` | Guida al primo utilizzo per l'utente (sola consultazione, nessuna installazione) |
| `knowledge.py` | Conoscenza dell'AI: addestramento sui documenti, schede dei concetti, domande al developer, aggiunta dei concetti confermati ai prompt di Ollama (vedi `TRAINING_AI.md`) |
| `knowledge/` | File della conoscenza: `glossario.json`, `domande.json`, `passaggi.json`, `fonti.json` |
| `webapp/tools.py` | Prerequisiti, CONFIG (descrizioni e valori forzati) e lancio delle opzioni, usati dal terminale developer |
| `webapp/static/` | Pagina web (HTML, CSS, JavaScript senza dipendenze esterne: `app.js` struttura/Chiedi/Guida, `explore.js` Esplora con PDF affiancati e requisiti, `offline.js` motore di risposta della pagina offline) |
| `TRAINING_AI.md` | Guida all'addestramento dell'AI per il developer |
| `GUIDA_WEB.md` | Guida unica dell'interfaccia web e delle funzioni (mostrata anche nella scheda Guida) |

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

## Fogli necessari e fogli creati automaticamente

| Foglio | Se manca |
|---|---|
| **Funzioni** | **Obbligatorio.** Tutte le opzioni si fermano con un errore che elenca i fogli presenti. |
| **Requisiti** | Viene creato dopo "Funzioni" con le colonne FUNC ID, DESCRIZIONE, FRS, REQUISITO, CONFIGURAZIONE APPARTENENZA e una colonna per configurazione (prima VZI_Base, poi le configurazioni lette da CONFIG e Funzioni). Lo compila l'opzione 1; per le opzioni 4 e 5 serve che sia già compilato. |
| **Reqs not matched** | Viene creato e compilato dall'opzione 5 e alla fine dell'opzione 1. Se "Requisiti" è vuoto, il foglio nasce con la sola intestazione. |
| **Index Funzioni** | Viene creato e compilato dall'opzione 2, dopo "Reqs not matched", "Requisiti" o "Funzioni". |

## Ambito dell'analisi (opzioni 1-5)

Ogni opzione di analisi chiede, dopo la scelta DB Flotte/RESULTS, su cosa
lavorare (modulo `analysis_scope.py`):

1. **FRS** — elenco numerato dei DOC ID (col B del foglio CONFIG / col D del
   foglio Funzioni), es. `FRS_Line Voltage`;
2. **funzioni degli FRS scelti** — FUNC ID del foglio Funzioni collegati a
   quegli FRS, con la descrizione, es. `LV_Pantograph_Lifting`,
   `LV_Pantograph_Selection`;
3. **configurazioni di treno** — es. `VZI_Base, VZI_New14, VZ_FR`.

Si rispondono numeri dell'elenco, intervalli (`5-8`), nomi o una parte
univoca del nome (`pantograph lifting`), separati da virgola. **Invio** =
valore proposto, `*` = tutti. Un nome non riconosciuto o ambiguo
(es. `line volt` → `FPD_Line Voltage` / `FRS_Line Voltage`) annulla
l'esecuzione da riga di comando e viene richiesto nel terminale.
Da riga di comando: `--frs`, `--funcs` (`-f`), `--configs` (`-c`).

| Opzione | Effetto dell'ambito |
|---|---|
| 1 | solo le celle "Funzioni AI" e i requisiti delle funzioni/FRS/configurazioni scelti; **VZI_Base** (`REQ_BASE_CONFIG`) è sempre elaborata come riferimento del confronto. Nel foglio Requisiti le colonne e le voci di col E delle configurazioni non scelte restano invariate |
| 2 | foglio Index Funzioni ricreato solo con i DOC ID, le configurazioni e i FUNC ID scelti (commento `Elenco PARZIALE` in A1) |
| 3 | solo le celle "Rif. Pagina" dell'ambito |
| 4 | DOC ID da confrontare = FRS scelti (almeno uno; default `CONFRONTO_REQS_DOC_IDS`), solo le configurazioni scelte; con funzioni scelte solo i requisiti che il foglio Requisiti attribuisce a quelle funzioni (eseguire prima l'opzione 1) |
| 5 | solo i requisiti degli FRS/funzioni scelti, fra le configurazioni scelte (almeno due; default `REQS_NOT_MATCHED_CONFIGS`) |

Nei fogli ricreati (opzioni 2, 4, 5) un ambito limitato è indicato dal
commento in A1. Nell'opzione 1 le celle fuori ambito ricevono il commento
`Not updated` (vedi sotto).

---

## Opzione 1 — cosa succede nel file Excel

Passi eseguiti da `python funzioni_ai_filter.py` → scelta **1**, visti dal
punto di vista del file Excel (`EXCEL_PATH` in `config.py`).

0. **Parametri dell'elaborazione** — dal menu interattivo vengono chiesti
   (Invio = valore proposto; da riga di comando vedi
   [Come eseguire](#come-eseguire)):

   | Domanda | Default | Opzione CLI |
   |---|---|---|
   | Aggiornare il file DB Flotte o creare solo il file RESULTS | aggiorna il DB | `--results-only` |
   | Numero massimo di celle "Funzioni AI" da compilare | tutte | `--max-cells N` |
   | Sovrascrivere le celle "Funzioni AI" già compilate: `A` automatico (solo se il documento è cambiato), `S` rielabora tutte, `N` solo celle vuote | `A` | `--overwrite A/S/N` |
   | FUNC ID da cui partire | inizio foglio | `--start FUNC_ID` |
   | FRS da compilare (DOC ID: col B del foglio CONFIG / col D del foglio Funzioni, es. `FRS_Line Voltage`) — vedi [Ambito](#ambito-dellanalisi-opzioni-1-5) | tutti | `--frs "FRS_Line Voltage, FRS_Air Supply"` |
   | Funzioni degli FRS scelti | tutte | `--funcs "LV_Pantograph_Lifting"` |
   | Configurazioni di treno (VZI_Base sempre inclusa come riferimento) | tutte | `--configs "VZ_FR, VZ_ES"` |
   | Aggiornare il foglio "Reqs not matched" al termine (se no il foglio non viene toccato) | sì | `--no-reqs-not-matched` |

   **Esecuzione parziale** (solo alcuni FRS, funzioni o configurazioni, numero di celle limitato,
   FUNC ID di partenza, solo celle vuote, interruzione): le celle elaborate
   seguono la logica normale; le celle "Funzioni AI" con testo **non**
   elaborate e la cella FUNC ID delle funzioni non elaborate nel foglio
   Requisiti ricevono il commento **`Not updated`** (con data e motivo).
   I commenti dell'utente non vengono sovrascritti; il commento viene tolto
   quando la cella viene rielaborata e da un'esecuzione completa. Con il
   filtro FRS anche il "Rif. Pagina" dinamico è calcolato solo per gli FRS
   scelti, e i requisiti degli altri FRS della stessa funzione non vengono
   eliminati.
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
     uguale → gruppo saltato; diversa → blocco "STORICO" nel log unico e
     rianalisi.
7. **Ricerca della sezione nel PDF** — partendo da "Rif. Pagina" si cerca il
   paragrafo della funzione nell'indice e se ne estrae il testo fino al
   paragrafo successivo (stesso livello o superiore: `3.3.4` termina a
   `3.3.5` o `3.4`; nei documenti senza numerazione al titolo successivo
   dell'indice, vedi [Strategia T](#strategia-t--paragrafi-senza-indice-numerico)).
   **Se il Rif. Pagina manca o non è valido** (anche dopo il calcolo
   dinamico) la configurazione viene saltata: funzione e requisiti non
   vengono analizzati né scritti.
8. **Estrazione dei requisiti** dalle tabelle e dal testo della sezione
   (gli ID citati dentro una Description non diventano nuovi requisiti).
   Nomi requisito equivalenti:
   - spazio dopo il punto: `2F_06.03.Zefiro Europe.CONCEPT. 165` =
     `2F_06.03.Zefiro Europe.CONCEPT.165`;
   - `Zefiro Europe`, `ZefiroEurope`, `Zefiro-Europe` (scritti sempre
     come `Zefiro-Europe`): `A.Zefiro Europe.B` = `A.Zefiro-Europe.B`;
   - ID spezzato su due righe della tabella (es. `2F _06 .03 .Zefiro-` /
     `EuropeCONCEPT393`): le due celle vengono ricomposte in un unico ID.
   Se due sezioni iniziano sulla stessa pagina, la prima termina al titolo
   della seconda (i requisiti della sezione successiva non vengono
   attribuiti alla funzione precedente).
9. **Foglio Requisiti**
   - cerca la riga della funzione (col A = FUNC ID, oppure col B =
     descrizione); se manca la crea;
   - col C = **FRS** (DOC ID del foglio Funzioni): sulla riga funzione
     tutti gli FRS della funzione, sulle righe requisito l'FRS da cui è
     stato estratto. Se manca, la colonna viene inserita automaticamente
     alla prima esecuzione dell'opzione 1 o 5;
   - sotto di essa, una riga per requisito: col D = numero requisito,
     col E = configurazioni in cui compare (colorate). I requisiti già
     presenti vengono aggiornati, i nuovi inseriti in coda al blocco;
   - colonne configurazione (da col F):
     - VZI_Base → testo completo del requisito, nero;
     - altre → `MATCHED` verde se identico alla base, altrimenti differenze
       in rosso;
     - VZI_Base assente → `MISS VZI_BASE REQ, MATCHED` (verde) o
       `MISS VZI_BASE REQ, FOUND DIFF` (rosso).
   - a fine esecuzione (anche se interrotta) il foglio viene **aggiornato
     e riordinato**:
     - i requisiti non più presenti nei documenti vengono eliminati
       (`REQ_REMOVE_STALE_ROWS`; solo per le funzioni analizzate per intero
       e le righe le cui configurazioni sono state tutte rianalizzate);
     - i blocchi funzione vengono disposti nell'ordine dei FUNC ID del
       foglio **Funzioni** (prima tutte le LV, poi AUX, BAT, …;
       `REQ_SORT_LIKE_FUNZIONI`). Una funzione assente dal foglio Funzioni
       va dopo l'ultima funzione con lo stesso prefisso;
     - il foglio **Reqs not matched** viene ricreato su tutte le
       configurazioni (`REQS_NOT_MATCHED_AFTER_OPTION1`, vedi opzione 5),
       salvo che l'utente abbia risposto di no alla domanda iniziale.
10. **Cella "Funzioni AI"** del foglio Funzioni:
    - VZI_Base → riassunto della funzione generato da Ollama, nero;
    - altre configurazioni → `RIFERIMENTO VZI_BASE, % SIMILARITY = X`,
      colorata in base alla percentuale (verde ≥ 90, verde ≥ 80,
      arancio ≥ 50, rosso sotto);
    - VZI_Base assente → `MISS VZI_BASE` + riassunto, nero;
    - in coda viene aggiunta la nota con la pagina usata.
11. **Salvataggio** — cache, storico e file Excel. Se il file è aperto in
    Excel si riprova ogni 5 s per 60 s, poi si salva
    `<nome>_backup.xlsx`. Log: `asktrainmind.log` (vedi [Log](#log-unico)).

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

**Lettura dell'indice resiliente al formato.** L'indice del PDF viene letto
con più metodi e si tiene il più completo:
- indice nativo (segnalibri) o testo "Contents" con indici numerici;
- indici su una riga e titolo/pagina sulla successiva (documenti Hitachi,
  es. FA020026053, FA020025419, FA020026562/3, FA020025252);
- indice senza numeri di paragrafo, con font/rientri diversi (documenti
  VSI, es. FA020022675): i livelli vengono ricavati dal rientro dei titoli
  e il paragrafo è riconosciuto nel corpo dal **titolo**;
- numerazione piatta (1, 2, 3…) ricostruita come gerarchia.

La funzione viene cercata anche tra i **sottoindici** (es. `3.3.4 Level 1
Alarm` per `BOG_Level_1_Alarm`): titolo del paragrafo e titolo del padre
concorrono al punteggio e i numeri nel FUNC ID devono coincidere (Level 1
≠ Level 2).

**Riepilogo finale.** Al termine viene stampato (console e log) un
riepilogo a tabella con:
- ❌ **riferimenti non trovati** — FUNC ID, configurazione, DOC ID, pagina
  utente e motivo; la cella resta invariata e, senza Rif. Pagina,
  l'opzione 1 non analizza quella funzione;
- ⚠ **riferimenti divergenti** — pagina utente, pagina dinamica e
  paragrafo trovato, da verificare;
- il numero dei documenti non applicabili (senza indice funzionale).

---

## Opzione 4 — Confronto specifico Funzioni-Requisiti (foglio "Confronto Reqs")

`python funzioni_ai_filter.py` → scelta **4** (oppure `--mode 4`, o
direttamente `--doc "FRS_Coupler"`). Non usa Ollama.

Serve a verificare se i requisiti di un documento sono presenti, con la
**stessa Description**, nei documenti di tutte le configurazioni.

1. **Scelta del DOC ID** — è l'FRS dell'[ambito](#ambito-dellanalisi-opzioni-1-5)
   (elenco numerato dei DOC ID; numeri, nomi o parte univoca, es. `FRS_Coup`),
   insieme alle funzioni e alle configurazioni da confrontare.
   Con `--doc`/`--frs` la scelta si passa da riga di comando; con `--mode 4`
   fuori da un terminale si usa `CONFRONTO_REQS_DOC_IDS` di `config.py`.
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

## Opzione 5 — Requisiti non MATCHED tra configurazioni (foglio "Reqs not matched")

`python funzioni_ai_filter.py` → scelta **5** (oppure `--mode 5`, o
direttamente `--configs "VZI_Base, VZI_New14, VZ_FR"`). Viene eseguita anche
in automatico al termine dell'opzione 1 con **tutte** le configurazioni.

1. **Scelta delle configurazioni** (con FRS e funzioni: vedi
   [Ambito](#ambito-dellanalisi-opzioni-1-5)) — viene mostrato l'elenco numerato delle
   configurazioni. Si
   indicano, separati da virgola, nomi (maiuscole indifferenti) o numeri;
   **Invio = tutte** (o `REQS_NOT_MATCHED_CONFIGS` di `config.py`). Servono
   almeno due configurazioni.
2. **Analisi del foglio Requisiti** — un requisito è *non MATCHED* fra le
   configurazioni scelte se:
   - manca in almeno una configurazione (cella vuota e configurazione non
     elencata in col E);
   - oppure è presente ma con testo diverso: celle con differenze in rosso,
     `MISS VZI_BASE REQ, FOUND DIFF`, `MISS VZI_BASE REQ`. Due configurazioni
     entrambe `MATCHED` (o entrambe `MISS VZI_BASE REQ, MATCHED`) sono uguali
     fra loro.
3. **Foglio "Reqs not matched"** — cancellato e ricreato a ogni chiamata,
   subito dopo **Requisiti**; righe nell'ordine del foglio Funzioni:

| Colonna | Contenuto |
|---|---|
| `FUNC ID` / `DESCRIZIONE FUNZIONE` | Funzione del requisito |
| `FRS` | DOC ID da cui è estratto il requisito (colonna FRS del foglio Requisiti) |
| `REQUISITO` | Nr/ID del requisito |
| una per configurazione scelta | `X` dove il requisito è presente |
| `Descrizione` | Testo (Description) del requisito |
| `Note AI` | Differenze rilevate (es. `Requisito non trovato per la configurazione VZ_FR.`, `VZ_FR: requisito diverso da VZI_Base — …`) seguite da una breve spiegazione in italiano, generata da Ollama, del requisito e della differenza funzionale, tecnica od operativa |

   Quando a una funzione mancano **tutti** i requisiti di una configurazione
   la nota invita a verificare documento e Rif. Pagina. Le note AI sono in
   cache (`REQS_NOT_MATCHED_AI_CACHE_FILE`) e i prompt identici vengono
   elaborati una sola volta. Il foglio contiene **sempre tutti** i requisiti
   non MATCHED: con `REQS_NOT_MATCHED_AI_MAX_CALLS = 0` (default) non c'è
   limite alle note AI; se si imposta un limite, le righe oltre il limite
   vengono comunque scritte con la nota «[Nota AI non generata: limite …]»
   (warning nel log) e le esecuzioni successive le completano.
   Senza Ollama la nota riporta solo le differenze.
   La Description dei requisiti `MATCHED` viene letta dall'archivio
   `REQ_DESC_CACHE_FILE` alimentato dall'opzione 1 oppure dalla stessa ID
   presente in un'altra riga del foglio Requisiti. Se un requisito manca in
   una configurazione per la funzione ma, in quella configurazione, compare
   sotto un'altra funzione, la nota lo indica (probabile sconfinamento di
   sezione: verificare il Rif. Pagina).
   - **Link documentale mancante**: se per una configurazione il foglio
     Funzioni non ha il link al documento dell'FRS, la nota riporta
     «Mancanza link documentale per l'FRS <FRS> nella configurazione <cfg>
     (inserire il link nel foglio Funzioni).» e la cella della
     configurazione è colorata in arancio chiaro con un commento.
   - **Requisiti simili**: al termine, i requisiti con ID diverso ma
     Description simile (≥ `REQS_NOT_MATCHED_SIMILAR_MIN`, stesso confronto
     di somiglianza del programma) vengono messi in righe contigue, con
     l'ID evidenziato in giallo chiaro e la nota «Requisito simile a <ID>
     (somiglianza …; presente in …)».
4. **Salvataggio** del file Excel (stessa logica dell'opzione 1).

---

## Archivio _OLD (versioni precedenti del file Excel)

Ogni opzione, **prima** di salvare per la prima volta il file Excel, ne
copia la versione precedente in

```
<cartella del file Excel>/_OLD/<AAAA-MM-GG_hh-mm-ss>_Opzione_<N>/
    DB Flotte ETR1000 Ver_1.8.xlsx   file su cui è stata richiesta l'opzione
    RICHIESTA.txt                    dettaglio della richiesta (vedi sotto)
```

`RICHIESTA.txt` contiene:
- **opzione richiesta** e data;
- **parametri scelti dall'utente** (aggiornamento DB o RESULTS, numero di
  celle, sovrascrittura, FUNC ID di partenza, FRS, "Reqs not matched", DOC
  ID, configurazioni);
- **ambito dell'elaborazione** (celle candidate, funzioni, FRS,
  configurazioni confrontate) e fogli ricreati/aggiornati;
- **aggiornamento del file**: DB aggiornato direttamente oppure percorso del
  file RESULTS da cui copiare le celle;
- **celle aggiornate**, per foglio e per funzione/FRS (es.
  `LV_Pantograph_Lifting / FRS_Line Voltage: F23, H23`, blocchi del foglio
  Requisiti come `A13:L79`, Rif. Pagina modificati, fogli ricreati per
  intero) e numero di celle marcate `Not updated`;
- **esito** (completata / interrotta).

Una sola copia per esecuzione (gli autosalvataggi non creano altre
cartelle); se l'opzione non modifica il file non viene archiviato nulla.
Il file aggiornato resta in `EXCEL_PATH`. Parametri: `OLD_ARCHIVE_ENABLED`,
`OLD_ARCHIVE_DIR`, `OLD_ARCHIVE_MAX_CELL_LINES`.

---

## File RESULTS (DB Flotte non modificato)

Se all'avvio si risponde **n** alla domanda "Aggiornare direttamente il file
DB Flotte?" (o si usa `--results-only`), il DB Flotte **non viene
modificato** e i fogli impattati dall'opzione vengono scritti in

```
<cartella del file Excel>/RESULTS/RESULTS_<AAAA-MM-GG_hh-mm-ss>_Opzione_<N>.xlsx
```

- lo storico incrementale non viene aggiornato, cosi' una successiva
  esecuzione che aggiorna il DB rielabora comunque le celle;
- solo i fogli impattati (es. opzione 1: Funzioni, Requisiti, Reqs not
  matched), con lo **stesso layout** del DB Flotte (stesse righe, colonne,
  formati e commenti `Not updated`): le celle si copiano direttamente;
- le formule sono sostituite dal loro valore (i fogli di origine non sono
  inclusi);
- il foglio **RESULTS info** riporta parametri e celle aggiornate.

La richiesta viene comunque tracciata in `_OLD` (copia del DB di partenza +
`RICHIESTA.txt` con il percorso del file RESULTS). Parametri:
`UPDATE_DB_DEFAULT`, `RESULTS_DIR`.

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
| 5 — Requisiti non MATCHED | Foglio "Reqs not matched" completo; le note AI non ancora generate riportano solo le differenze | Rilanciare l'opzione (le note già generate sono in cache) |

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

### Schema attuale (sigla di similarità)

| Configurazione | Contenuto della cella | Colore |
|---|---|---|
| `VZI_Base` | riassunto della funzione | nero |
| altre configurazioni | `RIFERIMENTO VZI_BASE, % SIMILARITY = X, X>90%` (oppure `X<90%`) + eventuale elenco `DIFFERENZE RILEVANTI:` | verde grassetto ≥ 90 · verde ≥ 80 · arancione ≥ 50 · rosso ≥ 25 · rosso grassetto < 25 |
| base assente | `MISS VZI_BASE` + riassunto | nero |
| nessun link al documento | `LINK DOCUMENTALE NON INSERITO` (esclusa dal confronto) | nero grassetto |
| link presente ma documento non trovato | `RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO` (esclusa dal confronto) | nero grassetto |

La percentuale è una **similarità funzionale**: misura se le due funzioni hanno lo stesso significato,
senza contare l'impaginazione. Le grandi differenze funzionali o d'impianto (valori e soglie diversi,
requisiti presenti in una sola configurazione, contenuto molto diverso, centraline e apparecchiature
diverse) abbassano la percentuale e vengono elencate in cella. Il calcolo è descritto in
[`README_FUNCT-REQS.md`](README_FUNCT-REQS.md) (§ 4).

### Schema precedente (percorso LLM di riserva)

Il percorso LLM, non più usato di default, compila la cella in **tre sezioni**:

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

> La tabella si riferisce al percorso LLM di riserva. Per la sigla di similarità attuale valgono i colori
> dello [schema attuale](#schema-attuale-sigla-di-similarità).

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

Le sotto-funzioni sono gestite: se nel foglio Funzioni è indicata
`3.3.4 Level 1 Alarm`, il testo include `3.3.4.x` e si ferma a `3.3.5`
(sottoindice successivo) o a `3.4` (livello superiore).

### Strategia T — Paragrafi senza indice numerico
Alcuni documenti (es. FA020022675) non numerano i paragrafi: la funzione è
identificata solo dal titolo (es. "Car ID and Vehicle Type", pag. 13–14).
In questo caso il paragrafo viene localizzato nell'indice del PDF tramite
`rif_pagina.locate_section`, il testo parte dal titolo e si ferma al titolo
successivo dello stesso livello o superiore ("MCM Enabling"). I titoli
standard interni a ogni funzione ("Function Design", "Requirements",
"Failure cases"…) non chiudono la sezione. Gli stessi confini delimitano
la ricerca dei requisiti nelle tabelle.

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

### Caso 5 — Link mancante o documento non trovato ⚫ (nero grassetto)
```
LINK DOCUMENTALE NON INSERITO
```
oppure
```
RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO
```
Il primo testo compare quando nel foglio *Funzioni* manca il link al documento della configurazione. Il secondo
compare quando il link c'è ma è `#N/A`, l'URL non si può costruire o il PDF non si trova. La configurazione
viene **esclusa dal confronto** con le altre (nessuna similarità e nessun requisito confrontato). Con
`FUNC_MARK_LINK_ISSUES = False` si torna al comportamento precedente: configurazione saltata, cella intatta,
oppure `[Testo non estratto: pag.13 di FA020022045]` in grigio.

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

### Log unico

| Opzione | Valore | Significato |
|---|---|---|
| `LOG_FILE` | `asktrainmind.log` | Unico file di log, accanto allo script: opzioni 1-4, storico differenze, report degli script in `debug/` |
| `LOG_MAX_LINES` | `20000` | Superato questo numero di righe il file viene troncato… |
| `LOG_KEEP_LINES` | `10000` | …conservando solo le ultime righe indicate |

### Rif. Pagina

| Opzione | Valore | Significato |
|---|---|---|
| `RIF_PAGINA_DYNAMIC` | `True` | Opzione 1: ricalcola il Rif. Pagina dall'indice dei PDF prima dell'analisi (`False` = usa i valori manuali). L'opzione 3 lo esegue sempre |

### Cella "Funzioni AI" (confronto funzioni)

| Opzione | Valore | Significato |
|---|---|---|
| `FUNC_SIMILARITY_GREEN` / `_HIGH` / `_MEDIUM` / `_DIFF` | `90` / `80` / `50` / `25` | Soglie % di similarità con VZI_Base: verde grassetto / verde / arancione / rosso; sotto = rosso grassetto |
| `FUNC_SIM_WEIGHTS` | `(0.45, 0.25, 0.30)` | Pesi della similarità funzionale: sequenza delle parole di contenuto, lessico, requisiti in comune |
| `FUNC_SIM_PENALTY_VALUE` / `_REQ` / `_COMPONENT` / `_MAX` | `3` / `1` / `0.5` / `30` | Penalità per valore diverso, requisito in una sola config, sigla d'impianto diversa; tetto totale |
| `FUNC_SIM_MAJOR_MIN_REQS` / `FUNC_SIM_MAJOR_MIN_COMPONENTS` | `2` / `3` | Da quanti requisiti / sigle diversi la differenza è «rilevante» (elencata in cella, mai verde grassetto) |
| `FUNC_APPEND_DIFF_DETAIL` / `FUNC_TXT_MAJOR_DIFF` | `True` / `"DIFFERENZE RILEVANTI:"` | Elenco delle differenze rilevanti sotto la sigla |
| `FUNC_MARK_LINK_ISSUES` / `FUNC_TXT_LINK_MISSING` / `FUNC_TXT_DOC_NOT_FOUND` | `True` / `"LINK DOCUMENTALE NON INSERITO"` / `"RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO"` | Messaggio in nero grassetto per le configurazioni senza documento (escluse dal confronto) |
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
| `REQ_FUNC_ID_COL` / `REQ_DESC_COL` / `REQ_FRS_COL` / `REQ_NUMBER_COL` / `REQ_CONFIG_COL` | `1` / `2` / `3` / `4` / `5` | Colonne A–E (FUNC ID, descrizione, FRS, Nr requisito, configurazione) |
| `REQ_CONFIG_COLS_START` | `6` | Prima colonna delle configurazioni (F) |
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
| `REQ_SORT_LIKE_FUNZIONI` | `True` | A fine opzione 1 ordina i blocchi come i FUNC ID del foglio Funzioni |
| `REQ_REMOVE_STALE_ROWS` | `True` | A fine opzione 1 elimina i requisiti non più presenti nei documenti rianalizzati |
| `REQ_DESC_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\req_desc_cache.json` | Archivio delle Description (usato dal foglio "Reqs not matched") |

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

### Requisiti non MATCHED (opzione 5, foglio "Reqs not matched")

| Opzione | Valore | Significato |
|---|---|---|
| `SHEET_REQS_NOT_MATCHED` | `"Reqs not matched"` | Nome del foglio generato |
| `REQS_NOT_MATCHED_CONFIGS` | `[]` | Configurazioni proposte di default (vuoto = tutte) |
| `REQS_NOT_MATCHED_AFTER_OPTION1` | `True` | Ricrea il foglio, con tutte le configurazioni, a fine opzione 1 |
| `REQS_NOT_MATCHED_AI_NOTES` | `True` | Spiegazione generata da Ollama nella colonna "Note AI" |
| `REQS_NOT_MATCHED_AI_MAX_CHARS` / `REQS_NOT_MATCHED_NOTE_MAX_CHARS` | `350` / `900` | Lunghezza della spiegazione AI / della cella |
| `REQS_NOT_MATCHED_AI_MAX_CALLS` | `0` | Note AI nuove per esecuzione (0 = nessun limite); le righe oltre il limite restano nel foglio con nota "non generata" |
| `REQS_NOT_MATCHED_AI_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\reqs_not_matched_ai_cache.json` | Cache delle note AI |
| `REQS_NOT_MATCHED_SIMILAR_MIN` | `0.80` | Requisiti con ID diverso e Description simile (≥ soglia) affiancati e annotati «Requisito simile a …» (1.0 = solo testo identico, 0 = disattivato) |

Se una configurazione non ha il link al documento dell'FRS nel foglio Funzioni,
la nota indica «Mancanza link documentale per l'FRS … nella configurazione …»
e la cella è colorata in arancio chiaro, invece di segnalare il requisito come mancante.

### Archivio _OLD

| Opzione | Valore | Significato |
|---|---|---|
| `OLD_ARCHIVE_ENABLED` | `True` | Copia la versione precedente del file Excel prima di ogni modifica |
| `OLD_ARCHIVE_DIR` | `None` | Cartella dell'archivio (`None` = `_OLD` accanto al file Excel) |
| `OLD_ARCHIVE_MAX_CELL_LINES` | `400` | Righe massime dell'elenco celle aggiornate in `RICHIESTA.txt` |

### Aggiornamento del DB / file RESULTS

| Opzione | Valore | Significato |
|---|---|---|
| `UPDATE_DB_DEFAULT` | `True` | Risposta proposta alla domanda "Aggiornare il DB Flotte?" |
| `RESULTS_DIR` | `None` | Cartella dei file RESULTS (`None` = `RESULTS` accanto al file Excel) |
| `NOT_UPDATED_COMMENT` | `"Not updated"` | Commento delle celle escluse da un'esecuzione parziale |

### Interfaccia web

| Opzione | Valore | Significato |
|---|---|---|
| `WEB_HOST` / `WEB_PORT` | `"127.0.0.1"` / `8765` | Indirizzo e porta del server (solo questo PC) |
| `WEB_OPEN_BROWSER` | `True` | Apre il browser all'avvio |
| `WEB_CACHE_DIR` | `None` | Cache dei fogli, indice PDF, figure e risposte (`None` = `HISTORY_DIR/web_cache`) |
| `WEB_EXTRA_DOC_DIRS` | `[]` | Altre cartelle di PDF per le risposte e la ricerca nei documenti |
| `WEB_PDF_INDEX_MAX_PAGES` | `0` | Pagine massime indicizzate per PDF (0 = tutte) |
| `WEB_PDF_INDEX_AT_START` | `True` | Costruisce/aggiorna l'indice dei PDF in background all'avvio (ricerca immediata) |
| `WEB_QA_USE_AI` | `True` | Spiegazione con l'AI locale nella sezione Chiedi |
| `WEB_QA_MAX_SECTION_PAGES` | `12` | Pagine massime analizzate per funzione (figure, testo) |
| `CONFIG_OVERRIDES_FILE` | `config_overrides.json` | Valori forzati dalla sezione CONFIG della pagina web |

### Conoscenza (glossario appreso)

| Opzione | Valore | Significato |
|---|---|---|
| `KNOWLEDGE_FILE` | `HISTORY_DIR/knowledge.json` | Glossario dei termini insegnati all'AI |
| `KNOWLEDGE_USE_IN_ANALYSIS` | `True` | Aggiunge ai prompt di Ollama le definizioni dei termini presenti nel testo |
| `KNOWLEDGE_MAX_TERMS_IN_PROMPT` | `25` | Termini massimi aggiunti a un prompt |
| `KNOWLEDGE_MAX_QUESTIONS` | `40` | Domande massime per sessione di apprendimento |
| `KNOWLEDGE_MAX_PAGES` | `80` | Pagine massime lette per sessione |
| `KNOWLEDGE_MAX_ANSWERS_PER_TERM` | `30` | Spiegazioni dell'esperto (risposte libere del questionAI) conservate per concetto |
| `QUESTION_SHEET_DIR` / `QUESTION_SHEET_MAX` | `""` / `200` | Cartella di `questionAI.xlsx` (vuoto = cartella del programma) e domande per questionario (0 = tutte) |
| `QUESTION_SHEET_USE_AI` / `QUESTION_SHEET_SAVE_EVERY` / `QUESTION_SHEET_SAVE_SECONDS` | `True` / `10` / `20` | Struttura con Ollama le risposte discorsive lunghe; righe caricate fra due salvataggi e intervallo minimo in secondi fra due salvataggi |

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
# Interfaccia web (esplora, fogli, domande, conoscenza, strumenti): http://127.0.0.1:8765
python asktrainmind_web.py

# Menu interattivo (1 = Funzioni AI e Requisiti, 2 = Ricerca Funzioni,
#                  3 = Cerca riferimento pagina,
#                  4 = Confronto specifico Funzioni-Requisiti,
#                  5 = Requisiti non MATCHED tra configurazioni)
python funzioni_ai_filter.py

# Senza menu
python funzioni_ai_filter.py --mode 1    # Funzioni AI e Requisiti
python funzioni_ai_filter.py --mode 2    # Ricerca Funzioni -> foglio "Index Funzioni"
python funzioni_ai_filter.py --mode 3    # Cerca riferimento pagina -> celle "Rif. Pagina"
python funzioni_ai_filter.py --mode 3 --start "AIR_Air_Dryer"
python funzioni_ai_filter.py --mode 4    # Confronto Funzioni-Requisiti -> foglio "Confronto Reqs"
python funzioni_ai_filter.py --mode 5    # Requisiti non MATCHED -> foglio "Reqs not matched"

# Opzione 4: DOC ID indicati da riga di comando (foglio CONFIG, col B)
python funzioni_ai_filter.py --doc "FRS_Coupler"
python funzioni_ai_filter.py -m 4 -d "FRS_Coupler, FRS_Horn"

# Opzione 5: configurazioni indicate da riga di comando
python funzioni_ai_filter.py --configs "VZI_Base, VZI_New14, VZ_FR"
python funzioni_ai_filter.py -m 5 -c "VZI_New14, VZ_FR"

# Ambito (opzioni 1-5): FRS, funzioni degli FRS e configurazioni di treno
python funzioni_ai_filter.py -m 5 --frs "FRS_Line Voltage" -f "LV_Pantograph_Lifting, LV_Pantograph_Selection" -c "VZI_Base, VZ_FR"
python funzioni_ai_filter.py -m 4 --frs "FRS_Line Voltage" -f "pantograph lifting" -c "1-3"
python funzioni_ai_filter.py -m 3 --frs "FRS_Line Voltage" -c "VZ_FR"

# Opzione 1: riprendi da una funzione specifica
python funzioni_ai_filter.py --mode 1 --start "LV_Pantograph_Lifting"
python funzioni_ai_filter.py -m 1 -s "LV_Pantograph_Lifting"

# Opzione 1: solo alcuni FRS, al massimo 20 celle, rielaborando anche le
# celle gia' compilate, senza aggiornare "Reqs not matched"
python funzioni_ai_filter.py --frs "FRS_Line Voltage" --max-cells 20 --overwrite S --no-reqs-not-matched

# Qualsiasi opzione senza modificare il DB: solo file RESULTS
python funzioni_ai_filter.py --mode 5 --configs "VZI_Base, VZ_FR" --results-only
```

---

## Diagnostica problemi comuni

### Il codice usa Strategia B invece di A
**Causa**: `func_id` non passato o titolo del documento in lingua diversa.
**Soluzione**: Verifica che `target.func_id` sia valorizzato in `excel_scanner.py`
e che venga passato a `extract_page_text(func_id=...)`.

### Gli indici del PDF non vengono rilevati
**Causa più comune**: gli indici si trovano oltre riga 60 della pagina.
**Debug**: esegui `debug/debug_pdf_indexes.py <file.pdf> <pag_inizio> <pag_fine>`
(output anche nel log unico).
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

`asktrainmind.log` non deve contenere WARNING in condizioni normali (fa
eccezione `Rif. Pagina assente o non valido`, che segnala una funzione
saltata perché priva di riferimento pagina).
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