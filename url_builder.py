"""
url_builder.py
--------------
Ricostruisce gli URL SharePoint replicando esattamente la logica
della formula Excel nel foglio Funzioni.

AGGIORNAMENTO: ora usa il valore della colonna C (DOC CARTELLA) per
instradare la ricerca nel foglio di supporto corretto:

  "CONFIG"     → cerca in sd.config_map   (foglio CONFIG, col B = Doc ID)
  "MAN_CPR"    → cerca in sd.man_cpr_map  (foglio MAN_CPR, col E = Doc ID)
  "DIAGNOSTIC" → costruisce URL con sottocartella DIAGNOSTIC/
  "GENERAL"    → costruisce URL con sottocartella GENERAL/
  Altro        → tenta CONFIG poi MAN_CPR (fallback)

Pattern URL per CONFIG:
    base_url + config_name + "/CONFIG/" + prefix + "/" + file_code + ".pdf" + #page=N

Pattern URL per MAN_CPR:
    base_url + "MAN_CPR/" + file_code + ".pdf" + #page=N

Pattern URL per DIAGNOSTIC / GENERAL (cartelle semplici):
    base_url + doc_cartella + "/" + doc_id + ".pdf" + #page=N
"""
from __future__ import annotations
import logging
from typing import Optional

from support_loader import SupportData

log = logging.getLogger(__name__)


def build(
    sd: SupportData,
    doc_id: str,
    config_name: str,
    page_number: int,
    doc_cartella: str = "",   # ← NUOVO parametro, default "" per compatibilità
) -> Optional[str]:
    """
    Costruisce l'URL SharePoint completo per un documento.

    Args:
        sd           : dati caricati dai fogli di supporto
        doc_id       : es. "FS_DM1", "FRS_Brake Control", "PBC_01A"
        config_name  : es. "VZI_Base", "VZI_New14", "VZ_FR"
        page_number  : numero pagina da Rif. Pagina (0 = nessuna pagina)
        doc_cartella : valore colonna C del foglio Funzioni
                       (es. "CONFIG", "MAN_CPR", "DIAGNOSTIC", "GENERAL")

    Returns:
        URL completo oppure None se non è possibile costruire l'URL.
    """
    if not sd.base_url:
        log.warning("  URL non costruibile: base_url vuota")
        return None

    page_suffix  = f"#page={page_number}" if page_number > 0 else ""
    cartella_key = doc_cartella.strip().upper() if doc_cartella else ""

    # ── Instradamento in base alla colonna C (DOC CARTELLA) ──────────────

    if cartella_key == "CONFIG":
        url = _build_from_config(sd, doc_id, config_name, page_suffix)
        if url:
            return url
        # Fallback: prova MAN_CPR nel caso di errore di classificazione
        log.debug(f"  CONFIG fallback → MAN_CPR per '{doc_id}'")
        return _build_from_man_cpr(sd, doc_id, config_name, page_suffix)

    if cartella_key == "MAN_CPR":
        url = _build_from_man_cpr(sd, doc_id, config_name, page_suffix)
        if url:
            return url
        log.debug(f"  MAN_CPR fallback → CONFIG per '{doc_id}'")
        return _build_from_config(sd, doc_id, config_name, page_suffix)

    if cartella_key in ("DIAGNOSTIC", "GENERAL"):
        # Per queste cartelle non c'è un foglio di lookup:
        # l'URL è costruito direttamente come
        # base_url + cartella + "/" + doc_id + ".pdf" + #page=N
        url = _build_from_simple_folder(
            sd, doc_id, doc_cartella.strip(), page_suffix
        )
        if url:
            return url

    # ── Fallback generale: prova CONFIG poi MAN_CPR ──────────────────────
    # Usato quando doc_cartella è vuota, "HW + SW", o altro valore non gestito
    if cartella_key:
        log.debug(
            f"  Cartella '{doc_cartella}' non gestita esplicitamente — "
            "tentativo CONFIG poi MAN_CPR"
        )

    url = _build_from_config(sd, doc_id, config_name, page_suffix)
    if url:
        return url

    url = _build_from_man_cpr(sd, doc_id, config_name, page_suffix)
    if url:
        return url

    log.warning(
        f"  ⚠ URL non costruibile:\n"
        f"    doc_id       = '{doc_id}'\n"
        f"    doc_cartella = '{doc_cartella}'\n"
        f"    config_name  = '{config_name}'\n"
        f"    Verifica che il Doc ID esista in CONFIG (col B) o MAN_CPR (col E)"
    )
    return None


