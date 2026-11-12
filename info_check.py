"""
info_check.py
-------------
Opzione 4 "Confronto specifico Funzioni-Requisiti": foglio "Info Check".

L'utente sceglie un insieme di funzioni del foglio "Requisiti"; il programma
confronta fra loro SOLO le Description dei requisiti di quelle funzioni e
riporta i requisiti con testo identico o simile, anche se hanno un Nr/ID
diverso o stanno in funzioni diverse.

SORGENTE DEL TESTO (foglio "Requisiti", nessun PDF e nessuna chiamata AI)
  Per ogni riga requisito (col A vuota, col C = Nr requisito) la Description
  si legge dalle colonne configurazione (da col E):
    - "Description: <testo>" + separatore + altri campi  → VZI_Base o FOUND DIFF
    - "MISS VZI_BASE REQ\\n<testo>"                        → unica configurazione
  Le celle "MATCHED" / "MISS VZI_BASE REQ, MATCHED" non contengono testo: se
  la riga non ha altre celle con la Description, il requisito viene elencato
  in fondo al foglio come "non confrontato".

CONFRONTO
  Testi normalizzati (maiuscole, spazi, virgolette, trattini): uguali →
  IDENTICO; altrimenti somiglianza difflib >= CHECK_REQ_SIMILARITY → SIMILE.
  I requisiti collegati (anche indirettamente) formano un gruppo. Le
  Description di una stessa riga (stesso requisito in configurazioni
  diverse) non vengono confrontate fra loro.
"""
from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink

import config as cfg

log = logging.getLogger(__name__)

SHEET_NAME: str = getattr(cfg, "SHEET_INFO_CHECK", "Info Check")
THRESHOLD: float = float(getattr(cfg, "CHECK_REQ_SIMILARITY", 0.85))
IGNORE_TEXTS = {t.strip().lower() for t in
                getattr(cfg, "CHECK_REQ_IGNORE_DESCRIPTIONS", ["DELETED"])}
MIN_CHARS: int = int(getattr(cfg, "CHECK_REQ_MIN_CHARS", 15))

_DESC_LABEL = "Description:"
_SEP_RE = re.compile(r"\n\s*[—\-_]{5,}\s*\n")

FONT_TITLE  = Font(bold=True, size=14)
FONT_BOLD   = Font(bold=True)
FONT_HEADER = Font(bold=True, color="FFFFFFFF")
FONT_IDENT  = Font(bold=True, color="FFC00000")
FONT_SIMIL  = Font(bold=True, color="FFE07000")
FONT_LINK   = Font(color="FF0563C1", underline="single")
FONT_GRAY   = Font(italic=True, color="FF808080")
FILL_HEADER = PatternFill("solid", fgColor="FF1F4E79")
FILL_GROUP  = PatternFill("solid", fgColor="FFF2F2F2")

HEADERS = ["Gruppo", "Esito", "Similarità %", "Funzioni diverse", "Nr diversi",
           "FUNC ID", "Nr requisito", "Configurazioni", "Description",
           "Riga Requisiti"]
WIDTHS  = [9, 12, 13, 15, 12, 38, 42, 30, 90, 15]


@dataclass
class FuncBlock:
    func_id: str
    desc: str
    row: int
    reqs: list = field(default_factory=list)


@dataclass
class ReqEntry:
    func_id: str
    req_id: str
    row: int
    configs: str
    text: str
    norm: str = ""


# ---------------------------------------------------------------------------
# Lettura del foglio Requisiti
# ---------------------------------------------------------------------------

def _s(v) -> str:
    if v is None:
        return ""
    if "formula" in type(v).__name__.lower():
        return ""
    return str(v).strip()


def extract_description(value: str) -> str:
    """Description contenuta in una cella configurazione ("" se assente)."""
    s = (value or "").replace("\r\n", "\n").strip()
    if not s:
        return ""
    idx = s.find(_DESC_LABEL)
    if idx >= 0:
        rest = s[idx + len(_DESC_LABEL):]
        return _SEP_RE.split(rest, maxsplit=1)[0].strip()
    first, _, rest = s.partition("\n")
    if first.strip() == cfg.REQ_TXT_MISS_ONLY and rest.strip():
        if rest.strip().startswith("[Description non estratta"):
            return ""
        return _SEP_RE.split(rest, maxsplit=1)[0].strip()
    return ""


