"""
config.py
---------
Configurazione centralizzata. Modifica SOLO questo file.
"""
from pathlib import Path

# ── Percorso file Excel ────────────────────────────────────────────────────
EXCEL_PATH = Path(
    r"C:\__SCRIPTS\AskTrainMind\DB Flotte ETR1000 Ver_1.8.xlsx"
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
OLLAMA_NUM_PREDICT = 300

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
MAX_CELLS_PER_RUN      = 4
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
#       Col C: Nr requisito   es. "2F_05.01.Zefiro-Europe.TRS.184"
#       Col D: Configurazione di appartenenza, colorata
#
SHEET_REQUISITI = "Requisiti"

# Riga di intestazione del foglio Requisiti
REQ_HEADER_ROW = 1

# ── Colonne di LIVELLO 1 (ricerca funzione) ───────────────────────────────
REQ_FUNC_ID_COL = 1      # Col A
REQ_DESC_COL    = 2      # Col B

# ── Colonne di LIVELLO 2 (scrittura requisiti) ────────────────────────────
REQ_NUMBER_COL  = 3      # Col C — Nr requisito
REQ_CONFIG_COL  = 4      # Col D — Configurazione di appartenenza

# ── Colonne per-configurazione (da E in poi) ──────────────────────────────
# Riga 1 del foglio "Requisiti": da col E in poi ci sono i nomi delle
# configurazioni. La mappa {config_name: colonna} viene costruita a runtime.
REQ_CONFIG_COLS_START = 5          # Col E
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

# Etichette della nuova cella. {pct} viene sostituito dalla percentuale.
FUNC_TXT_REF_BASE_OK   = "RIFERIMENTO VZI_BASE, % SIMILARITY = {pct}, X>90%"
FUNC_TXT_REF_BASE_DIFF = "RIFERIMENTO VZI_BASE, % SIMILARITY = {pct}, X<90%"
FUNC_TXT_MISS_BASE     = "MISS VZI_BASE"

# Decimali della percentuale scritta in cella (0 = numero intero)
FUNC_SIMILARITY_DECIMALS = 1

# Se True, sotto la sigla rossa viene aggiunto il dettaglio testuale dei
# frammenti divergenti (describe_text_diff, deterministico e istantaneo).
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

# Quante intestazioni devono comparire perché una riga sia riconosciuta
# come riga di testata della tabella orizzontale.
REQ_H_HEADER_MIN_MATCH = 3

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
# Log leggibile affiancato allo script
HISTORY_READABLE_LOG = Path(__file__).parent / "storico_differenze.log"

# Modalità di ri-controllo delle celle GIÀ compilate:
#   "off"   → come oggi: le celle piene vengono saltate
#   "fast"  → livello 1: confronto size+mtime del PDF. Se invariato → skip totale
#   "deep"  → livello 1 + livello 2: estrae il testo e confronta l'hash
RECHECK_MODE = "fast"

# In modalità "fast", ogni quanti giorni forzare comunque un controllo "deep"
RECHECK_DEEP_EVERY_DAYS = 30

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