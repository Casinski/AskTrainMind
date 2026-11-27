"""
config.py
---------
Configurazione centralizzata. Modifica SOLO questo file.
"""
from pathlib import Path

# ── Percorso file Excel ────────────────────────────────────────────────────
EXCEL_PATH = Path(
    r"C:\__SCRIPTS\AskTrainMind\DB Flotte ETR1000 Ver_2.1_tbupdated.xlsx" 
)

# ── Cartella OneDrive locale ───────────────────────────────────────────────
ONEDRIVE_DOCS_ROOT = Path(
    r"C:\Users\2954534.UTENTI\OneDrive - Gruppo Ferrovie Dello Stato\Documenti - Ingegneria ETR - Trenitalia\DB_ETR1000\DOC_FLOTTE"
)

# ── Modello AI locale (Ollama) ─────────────────────────────────────────────
# ── Modello AI locale (Ollama) ─────────────────────────────────────────────
# Scelta del modello: il compito è ragionamento comparativo su testo
# tecnico in inglese con output JSON vincolato. Serve un modello che
# rispetti le istruzioni negative ("NON elencare ciò che è uguale").
#
#   qwen2.5:14b-instruct   consigliato — ottimo instruction-following e
#                          JSON affidabile; ~9 GB, richiede ~12 GB RAM/VRAM
#   qwen2.5:7b-instruct    buon compromesso; ~4,7 GB, gira su 8 GB
#   llama3.1:8b-instruct-q8_0  alternativa, più verboso sul JSON
#   llama3.2               3B: TROPPO PICCOLO per questo confronto,
#                          ignora le istruzioni negative
# PRIMA: OLLAMA_MODEL = "qwen2.5:14b-instruct"
OLLAMA_MODEL = "qwen2.5:7b-instruct"

# Mantiene il modello caricato in RAM/VRAM fra una chiamata e l'altra.
# Senza questo Ollama lo scarica dopo 5 minuti e lo ricarica da disco.
OLLAMA_KEEP_ALIVE = "30m"

# Quante chiamate LLM eseguire contemporaneamente (vedi Modifica E).
# Metti 1 per tornare al comportamento sequenziale.
# Su GPU: 3-4. Su CPU: 2.
LLM_PARALLEL_WORKERS = 3

# Finestra di contesto. Il default di Ollama è 2048 token: due Description
# lunghe più il prompt la saturano e il modello perde le REGOLE iniziali,
# rispondendo fuori formato. Va alzata esplicitamente.
OLLAMA_NUM_CTX = 8192

# Token massimi in uscita: la risposta è un JSON breve.
# E' solo il MINIMO: le chiamate che producono testo lungo (riassunto
# della funzione, paragrafo di differenze) calcolano da sole il budget
# necessario a partire dal numero di caratteri attesi. Con un valore
# fisso troppo basso il JSON veniva troncato a metà stringa e ogni
# riassunto degradava a semplice estratto testuale.
OLLAMA_NUM_PREDICT = 300

# Tetto massimo al budget calcolato automaticamente.
OLLAMA_NUM_PREDICT_MAX = 1536

# Secondi di attesa per una risposta. Un 14B su CPU può superare i 60 s.
OLLAMA_TIMEOUT = 300

# ── Nomi dei fogli ─────────────────────────────────────────────────────────
SHEET_FUNZIONI = "Funzioni"
SHEET_CARTELLE = "Cartelle"
SHEET_CONFIG   = "CONFIG"
SHEET_MAN_CPR  = "MAN_CPR"

# ── Label righe di terzo livello ───────────────────────────────────────────
FUNZIONI_AI_LABEL = "Funzioni AI"
RIF_PAGINA_LABEL  = "Rif. Pagina"

# ── Cella base URL SharePoint ─────────────────────────────────────────────
CARTELLE_BASE_URL_ROW = 5
CARTELLE_BASE_URL_COL = 4

# ── Esecuzione ────────────────────────────────────────────────────────────
MAX_CELLS_PER_RUN      = 99999
AI_CALL_DELAY_SECONDS  = 0.0
START_FROM_FUNC_ID: str = ""

# ── Similarità testuale (Strategia B in document_handler) ─────────────────
SIMILARITY_THRESHOLD = 0.26

# Numero massimo di pagine aggiuntive lette dopo la pagina iniziale di una
# sezione. Una funzione come 3.2.1 "Pantograph - Lifting" si estende da
# pag.8 a pag.13 (3.2.2 "Pantograph - Lowering" inizia a pag.14): il limite
# deve lasciare spazio alle sezioni piu' lunghe del documento.
MAX_SECTION_PAGES = 25

# ── Cache documenti ───────────────────────────────────────────────────────
CACHE_DIR = Path.home() / "AppData" / "Local" / "FunzioniAI" / "cache"

# ── Autenticazione Microsoft 365 ──────────────────────────────────────────
MS_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
MS_SCOPES = [
    "https://graph.microsoft.com/Files.Read",
    "https://graph.microsoft.com/Sites.Read.All",
]

# ── Soglie colore cella (ai_synthesizer) ──────────────────────────────────
# score >= LLM_SCORE_GREEN → VERDE
LLM_SCORE_GREEN = 80

# score <  LLM_SCORE_RED   → ROSSO
LLM_SCORE_RED   = 60

# Categorie funzionali valutate dal LLM (NO codici documento/requisiti)
CRITICAL_CHECKLIST_KEYS = [
    "functional_purpose",
    "operational_logic",
    "performance",
    "failure_handling",
    "diagnostics",
    "safety",
]

# ═══════════════════════════════════════════════════════════════════════════
# FOGLIO REQUISITI
# ═══════════════════════════════════════════════════════════════════════════
#
#   LIVELLO 1 — riga funzione (già presente nel foglio)
#       Col A: FUNC ID        es. "LV_Country_code_selection"
#       Col B: DESCRIZIONE    es. "Selezione su IDU del paese corrente..."
#
#   LIVELLO 2 — righe requisito (scritte dal codice, INSERITE sotto la funzione)
#       Col A: vuota          ← discriminatore di secondo livello
#       Col B: vuota
#       Col C: FRS (DOC ID)   es. "FRS_Line Voltage" (anche sulla riga funzione)
#       Col D: Nr requisito   es. "2F_05.01.Zefiro-Europe.TRS.184"
#       Col E: Configurazione di appartenenza, colorata
#
#   Un file con il vecchio layout (senza colonna FRS) viene migrato in
#   automatico alla prima apertura da parte del programma.
#
SHEET_REQUISITI = "Requisiti"

# Riga di intestazione del foglio Requisiti
REQ_HEADER_ROW = 1

# ── Colonne di LIVELLO 1 (ricerca funzione) ───────────────────────────────
REQ_FUNC_ID_COL = 1      # Col A
REQ_DESC_COL    = 2      # Col B

