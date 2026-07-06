"""
config.py
---------
Configurazione centralizzata. Modifica SOLO questo file.
"""
from pathlib import Path

# ── Percorso file Excel ────────────────────────────────────────────────────
# Apri Esplora Risorse → naviga al file → clicca sulla barra indirizzi → copia
EXCEL_PATH = Path(
    r"C:\__SCRIPTS\AskTrainMind\DB Flotte ETR1000 Ver_1.5.xlsx"
)

# ── Cartella OneDrive locale ───────────────────────────────────────────────
# Percorso della cartella OneDrive dove sono sincronizzati i documenti PDF.
# Apri Esplora Risorse → naviga nella cartella che contiene i PDF → 
# clicca sulla barra degli indirizzi → copia il percorso.
# Esempio: r"C:\Users\2954534.UTENTI\OneDrive - GruppoFS\DB_ETR1000\DOC_FLOTTE"
ONEDRIVE_DOCS_ROOT = Path(
    r"C:\Users\2954534.UTENTI\OneDrive - Gruppo Ferrovie Dello Stato\Documenti - Ingegneria ETR - Trenitalia\DB_ETR1000\DOC_FLOTTE"
)

# ── Modello AI locale (Ollama) ─────────────────────────────────────────────
# Scarica con: ollama pull llama3.2
# Opzioni: "llama3.2" (consigliato), "phi3:mini" (per PC con poca RAM)
OLLAMA_MODEL = "llama3.2"

# ── Nomi dei fogli ─────────────────────────────────────────────────────────
SHEET_FUNZIONI = "Funzioni"
SHEET_CARTELLE = "Cartelle"
SHEET_CONFIG   = "CONFIG"
SHEET_MAN_CPR  = "MAN_CPR"

# ── Label righe di terzo livello ───────────────────────────────────────────
FUNZIONI_AI_LABEL = "Funzioni AI"   # la riga da compilare automaticamente
RIF_PAGINA_LABEL  = "Rif. Pagina"   # la riga con il numero di pagina

# ── Cella base URL SharePoint ─────────────────────────────────────────────
# La formula usa Cartelle!$D$5 come radice di tutti gli URL
CARTELLE_BASE_URL_ROW = 5
CARTELLE_BASE_URL_COL = 4  # colonna D

# ── Esecuzione ────────────────────────────────────────────────────────────
# Quante celle "Funzioni AI" elaborare per esecuzione.
# 0 = tutte. Usa 3 per il primo test.
MAX_CELLS_PER_RUN = 0

# Pausa tra una chiamata AI e la successiva (secondi).
# Ollama è locale — anche 0 va bene.
AI_CALL_DELAY_SECONDS = 1.0

# ── Cache documenti scaricati ─────────────────────────────────────────────
CACHE_DIR = Path.home() / "AppData" / "Local" / "FunzioniAI" / "cache"

# ── Autenticazione Microsoft 365 ──────────────────────────────────────────
# Client ID pubblico Azure CLI — pre-approvato da Microsoft, gratuito,
# funziona con qualsiasi account Microsoft 365 aziendale.
MS_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
MS_SCOPES = [
    "https://graph.microsoft.com/Files.Read",
    "https://graph.microsoft.com/Sites.Read.All",
]