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
MAX_CELLS_PER_RUN      = 4
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

SHEET_REQUISITI = "Requisiti"

# Intestazioni attese nel foglio Requisiti (match case-insensitive, parziale)
REQ_COL_FUNC_ID       = "func id"
REQ_COL_DESCRIZIONE   = "descrizione funzione"
REQ_COL_REQUISITO     = "requisito"
REQ_COL_APPARTENENZA  = "configurazione appartenenza"

# Riga di intestazione del foglio Requisiti
REQ_HEADER_ROW = 1

# Scrive anche Description / Type / SIL se le colonne omonime esistono
REQ_WRITE_EXTRA_FIELDS = True

# ── Riconoscimento ID requisito ───────────────────────────────────────────
# Token "a punti" che contiene la stringa Zefiro (case-insensitive).
# Es: 2F_05.01.Zefiro-Europe.TRS.184
REQ_ID_MARKER      = "zefiro"
REQ_ID_MIN_SEGMENTS = 3     # numero minimo di segmenti separati da punto
# Pattern generico di fallback (ID senza "Zefiro")
REQ_ID_FALLBACK_PATTERNS = [
    r"\b[A-Z0-9]{2,}[A-Z0-9_\-]*(?:\.[A-Za-z0-9_\-]+){2,}\b",
    r"\bREQ[-_][A-Za-z0-9_.\-]{3,}\b",
]
# Token da scartare (falsi positivi tipici dei PDF)
REQ_ID_BLACKLIST_SUBSTR = ["www.", ".pdf", ".doc", "http", "e.g.", "i.e."]

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