"""
requisiti_sorter.py
-------------------
Riordina il foglio "Requisiti" secondo l'ordine delle funzioni del foglio
"Funzioni" (colonna A, FUNC ID): prima tutte le funzioni LV, poi AUX, BAT,
AIR, ... esattamente come compaiono nel foglio Funzioni.

Il foglio Requisiti e' fatto di BLOCCHI:
    riga funzione  (col A = FUNC ID, col B = descrizione)
    righe requisito sotto di essa (col A vuota)
Ogni blocco viene spostato per intero; l'ordine dei requisiti all'interno
del blocco non cambia.

Funzioni presenti in Requisiti ma non in Funzioni: vengono messe in coda al
gruppo con lo stesso prefisso (es. "LV_..." dopo l'ultima funzione LV); se
il prefisso non esiste in Funzioni finiscono in fondo al foglio, nell'ordine
in cui si trovavano.

Il foglio viene RICOSTRUITO: valori, stili, commenti, link e altezze di riga
vengono riscritti nell'ordine nuovo, le righe completamente vuote fra i
blocchi vengono eliminate e il filtro automatico aggiornato.
"""
from __future__ import annotations

import logging
from copy import copy

from openpyxl.utils import get_column_letter

import config as cfg

log = logging.getLogger(__name__)


def _s(v) -> str:
    if v is None:
        return ""
    t = type(v).__name__
    if "Formula" in t or "formula" in t:
        return ""
    return str(v).strip()


def norm_id(s: str) -> str:
    return " ".join((s or "").split()).lower()


def func_prefix(func_id: str) -> str:
    """Prefisso del FUNC ID: 'LV' per 'LV_Pantograph_Lifting'."""
    s = norm_id(func_id)
    return s.split("_", 1)[0] if "_" in s else s


def funzioni_order(ws_funz) -> list[str]:
    """FUNC ID (col A) del foglio Funzioni nell'ordine in cui compaiono."""
    out: list[str] = []
    seen: set[str] = set()
    for row in range(2, ws_funz.max_row + 1):
        fid = _s(ws_funz.cell(row, 1).value)
        if fid and norm_id(fid) not in seen:
            seen.add(norm_id(fid))
            out.append(fid)
    return out


def order_positions(func_ids: list[str], order: list[str]) -> list[int]:
    """
    Indici di func_ids nel nuovo ordine.

    func_ids  FUNC ID dei blocchi del foglio Requisiti, nell'ordine attuale
    order     FUNC ID del foglio Funzioni, nell'ordine desiderato
    """
    pos = {norm_id(f): i for i, f in enumerate(order)}
    last_of_prefix: dict[str, int] = {}
    for i, f in enumerate(order):
        last_of_prefix[func_prefix(f)] = i

    def key(i: int) -> tuple:
        f = norm_id(func_ids[i])
        if f in pos:
            return (pos[f], 0, i)
        p = func_prefix(f)
        if p in last_of_prefix:
            return (last_of_prefix[p], 1, i)
        return (len(order), 1, i)

    return sorted(range(len(func_ids)), key=key)


def _row_empty(ws, row: int, max_col: int) -> bool:
    return not any(_s(ws.cell(row, c).value) for c in range(1, max_col + 1))


def _last_content_row(ws, header_row: int, max_col: int) -> int:
    for row in range(ws.max_row, header_row, -1):
        if not _row_empty(ws, row, max_col):
            return row
    return header_row


def read_blocks(ws, header_row: int | None = None,
                func_col: int | None = None) -> tuple[list[int], list[tuple[str, list[int]]]]:
    """
    (righe di testa senza funzione, [(func_id, [righe del blocco]), ...]).
    Le righe completamente vuote vengono scartate.
    """
    header_row = header_row or cfg.REQ_HEADER_ROW
    func_col = func_col or cfg.REQ_FUNC_ID_COL
    max_col = ws.max_column
    last = _last_content_row(ws, header_row, max_col)
    head: list[int] = []
    blocks: list[tuple[str, list[int]]] = []
    for row in range(header_row + 1, last + 1):
        fid = _s(ws.cell(row, func_col).value)
        if fid:
            blocks.append((fid, [row]))
        elif _row_empty(ws, row, max_col):
            continue
        elif blocks:
            blocks[-1][1].append(row)
        else:
            head.append(row)
    return head, blocks


def sort_sheet(ws_req, ws_funz) -> bool:
    """
    Riordina e ricostruisce il foglio Requisiti. Ritorna True se il foglio
    e' stato modificato.
    """
    header_row = cfg.REQ_HEADER_ROW
    max_col = ws_req.max_column
    head, blocks = read_blocks(ws_req)
    if not blocks:
        return False
    order = funzioni_order(ws_funz)
    perm = order_positions([b[0] for b in blocks], order)

    new_rows: list[int] = list(head)
    for i in perm:
        new_rows.extend(blocks[i][1])
    old_rows = list(range(header_row + 1, header_row + 1 + len(new_rows)))
    last_old = _last_content_row(ws_req, header_row, max_col)
    if new_rows == old_rows and last_old == old_rows[-1]:
        log.info(f"  [Requisiti] Foglio gia' ordinato come '{ws_funz.title}'.")
        return False

    # Fotografia delle righe da spostare (valori, stili, link, commenti)
    snap = []
    for r in new_rows:
        cells = []
        for c in range(1, max_col + 1):
            cell = ws_req.cell(r, c)
            cells.append((
                cell._value, cell.data_type, copy(cell._style),
                copy(cell.hyperlink) if cell.hyperlink else None,
                copy(cell.comment) if cell.comment else None,
            ))
        rd = ws_req.row_dimensions[r]
        snap.append((cells, rd.height, rd.hidden, rd.outlineLevel))

    # Riscrittura nell'ordine nuovo, poi pulizia delle righe in eccesso
    default_style = copy(ws_req.cell(last_old + 1, 1)._style)
    for k, (cells, height, hidden, level) in enumerate(snap):
        r = header_row + 1 + k
        for c, (val, dtype, style, link, comment) in enumerate(cells, start=1):
            cell = ws_req.cell(r, c)
            cell._value = val
            cell.data_type = dtype
            cell._style = style
            cell.hyperlink = link
            cell.comment = comment
        rd = ws_req.row_dimensions[r]
        rd.height, rd.hidden, rd.outlineLevel = height, hidden, level

    new_last = header_row + len(snap)
    for r in range(new_last + 1, last_old + 1):
        for c in range(1, max_col + 1):
            cell = ws_req.cell(r, c)
            cell.value = None
            cell.hyperlink = None
            cell.comment = None
            cell._style = copy(default_style)
        rd = ws_req.row_dimensions[r]
        rd.height, rd.hidden, rd.outlineLevel = None, False, 0

    if ws_req.auto_filter.ref:
        ws_req.auto_filter.ref = f"A{header_row}:{get_column_letter(max_col)}{new_last}"

    spostate = sum(1 for k, i in enumerate(perm) if k != i)
    log.info(
        f"  [Requisiti] Foglio riordinato come '{ws_funz.title}': "
        f"{len(blocks)} funzioni ({spostate} spostate), "
        f"{last_old - new_last} righe vuote eliminate."
    )
    return True