# ── Colonne di LIVELLO 2 (scrittura requisiti) ────────────────────────────
REQ_FRS_COL     = 3      # Col C — FRS (DOC ID: col B CONFIG / col D Funzioni)
REQ_FRS_HEADER  = "FRS"
REQ_NUMBER_COL  = 4      # Col D — Nr requisito
REQ_CONFIG_COL  = 5      # Col E — Configurazione di appartenenza

# ── Colonne per-configurazione (da F in poi) ──────────────────────────────
# Riga 1 del foglio "Requisiti": da col F in poi ci sono i nomi delle
# configurazioni. La mappa {config_name: colonna} viene costruita a runtime.
REQ_CONFIG_COLS_START = 6          # Col F
REQ_BASE_CONFIG       = "VZI_Base" # configurazione di riferimento

# Separatori usati nel dump dei campi tabella del requisito
REQ_FIELD_SEP   = "\n" + "—" * 20 + "\n"
# Campi della tabella ORIZZONTALE
REQ_FIELD_LABEL = {
    "description":    "Description",
    "req_type":       "Type / Applicability Details",
    "derived_to":     "Derived to",
    "user_interface": "User Interface",
    "sil":            "SIL",
}
# Campi della tabella VERTICALE (ID | Description | Safety level)
REQ_FIELD_LABEL_V = {
    "description": "Description",
    "sil":         "Safety level",
}

# Etichette e colori
REQ_TXT_MATCHED        = "MATCHED"
REQ_TXT_MISS_MATCHED   = "MISS VZI_BASE REQ, MATCHED"
REQ_TXT_MISS_DIFF      = "MISS VZI_BASE REQ, FOUND DIFF"
REQ_COLOR_GREEN        = "FF008000"
REQ_COLOR_RED          = "FFC00000"
REQ_COLOR_BLACK        = "FF000000"

# Etichetta per il requisito presente in UNA SOLA configurazione non-base:
# non c'è nulla da confrontare, quindi niente "FOUND DIFF".
REQ_TXT_MISS_ONLY = "MISS VZI_BASE REQ"

# Dump delle matrici riconosciute come verticali. Attivare SOLO per il
# debug di un singolo documento: produce molte righe di log.
REQ_DEBUG_DUMP_VERTICAL = False

# Quante differenze di dettaglio allegare al responso dell'IA
REQ_DIFF_DETAIL_MAX = 3
REQ_DIFF_SNIPPET_LEN = 160

# Stile del testo delle differenze scritto nella cella:
#   "narrativo" → paragrafo discorsivo leggibile (consigliato)
#   "puntuale"  → elenco puntato dei frammenti divergenti
REQ_DIFF_STYLE = "narrativo"

# Differenze fra le Description spiegate A LIVELLO DI CONCETTO (paragrafo in
# italiano che non cita le parole differenti), nel foglio Requisiti e nella
# pagina web. True = genera il testo con l'AI locale (cache in HISTORY_DIR);
# senza AI, o con False, si usa una spiegazione di riserva deterministica.
REQ_CONCEPT_DIFF_AI = True

# Lunghezza massima del paragrafo di differenze scritto nella cella
REQ_DIFF_MAX_CHARS = 700

# Soglia LLM sui requisiti: score >= → MATCHED
REQ_LLM_SCORE_MATCH = 80

# Campo che determina davvero l'identità del requisito. Gli altri campi
# della tabella (Type/ApplicabilityDetails, Derived to, User Interface, SIL)
# descrivono il contesto di applicazione e NON generano da soli un DIFF.
REQ_PRIMARY_FIELD = "description"

# Immutata nella sostanza: questi campi non generano MAI da soli un rosso.
# Confermata esplicitamente perche' 'Type' e 'ApplicabilityDetails' sono
# la stessa colonna con nome diverso a seconda della configurazione.
REQ_SECONDARY_FIELDS = ("req_type", "derived_to", "user_interface", "sil")

# Similarità minima della Description sotto la quale si interpella il LLM.
# Sopra questa soglia il requisito è considerato MATCHED senza chiamata.
REQ_DESC_SIMILARITY_MATCH = 0.94

# NUOVA: sotto questa soglia i testi sono palesemente diversi.
# Non serve il modello per saperlo: si scrive il confronto testuale
# prodotto da describe_desc_diff(). Elimina le chiamate "inutili"
# sui requisiti completamente riscritti.
REQ_DESC_SIMILARITY_DIFF = 0.55

# Frasi che il modello produce quando NON ha trovato differenze reali:
# se la risposta è composta solo da queste, va trattata come MATCHED.
REQ_NO_DIFF_MARKERS = [
    "identic", "identich", "nessuna differenza", "non sono differenze",
    "non vi sono differenze", "equivalent", "coincidono", "uguali",
    "stessa logica", "nessuna variazione", "no difference", "same",
    # Formule ricorrenti con cui il modello elenca cio' che e' UGUALE
    "stesso comportamento", "stessa prescrizione", "stesso valore",
    "stessa soglia", "medesim", "corrispond", "allineat", "conform",
    "nessun cambiamento", "non cambia", "non differisce", "invariat",
    "solo riformulazion", "differenza redazionale", "differenza formale",
    "no differences", "sono allineati", "entrambe", "entrambi",
]

# Se True, un ID presente in più configurazioni genera UNA riga per ogni
# configurazione. Se False, genera una riga sola con l'elenco colorato.
REQ_ONE_ROW_PER_CONFIG = False

# Se True antepone un progressivo al Nr requisito ("1) 2F_05.01...")
REQ_PROGRESSIVE_NUMBER = False

# Scrive Description / Type / SIL nelle colonne E, F, G... se valorizzate.
# Metti a False per lasciare pulite le colonne oltre la D.
REQ_WRITE_EXTRA_FIELDS = False
REQ_EXTRA_FIELDS_START_COL = 5     # Col E

# Se la funzione non esiste nel foglio Requisiti, creane la riga di livello 1
REQ_CREATE_MISSING_FUNCTION = True

# ═══════════════════════════════════════════════════════════════════════════
# CONFRONTO FUNZIONI — stessa logica del foglio Requisiti
# ═══════════════════════════════════════════════════════════════════════════
#
# La cella "Funzioni AI" di ogni configurazione viene compilata
# confrontando il testo della sezione con quello di VZI_Base:
#   base + altre, testi equivalenti  → "MATCHED" verde grassetto
#   base + altre, testi divergenti   → differenze in rosso
#   solo base                        → testo della sezione in nero
#   senza base, tutte identiche      → "MISS VZI_BASE FUNC, MATCHED" verde
#   senza base, divergenti           → "MISS VZI_BASE FUNC, FOUND DIFF" rosso
#   senza base, una sola config      → "MISS VZI_BASE FUNC" nero + testo
FUNC_TXT_MATCHED      = "MATCHED"
FUNC_TXT_MISS_MATCHED = "MISS VZI_BASE FUNC, MATCHED"
FUNC_TXT_MISS_DIFF    = "MISS VZI_BASE FUNC, FOUND DIFF"
FUNC_TXT_MISS_ONLY    = "MISS VZI_BASE FUNC"

