"""
confronto_reqs.py
-----------------
Opzione 4 "CONFRONTO SPECIFICO FUNZIONI-REQUISITI": foglio "Confronto Reqs".

L'utente sceglie uno o piu' DOC ID del foglio CONFIG (es. "FRS_Coupler").
Per ogni DOC ID:

1. DOCUMENTI — dalla riga del DOC ID in CONFIG si ricava, per ogni
   configurazione (VZI_Base, VZI_New14, VZ_FR, ...), il codice del documento
   e lo si cerca in ONEDRIVE_DOCS_ROOT (stessa ricerca dell'opzione 2).
2. REQUISITI — da ogni documento si estraggono TUTTI i requisiti (tabelle
   orizzontali con colonna "Nr" e blocchi verticali con campo "ID", vedi
   requirements_extractor.py) con il relativo campo Description.
3. CONFRONTO — ogni requisito viene cercato negli altri documenti in base
   alla Description (uguale ignorando maiuscole, spazi, virgolette e
   trattini). Per ogni configurazione:
     MATCHED               stessa Description, stesso Nr/ID
     MATCHED DIFFERENT ID  stessa Description sotto un Nr/ID diverso
                           (il Nr/ID della configurazione e' scritto sotto)
     MISS                  nessun requisito con la stessa Description
     N/A                   la configurazione non ha il documento
4. FOGLIO "Confronto Reqs" — rigenerato a ogni esecuzione: una riga per
   requisito (Nr/ID, campo di provenienza "Nr"/"ID", Description) e una
   colonna per configurazione con l'esito.

Non usa Ollama: il confronto e' solo testuale.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import config as cfg
import index_funzioni
import interrupt_guard
import requirements_extractor
from requirements_extractor import id_key

log = logging.getLogger(__name__)

SHEET_NAME: str = getattr(cfg, "SHEET_CONFRONTO_REQS", "Confronto Reqs")
BASE_CONFIG: str = getattr(cfg, "REQ_BASE_CONFIG", "VZI_Base")
IGNORE_TEXTS = {t.strip().lower() for t in
                getattr(cfg, "CONFRONTO_REQS_IGNORE_DESCRIPTIONS", ["DELETED"])}

TXT_MATCHED = "MATCHED"
TXT_DIFF_ID = "MATCHED DIFFERENT ID"
TXT_MISS    = "MISS"
TXT_NA      = "N/A"

COL_REQ, COL_FIELD, COL_DESC, FIRST_CFG_COL = 1, 2, 3, 4

FONT_HEADER = Font(bold=True, color="FFFFFFFF")
FILL_HEADER = PatternFill("solid", fgColor="FF1F4E79")
FONT_DOC    = Font(bold=True, size=12)
FILL_DOC    = PatternFill("solid", fgColor="FFD9E1F2")
FONT_INFO   = Font(italic=True, color="FF808080")
FONT_STATUS = {
    TXT_MATCHED: Font(bold=True, color="FF008000"),
    TXT_DIFF_ID: Font(bold=True, color="FFE07000"),
    TXT_MISS:    Font(bold=True, color="FFC00000"),
    TXT_NA:      Font(italic=True, color="FF808080"),
}


# ---------------------------------------------------------------------------
# Modello dati
# ---------------------------------------------------------------------------

@dataclass
class DocReqs:
    """Documento di UNA configurazione per il DOC ID scelto."""
    code: str = ""
    note: str = ""
    path: Optional[Path] = None
    status: str = ""            # ok | no_code | missing | not_found
    reqs: list = field(default_factory=list)

    def label(self) -> str:
        if self.status == "ok":
            return f"{self.code} ({len(self.reqs)} requisiti)"
        if self.status == "no_code":
            return self.code or "\\"
        reason = {"missing": index_funzioni.MISSING_NOTE,
                  "not_found": "file non trovato"}.get(self.status, self.status)
        return f"{self.code} ({reason})"


@dataclass
class Cell:
    status: str
    req_id: str = ""            # Nr/ID del requisito nella configurazione
    note: str = ""              # commento della cella


@dataclass
class ReqRow:
    req_id: str
    field_name: str             # "Nr" (tabella orizzontale) o "ID" (verticale)
    description: str
    origin: str                 # configurazione da cui proviene il requisito
    cells: dict = field(default_factory=dict)   # {config: Cell}

    def all_matched(self) -> bool:
        return all(c.status in (TXT_MATCHED, TXT_NA) for c in self.cells.values())


# ---------------------------------------------------------------------------
# Foglio CONFIG
# ---------------------------------------------------------------------------

def read_doc_ids(ws) -> list[str]:
    """DOC ID del foglio CONFIG (col B) nell'ordine del foglio, senza doppioni."""
    out, seen = [], set()
    for r in range(2, ws.max_row + 1):
        v = index_funzioni._str(ws.cell(r, 2).value)
        if v and v.lower() not in ("doc id",) and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def read_doc_row(ws, doc_id: str, groups) -> dict[str, tuple[str, str]]:
    """
    {configurazione: (codice, nota)} del DOC ID. Se il DOC ID compare su piu'
    righe (es. FRS_Train Protection) si usa, per ogni configurazione, la
    prima riga con un codice valido.
    """
    data: dict[str, tuple[str, str]] = {}
    for r in range(2, ws.max_row + 1):
        if index_funzioni._str(ws.cell(r, 2).value).lower() != doc_id.lower():
            continue
        for cname, value in index_funzioni.config_row_data(ws, r, groups).items():
            if cname not in data or not index_funzioni._codes(data[cname][0]):
                data[cname] = value
    return data


