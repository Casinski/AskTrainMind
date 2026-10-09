"""
config.py
---------
Configurazione centralizzata. Modifica SOLO questo file.
"""
from pathlib import Path

# ── Percorso file Excel ────────────────────────────────────────────────────
EXCEL_PATH = Path(
    r"C:\__SCRIPTS\AskTrainMind\DB Flotte ETR1000 Ver_1.8_PROVA.xlsx"
)

# ── Cartella OneDrive locale ───────────────────────────────────────────────
ONEDRIVE_DOCS_ROOT = Path(
    r"C:\Users\2954534.UTENTI\OneDrive - Gruppo Ferrovie Dello Stato\Documenti - Ingegneria ETR - Trenitalia\DB_ETR1000\DOC_FLOTTE"
)

# ── Modello AI locale (Ollama) ─────────────────────────────────────────────
OLLAMA_MODEL = "llama3.2"

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
MAX_CELLS_PER_RUN      = 8
AI_CALL_DELAY_SECONDS  = 1.0
START_FROM_FUNC_ID: str = ""

# ── Similarità testuale (Strategia B in document_handler) ─────────────────
SIMILARITY_THRESHOLD = 0.26

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
REQ_ID_BLACKLIST_SUBSTR = ["www.", ".pdf", ".doc", "http", "e.g.", "i.e."]

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
REQ_H_HEADER_MIN_MATCH = 3

# Filtri anti-prosa: senza spazi, una frase somiglia a un ID.
REQ_PROSE_PREFIXES = ("e.g.", "i.e.", "etc.", "ref.", "fig.", "cfr.", "n.a.")
REQ_MAX_ALPHA_RUN = 28      # blocco alfabetico oltre il quale è prosa

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
REQ_H_HEADER_ID = ["nr", "nr.", "n.", "nr requisito", "req nr", "number"]
# Altre intestazioni della tabella orizzontale
REQ_H_HEADER_DESCRIPTION = ["description", "descrizione"]
REQ_H_HEADER_TYPE        = ["type", "tipo"]
REQ_H_HEADER_DERIVED     = ["derived to", "derived from", "derived"]
REQ_H_HEADER_UI          = ["user interface", "user if", "ui"]
REQ_H_HEADER_SIL         = ["sil", "safety integrity level"]

# Intestazione della colonna ID nella tabella VERTICALE
REQ_V_HEADER_ID          = ["id", "requirement id", "req id", "identifier"]
REQ_V_HEADER_DESCRIPTION = ["description", "descrizione"]
REQ_V_HEADER_SAFETY      = ["safety level", "safety integrity level", "sil"]

# Quante intestazioni devono comparire perché una riga sia riconosciuta
# come riga di testata della tabella orizzontale.
REQ_H_HEADER_MIN_MATCH = 3

# Righe massime di distanza entro cui cercare il valore di un campo
# verticale quando l'etichetta è su una riga e il valore su quella dopo.
REQ_V_LOOKAHEAD = 2

# Se True, un ID trovato FUORI da qualsiasi tabella riconosciuta viene
# comunque registrato come requisito. Sconsigliato: è la causa principale
# dei falsi positivi (ID citati nel testo discorsivo o in "Derived to").
REQ_ACCEPT_LOOSE_IDS = False

# ── Terminazione e robustezza delle tabelle orizzontali ───────────────────
# fitz intercala spesso righe vuote tra le righe di una tabella PDF.
# Interrompere alla terza riga vuota tronca la tabella dopo il primo
# requisito: la soglia va tenuta alta e, soprattutto, non si interrompe
# mai mentre un requisito è ancora aperto.
REQ_H_MAX_BLANK_LINES = 12

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
REQ_DEBUG_LOG_EACH = True

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