# Soglia LLM sul confronto di funzione
FUNC_LLM_SCORE_MATCH = 80

# Similarita' minima del testo di sezione oltre la quale si dichiara
# MATCHED senza interpellare il modello.
FUNC_TEXT_SIMILARITY_MATCH = 0.95

# ════════════════════════════════════════════════════════════════
# NUOVO SCHEMA DELLA CELLA "Funzioni AI"
# ════════════════════════════════════════════════════════════════
#   VZI_Base              → RIASSUNTO della funzione, in NERO
#   altre configurazioni  → "RIFERIMENTO VZI_BASE, % SIMILARITY = X, X>90%"
#                            verde grassetto se X > FUNC_SIMILARITY_GREEN
#                            rosso con "X<90%" altrimenti
#   base assente          → "MISS VZI_BASE" + riassunto in NERO per ognuna
#
# Soglia percentuale di similarita' (0-100) che separa verde da rosso.
FUNC_SIMILARITY_GREEN = 90.0
FUNC_SIMILARITY_HIGH = 80.0
FUNC_SIMILARITY_MEDIUM = 50.0
FUNC_SIMILARITY_DIFF = 25.0
# Colori della sigla (vedi FONT_* in funzioni_ai_filter.py):
#   X ≥ GREEN          → verde grassetto  (funzione analoga)
#   HIGH ≤ X < GREEN   → verde            (analoga, piccole differenze)
#   MEDIUM ≤ X < HIGH  → arancione        (differenze moderate)
#   DIFF ≤ X < MEDIUM  → rosso            (differenze rilevanti)
#   X < DIFF           → rosso grassetto  (funzionamento diverso)

# ── Similarita' FUNZIONALE (func_ai_comparator.functional_similarity) ────
# Due funzioni sono analoghe se il loro SIGNIFICATO e' analogo: intestazioni
# di pagina, a capo e tabelle riformattate non contano. Pesi di:
#   (sequenza delle parole di contenuto, lessico di contenuto, requisiti
#    in comune). Senza requisiti nelle due sezioni l'ultimo peso e' ignorato.
FUNC_SIM_WEIGHTS = (0.45, 0.25, 0.30)
# Penalita' (punti percentuali) per le differenze funzionali/d'impianto:
FUNC_SIM_PENALTY_VALUE = 3.0       # per valore/soglia con unita' diverso (max 6)
FUNC_SIM_PENALTY_REQ = 1.0         # per requisito presente in una sola config (max 10)
FUNC_SIM_PENALTY_COMPONENT = 0.5   # per sigla d'impianto presente in una sola config (max 10)
FUNC_SIM_PENALTY_MAX = 30.0        # tetto complessivo della penalita'
# Soglie oltre le quali requisiti / sigle diversi sono "differenze rilevanti"
# (un valore numerico diverso o >30% di contenuto in piu'/in meno lo sono sempre).
FUNC_SIM_MAJOR_MIN_REQS = 2
FUNC_SIM_MAJOR_MIN_COMPONENTS = 3
# Con differenze rilevanti la percentuale resta sotto FUNC_SIMILARITY_GREEN
# (mai verde grassetto) e, se FUNC_APPEND_DIFF_DETAIL e' True, sotto la sigla
# compare questa intestazione seguita dall'elenco puntato delle differenze.
FUNC_TXT_MAJOR_DIFF = "DIFFERENZE RILEVANTI:"



# Etichette della nuova cella. {pct} viene sostituito dalla percentuale.
FUNC_TXT_REF_BASE_OK   = "RIFERIMENTO VZI_BASE, % SIMILARITY = {pct}, X>90%"
FUNC_TXT_REF_BASE_DIFF = "RIFERIMENTO VZI_BASE, % SIMILARITY = {pct}, X<90%"
FUNC_TXT_MISS_BASE     = "MISS VZI_BASE"

# ── Link documentale della configurazione ────────────────────────────────
# Cella "Funzioni AI" di una configurazione senza documento analizzabile,
# scritta in NERO GRASSETTO; la configurazione resta FUORI dal confronto
# con le altre (nessuna similarita', nessun requisito):
#   nessun link nella funzione per la configurazione → FUNC_TXT_LINK_MISSING
#   link presente ma #N/A, URL non costruibile o
#   documento non trovato/scaricabile                 → FUNC_TXT_DOC_NOT_FOUND
# False = comportamento precedente (configurazione saltata, cella intatta).
FUNC_MARK_LINK_ISSUES  = True
FUNC_TXT_LINK_MISSING  = "LINK DOCUMENTALE NON INSERITO"
FUNC_TXT_DOC_NOT_FOUND = "RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO"

# Decimali della percentuale scritta in cella (0 = numero intero)
FUNC_SIMILARITY_DECIMALS = 1

# Se True, sotto la sigla di similarita' viene aggiunto l'elenco delle
# DIFFERENZE RILEVANTI (valori, requisiti, contenuto, impianto).
# False = solo la sigla, cella piu' compatta.
FUNC_APPEND_DIFF_DETAIL = True

# ── Riassunto della funzione (solo VZI_Base, o tutte se base assente) ────
# Frasi del riassunto prodotto dal modello.
FUNC_SUMMARY_SENTENCES = 5
# Caratteri massimi del testo di sezione inviati al modello.
FUNC_SUMMARY_INPUT_CHARS = 6000
# Caratteri massimi del riassunto scritto in cella.
FUNC_SUMMARY_MAX_CHARS = 1200

# COERENZA REQUISITI → FUNZIONE
# Una funzione contiene il testo discorsivo E le tabelle dei requisiti:
# se TUTTI i requisiti della funzione sono MATCHED, la funzione non puo'
# avere differenze sostanziali. Con questo flag attivo l'esito dei
# requisiti, gia' calcolato, forza il MATCHED della funzione ed evita
# una chiamata LLM.
FUNC_USE_REQ_VERDICT = True

# Se i requisiti divergono, la funzione non puo' essere MATCHED:
# l'esito rosso viene imposto anche se il modello dicesse il contrario.
FUNC_REQ_DIFF_FORCES_DIFF = True

# Caratteri massimi del testo di differenze scritto nella cella
FUNC_DIFF_MAX_CHARS = 900

# ── Riconoscimento ID requisito ───────────────────────────────────────────
# Token "a punti" che contiene la stringa Zefiro (case-insensitive).
# Es: 2F_05.01.Zefiro-Europe.TRS.184
REQ_ID_MARKER       = "zefiro"
REQ_ID_MIN_SEGMENTS = 3     # segmenti minimi separati da punto
# Pattern generico di fallback (ID senza "Zefiro")
REQ_ID_FALLBACK_PATTERNS = [
    r"\b[A-Z0-9]{2,}[A-Z0-9_\-]*(?:\.[A-Za-z0-9_\-]+){2,}\b",
    r"\bREQ[-_][A-Za-z0-9_.\-]{3,}\b",
]
# Token da scartare (falsi positivi tipici dei PDF)
REQ_ID_BLACKLIST_SUBSTR = [
    "www.", ".pdf", ".doc", ".docx", ".xls", "http", "https",
    "e.g.", "i.e.", "etc.", "@", "ver.", "rev.", "fig.", "tab.",
]