def read_functions(ws) -> list[FuncBlock]:
    """Funzioni (livello 1) del foglio Requisiti con i loro requisiti."""
    blocks: list[FuncBlock] = []
    cur: FuncBlock | None = None
    first_cfg_col = cfg.REQ_CONFIG_COLS_START
    for row in range(cfg.REQ_HEADER_ROW + 1, ws.max_row + 1):
        fid = _s(ws.cell(row, cfg.REQ_FUNC_ID_COL).value)
        if fid:
            cur = FuncBlock(fid, _s(ws.cell(row, cfg.REQ_DESC_COL).value), row)
            blocks.append(cur)
            continue
        req_id = _s(ws.cell(row, cfg.REQ_NUMBER_COL).value)
        if cur is None or not req_id:
            continue
        texts: list[str] = []
        for col in range(first_cfg_col, ws.max_column + 1):
            d = extract_description(_s(ws.cell(row, col).value))
            if d and d not in texts:
                texts.append(d)
        cur.reqs.append((req_id, row,
                         _s(ws.cell(row, cfg.REQ_CONFIG_COL).value), texts))
    return blocks


# ---------------------------------------------------------------------------
# Scelta delle funzioni
# ---------------------------------------------------------------------------

def parse_selection(text: str, blocks: list[FuncBlock]) -> tuple[list[FuncBlock], list[str]]:
    """
    Interpreta la scelta: numeri dell'elenco ("3"), intervalli ("5-8"),
    FUNC ID ("LV_Pantograph_Lifting") o modelli con * e ? ("LV_Pantograph*"),
    separati da virgola, punto e virgola o a capo.
    Restituisce (funzioni scelte nell'ordine del foglio, voci non riconosciute).
    """
    chosen: set[int] = set()
    unknown: list[str] = []
    for tok in re.split(r"[,;\n]+", text or ""):
        tok = tok.strip()
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", tok)
        if m:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            idx = [i - 1 for i in range(a, b + 1) if 1 <= i <= len(blocks)]
            if idx:
                chosen.update(idx)
            else:
                unknown.append(tok)
            continue
        if tok.isdigit():
            i = int(tok) - 1
            if 0 <= i < len(blocks):
                chosen.add(i)
            else:
                unknown.append(tok)
            continue
        low = tok.lower()
        if any(ch in tok for ch in "*?["):
            hits = [i for i, b in enumerate(blocks)
                    if fnmatch.fnmatchcase(b.func_id.lower(), low)]
        else:
            hits = [i for i, b in enumerate(blocks) if b.func_id.lower() == low]
        if hits:
            chosen.update(hits)
        else:
            unknown.append(tok)
    return [blocks[i] for i in sorted(chosen)], unknown


def ask_functions(blocks: list[FuncBlock], default: str = "") -> list[FuncBlock]:
    """Menu interattivo per scegliere le funzioni da confrontare."""
    print("\n" + "=" * 60)
    print("  CONFRONTO SPECIFICO FUNZIONI-REQUISITI — funzioni disponibili")
    print("=" * 60)
    width = len(str(len(blocks)))
    for i, b in enumerate(blocks, 1):
        print(f"  {i:>{width}}) {b.func_id}  ({len(b.reqs)} requisiti)")
    print("\n  Indica le funzioni da confrontare: numeri (1,4,7), intervalli "
          "(5-8),\n  FUNC ID o modelli con * (LV_Pantograph*), separati da virgola.")
    if default:
        print(f"  Invio = funzioni di CHECK_FUNC_IDS: {default}")
    while True:
        try:
            ans = input("\nFunzioni: ").strip()
        except EOFError:
            ans = ""
        if not ans and default:
            ans = default
        sel, unknown = parse_selection(ans, blocks)
        if unknown:
            print(f"  Non riconosciute: {', '.join(unknown)}")
        if sel:
            if unknown:
                try:
                    ok = input("  Procedere con le altre? [S/n]: ").strip().lower()
                except EOFError:
                    ok = ""
                if ok in ("n", "no"):
                    continue
            return sel
        print("  Nessuna funzione selezionata: riprova.")


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'",
                         "`": "'", "–": "-", "—": "-", "\u00a0": " "})


def normalize(text: str) -> str:
    t = (text or "").translate(_QUOTES).lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t.rstrip(" .;:")


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb or 2 * min(la, lb) / (la + lb) < THRESHOLD:
        return 0.0
    sm = SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < THRESHOLD or sm.quick_ratio() < THRESHOLD:
        return 0.0
    return sm.ratio()


