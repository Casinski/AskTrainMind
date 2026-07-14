"""
support_loader.py
-----------------
Legge i fogli di supporto del file Excel (Cartelle, CONFIG, MAN_CPR)
e costruisce la struttura dati necessaria per ricostruire gli URL SharePoint.

Questi fogli contengono le stesse informazioni usate dalle formule Excel:
  - Cartelle!$D$5  → URL base SharePoint
  - CONFIG         → mapping Doc ID → codice file per ogni configurazione
  - MAN_CPR        → mapping alternativo per documenti manuali

Questa lettura viene fatta UNA VOLTA SOLA all'avvio, poi i dati
vengono riutilizzati per ogni cella da compilare.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

import config as cfg

log = logging.getLogger(__name__)


@dataclass
class SupportData:
    """
    Contiene tutti i dati letti dai fogli di supporto.

    Struttura config_map e man_cpr_map:
        {
            "FS_DM1": {
                "VZI_Base":   "3ECP410467-0001",
                "VZI_New14":  "3ECP400500-0005",
                "VZ_FR":      "3ECP410467-0001",
                ...
            },
            "FRS_Brake Control": { ... },
            ...
        }
    """
    # URL base SharePoint (da Cartelle!$D$5)
    # es. "https://gruppofsitaliane.sharepoint.com/.../DOC_FLOTTE/"
    base_url: str = ""

    # Dati da foglio CONFIG: {doc_id: {config_name: file_code}}
    config_map: dict[str, dict[str, str]] = field(default_factory=dict)

    # Dati da foglio MAN_CPR: {doc_id: {config_name: file_code}}
    man_cpr_map: dict[str, dict[str, str]] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return bool(self.base_url)


def load(wb_data) -> SupportData:
    """
    Punto di ingresso: carica tutti i fogli di supporto dal workbook
    aperto con data_only=True e restituisce un SupportData popolato.

    Args:
        wb_data: workbook openpyxl aperto con data_only=True
    """
    sd = SupportData()
    _load_cartelle(wb_data, sd)
    _load_config(wb_data, sd)
    _load_man_cpr(wb_data, sd)
    return sd


# ---------------------------------------------------------------------------
# Lettura foglio Cartelle
# ---------------------------------------------------------------------------

def _load_cartelle(wb_data, sd: SupportData) -> None:
    """
    Legge la base URL SharePoint dal foglio Cartelle.

    Struttura foglio Cartelle:
        Riga 2: Root SharePoint   → https://...sharepoint.com/.../
        Riga 3: Shared Documents  → .../Shared%20Documents/
        Riga 4: DB_ETR1000        → .../DB_ETR1000/
        Riga 5: DOC_FLOTTE        → .../DB_ETR1000/DOC_FLOTTE/  ← target
        Riga 6: DOC_FUNC          → .../DB_ETR1000/DOC_FUNC/

    La formula in D5 è =CONCATENATE($D$4, B5):
        D4 = URL di DB_ETR1000
        B5 = "DOC_FLOTTE/"
        D5 = URL completo di DOC_FLOTTE (quello che vogliamo)

    Strategia a cascata:
      1. Legge D5 data_only (valore calcolato da Excel) — caso ideale
      2. Ricostruisce CONCATENATE($D$4, B5) leggendo D4 e B5 come plain text
      3. Ricostruisce risalendo la catena: B2+B3+B4+B5
      4. Scansione colonna D cercando URL che contiene "DOC_FLOTTE"
    """
    if cfg.SHEET_CARTELLE not in wb_data.sheetnames:
        log.warning(f"Foglio '{cfg.SHEET_CARTELLE}' non trovato nel workbook.")
        return

    ws = wb_data[cfg.SHEET_CARTELLE]

    # ── Strategia 1: valore data_only diretto in D5 ──────────────────────
    val = ws.cell(cfg.CARTELLE_BASE_URL_ROW, cfg.CARTELLE_BASE_URL_COL).value
    if val and isinstance(val, str) and val.strip().startswith("http"):
        sd.base_url = val.strip()
        if not sd.base_url.endswith("/"):
            sd.base_url += "/"
        log.info(f"  [Cartelle] Base URL (da D{cfg.CARTELLE_BASE_URL_ROW} data_only): {sd.base_url}")
        return

    # ── Strategia 2: ricostruisce CONCATENATE($D$4, B5) ──────────────────
    # D4 = URL DB_ETR1000 (già calcolato come plain text o formula semplice)
    # B5 = "DOC_FLOTTE/" (plain text, mai formula)
    log.info(
        f"  [Cartelle] D{cfg.CARTELLE_BASE_URL_ROW} data_only vuota — "
        "ricostruzione da D4 + B5..."
    )
    d4 = _read_plain_or_walk_up(ws, row=4, col=4)   # $D$4
    b5 = ws.cell(5, 2).value                         # B5 = "DOC_FLOTTE/" (plain)

    if d4 and b5 and isinstance(b5, str):
        b5_clean  = b5.strip().strip("/")
        candidate = d4.rstrip("/") + "/" + b5_clean + "/"
        if candidate.startswith("http"):
            sd.base_url = candidate
            log.info(f"  [Cartelle] Base URL (ricostruita D4+B5): {sd.base_url}")
            return

    # ── Strategia 3: risale la catena B2+B3+B4+B5 ────────────────────────
    # Legge i valori plain delle colonne B (nomi cartelle) e D (URL root)
    log.info("  [Cartelle] Ricostruzione catena B2..B5...")
    root_url = ws.cell(2, 4).value   # D2 = URL root SharePoint (plain)
    if root_url and isinstance(root_url, str) and root_url.startswith("http"):
        parts = [root_url.rstrip("/")]
        for row in range(3, 6):      # righe 3, 4, 5 → Shared, DB_ETR1000, DOC_FLOTTE
            b_val = ws.cell(row, 2).value
            if b_val and isinstance(b_val, str):
                parts.append(b_val.strip().strip("/"))
        candidate = "/".join(parts) + "/"
        if "DOC_FLOTTE" in candidate:
            sd.base_url = candidate
            log.info(f"  [Cartelle] Base URL (catena B2..B5): {sd.base_url}")
            return

    # ── Strategia 4: scansione cercando URL con "DOC_FLOTTE" ─────────────
    # A differenza di prima, cerca SPECIFICAMENTE "DOC_FLOTTE" e NON
    # prende il più lungo (che sarebbe DOC_FUNC o altro)
    log.info("  [Cartelle] Scansione colonna D per URL contenente 'DOC_FLOTTE'...")
    for row in range(1, min(20, ws.max_row + 1)):
        for col in range(1, min(6, ws.max_column + 1)):
            v = ws.cell(row, col).value
            if (v and isinstance(v, str)
                    and "sharepoint.com" in v.lower()
                    and "DOC_FLOTTE" in v
                    and v.startswith("http")):
                sd.base_url = v.strip()
                if not sd.base_url.endswith("/"):
                    sd.base_url += "/"
                log.info(
                    f"  [Cartelle] Base URL (scansione DOC_FLOTTE): {sd.base_url}"
                )
                return

    log.error(
        "  [Cartelle] Impossibile determinare la base URL DOC_FLOTTE.\n"
        "  Apri il file Excel, foglio 'Cartelle', cella D5.\n"
        "  Verifica che contenga l'URL SharePoint e salva con Ctrl+S."
    )

def _read_plain_or_walk_up(ws, row: int, col: int, max_depth: int = 5) -> str:
    """
    Legge il valore di una cella. Se è None o è un oggetto Formula,
    tenta di leggere la cella referenziata (per formule semplici come =D4).
    Usato per risalire la catena di CONCATENA in Cartelle.

    max_depth limita la ricorsione per evitare loop infiniti.
    """
    if max_depth <= 0:
        return ""

    val = ws.cell(row, col).value
    if val is None:
        return ""

    # ArrayFormula o Formula object — non leggibile direttamente
    type_name = type(val).__name__
    if "Formula" in type_name or "formula" in type_name:
        return ""

    s = str(val).strip()

    # Valore stringa utile
    if s and not s.startswith("="):
        return s

    # Formula semplice tipo =D4 → segui il riferimento
    if s.startswith("="):
        import re
        m = re.match(r"^=\$?([A-Za-z]+)\$?(\d+)$", s)
        if m:
            ref_col = sum(
                (ord(c) - 64) * (26 ** i)
                for i, c in enumerate(reversed(m.group(1).upper()))
            )
            ref_row = int(m.group(2))
            return _read_plain_or_walk_up(ws, ref_row, ref_col, max_depth - 1)

    return ""

# ---------------------------------------------------------------------------
# Lettura foglio CONFIG
# ---------------------------------------------------------------------------

def _load_config(wb_data, sd: SupportData) -> None:
    """
    Legge il foglio CONFIG — struttura Ver_1.7_00:

        Col 1: DOC DESCRIPTION
        Col 2: DOC ID          ← chiave di ricerca
        Col 3: DOC EXT         ← NUOVO (es. "pdf") — da ignorare come config
        Col 4: VZI_Base        ← prima configurazione (File/Codice)
        Col 5: (Rev)
        Col 6: (Codice Config)
        Col 7: VZI_New14       ← seconda configurazione
        ...

    Riga 1: nomi configurazioni (in col 4, 7, 10, 13, 16, 18, 20, 22...)
    Riga 2: versioni BL
    Riga 3: sotto-intestazioni (File/Codice | Rev | Codice Config)
    Riga 4+: dati — col 2 = Doc ID, prima col del gruppo = File/Codice
    """
    if cfg.SHEET_CONFIG not in wb_data.sheetnames:
        log.warning(f"Foglio '{cfg.SHEET_CONFIG}' non trovato.")
        return

    ws      = wb_data[cfg.SHEET_CONFIG]
    max_col = ws.max_column
    max_row = ws.max_row

    # Colonne da escludere esplicitamente come non-config
    SKIP_HEADERS = {
        "doc description", "doc id", "doc ext", "doe ext",
        "codice", "tipo", "volume", ""
    }

    # Passo 1: mappa colonna → nome configurazione da riga 1
    col_to_config: dict[int, str] = {}
    for col in range(1, max_col + 1):
        val = ws.cell(1, col).value
        if val is None:
            continue
        v = str(val).strip()
        if v.lower() not in SKIP_HEADERS:
            col_to_config[col] = v

    log.info(
        f"  [CONFIG] Configurazioni trovate in riga 1: "
        f"{list(col_to_config.values())}"
    )

    # Passo 2: dati dalla riga 4 in poi (riga 1=intestazioni, 2=BL, 3=sotto-intestaz.)
    # Col 2 = Doc ID
    # La colonna di ogni config group = prima col del gruppo (quella con il nome in riga 1)
    # contiene il File/Codice (es. "3ECP410467-0001")
    INVALID_CODES = {"", "\\", "_", "tbd", "#n/a", "n/a", "–", "-", "ref", "rev"}

    for row in range(4, max_row + 1):
        doc_id_val = ws.cell(row, 2).value   # col 2 = Doc ID
        if not doc_id_val:
            continue
        doc_id = str(doc_id_val).strip()
        if not doc_id or doc_id.lower() in SKIP_HEADERS:
            continue

        row_data: dict[str, str] = {}
        for col, config_name in col_to_config.items():
            file_val = ws.cell(row, col).value
            if file_val is None:
                continue
            file_code = str(file_val).strip()
            if file_code.lower() not in INVALID_CODES and len(file_code) > 2:
                row_data[config_name] = file_code

        if row_data:
            sd.config_map[doc_id] = row_data

    log.info(
        f"  [CONFIG] {len(sd.config_map)} documenti caricati. "
        f"Esempi: {list(sd.config_map.keys())[:8]}"
    )
    
# ---------------------------------------------------------------------------
# Lettura foglio MAN_CPR
# ---------------------------------------------------------------------------
def _load_man_cpr(wb_data, sd: SupportData) -> None:
    """
    Legge il foglio MAN_CPR — struttura Ver_1.7_00:

        Col 1: DOC DESCRIPTION
        Col 2: DOC ID          ← NUOVO: chiave esplicita (es. "PBC_01A") — MA può essere vuota
        Col 3: DOC EXT         ← NUOVO (es. "pdf")
        Col 4: TIPO            ← es. "PBC", "PBS", "MR1"
        Col 5: VOLUME/SUBTOMO  ← es. "01A", "01B"
        Col 6: CODICE          ← codice interno
        Col 7: VZI_Base REF    ← prima config (File/Codice)
        Col 8: VZI_Base REV
        Col 9: VZI_Base DATA
        Col 10: VZI_New14 REF
        ...

    Riga 1: nomi configurazioni (in col 7, 10, 13, 16, 19, 22...)
    Riga 2: sotto-intestazioni (REF | REV | DATA per ogni gruppo)
    Riga 3+: dati

    CHIAVE Doc ID:
      Se col 2 è valorizzata → usala direttamente
      Altrimenti costruiscila come TIPO + "_" + VOLUME (es. "PBC" + "_" + "01A" = "PBC_01A")
    """
    if cfg.SHEET_MAN_CPR not in wb_data.sheetnames:
        log.warning(f"Foglio '{cfg.SHEET_MAN_CPR}' non trovato.")
        return

    import datetime as _dt
    import re as _re

    ws      = wb_data[cfg.SHEET_MAN_CPR]
    max_col = ws.max_column
    max_row = ws.max_row

    # Colonne strutturali da escludere come config
    SKIP_MAN = {
        "doc description", "doc id", "doc ext", "tipo",
        "codice", "volume subvolume _tomo", "volume\nsubvolume\n_tomo", ""
    }

    # Passo 1: intestazioni riga 1 → colonna → nome configurazione
    col_to_config: dict[int, str] = {}
    for col in range(1, max_col + 1):
        val = ws.cell(1, col).value
        if val is None:
            continue
        v = str(val).strip().replace("\n", " ")
        if v.lower() not in SKIP_MAN and "volume" not in v.lower():
            col_to_config[col] = v

    log.info(
        f"  [MAN_CPR] Configurazioni trovate in riga 1: "
        f"{list(col_to_config.values())}"
    )

    if not col_to_config:
        log.warning("  [MAN_CPR] Nessuna configurazione trovata in riga 1.")
        return

    # Passo 2: dati dalla riga 3 in poi
    INVALID_CODES = {"", "tbd", "#n/a", "n/a", "ref", "rev", "data"}

    for row in range(3, max_row + 1):

        # ── Determina Doc ID ─────────────────────────────────────────────
        # Strategia 1: col 2 esplicita
        doc_id_val = ws.cell(row, 2).value
        if doc_id_val and not isinstance(doc_id_val, _dt.datetime):
            doc_id = str(doc_id_val).strip()
        else:
            # Strategia 2: costruisci da TIPO (col 4) + VOLUME (col 5)
            tipo_val   = ws.cell(row, 4).value
            volume_val = ws.cell(row, 5).value
            if tipo_val and volume_val:
                tipo   = str(tipo_val).strip()
                volume = str(volume_val).strip()
                # Costruisce "PBC_01A" da "PBC" + "01A"
                doc_id = f"{tipo}_{volume}" if volume else tipo
            else:
                continue

        if not doc_id or doc_id.lower() in ("doc id", ""):
            continue

        # ── Leggi codice REF per ogni configurazione ──────────────────────
        row_data: dict[str, str] = {}
        for col, config_name in col_to_config.items():
            ref_val = ws.cell(row, col).value

            if ref_val is None:
                continue
            if isinstance(ref_val, _dt.datetime):
                continue
            if isinstance(ref_val, (int, float)):
                continue

            ref_code = str(ref_val).strip()

            is_invalid = (
                ref_code.lower() in INVALID_CODES
                or ref_code.startswith("/")
                or ref_code.startswith("SGF")
                or ref_code.startswith("esiste")
                or ref_code.startswith("TBD")
                or len(ref_code) <= 3
            )
            if is_invalid:
                continue

            # Il codice deve contenere cifre o trattini (pattern codice documento)
            if not _re.search(r"[0-9\-]", ref_code):
                continue

            row_data[config_name] = ref_code

        if row_data:
            sd.man_cpr_map[doc_id] = row_data

    log.info(
        f"  [MAN_CPR] {len(sd.man_cpr_map)} documenti caricati. "
        f"Esempi: {list(sd.man_cpr_map.keys())[:8]}"
    )