# ═══════════════════════════════════════════════════════════════════════════
# ESTRAZIONE REQUISITI — parsing di matrice (PyMuPDF find_tables)
# ═══════════════════════════════════════════════════════════════════════════
#
# Il testo lineare di get_text() è inaffidabile: le colonne delle tabelle
# sono strette e gli ID vanno a capo più volte
#     "2F_04.01.Zefiro-\nEurope.CONCEPT.\n1013"
# producendo frammenti irrecuperabili. Con find_tables() ogni ID resta in
# UNA sola cella e la ricostruzione è deterministica.

# Usa il parsing di matrice come strategia primaria.
# False → torna al solo parsing testuale (solo per confronto diagnostico).
REQ_USE_MATRIX_PARSER = True

# Marcatore obbligatorio in un ID requisito reale. Gli ID di provenienza
# della colonna "Derived to" (4S_09.03.05.-.TCMSSoftware) ne sono privi.
REQ_ID_MARKER = "zefiro"

# Intestazioni minime sulla stessa riga perché sia una testata orizzontale.
# La colonna "Nr" è sempre obbligatoria, in aggiunta a questa soglia.
REQ_H_HEADER_MIN_MATCH = 2

# Filtri anti-prosa: senza spazi, una frase somiglia a un ID.
REQ_PROSE_PREFIXES = ("e.g.", "i.e.", "etc.", "ref.", "fig.", "cfr.", "n.a.",
                      "vedi", "see", "note", "nota", "tab.", "par.",
                      "sec.", "cap.", "doc.", "rev.", "p.es.")
REQ_MAX_ALPHA_RUN = 24     # blocco alfabetico oltre il quale è prosa

# Log di diagnostica: elenca ogni requisito estratto con layout e pagina
REQ_DEBUG_LOG_EACH = False


# ═══════════════════════════════════════════════════════════════════════════
# INTESTAZIONI DELLE TABELLE REQUISITI NEI PDF
# ═══════════════════════════════════════════════════════════════════════════
#
#  TABELLA ORIZZONTALE (una riga per requisito)
#     Nr | Description | Type | Derived to | User Interface | SIL
#     ▲                             ▲
#     └── è l'ID del requisito      └── NON è un requisito: è l'ID di
#                                       provenienza. Va registrato come
#                                       informazione, mai come requisito.
#
#  TABELLA VERTICALE (una tabella per requisito)
#     ID            | 2F_05.01.Zefiro-Europe.TRS.184
#     Description   | ...
#     Safety Level  | SIL2
#
# Varianti accettate per ogni intestazione (confronto case-insensitive).

# Intestazione della colonna ID nella tabella ORIZZONTALE
REQ_H_HEADER_ID = ["nr", "nr.", "n.", "n°", "num", "num.", "nr requisito",
                   "req nr", "req. nr", "number", "req number", "req id",
                   "requirement", "requirement id", "id"]
REQ_H_HEADER_DESCRIPTION = ["description", "descrizione", "descripcion",
                            "descripción", "req description", "text",
                            "requirement description"]
REQ_H_HEADER_DERIVED     = ["derived to", "derived from", "derived",
                            "derivedto", "derived-to", "traced to",
                            "parent", "source"]
REQ_H_HEADER_UI          = ["user interface", "user if", "ui", "userif",
                            "hmi", "interface"]
REQ_H_HEADER_SIL         = ["sil", "safety integrity level", "safety level",
                            "safety", "sil level"]

# Intestazione della colonna ID nella tabella VERTICALE
REQ_V_HEADER_ID          = ["id", "requirement id", "req id", "identifier",
                            "req. id", "requirement", "nr", "n°"]
REQ_V_HEADER_DESCRIPTION = ["description", "descrizione", "text",
                            "requirement description", "descripcion"]
REQ_V_HEADER_SAFETY      = ["safety level", "safety integrity level", "sil",
                            "safety", "sil level", "livello sil"]



# Righe massime di distanza entro cui cercare il valore di un campo
# verticale quando l'etichetta è su una riga e il valore su quella dopo.
REQ_V_LOOKAHEAD = 4

# Se True, un ID trovato FUORI da qualsiasi tabella riconosciuta viene
# comunque registrato come requisito. Sconsigliato: è la causa principale
# dei falsi positivi (ID citati nel testo discorsivo o in "Derived to").
REQ_ACCEPT_LOOSE_IDS = False

# ── Terminazione e robustezza delle tabelle orizzontali ───────────────────
# fitz intercala spesso righe vuote tra le righe di una tabella PDF.
# Interrompere alla terza riga vuota tronca la tabella dopo il primo
# requisito: la soglia va tenuta alta e, soprattutto, non si interrompe
# mai mentre un requisito è ancora aperto.
REQ_H_MAX_BLANK_LINES = 18

# La tabella si considera chiusa quando compare un nuovo titolo di sezione
# numerato (es. "3.2.2 Diagnostics") o una didascalia di tabella/figura.
REQ_TABLE_END_PATTERNS = [
    r"^\d+(?:\.\d+){1,5}\s+[A-Za-z]",     # nuovo indice di sezione
    r"^(table|tabella|figure|figura)\s+\d+",
    r"^(appendix|appendice|annex)\b",
]

# Se la testata (Nr | Description | ...) si ripete a ogni cambio pagina,
# la riga viene saltata senza chiudere la tabella in corso.
REQ_H_SKIP_REPEATED_HEADER = True

# ── Fallback ancorato a inizio riga ───────────────────────────────────────
# Dopo il parsing delle tabelle, ogni riga che INIZIA con un ID valido
# genera un requisito, se non già trovato e se non è un ID derivato.
# Recupera i requisiti delle tabelle che fitz destruttura al punto da
# rendere irriconoscibile la testata. È molto più sicuro di
# REQ_ACCEPT_LOOSE_IDS perché richiede l'ID in posizione di prima colonna.
REQ_ID_ANCHORED_FALLBACK = True

# Log di diagnostica: elenca ogni requisito estratto con layout e riga
REQ_DEBUG_LOG_EACH = False

REQ_H_HEADER_TYPE        = ["type", "tipo", "applicability details",
                            "applicability detail", "applicability"]

# ═══════════════════════════════════════════════════════════════════════════
# STORICO / RE-CHECK INCREMENTALE
# ═══════════════════════════════════════════════════════════════════════════

