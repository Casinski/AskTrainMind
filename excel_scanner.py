"""
excel_scanner.py
----------------
Scansiona il foglio "Funzioni" riga per riga riconoscendo
la struttura a 3 livelli e raccogliendo le informazioni
necessarie per compilare le celle "Funzioni AI".

STRUTTURA DEL FOGLIO AGGIORNATA (3 livelli verticali):

  LIVELLO 1 — Riga funzione
    Col A (FUNC ID)             : "Park_Brake_01"
    Col B (DESCRIZIONE FUNZIONE): "Comando applicazione/rilascio FAM..."
    Col C (DOC CARTELLA)        : None (vuota nelle righe di livello 1)
    Col D (DOC ID)              : formula =IF($A...) — link all'oggetto
    → identifica l'oggetto funzione principale

  LIVELLO 2 — Riga documento
    Col A: vuota
    Col B: vuota  (o testo secondario)
    Col C (DOC CARTELLA): "CONFIG" | "MAN_CPR" | "DIAGNOSTIC" | "GENERAL" | ...
                          → indica in quale foglio/cartella cercare il documento
    Col D (DOC ID)      : "FS_DM1" | "FRS_Brake Control" | "PBC_01A" | ...
                          → identificatore del documento
    Col E (Info DOC)    : "Link"
    Col F-L (config)    : valore calcolato "#Sharepoint//DocID" se link esiste,
                          "#N/A" se non mappato, None se vuoto
    → identifica il documento e la cartella di appartenenza

  LIVELLO 3 — Righe dettaglio
    Col E (label): "Rif. Pagina" | "Componenti circuito elettrico" |
                   "Descrizione circuitale" | "Requisiti specifici" |
                   "Funzioni AI" | "Pagina" | "Descrizione" | ...
    Col F-L (valori): uno per ogni configurazione
    → dettagli dell'oggetto per ogni configurazione

NOTA sulla colonna C (DOC CARTELLA):
  Il valore di C indica quale foglio di supporto usare per costruire l'URL:
    "CONFIG"     → url_builder usa sd.config_map   (foglio CONFIG)
    "MAN_CPR"    → url_builder usa sd.man_cpr_map  (foglio MAN_CPR)
    "DIAGNOSTIC" → url_builder costruisce URL con cartella DIAGNOSTIC/
    "GENERAL"    → url_builder costruisce URL con cartella GENERAL/
    Altro/None   → tentativo con CONFIG poi MAN_CPR (fallback)
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Iterator

import config as cfg
from support_loader import SupportData
import url_builder

log = logging.getLogger(__name__)


@dataclass
class FillTarget:
    """
    Rappresenta una singola cella "Funzioni AI" da compilare.
    Contiene tutto il necessario per trovare il documento,
    estrarre il testo e generare la sintesi.
    """
    func_id: str
    func_desc: str
    doc_id: str
    doc_cartella: str    # ← NUOVO: valore colonna C (es. "CONFIG", "MAN_CPR", ...)
    config_name: str
    row: int
    col: int
    url: str
    page_number: int


def scan(
    ws_write,
    ws_data,
    sd: SupportData,
) -> Iterator[FillTarget]:
    """
    Generatore: scansiona il foglio Funzioni e produce un FillTarget
    per ogni cella "Funzioni AI" vuota che ha un link disponibile.
    """
    # ── Leggi intestazioni riga 1 ─────────────────────────────────────────
    col_map    = _build_header_map(ws_write)
    id_col     = col_map.get("id", 1)           # Col A: FUNC ID
    label_col  = col_map.get("funzione", 2)      # Col B: DESCRIZIONE FUNZIONE
    cart_col   = col_map.get("doc_cartella", 3)  # Col C: DOC CARTELLA ← NUOVO
    doc_id_col = col_map.get("doc_id", 4)        # Col D: DOC ID
    info_col   = col_map.get("info_doc", 5)      # Col E: Info DOC
    gen_col    = ws_write.max_column

    config_cols: list[int] = list(range(info_col + 1, gen_col))
    config_names: dict[int, str] = {
        col: (
            str(ws_write.cell(1, col).value).strip().replace("\n", " / ")
            if ws_write.cell(1, col).value else f"CONF_{col}"
        )
        for col in config_cols
    }

    log.info(
        f"Struttura foglio rilevata:\n"
        f"  FUNC ID={id_col}, DESCRIZIONE={label_col}, "
        f"DOC CARTELLA={cart_col}, DOC ID={doc_id_col}, Info={info_col}\n"
        f"  Configurazioni ({len(config_cols)}): "
        f"{list(config_names.values())}"
    )

    # ── Stato della scansione ─────────────────────────────────────────────
    func_id:   str = ""
    func_desc: str = ""
    doc_id:    str = ""
    doc_cartella: str = ""   # ← NUOVO
    doc_row:   int = 0
    configs_with_link: set[str] = set()
    rif_pagina: dict[str, str] = {}

    # ── Scansione riga per riga ───────────────────────────────────────────
    for row in range(2, ws_write.max_row + 1):
        v_id    = _cell_str(ws_write, row, id_col)
        v_label = _cell_str(ws_write, row, label_col)
        v_cart  = _cell_str(ws_write, row, cart_col)   # ← NUOVO
        v_doc   = _cell_str(ws_write, row, doc_id_col)
        v_info  = _cell_str(ws_write, row, info_col)

        # ── LIVELLO 1: nuova funzione ─────────────────────────────────────
        # Identificato da: Col A non vuota E Col B non vuota
        # Col C è None nelle righe di primo livello
        if v_id and v_label and not v_cart:
            func_id   = v_id
            func_desc = v_label
            doc_id    = ""
            doc_cartella = ""
            doc_row   = 0
            configs_with_link = set()
            rif_pagina = {}
            continue

        if not func_id:
            continue

        # ── LIVELLO 2: nuovo documento ────────────────────────────────────
        # Identificato da: Col C non vuota (DOC CARTELLA) E Col D non vuota (DOC ID)
        # Col E = "Link" nella riga di secondo livello
        if v_cart and v_doc and v_doc not in ("\\", ""):
            doc_id       = v_doc
            doc_cartella = v_cart   # ← NUOVO: salva la cartella di appartenenza
            doc_row      = row
            configs_with_link = set()
            rif_pagina = {}

            count = 0
            for col in config_cols:
                if url_builder.cell_has_valid_link(ws_data, row, col):
                    configs_with_link.add(config_names[col])
                    count += 1

            log.info(
                f"  Doc '{doc_id}' [cartella: {doc_cartella}] (riga {row}): "
                f"{count}/{len(config_cols)} configurazioni con link"
            )
            continue

        # ── LIVELLO 3: righe dettaglio ────────────────────────────────────
        if v_info and doc_id:
            label_lower = v_info.lower().strip()

            # Salva Rif. Pagina (gestisce anche la label "Pagina" oltre a "Rif. Pagina")
            if label_lower.startswith("rif") or label_lower == "pagina":
                for col in config_cols:
                    val = _cell_str(ws_write, row, col)
                    if val:
                        rif_pagina[config_names[col]] = val
                continue

            # ── RIGA "Funzioni AI" ────────────────────────────────────────
            if v_info.strip() == cfg.FUNZIONI_AI_LABEL:
                log.info(
                    f"\n{'─' * 55}\n"
                    f"  FUNZIONE    : {func_id} — {func_desc[:50]}\n"
                    f"  DOCUMENTO   : {doc_id}\n"
                    f"  DOC CARTELLA: {doc_cartella}\n"   # ← NUOVO nel log
                    f"  RIGA Doc    : {doc_row} | RIGA AI: {row}\n"
                    f"{'─' * 55}"
                )

                for col in config_cols:
                    cname = config_names[col]

                    if _cell_str(ws_write, row, col):
                        log.info(f"  [{cname}] già compilata — skip")
                        continue

                    if cname not in configs_with_link:
                        log.info(f"  [{cname}] nessun link — skip")
                        continue

                    rif_raw     = rif_pagina.get(cname, "")
                    page_number = _parse_page(rif_raw)

                    # ← NUOVO: passa doc_cartella a url_builder
                    url = url_builder.build(
                        sd, doc_id, cname, page_number,
                        doc_cartella=doc_cartella
                    )
                    if not url:
                        log.warning(f"  [{cname}] URL non costruibile — skip")
                        continue

                    log.info(
                        f"  [{cname}]\n"
                        f"    URL    : {url}\n"
                        f"    Pagina : {rif_raw!r} → {page_number}"
                    )

                    yield FillTarget(
                        func_id=func_id,
                        func_desc=func_desc,
                        doc_id=doc_id,
                        doc_cartella=doc_cartella,   # ← NUOVO
                        config_name=cname,
                        row=row,
                        col=col,
                        url=url,
                        page_number=page_number,
                    )


# ---------------------------------------------------------------------------
# Helpers interni
# ---------------------------------------------------------------------------

def _cell_str(ws, row: int, col: int) -> str:
    """Restituisce il valore stringa di una cella, mai None."""
    val = ws.cell(row, col).value
    if val is None:
        return ""
    type_name = type(val).__name__
    if "Formula" in type_name or "formula" in type_name:
        return ""
    return str(val).strip()


def _build_header_map(ws) -> dict[str, int]:
    """
    Costruisce una mappa {nome_normalizzato: col_index} dalle intestazioni
    della riga 1.
    """
    raw_map: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        val = ws.cell(1, col).value
        if not val:
            continue
        key = str(val).strip().lower().replace("\n", " ")
        raw_map[key] = col

    return {
        "id":           raw_map.get("func id",
                        raw_map.get("id", 1)),
        "funzione":     raw_map.get("descrizione funzione",
                        raw_map.get("funzione", 2)),
        "doc_cartella": raw_map.get("doc cartella",
                        raw_map.get("doc\ncartella", 3)),   # ← NUOVO
        "doc_id":       raw_map.get("doc id", 4),
        "info_doc":     raw_map.get("info doc", 5),
    }


def _parse_page(value: str) -> int:
    """
    Estrae il primo numero intero dal campo Rif. Pagina.
    Esempi: '276' → 276 | 'pag. 12' → 12 | '12-14' → 12 | '' → 0
    """
    import re
    if not value:
        return 0
    numbers = re.findall(r"\d+", str(value))
    return int(numbers[0]) if numbers else 0