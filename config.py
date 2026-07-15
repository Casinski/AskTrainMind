"""
config.py
---------
Configurazione centralizzata. Modifica SOLO questo file.
"""
from pathlib import Path

# ── Percorso file Excel ────────────────────────────────────────────────────
EXCEL_PATH = Path(
    r"C:\__SCRIPTS\AskTrainMind\DB Flotte ETR1000 Ver_1.7_00.xlsx"
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
CARTELLE_BASE_URL_COL = 4  # colonna D

# ── Esecuzione ────────────────────────────────────────────────────────────
# Quante celle "Funzioni AI" elaborare per esecuzione.
# 0 = tutte. Usa 3 per il primo test.
MAX_CELLS_PER_RUN = 10

# Pausa tra una chiamata AI e la successiva (secondi).
AI_CALL_DELAY_SECONDS = 1.0

# ── Funzione di partenza ──────────────────────────────────────────────────
# Se valorizzato, lo scanner salta tutte le funzioni precedenti a questa
# e inizia l'elaborazione da essa (inclusa).
# Deve corrispondere esattamente al valore della colonna A (FUNC ID).
# Esempi: "LV_HVAC_pre-conditioning_on_DC_line"
#         "Park_Brake_01"
# Se vuoto ("") → parte dall'inizio del foglio (comportamento normale).
START_FROM_FUNC_ID: str = ""

# Soglia similarità testuale per il rilevamento fine sezione (Strategia B)
# Valori consigliati: tra 0.15 (permissivo) e 0.40 (restrittivo)
SIMILARITY_THRESHOLD = 0.26

# ── Cache documenti scaricati ─────────────────────────────────────────────
CACHE_DIR = Path.home() / "AppData" / "Local" / "FunzioniAI" / "cache"

# ── Autenticazione Microsoft 365 ──────────────────────────────────────────
MS_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
MS_SCOPES = [
    "https://graph.microsoft.com/Files.Read",
    "https://graph.microsoft.com/Sites.Read.All",
]