def _find_file_code(
    doc_map: dict[str, str],
    config_name: str,
    doc_id: str,
    sheet_name: str,
) -> Optional[str]:
    """
    Cerca il codice file nel dizionario {config_name: file_code}.
    Prima match esatto, poi match parziale.
    """
    if config_name in doc_map:
        return doc_map[config_name]

    for key, code in doc_map.items():
        if config_name in key or key in config_name:
            log.debug(
                f"    Match parziale [{sheet_name}] "
                f"'{config_name}' → '{key}' → '{code}'"
            )
            return code

    log.debug(
        f"    Nessun match [{sheet_name}] per config='{config_name}' "
        f"in doc='{doc_id}'. Chiavi: {list(doc_map.keys())}"
    )
    return None


def _build_from_config(
    sd: SupportData,
    doc_id: str,
    config_name: str,
    page_suffix: str,
) -> Optional[str]:
    """
    Costruisce URL per documenti nel foglio CONFIG.

    Pattern:
        base_url + config_name + "/CONFIG/" + prefix + "/" + file_code + ".pdf" + page_suffix

    dove prefix = parte del doc_id prima del primo "_"
        "FS_DM1"          → "FS"
        "FRS_Brake Control" → "FRS"
        "FPD_xx"          → "FPD"
    """
    if doc_id not in sd.config_map:
        return None

    file_code = _find_file_code(
        sd.config_map[doc_id], config_name, doc_id, "CONFIG"
    )
    if not file_code:
        return None

    prefix = doc_id.split("_")[0] if "_" in doc_id else doc_id

    url = (
        f"{sd.base_url}"
        f"{config_name}/CONFIG/{prefix}/"
        f"{file_code}.pdf{page_suffix}"
    )
    log.debug(f"    URL da CONFIG: {url}")
    return url


def _build_from_man_cpr(
    sd: SupportData,
    doc_id: str,
    config_name: str,
    page_suffix: str,
) -> Optional[str]:
    """
    Costruisce URL per documenti nel foglio MAN_CPR.

    Pattern:
        base_url + "MAN_CPR/" + file_code + ".pdf" + page_suffix
    """
    if doc_id not in sd.man_cpr_map:
        return None

    file_code = _find_file_code(
        sd.man_cpr_map[doc_id], config_name, doc_id, "MAN_CPR"
    )
    if not file_code:
        return None

    url = (
        f"{sd.base_url}"
        f"MAN_CPR/{file_code}.pdf{page_suffix}"
    )
    log.debug(f"    URL da MAN_CPR: {url}")
    return url


def _build_from_simple_folder(
    sd: SupportData,
    doc_id: str,
    doc_cartella: str,
    page_suffix: str,
) -> Optional[str]:
    """
    Costruisce URL per cartelle semplici (DIAGNOSTIC, GENERAL, ecc.)
    dove non c'è un foglio di lookup ma il file si trova direttamente
    nella sottocartella con nome uguale al doc_id.

    Pattern:
        base_url + doc_cartella + "/" + doc_id + ".pdf" + page_suffix

    Esempio:
        DOC CARTELLA = "DIAGNOSTIC", DOC ID = "DIA_Regole"
        → base_url + "DIAGNOSTIC/DIA_Regole.pdf" + #page=N
    """
    if not doc_cartella or not doc_id:
        return None

    url = (
        f"{sd.base_url}"
        f"{doc_cartella}/{doc_id}.pdf{page_suffix}"
    )
    log.debug(f"    URL da cartella semplice '{doc_cartella}': {url}")
    return url


def cell_has_valid_link(ws_data, row: int, col: int, ws_write=None) -> bool:
    """
    Controlla se la cella ha un link valido.

    Strategia a cascata:
    1. Legge ws_data (data_only=True) — valore calcolato da Excel (ideale)
    2. Se None, legge ws_write (data_only=False) — testo della formula/valore scritto
       Utile quando il file non è stato salvato da Excel dopo l'aggiornamento
       delle formule e data_only restituisce None.

    La formula ArrayFormula produce:
        '#Sharepoint//DocID'  → link valido esiste
        '#N/A'                → documento non mappato per questa configurazione
        None                  → cella vuota, nessuna formula
    """
    # ── Strategia 1: data_only ────────────────────────────────────────────
    val = ws_data.cell(row, col).value
    if val is not None:
        s = str(val).strip()
        if not s or s.startswith("#N/A") or s.startswith("#REF") or s.startswith("#VALUE"):
            return False
        return True

    # ── Strategia 2: fallback su ws_write (data_only=False) ──────────────
    if ws_write is not None:
        val_w = ws_write.cell(row, col).value
        if val_w is not None:
            s_w = str(val_w).strip()
            # Salta formule e valori di errore
            if s_w.startswith("=") or s_w.startswith("#N/A") or s_w.startswith("#REF"):
                return False
            # Salta backslash (usato come placeholder per "non disponibile")
            if s_w in ("\\", ""):
                return False
            # Qualsiasi altro valore non-formula indica un link presente
            # (es. '#Sharepoint//DocID' scritto direttamente)
            return True

    return False