# Stato persistente (impronte dei documenti già analizzati)
HISTORY_DIR        = Path.home() / "AppData" / "Local" / "FunzioniAI"
HISTORY_STATE_FILE = HISTORY_DIR / "state.json"
HISTORY_LOG_FILE   = HISTORY_DIR / "history.jsonl"
# Le differenze rilevate sono scritte (in forma leggibile) nel log unico
# LOG_FILE, sezione "STORICO".

# ═══════════════════════════════════════════════════════════════════════════
# LOG UNICO
# ═══════════════════════════════════════════════════════════════════════════
# Un solo file di log per tutto il programma (opzioni 1-4, storico e script
# di debug). Superate LOG_MAX_LINES righe il file viene troncato alle ultime
# LOG_KEEP_LINES, cosi' non occupa spazio crescente.
LOG_FILE       = Path(__file__).parent / "asktrainmind.log"
LOG_MAX_LINES  = 20000
LOG_KEEP_LINES = 10000

# Modalità di ri-controllo delle celle GIÀ compilate:
#   "off"   → come oggi: le celle piene vengono saltate
#   "fast"  → livello 1: confronto size+mtime del PDF. Se invariato → skip totale
#   "deep"  → livello 1 + livello 2: estrae il testo e confronta l'hash
RECHECK_MODE = "fast"

# In modalità "fast", ogni quanti giorni forzare comunque un controllo "deep"
RECHECK_DEEP_EVERY_DAYS = 30

# ═══════════════════════════════════════════════════════════════════════════
# SALVATAGGIO DEI PROGRESSI E RIPRESA DOPO INTERRUZIONE
# ═══════════════════════════════════════════════════════════════════════════
# True  → su Ctrl+C / Ctrl+Break / chiusura richiesta l'opzione in corso si
#         ferma, scrive nel file Excel cio' che ha gia' elaborato (fogli
#         "Funzioni", "Requisiti", "Index Funzioni", senza colonne in piu'),
#         salva storico e cache e annota il punto di ripresa. Il file Excel
#         viene scritto in modo atomico (mai lasciato a meta').
# False → comportamento originale: Ctrl+C termina subito, il non salvato va perso.
SAVE_PROGRESS = True

# Opzione 1: salvataggio automatico del file Excel ogni N funzioni elaborate
# (protegge anche da chiusure brusche della finestra). 0 = disattivato.
AUTOSAVE_EVERY_N_GROUPS = 5

# True  → alla ripartenza le opzioni 1 e 3 riprendono dalla funzione in cui
#         erano state interrotte (dal menu viene chiesta conferma).
#         --start ha sempre la precedenza.
RESUME_FROM_CHECKPOINT = True

# Punti di ripresa (uno per opzione del menu)
PROGRESS_STATE_FILE = HISTORY_DIR / "progress_state.json"

# ═══════════════════════════════════════════════════════════════════════════
# RIF. PAGINA DINAMICO
# ═══════════════════════════════════════════════════════════════════════════
# True  → prima dell'analisi "Funzioni AI" il Rif. Pagina viene ricavato
#         dall'indice di ogni PDF e riscritto nella relativa cella:
#         verde se coincide con il valore inserito a mano o se la cella era
#         vuota, rosso nel formato "32 utente - 34 dinamico" se divergono.
# False → le celle "Rif. Pagina" restano quelle compilate manualmente.
RIF_PAGINA_DYNAMIC = True

# ═══════════════════════════════════════════════════════════════════════════
# COLORI CONFIGURAZIONI
# ═══════════════════════════════════════════════════════════════════════════
# Mappa fissa: ogni configurazione nota ha il suo colore.
# Le configurazioni NON presenti qui ricevono automaticamente un colore
# distinto preso da CONFIG_COLOR_PALETTE (vedi config_colors.py).
CONFIG_COLOR_MAP = {
    "VZI_Base":  "1F4E79",   # blu scuro
    "VZI_New14": "C00000",   # rosso
    "VZ_FR":     "00703C",   # verde
    "VZ_ES":     "7030A0",   # viola
    "VZI-6_R1":  "BF8F00",   # ocra
    "VZI-4_R1":  "0070C0",   # azzurro
    "VZ_DAI":    "D2691E",   # arancio
    "VZ_Esxx":   "008080",   # teal
}

# Palette di riserva per configurazioni nuove (nessun colore ripetuto)
CONFIG_COLOR_PALETTE = [
    "8B0000", "2F4F4F", "B8860B", "4B0082", "006400",
    "8B4513", "483D8B", "A0522D", "191970", "556B2F",
    "800000", "00554B", "6A0DAD", "AD1457", "33691E",
]
# ═══════════════════════════════════════════════════════════════════════════
# RICERCA FUNZIONI → foglio "Index Funzioni"  (opzione 2 del menu)
# ═══════════════════════════════════════════════════════════════════════════
# Foglio generato (rigenerato ad ogni esecuzione dell'opzione 2)
SHEET_INDEX_FUNZIONI = "Index Funzioni"

# Righe del foglio CONFIG (colonna B = DOC ID) da analizzare, estremi inclusi
INDEX_FUNC_FIRST_DOC_ID = "FRS_Drive Control"
INDEX_FUNC_LAST_DOC_ID  = "FRS_EMS"

# Titolo del capitolo dell'indice sotto cui si trovano le funzioni
# (confronto senza spazi/punteggiatura, maiuscole ignorate)
INDEX_FUNC_CHAPTER_TITLES = ["Functional requirements", "Functional requirement"]

# Profondita' sotto il capitolo:
#   1 → solo le funzioni (3.1 Coupling, 3.2 Pantograph Control, ...)
#   2 → anche le sotto-funzioni (3.2.1 Pantograph - Lifting, ...)
INDEX_FUNC_MAX_DEPTH = 2

# Sotto-titoli generici da NON considerare funzioni
INDEX_FUNC_GENERIC_TITLES = [
    "Function Design", "Functional Design", "Requirements", "Requirement",
    "General", "Description", "Overview", "Normal condition",
    "Normal conditions", "Failure cases", "Failure detection",
    "Failure handling", "Degraded mode", "Degraded modes",
    "Introduction", "Definitions",
]

# Somiglianza minima (0-1) tra due titoli per considerarli la stessa funzione
# (oltre all'uguaglianza esatta ignorando maiuscole, spazi e punteggiatura)
INDEX_FUNC_FUZZY_MATCH = 0.92

# Pagine iniziali del PDF in cui cercare il sommario
INDEX_FUNC_TOC_MAX_PAGES = 12

# Testo della nota in CONFIG che indica un documento mancante
INDEX_FUNC_MISSING_NOTE = "manca"

# ── FUNC ID e DESCRIZIONE FUNZIONE proposti ───────────────────────────────
# Con True il foglio "Index Funzioni" ha due colonne in piu' (C = FUNC ID,
# D = DESCRIZIONE FUNZIONE) con i valori da riportare nelle colonne A e B
# del foglio "Funzioni": ricopiati se la funzione e' gia' presente,
# altrimenti proposti seguendo la convenzione delle funzioni esistenti.
# Con False il foglio contiene solo titolo, paragrafo e MATCHED.
INDEX_FUNC_PROPOSE_IDS = True

