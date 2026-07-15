"""
excel_scanner.py
----------------
Scansiona il foglio "Funzioni" riga per riga riconoscendo
la struttura a 3 livelli e raccogliendo le informazioni
necessarie per compilare le celle "Funzioni AI".

STRUTTURA DEL FOGLIO (3 livelli verticali):

  LIVELLO 1 — Riga funzione principale
    Col A (FUNC ID): "Park_Brake_01"  ← DISCRIMINATORE: col A non vuota
    Col B (DESCRIZIONE FUNZIONE): testo
    Col C (DOC CARTELLA): può essere vuota O contenere "HW + SW" ecc.
    Col D (DOC ID): formula link oppure "\\"

  LIVELLO 2 — Riga documento
    Col A: VUOTA  ← discriminatore principale
    Col C (DOC CARTELLA): "CONFIG" | "MAN_CPR" | "DIAGNOSTIC" | "GENERAL"
    Col D (DOC ID): "FS_DM1" | "FRS_Brake Control" | ...
    Col E (Info DOC): "Link"

  LIVELLO 3 — Righe dettaglio
    Col A: vuota, Col C: vuota
    Col E (label): "Rif. Pagina" | "Funzioni AI" | "Componenti" | ...

PARAMETRO start_from_func_id:
  Se valorizzato, tutte le funzioni con FUNC ID precedente a quello
  indicato vengono saltate (non processate). Dalla funzione indicata
  in poi il comportamento è normale.
  Utile per riprendere l'elaborazione da un punto specifico o per
  testare una singola funzione senza rielaborare tutto il foglio.
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
    """
    func_id: str
    func_desc: str
    doc_id: str
    doc_cartella: str
    config_name: str
    row: int
    col: int
    url: str
    page_number: int
    page_number_end: int = 0
    start_is_partial: bool = False
    end_is_partial: bool   = False


def scan(
    ws_write,
    ws_data,
    sd: SupportData,
    start_from_func_id: str = "",
) -> Iterator[FillTarget]:
    """
    Generatore: scansiona il foglio Funzioni e produce un FillTarget
    per ogni cella "Funzioni AI" vuota che ha un link disponibile.

    Args:
        ws_write          : foglio aperto con data_only=False (lettura + scrittura)
        ws_data           : foglio aperto con data_only=True (valori calcolati)
        sd                : dati dai fogli di supporto (Cartelle, CONFIG, MAN_CPR)
        start_from_func_id: FUNC ID da cui iniziare l'elaborazione.
                            - Se vuoto ("") → elabora tutto il foglio dall'inizio.
                            - Se valorizzato → salta tutte le funzioni precedenti
                              a quella indicata; dalla funzione indicata procede
                              normalmente fino alla fine del foglio.
                            - Se il FUNC ID non viene trovato nel foglio, viene
                              emesso un warning e si elabora tutto il foglio.
    """
    # ── Leggi intestazioni riga 1 ─────────────────────────────────────────
    col_map    = _build_header_map(ws_write)
    id_col     = col_map.get("id", 1)
    label_col  = col_map.get("funzione", 2)
    cart_col   = col_map.get("doc_cartella", 3)
    doc_id_col = col_map.get("doc_id", 4)
    info_col   = col_map.get("info_doc", 5)
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

    # ── Gestione parametro start_from_func_id ────────────────────────────
    # Se valorizzato, lo scanner entra in modalità "attesa":
    # ignora tutto finché non trova la riga con FUNC ID == start_from_func_id,
    # poi passa in modalità "attiva" e procede normalmente.
    waiting_for_start = bool(start_from_func_id.strip())
    start_target      = start_from_func_id.strip()

    if waiting_for_start:
        log.info(
            f"⏩ Modalità partenza da funzione specificata: '{start_target}'\n"
            f"   Tutte le funzioni precedenti verranno saltate."
        )
    else:
        log.info("▶ Elaborazione dall'inizio del foglio.")

    # ── Stato della scansione ─────────────────────────────────────────────
    func_id:      str = ""
    func_desc:    str = ""
    doc_id:       str = ""
    doc_cartella: str = ""
    doc_row:      int = 0
    configs_with_link: set[str] = set()
    rif_pagina:   dict[str, str] = {}

    # ── Scansione riga per riga ───────────────────────────────────────────
    for row in range(2, ws_write.max_row + 1):
        v_id   = _cell_str(ws_write, row, id_col)
        v_cart = _cell_str(ws_write, row, cart_col)
        v_doc  = _cell_str(ws_write, row, doc_id_col)
        v_info = _cell_str(ws_write, row, info_col)

        # ── LIVELLO 1: nuova funzione ─────────────────────────────────────
        # DISCRIMINATORE: col A (FUNC ID) non vuota.
        if v_id:
            func_id      = v_id
            func_desc    = _cell_str(ws_write, row, label_col)
            doc_id       = ""
            doc_cartella = ""
            doc_row      = 0
            configs_with_link = set()
            rif_pagina   = {}

            # Controlla se questa è la funzione di partenza
            if waiting_for_start:
                if func_id == start_target:
                    # Funzione trovata: passa in modalità attiva
                    waiting_for_start = False
                    log.info(
                        f"✅ Funzione di partenza trovata: '{func_id}' "
                        f"(riga {row}) — elaborazione attivata."
                    )
                else:
                    # Ancora in attesa: logga solo a DEBUG per non inquinare il log
                    log.debug(f"  ⏩ Skip funzione (precedente al punto di partenza): '{func_id}'")
            continue

        # Se non abbiamo ancora una funzione, ignora la riga
        if not func_id:
            continue

        # Se siamo ancora in attesa della funzione di partenza,
        # salta tutte le righe di questa funzione (livelli 2 e 3)
        if waiting_for_start:
            continue

        # ── LIVELLO 2: nuovo documento ────────────────────────────────────
        # DISCRIMINATORE: col A vuota E col C non vuota E col D valida
        INVALID_DOC = {"", "\\", "/", "tbd"}
        if v_cart and v_doc and v_doc.strip() not in INVALID_DOC:
            doc_id       = v_doc
            doc_cartella = v_cart
            doc_row      = row
            configs_with_link = set()
            rif_pagina   = {}

            count = 0
            for col in config_cols:
                # Passa ws_write come fallback quando data_only restituisce None
                if url_builder.cell_has_valid_link(ws_data, row, col, ws_write=ws_write):
                    configs_with_link.add(config_names[col])
                    count += 1

            log.info(
                f"  Doc '{doc_id}' [cartella: {doc_cartella}] (riga {row}): "
                f"{count}/{len(config_cols)} configurazioni con link"
            )
            continue

        # ── LIVELLO 3: righe dettaglio ────────────────────────────────────
        # DISCRIMINATORE: col A vuota, col C vuota, col E non vuota
        if v_info and doc_id and not v_cart:
            label_lower = v_info.lower().strip()

            # Rif. Pagina (anche "Pagina" semplice)
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
                    f"  DOC CARTELLA: {doc_cartella}\n"
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
                        doc_cartella=doc_cartella,
                        config_name=cname,
                        row=row,
                        col=col,
                        url=url,
                        page_number=page_number,
                    )

    # Avviso se il FUNC ID di partenza non è mai stato trovato
    if waiting_for_start:
        log.warning(
            f"⚠ Funzione di partenza '{start_target}' NON trovata nel foglio.\n"
            f"  Verifica che il FUNC ID corrisponda esattamente al valore "
            f"nella colonna A del foglio '{cfg.SHEET_FUNZIONI}'.\n"
            f"  Nessuna cella è stata elaborata."
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
                        raw_map.get("doc\ncartella", 3)),
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