def resolve_selection(text: str, doc_ids: list[str]) -> tuple[list[str], list[str]]:
    """
    Voci separate da virgola: numero dell'elenco, DOC ID (maiuscole
    ignorate) o parte univoca del DOC ID. Ritorna (scelti, non_riconosciuti).
    """
    chosen, unknown = [], []
    for tok in (t.strip() for t in (text or "").split(",")):
        if not tok:
            continue
        found = None
        if tok.isdigit() and 1 <= int(tok) <= len(doc_ids):
            found = doc_ids[int(tok) - 1]
        else:
            exact = [d for d in doc_ids if d.lower() == tok.lower()]
            part = [d for d in doc_ids if tok.lower() in d.lower()]
            found = exact[0] if exact else (part[0] if len(part) == 1 else None)
        if found is None:
            unknown.append(tok)
        elif found not in chosen:
            chosen.append(found)
    return chosen, unknown


def ask_doc_ids(doc_ids: list[str], default: str = "") -> str:
    print("\n" + "=" * 60)
    print("  CONFRONTO REQUISITI — DOC ID disponibili (foglio CONFIG)")
    print("=" * 60)
    for i, d in enumerate(doc_ids, 1):
        print(f"  {i:3d}) {d}")
    hint = f" [Invio = {default}]" if default else ""
    try:
        ans = input(f"\nDOC ID da confrontare (numeri o nomi separati da virgola){hint}: ")
    except EOFError:
        ans = ""
    return ans.strip() or default


# ---------------------------------------------------------------------------
# Estrazione requisiti
# ---------------------------------------------------------------------------

_doc_cache: dict[str, list] = {}


def extract_document(path: Path, config_name: str) -> list:
    """Tutti i requisiti del documento (tabelle + testo lineare, come l'opzione 1)."""
    key = str(path).lower()
    if key not in _doc_cache:
        reqs: list = []
        if path.suffix.lower() == ".pdf":
            import fitz
            with fitz.open(str(path)) as pdf:
                n_pages = pdf.page_count
                text = "\n".join(f"[Pagina {i}]\n{page.get_text()}"
                                  for i, page in enumerate(pdf, 1))
            reqs = requirements_extractor.extract_from_tables(
                doc_path=path, page_start=1, page_end=n_pages,
                config_name=config_name)
            seen = {r.key() for r in reqs}
            for r in requirements_extractor.extract(text=text, config_name=config_name):
                if r.key() not in seen:
                    seen.add(r.key())
                    reqs.append(r)
        else:
            log.warning(f"  [{config_name}] {path.name}: formato non supportato "
                        f"(solo PDF)")
        _doc_cache[key] = reqs
    return _doc_cache[key]


def load_documents(doc_id: str, data: dict, configs: list[str]) -> dict[str, DocReqs]:
    prefix = doc_id.split("_")[0] if "_" in doc_id else "FRS"
    out: dict[str, DocReqs] = {}
    for cname in configs:
        raw, note = data.get(cname, ("", ""))
        res = DocReqs(code=raw.replace("\n", " / "), note=note)
        codes = index_funzioni._codes(raw)
        if not codes:
            res.status = "no_code"
            out[cname] = res
            continue
        for code in codes:
            p = index_funzioni.find_file(code, cname, prefix)
            if p:
                res.path, res.code = p, code
                break
        if res.path is None:
            noted = index_funzioni.MISSING_NOTE.lower() in note.lower()
            res.status = "missing" if noted else "not_found"
            log.info(f"  [{cname}] {raw!r}: "
                     f"{'segnato ' + index_funzioni.MISSING_NOTE if noted else 'file non trovato'}")
        else:
            res.status = "ok"
            res.reqs = extract_document(res.path, cname)
            log.info(f"  [{cname}] {res.path.name}: {len(res.reqs)} requisiti")
        out[cname] = res
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                         "\u2013": "-", "\u2014": "-", "\u00a0": " "})