# True → il prefisso del FUNC ID (es. "AIR" per "FRS_Air Supply") viene
# appreso dalle funzioni gia' presenti nel foglio "Funzioni" con lo stesso
# DOC ID. False → solo INDEX_FUNC_ID_PREFIX_MAP o prefisso derivato dal
# titolo del documento ("Drive Control" → "DRI", "TCMS - Operational" → "TCMS").
INDEX_FUNC_ID_LEARN_FROM_SHEET = True

# Prefissi imposti per DOC ID (hanno la precedenza su quelli appresi),
# es. {"FRS_Drive Control": "DRV", "FRS_Diagnostics": "DIAG"}
INDEX_FUNC_ID_PREFIX_MAP = {}

# Titolo del paragrafo padre nel FUNC ID delle sotto-funzioni:
#   "auto"   → come fanno le sotto-funzioni gia' presenti nel foglio; in
#              ogni caso anteposto se il titolo ha al massimo
#              INDEX_FUNC_ID_SHORT_TITLE_WORDS parole ("Activation")
#   "always" → sempre anteposto   (BAT_Battery_Contactors_Failure_modes)
#   "never"  → mai                (BAT_Failure_modes)
# Se il FUNC ID risultante e' gia' usato viene comunque anteposto il padre.
INDEX_FUNC_ID_PARENT_MODE = "auto"
INDEX_FUNC_ID_SHORT_TITLE_WORDS = 1

# Somiglianza minima (0-1) tra titolo del paragrafo e FUNC ID esistente
# per considerare la funzione gia' presente nel foglio "Funzioni"
INDEX_FUNC_ID_EXISTING_FUZZY = 0.9

# Descrizione delle funzioni nuove:
#   "ai"       → Ollama, con le descrizioni esistenti come esempi di stile,
#                il titolo del documento, il paragrafo padre e il testo
#                del paragrafo (se Ollama non risponde si usa il modello)
#   "template" → INDEX_FUNC_DESC_TEMPLATE
#   "off"      → descrizione vuota (viene proposto solo il FUNC ID)
INDEX_FUNC_DESC_MODE = "ai"

# Segnaposto: {title} {doc_title} {doc_id} {paragraph} {parent}
INDEX_FUNC_DESC_TEMPLATE = "Funzione per gestire {title} ({doc_title}, §{paragraph})"

# Numero di descrizioni esistenti passate al modello come esempi
INDEX_FUNC_DESC_EXAMPLES = 6
# Lunghezza massima della descrizione proposta (caratteri)
INDEX_FUNC_DESC_MAX_CHARS = 300
# Caratteri del testo del paragrafo inviati al modello
INDEX_FUNC_DESC_INPUT_CHARS = 3000
# Cache delle descrizioni generate da Ollama (riusate se titolo, testo e
# modello non cambiano). Cancellare il file per rigenerarle.
INDEX_FUNC_DESC_CACHE_FILE = Path.home() / "AppData" / "Local" / "FunzioniAI" / "index_desc_cache.json"

# Cache delle analisi dei PDF dell'opzione 2 (solo con SAVE_PROGRESS = True):
# dopo un'interruzione i documenti gia' letti non vengono riletti. Una voce
# viene invalidata se dimensione o data del PDF cambiano. Cancellare il file
# per forzare la rilettura di tutti i documenti.
INDEX_FUNC_DOC_CACHE_FILE = Path.home() / "AppData" / "Local" / "FunzioniAI" / "index_doc_cache.json"

# ═══════════════════════════════════════════════════════════════════════════
# CONFRONTO SPECIFICO FUNZIONI-REQUISITI → foglio "Confronto Reqs"  (opzione 4)
# ═══════════════════════════════════════════════════════════════════════════
# Foglio generato (rigenerato ad ogni esecuzione, accanto a "Index Funzioni")
SHEET_CONFRONTO_REQS = "Confronto Reqs"

# DOC ID proposti di default (col B del foglio CONFIG, es. ["FRS_Coupler"]):
# usati premendo Invio nella scelta del DOC ID o con --mode 4 fuori dal
# terminale interattivo.
CONFRONTO_REQS_DOC_IDS = []

# Description che non identificano un requisito (es. requisiti cancellati):
# questi requisiti vengono confrontati per Nr/ID invece che per Description.
CONFRONTO_REQS_IGNORE_DESCRIPTIONS = ["DELETED"]

# ═══════════════════════════════════════════════════════════════════════════
# FOGLIO REQUISITI — ordinamento e aggiornamento (opzione 1)
# ═══════════════════════════════════════════════════════════════════════════
# Al termine dell'opzione 1 i blocchi funzione del foglio Requisiti vengono
# ordinati come i FUNC ID del foglio Funzioni (prima tutte le LV, poi AUX,
# BAT, ...). Le funzioni assenti dal foglio Funzioni vanno dopo l'ultima
# funzione con lo stesso prefisso.
REQ_SORT_LIKE_FUNZIONI = True

# Elimina i requisiti non piu' presenti nei documenti, cosi' il foglio
# riflette sempre l'ultima analisi. Riguarda solo le funzioni analizzate per
# intero nell'esecuzione e le righe le cui configurazioni (col D) sono state
# tutte rianalizzate.
REQ_REMOVE_STALE_ROWS = True

# Archivio delle Description dei requisiti (alimentato dall'opzione 1):
# serve al foglio "Reqs not matched" quando nel foglio Requisiti c'e' solo
# "MATCHED" / "MISS VZI_BASE REQ, MATCHED".
REQ_DESC_CACHE_FILE = HISTORY_DIR / "req_desc_cache.json"

# ═══════════════════════════════════════════════════════════════════════════
# REQUISITI NON MATCHED TRA CONFIGURAZIONI → foglio "Reqs not matched" (opzione 5)
# ═══════════════════════════════════════════════════════════════════════════
# Foglio generato (cancellato e ricreato a ogni esecuzione, dopo "Requisiti")
SHEET_REQS_NOT_MATCHED = "Reqs not matched"

# Configurazioni proposte di default nella scelta (es. ["VZI_Base",
# "VZI_New14", "VZ_FR"]). Lista vuota = tutte le configurazioni.
REQS_NOT_MATCHED_CONFIGS = []

# Ricrea il foglio, con tutte le configurazioni, al termine dell'opzione 1
REQS_NOT_MATCHED_AFTER_OPTION1 = True