@dataclass
class Group:
    members: list[ReqEntry]
    best: dict[int, float]       # indice membro → somiglianza massima

    @property
    def identical(self) -> bool:
        return len({m.norm for m in self.members}) == 1

    @property
    def cross_function(self) -> bool:
        return len({m.func_id for m in self.members}) > 1

    @property
    def different_ids(self) -> bool:
        return len({m.req_id for m in self.members}) > 1


def build_entries(funcs: list[FuncBlock]) -> tuple[list[ReqEntry], list[tuple]]:
    """(requisiti confrontabili, requisiti senza Description)."""
    entries: list[ReqEntry] = []
    missing: list[tuple] = []
    for f in funcs:
        for req_id, row, configs, texts in f.reqs:
            usable = []
            for t in texts:
                n = normalize(t)
                if n in IGNORE_TEXTS or len(n) < MIN_CHARS:
                    continue
                usable.append(ReqEntry(f.func_id, req_id, row, configs, t, n))
            if usable:
                entries.extend(usable)
            elif not texts:
                missing.append((f.func_id, req_id, row, configs))
    return entries, missing


def find_groups(entries: list[ReqEntry]) -> list[Group]:
    """Gruppi di requisiti con Description identica o simile."""
    parent = list(range(len(entries)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    best: dict[int, float] = {}
    for i in range(len(entries)):
        a = entries[i]
        for j in range(i + 1, len(entries)):
            b = entries[j]
            if a.row == b.row:
                continue
            r = similarity(a.norm, b.norm)
            if r >= THRESHOLD:
                best[i] = max(best.get(i, 0.0), r)
                best[j] = max(best.get(j, 0.0), r)
                ri, rj = root(i), root(j)
                if ri != rj:
                    parent[rj] = ri

    clusters: dict[int, list[int]] = {}
    for i in best:
        clusters.setdefault(root(i), []).append(i)

    groups: list[Group] = []
    for idx in clusters.values():
        idx.sort(key=lambda k: (entries[k].row, k))
        if len({entries[k].row for k in idx}) < 2:
            continue
        groups.append(Group([entries[k] for k in idx],
                            {n: best[k] for n, k in enumerate(idx)}))
    groups.sort(key=lambda g: (not g.identical, not g.cross_function,
                               g.members[0].row))
    return groups


# ---------------------------------------------------------------------------
# Scrittura del foglio "Info Check"
# ---------------------------------------------------------------------------

def _prepare_sheet(wb):
    """
    Rigenera il foglio: se esiste lo ricrea nella stessa posizione,
    altrimenti lo crea subito dopo "Index Funzioni" (o in fondo).
    """
    pos = None
    if SHEET_NAME in wb.sheetnames:
        pos = wb.sheetnames.index(SHEET_NAME)
        del wb[SHEET_NAME]
    else:
        index_name = getattr(cfg, "SHEET_INDEX_FUNZIONI", "Index Funzioni")
        if index_name in wb.sheetnames:
            pos = wb.sheetnames.index(index_name) + 1
    return wb.create_sheet(SHEET_NAME, pos)


def _cell(ws, r, c, value, font=None, fill=None):
    cell = ws.cell(r, c, value)
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell


def _link(ws, r, c, req_row: int, req_sheet: str, fill=None):
    cell = _cell(ws, r, c, req_row, FONT_LINK, fill)
    cell.hyperlink = Hyperlink(
        ref=cell.coordinate,
        location=f"'{req_sheet}'!{get_column_letter(cfg.REQ_NUMBER_COL)}{req_row}",
    )
    return cell


def write_sheet(wb, funcs: list[FuncBlock], entries: list[ReqEntry],
                groups: list[Group], missing: list[tuple]) -> None:
    ws = _prepare_sheet(wb)
    req_sheet = cfg.SHEET_REQUISITI
    n_ident = sum(g.identical for g in groups)
    n_cross = sum(g.cross_function for g in groups)

    _cell(ws, 1, 1, "CONFRONTO SPECIFICO FUNZIONI-REQUISITI", FONT_TITLE)
    _cell(ws, 2, 1,
          f"Eseguito il {datetime.now():%d/%m/%Y %H:%M} — confronto delle sole "
          f"Description del foglio '{req_sheet}' — soglia di somiglianza "
          f"{THRESHOLD * 100:.0f}%")
    _cell(ws, 3, 1, f"Funzioni selezionate ({len(funcs)}): "
                    + ", ".join(f.func_id for f in funcs))
    _cell(ws, 4, 1,
          f"Requisiti confrontati: {len({e.row for e in entries})} — gruppi "
          f"trovati: {len(groups)} (identici: {n_ident}, simili: "
          f"{len(groups) - n_ident}) — gruppi tra funzioni diverse: {n_cross}",
          FONT_BOLD)
    for r in range(1, 5):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(HEADERS))

    hr = 6
    for c, (h, w) in enumerate(zip(HEADERS, WIDTHS), 1):
        _cell(ws, hr, c, h, FONT_HEADER, FILL_HEADER)
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = ws.cell(hr + 1, 1)

    r = hr + 1
    if not groups:
        _cell(ws, r, 1, "Nessun requisito con Description identica o simile "
                        "tra le funzioni selezionate.", FONT_GRAY)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(HEADERS))
        r += 1
    for gi, g in enumerate(groups, 1):
        fill = FILL_GROUP if gi % 2 else None
        esito, font = ("IDENTICO", FONT_IDENT) if g.identical else ("SIMILE", FONT_SIMIL)
        cross = "Sì" if g.cross_function else "No"
        diff_ids = "Sì" if g.different_ids else "No"
        for mi, m in enumerate(g.members):
            _cell(ws, r, 1, gi, FONT_BOLD, fill)
            _cell(ws, r, 2, esito, font, fill)
            _cell(ws, r, 3, round(g.best[mi] * 100, 1), None, fill)
            _cell(ws, r, 4, cross, None, fill)
            _cell(ws, r, 5, diff_ids, None, fill)
            _cell(ws, r, 6, m.func_id, None, fill)
            _cell(ws, r, 7, m.req_id, None, fill)
            _cell(ws, r, 8, m.configs, None, fill)
            _cell(ws, r, 9, m.text, None, fill)
            _link(ws, r, 10, m.row, req_sheet, fill)
            r += 1

    if missing:
        r += 1
        _cell(ws, r, 1, f"Requisiti NON confrontati: Description non presente nel "
                        f"foglio '{req_sheet}' (es. '{cfg.REQ_TXT_MISS_MATCHED}')",
              FONT_BOLD)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(HEADERS))
        r += 1
        for func_id, req_id, row, configs in missing:
            _cell(ws, r, 6, func_id, FONT_GRAY)
            _cell(ws, r, 7, req_id, FONT_GRAY)
            _cell(ws, r, 8, configs, FONT_GRAY)
            _link(ws, r, 10, row, req_sheet)
            r += 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(wb, selection: str = "", interactive: bool = True) -> int | None:
    """
    Esegue il confronto e scrive il foglio "Info Check" in 'wb'.
    Restituisce il numero di gruppi trovati, None se non c'e' nulla da fare.
    """
    if cfg.SHEET_REQUISITI not in wb.sheetnames:
        log.error(f"Foglio '{cfg.SHEET_REQUISITI}' non trovato.")
        return None
    blocks = read_functions(wb[cfg.SHEET_REQUISITI])
    if not blocks:
        log.error(f"Nessuna funzione nel foglio '{cfg.SHEET_REQUISITI}'.")
        return None

    default = ", ".join(getattr(cfg, "CHECK_FUNC_IDS", []) or [])
    if selection.strip():
        funcs, unknown = parse_selection(selection, blocks)
    elif interactive:
        funcs, unknown = ask_functions(blocks, default), []
    else:
        funcs, unknown = parse_selection(default, blocks)
    if unknown:
        log.warning(f"  Funzioni non riconosciute (ignorate): {', '.join(unknown)}")
    if not funcs:
        log.error("Nessuna funzione selezionata: indicale con --funcs, con "
                  "CHECK_FUNC_IDS in config.py o dal menu interattivo.")
        return None

    log.info(f"  Funzioni selezionate ({len(funcs)}): "
             + ", ".join(f.func_id for f in funcs))
    entries, missing = build_entries(funcs)
    log.info(f"  Description da confrontare: {len(entries)} "
             f"(senza Description: {len(missing)}) — soglia {THRESHOLD:.2f}")
    groups = find_groups(entries)
    n_ident = sum(g.identical for g in groups)
    log.info(f"  Gruppi trovati: {len(groups)} (identici {n_ident}, simili "
             f"{len(groups) - n_ident}, tra funzioni diverse "
             f"{sum(g.cross_function for g in groups)})")
    write_sheet(wb, funcs, entries, groups, missing)
    log.info(f"  Foglio '{SHEET_NAME}' aggiornato.")
    return len(groups)