def desc_key(text: str) -> str:
    """Chiave di confronto della Description ('' = non confrontabile)."""
    s = (text or "").translate(_QUOTES).lower()
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s).strip(" .;:")
    s = re.sub(r"\s+([,.;:)])", r"\1", s)
    if not s or s in IGNORE_TEXTS:
        return ""
    return s


def field_name(req) -> str:
    return "Nr" if getattr(req, "layout", "") == "H" else "ID"


def compare(docs: dict[str, DocReqs], configs: list[str]) -> list[ReqRow]:
    """
    Una riga per requisito. Le configurazioni sono scorse a partire da
    VZI_Base: ogni requisito non ancora assegnato apre una riga e viene
    cercato negli altri documenti per Description (a parita' di Description
    si preferisce lo stesso Nr/ID). Un requisito di un documento viene
    assegnato a una sola riga. Le Description vuote o in
    CONFRONTO_REQS_IGNORE_DESCRIPTIONS (es. "DELETED") si confrontano per Nr/ID.
    """
    ok = [c for c in configs if docs.get(c) and docs[c].status == "ok"]
    order = sorted(ok, key=lambda c: c.lower() != BASE_CONFIG.lower())
    used = {c: set() for c in ok}

    def candidates(cname: str, req):
        dk = desc_key(req.description)
        for i, r in enumerate(docs[cname].reqs):
            if i in used[cname]:
                continue
            if dk and desc_key(r.description) == dk:
                yield i, r
            elif not dk and r.key() == req.key():
                yield i, r

    rows: list[ReqRow] = []
    for cname in order:
        for i, req in enumerate(docs[cname].reqs):
            if i in used[cname]:
                continue
            used[cname].add(i)
            row = ReqRow(req.req_id, field_name(req), req.description, cname)
            for other in configs:
                if other == cname:
                    row.cells[other] = Cell(TXT_MATCHED, req.req_id)
                    continue
                if other not in used:
                    row.cells[other] = Cell(TXT_NA)
                    continue
                found = sorted(candidates(other, req),
                               key=lambda ir: ir[1].key() != req.key())
                if not found:
                    same_id = [r for r in docs[other].reqs if r.key() == req.key()]
                    note = ("Nr/ID presente con Description diversa"
                            if same_id and desc_key(req.description) else "")
                    row.cells[other] = Cell(TXT_MISS, note=note)
                    continue
                j, match = found[0]
                used[other].add(j)
                status = TXT_MATCHED if match.key() == req.key() else TXT_DIFF_ID
                row.cells[other] = Cell(status, match.req_id)
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Scrittura del foglio
# ---------------------------------------------------------------------------

def _prepare_sheet(wb):
    pos = None
    if SHEET_NAME in wb.sheetnames:
        pos = wb.sheetnames.index(SHEET_NAME)
        del wb[SHEET_NAME]
    elif index_funzioni.SHEET_NAME in wb.sheetnames:
        pos = wb.sheetnames.index(index_funzioni.SHEET_NAME) + 1
    return wb.create_sheet(SHEET_NAME, pos)


def _cell(ws, r, c, value, font=None, fill=None):
    cell = ws.cell(r, c, value)
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell


def write_sheet(wb, configs: list[str],
                blocks: list[tuple[str, dict, list]]) -> int:
    ws = _prepare_sheet(wb)
    _cell(ws, 1, COL_REQ, "DOC ID / Requisito", FONT_HEADER, FILL_HEADER)
    _cell(ws, 1, COL_FIELD, "Nr / ID", FONT_HEADER, FILL_HEADER)
    _cell(ws, 1, COL_DESC, "Description", FONT_HEADER, FILL_HEADER)
    colors = getattr(cfg, "CONFIG_COLOR_MAP", {})
    for j, cname in enumerate(configs, start=FIRST_CFG_COL):
        fill = (PatternFill("solid", fgColor="FF" + colors[cname])
                if cname in colors else FILL_HEADER)
        _cell(ws, 1, j, cname, FONT_HEADER, fill)

    row, n = 2, 0
    for doc_id, docs, rows in blocks:
        n_ok = sum(1 for r in rows if r.all_matched())
        _cell(ws, row, COL_REQ, doc_id, FONT_DOC, FILL_DOC)
        _cell(ws, row, COL_FIELD, None, FONT_DOC, FILL_DOC)
        _cell(ws, row, COL_DESC,
              f"{len(rows)} requisiti, {n_ok} MATCHED in tutte le configurazioni "
              f"({datetime.now():%d/%m/%Y %H:%M})", FONT_DOC, FILL_DOC)
        for j, cname in enumerate(configs, start=FIRST_CFG_COL):
            _cell(ws, row, j, docs[cname].label(), FONT_DOC, FILL_DOC)
        row += 1
        for rr in rows:
            _cell(ws, row, COL_REQ, rr.req_id)
            _cell(ws, row, COL_FIELD, rr.field_name)
            _cell(ws, row, COL_DESC, rr.description or "(Description non letta)",
                  None if rr.description else FONT_INFO)
            for j, cname in enumerate(configs, start=FIRST_CFG_COL):
                c = rr.cells[cname]
                text = f"{c.status}\n{c.req_id}" if c.status == TXT_DIFF_ID else c.status
                cell = _cell(ws, row, j, text, FONT_STATUS[c.status])
                if c.note:
                    cell.comment = Comment(c.note, "AskTrainMind")
            row += 1
            n += 1

    ws.freeze_panes = ws.cell(2, FIRST_CFG_COL)
    ws.column_dimensions[get_column_letter(COL_REQ)].width = 42
    ws.column_dimensions[get_column_letter(COL_FIELD)].width = 9
    ws.column_dimensions[get_column_letter(COL_DESC)].width = 70
    for j in range(FIRST_CFG_COL, FIRST_CFG_COL + len(configs)):
        ws.column_dimensions[get_column_letter(j)].width = 28
    return n


# ---------------------------------------------------------------------------
# Esecuzione
# ---------------------------------------------------------------------------

def run(wb_data, wb_write, selection: str = "", interactive: bool = True) -> Optional[int]:
    """
    Esegue il confronto per i DOC ID scelti. Ritorna il numero di righe
    requisito scritte, None se non c'e' nulla da salvare.
    """
    if cfg.SHEET_CONFIG not in wb_data.sheetnames:
        log.error(f"Foglio '{cfg.SHEET_CONFIG}' non trovato.")
        return None
    if not cfg.ONEDRIVE_DOCS_ROOT.exists():
        log.error(f"Cartella documenti non trovata: {cfg.ONEDRIVE_DOCS_ROOT}")
        return None

    ws = wb_data[cfg.SHEET_CONFIG]
    groups = index_funzioni.config_groups(ws)
    configs = [g[0] for g in groups]
    doc_ids = read_doc_ids(ws)
    default = ", ".join(getattr(cfg, "CONFRONTO_REQS_DOC_IDS", []))

    if not selection.strip():
        selection = ask_doc_ids(doc_ids, default) if interactive else default
    chosen, unknown = resolve_selection(selection, doc_ids)
    if unknown:
        log.warning(f"  [Confronto Reqs] DOC ID non riconosciuti: {', '.join(unknown)}")
    if not chosen:
        log.error("  [Confronto Reqs] Nessun DOC ID scelto.")
        return None
    log.info(f"  [Confronto Reqs] Configurazioni: {configs}")
    log.info(f"  [Confronto Reqs] DOC ID: {', '.join(chosen)}")

    blocks = []
    current = ""
    try:
        for doc_id in chosen:
            current = doc_id
            log.info(f"\n{'─' * 55}\n  {doc_id}\n{'─' * 55}")
            docs = load_documents(doc_id, read_doc_row(ws, doc_id, groups), configs)
            if not any(d.status == "ok" for d in docs.values()):
                log.warning(f"  [Confronto Reqs] {doc_id}: nessun documento trovato")
            rows = compare(docs, configs)
            n_ok = sum(1 for r in rows if r.all_matched())
            log.info(f"  [Confronto Reqs] {doc_id}: {len(rows)} requisiti, "
                     f"{n_ok} MATCHED in tutte le configurazioni")
            blocks.append((doc_id, docs, rows))
        current = ""
    except KeyboardInterrupt as exc:
        interrupt_guard.handle(exc, f"Confronto Reqs, DOC ID '{current}'")

    if not blocks:
        return None
    with interrupt_guard.protected():
        n = write_sheet(wb_write, configs, blocks)
    log.info(f"\n  [Confronto Reqs] Foglio '{SHEET_NAME}': {len(blocks)} DOC ID, "
             f"{n} requisiti" + (" (PARZIALE: esecuzione interrotta)" if current else ""))
    return n