# "Note AI": spiegazione in italiano del requisito e delle differenze fra le
# configurazioni generata da Ollama. Con False (o Ollama non attivo) la nota
# riporta solo le differenze rilevate ("Requisito non trovato per la
# configurazione ...").
REQS_NOT_MATCHED_AI_NOTES = True
REQS_NOT_MATCHED_AI_MAX_CHARS = 350     # lunghezza della parte generata
REQS_NOT_MATCHED_NOTE_MAX_CHARS = 900   # lunghezza massima della cella
# Note nuove generate per esecuzione (0 = nessun limite, default). Il foglio
# contiene SEMPRE tutti i requisiti non MATCHED: con un limite > 0 le righe
# oltre il limite restano senza nota AI e sono marcate "[Nota AI non
# generata ...]"; le note gia' generate sono in cache e le esecuzioni
# successive completano le restanti.
REQS_NOT_MATCHED_AI_MAX_CALLS = 0
REQS_NOT_MATCHED_AI_CACHE_FILE = HISTORY_DIR / "reqs_not_matched_ai_cache.json"
# Requisiti con ID diverso ma Description simile (stesso requisito
# rinumerato in un'altra configurazione): al termine dell'opzione 5 le righe
# con somiglianza >= soglia vengono affiancate e annotate nelle Note
# ("Requisito simile a ..."). 1.0 = solo testo identico, 0 = disattivato.
REQS_NOT_MATCHED_SIMILAR_MIN = 0.80

# ═══════════════════════════════════════════════════════════════════════════
# ARCHIVIO _OLD — versioni precedenti del file Excel
# ═══════════════════════════════════════════════════════════════════════════
# Prima che un'opzione modifichi il file Excel, la versione precedente viene
# copiata in _OLD/<data_ora>_Opzione_<N>/ insieme a RICHIESTA.txt (opzione
# richiesta, parametri, fogli modificati, esito).
OLD_ARCHIVE_ENABLED = True
# None = cartella "_OLD" accanto al file Excel
OLD_ARCHIVE_DIR = None
# Celle aggiornate elencate in RICHIESTA.txt (oltre il limite: troncate)
OLD_ARCHIVE_MAX_CELL_LINES = 400

# ═══════════════════════════════════════════════════════════════════════════
# AGGIORNAMENTO DEL DB O FILE RESULTS
# ═══════════════════════════════════════════════════════════════════════════
# Default: le opzioni rielaborano e salvano i fogli impattati nel file DB
# Flotte. Se l'utente sceglie di NON aggiornare il DB (domanda all'avvio o
# --results-only) i fogli impattati vengono scritti, con lo stesso layout,
# in RESULTS_DIR/RESULTS_<data_ora>_Opzione_<N>.xlsx e il DB resta invariato.
UPDATE_DB_DEFAULT = True
# None = cartella "RESULTS" accanto al file Excel
RESULTS_DIR = None
# Esecuzioni parziali dell'opzione 1 (solo alcuni FRS, numero di celle
# limitato, FUNC ID di partenza, solo celle vuote): le celle "Funzioni AI" e
# i FUNC ID del foglio Requisiti esclusi ricevono questo commento.
NOT_UPDATED_COMMENT = "Not updated"

# ═══════════════════════════════════════════════════════════════════════════
# INTERFACCIA WEB (asktrainmind_web.py)
# ═══════════════════════════════════════════════════════════════════════════
# Anteprima developer con server locale (asktrainmind_web.py). L'utente usa
# invece la pagina offline User/AskTrainMind.html.
# Indirizzo del server locale. 127.0.0.1 = raggiungibile solo da questo PC
# (consigliato). "0.0.0.0" la rende visibile in rete.
WEB_HOST = "127.0.0.1"
WEB_PORT = 8765
# Apre automaticamente il browser all'avvio del server
WEB_OPEN_BROWSER = True
# Cartella della cache della web app (fogli gia' convertiti, indice PDF,
# risposte). None = HISTORY_DIR / "web_cache"
WEB_CACHE_DIR = None
# Cartelle (oltre a ONEDRIVE_DOCS_ROOT e alla cartella "docs" accanto al
# programma) in cui la sezione "Chiedi" cerca i documenti PDF quando
# l'utente abilita la ricerca nei documenti del computer.
WEB_EXTRA_DOC_DIRS = []
# Pagine massime indicizzate per PDF nella ricerca full-text (0 = tutte)
WEB_PDF_INDEX_MAX_PAGES = 0
# Aggiorna l'indice full-text dei PDF in background all'avvio del server
# (solo i file nuovi o modificati): la ricerca nei documenti e' subito veloce.
WEB_PDF_INDEX_AT_START = True
# Usa Ollama (se disponibile) per riformulare in italiano le risposte della
# sezione "Chiedi". Con False le risposte sono solo deterministiche (piu'
# veloci) e costruite dai dati del file Excel e dei PDF.
WEB_QA_USE_AI = True
# Pagine PDF analizzate al massimo per una sezione (figure/tabelle/testo)
WEB_QA_MAX_SECTION_PAGES = 12

# ═══════════════════════════════════════════════════════════════════════════
# CONOSCENZA DELL'AI (addestramento dal terminale developer)
# ═══════════════════════════════════════════════════════════════════════════
# Cartella della conoscenza appresa (vedi README.md, Parte 4). Contiene file JSON
# modificabili anche a mano: glossario.json (concetti, significati, relazioni),
# domande.json (domande in sospeso dell'AI), passaggi.json (frasi dei
# documenti di addestramento), fonti.json (documenti gia' letti).
KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
# Vecchio file del glossario (versioni precedenti): importato automaticamente
# in KNOWLEDGE_DIR alla prima esecuzione.
KNOWLEDGE_FILE = HISTORY_DIR / "knowledge.json"
# Usa il glossario appreso nei prompt di analisi (opzioni 1, 2, 5) e nelle
# risposte della sezione Chiedi: vengono aggiunti solo i termini presenti
# nel testo analizzato.
KNOWLEDGE_USE_IN_ANALYSIS = True
# Numero massimo di termini del glossario aggiunti a un singolo prompt
KNOWLEDGE_MAX_TERMS_IN_PROMPT = 25
# Domande nuove accodate al massimo per ogni documento letto
KNOWLEDGE_MAX_QUESTIONS = 40
# Pagine di un documento lette al massimo durante l'addestramento (0 = tutte)
KNOWLEDGE_MAX_PAGES = 0
# Cartelle proposte di default per l'addestramento (separate da ";")
KNOWLEDGE_TRAIN_DIRS = [Path(__file__).with_name("docs")]
# Frasi dei documenti conservate al massimo per ogni concetto
KNOWLEDGE_MAX_PASSAGES = 8
# Durante l'addestramento chiede all'AI locale (Ollama, se attiva) una
# proposta di significato per i termini senza definizione nei documenti.
KNOWLEDGE_USE_OLLAMA = False
# Spiegazioni dell'esperto (domanda + risposta originale) conservate al
# massimo nella scheda di ogni concetto: Chiedi le mostra e le usa come contesto.
KNOWLEDGE_MAX_ANSWERS_PER_TERM = 30

# ── Foglio Excel «questionAI» (addestramento rapido, voci 15 e 16) ─────────
# Cartella in cui viene creato questionAI.xlsx ("" = cartella del programma)
QUESTION_SHEET_DIR = ""
# Domande inserite al massimo in un foglio (0 = tutte quelle in attesa)
QUESTION_SHEET_MAX = 200
# Al caricamento, le risposte discorsive sono strutturate anche dall'AI
# locale (Ollama) se raggiungibile; senza Ollama vale la lettura automatica.
QUESTION_SHEET_USE_AI = True
# Durante il caricamento la conoscenza e' salvata ogni N risposte (e sempre
# alla fine o in caso di interruzione)
QUESTION_SHEET_SAVE_EVERY = 10
QUESTION_SHEET_SAVE_SECONDS = 20     # ...e non piu' spesso di ogni N secondi (velocita' con migliaia di risposte)

# ═══════════════════════════════════════════════════════════════════════════
# CARTELLA "User" (pagina web offline per l'utente)
# ═══════════════════════════════════════════════════════════════════════════
# Cartella generata da export_user.py (menu developer): contiene la pagina
# AskTrainMind.html (si apre con doppio clic, senza installare nulla) e una
# copia del file Excel.
USER_DIR = Path(__file__).with_name("User")
# Rigenera automaticamente la cartella User dopo ogni operazione del menu
# developer che modifica il file Excel o la conoscenza dell'AI.
USER_AUTO_EXPORT = True
# Da dove la pagina utente mostra i PDF:
#   "relative"   → percorsi relativi alla pagina USER_DOCS_FOLDER/<config>/CONFIG/
#                  <tipo>/<file>, ricavati dai link SharePoint del file Excel: la
#                  pagina e il file Excel vanno copiati nella cartella SharePoint
#                  che contiene DOC_FLOTTE (es. DB_ETR1000), sincronizzata con
#                  OneDrive. I PDF si vedono dentro la pagina, senza cartella docs.
#   "local"      → copia dei PDF trovati sul computer in docs/ accanto alla pagina.
#   "sharepoint" → solo i link SharePoint (nuova scheda): SharePoint non permette
#                  di mostrare i PDF dentro una pagina aperta dal computer.
USER_PDF_SOURCE = "relative"
# Cartella dei documenti, accanto alla pagina, con le sottocartelle per configurazione
USER_DOCS_FOLDER = "DOC_FLOTTE"

# True  = nella cartella User finiscono anche i concetti "proposti" dall'AI
#         (ricavati dai documenti, segnalati come "da verificare");
# False = solo i concetti confermati dal developer.
USER_EXPORT_PROPOSED = True

# ═══════════════════════════════════════════════════════════════════════════
# OPZIONE 0 (aggiornamento incrementale dei documenti del foglio CONFIG)
# ═══════════════════════════════════════════════════════════════════════════
# Memoria "FOGLIO CONFIG CODICE-REV FRS PER CONFIGURAZIONE": Codice e Rev di
# ogni DOC ID per configurazione, letti dal foglio CONFIG (OPZIONE 0 CREA DB
# CONFIG). OPZIONE 0 TOTAL confronta il foglio con questa memoria per sapere
# quali documenti sono cambiati; la versione sostituita resta in
# CONFIG_DB_PREV_FILE. Accanto al JSON viene scritta una copia .csv leggibile.
CONFIG_DB_FILE = Path(__file__).with_name("db_config") / "config_db.json"
CONFIG_DB_PREV_FILE = Path(__file__).with_name("db_config") / "config_db_prev.json"
CONFIG_DB_TITLE = "FOGLIO CONFIG CODICE-REV FRS PER CONFIGURAZIONE"
# Sottocartella di <configurazione>/CONFIG/ per ogni tipo di documento del
# foglio CONFIG (sezioni riconosciute dal titolo in colonna A) ed etichetta
# mostrata nella pagina web.
CONFIG_DOC_FOLDERS = {
    "FRS": ("FRS", "Functional Requirement Specification (FRS)"),
    "FPD": ("FPD", "Functional principle diagrams (VISIO)"),
    "FS":  ("FS",  "Functional schematics"),
    "WT":  ("WT",  "Wiring tables"),
    "EPL": ("EPL", "Electrical part lists"),
    "GEN": ("GVD", "General Vehicle Documents"),
    "ICD": ("ICD", "Interface control documents"),
}
# Cartella dei risultati: dist/<AAAA-MM-GG>/<OPZIONE0_PAGE_NAME> + copia Excel
DIST_DIR = Path(__file__).with_name("dist")
OPZIONE0_PAGE_NAME = "DBFlotte1000.html"
# Testi e colori delle celle "Funzioni AI" gestite dall'opzione 0
FUNC_TXT_NOT_PRESENT = "FUNZIONE NON PRESENTE"
# Sfondo di "LINK DOCUMENTALE NON INSERITO": colore tema 5 (Accent 2,
# arancione) schiarito del 40% come nel file Excel; RGB di riserva F4B084.
FILL_LINK_MISSING_THEME = (5, 0.3999755851924192)
FILL_LINK_MISSING_RGB = "F4B084"
FILL_NOT_PRESENT_RGB = "FFFF00"      # giallo
# Rif. Pagina di un documento non FRS (FS, FPD, WT, ...) aggiornato nel foglio
# CONFIG: "X" rossa in grassetto finche' l'utente non inserisce la pagina
# nuova; la pagina web non mostra quel PDF.
RIF_PAGINA_INVALID_TXT = "X"
# Storico del DB Flotte: all'avvio dell'OPZIONE 0 TOTAL / CREA DB CONFIG il
# file Excel viene copiato in <OPZ0_HISTORY_DIR>/<AAAA-MM-GG_hh-mm-ss>/;
# la copia resta solo se l'opzione termina con successo.
OPZ0_HISTORY_DIR = Path(__file__).with_name("DB_FLOTTE HISTORY OPZ. 0")

# ═══════════════════════════════════════════════════════════════════════════
# VALORI FORZATI DAL MENU DEVELOPER (Parametri CONFIG)
# ═══════════════════════════════════════════════════════════════════════════
# Le variabili modificate dal menu developer (AVVIA_DEVELOPER.bat, voce
# "Parametri CONFIG") sono salvate in config_overrides.json accanto a questo
# file e sostituiscono i valori qui sopra. Per tornare ai valori del file:
# comando "r" nel menu oppure cancellare config_overrides.json. NOTA: le variabili calcolate da
# altre (es. *_CACHE_FILE = HISTORY_DIR / ...) non vengono ricalcolate.
CONFIG_OVERRIDES_FILE = Path(__file__).with_name("config_overrides.json")


def _apply_overrides() -> None:
    import json
    try:
        data = json.loads(CONFIG_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    g = globals()
    for name, value in (data or {}).items():
        if not name.isupper() or name not in g:
            continue
        if isinstance(g[name], Path) and isinstance(value, str):
            value = Path(value)
        g[name] = value


_apply_overrides()
