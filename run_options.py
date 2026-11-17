"""
run_options.py
--------------
Parametri scelti dall'utente all'avvio e servizi comuni alle opzioni:

  * Option1Params    : domande dell'opzione 1 (numero celle, sovrascrittura,
                       FUNC ID di partenza, FRS, "Reqs not matched").
  * update_db / RESULTS
                     : se l'utente NON vuole aggiornare il file DB Flotte i
                       fogli modificati dall'opzione vengono scritti in
                       <cartella Excel>/RESULTS/RESULTS_<data>_Opzione_<N>.xlsx
                       con lo stesso layout del DB (solo i fogli impattati,
                       formule convertite in valori) e il DB resta invariato.
  * UpdateTracker    : celle aggiornate dall'esecuzione (per RICHIESTA.txt
                       in _OLD e per il foglio informativo del RESULTS).
  * mark_not_updated : nelle esecuzioni PARZIALI le celle "Funzioni AI" (e i
                       FUNC ID del foglio Requisiti) escluse dall'elaborazione
                       ricevono il commento "Not updated".
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font
from openpyxl.worksheet.formula import ArrayFormula

import config as cfg

log = logging.getLogger(__name__)

NOT_UPDATED = getattr(cfg, "NOT_UPDATED_COMMENT", "Not updated")
COMMENT_AUTHOR = "AskTrainMind"
RESULTS_INFO_SHEET = "RESULTS info"

OVERWRITE_LABELS = {
    "A": "automatica (rielabora le celle compilate solo se il documento e' cambiato)",
    "S": "si' (rielabora anche tutte le celle gia' compilate)",
    "N": "no (compila solo le celle vuote)",
}


# ---------------------------------------------------------------------------
# Aggiornamento del DB o file RESULTS (tutte le opzioni)
# ---------------------------------------------------------------------------

_update_db = True
_results_path: Path | None = None


def set_update_db(value: bool) -> None:
    global _update_db, _results_path
    _update_db = bool(value)
    _results_path = None


def update_db() -> bool:
    return _update_db


def results_path(option: str, stamp: datetime | None = None) -> Path:
    global _results_path
    if _results_path is None:
        root = getattr(cfg, "RESULTS_DIR", None)
        root = Path(root) if root else Path(cfg.EXCEL_PATH).parent / "RESULTS"
        t = stamp or datetime.now()
        _results_path = root / f"RESULTS_{t:%Y-%m-%d_%H-%M-%S}_Opzione_{option}.xlsx"
    return _results_path


def ask_yes_no(question: str, default: bool) -> bool:
    hint = "S/n" if default else "s/N"
    try:
        ans = input(f"  {question} [{hint}]: ").strip().lower()
    except EOFError:
        return default
    if not ans:
        return default
    return ans in ("s", "si", "si'", "sì", "y", "yes")


# ---------------------------------------------------------------------------
# Parametri dell'opzione 1
# ---------------------------------------------------------------------------

@dataclass
class Option1Params:
    max_cells: int = 0                 # 0 = nessun limite
    overwrite: str = "A"               # A / S / N (vedi OVERWRITE_LABELS)
    start: str = ""                    # FUNC ID di partenza
    frs: list[str] = field(default_factory=list)   # DOC ID scelti (vuoto = tutti)
    reqs_not_matched: bool = True

    @property
    def include_filled(self) -> bool | None:
        return {"S": True, "N": False}.get(self.overwrite)

    @property
    def force(self) -> bool:
        return self.overwrite == "S"

    def partial_reasons(self) -> list[str]:
        out = []
        if self.frs:
            out.append(f"solo FRS {', '.join(self.frs)}")
        if self.start:
            out.append(f"partenza da {self.start}")
        if self.max_cells > 0:
            out.append(f"massimo {self.max_cells} celle")
        if self.overwrite == "N":
            out.append("solo celle vuote")
        return out

    def describe(self) -> dict:
        return {
            "Numero celle": str(self.max_cells) if self.max_cells > 0 else "tutte",
            "Sovrascrittura": f"{self.overwrite} = {OVERWRITE_LABELS[self.overwrite]}",
            "FUNC ID partenza": self.start or "inizio foglio",
            "FRS": ", ".join(self.frs) if self.frs else "tutti",
            "Reqs not matched": "aggiornato" if self.reqs_not_matched else "NON aggiornato",
        }


def frs_choices() -> list[str]:
    """DOC ID del foglio CONFIG (col B) del file Excel."""
    import confronto_reqs
    try:
        wb = load_workbook(str(cfg.EXCEL_PATH), read_only=True, data_only=True)
        try:
            ws = wb[getattr(cfg, "SHEET_CONFIG", "CONFIG")]
        except KeyError:
            return []
        out = confronto_reqs.read_doc_ids(ws)
        wb.close()
        return out
    except Exception as exc:
        log.warning(f"  Elenco FRS non disponibile: {exc}")
        return []


def resolve_frs(text: str, choices: list[str]) -> tuple[list[str], list[str]]:
    import confronto_reqs
    if not choices:
        toks = [t.strip() for t in (text or "").split(",") if t.strip()]
        return toks, []
    return confronto_reqs.resolve_selection(text, choices)


def ask_option1(defaults: Option1Params) -> Option1Params:
    """Domande interattive dell'opzione 1 (Invio = valore proposto)."""
    p = Option1Params(**{**defaults.__dict__, "frs": list(defaults.frs)})
    print("\n" + "-" * 60)
    print("  Opzione 1 — parametri dell'elaborazione (Invio = default)")
    print("-" * 60)

    def _inp(msg: str) -> str:
        try:
            return input(msg).strip()
        except EOFError:
            return ""

    while True:
        a = _inp(f"  Numero massimo di celle 'Funzioni AI' da compilare "
                 f"[Invio = {p.max_cells or 'tutte'}]: ")
        if not a:
            break
        if a.isdigit():
            p.max_cells = int(a)
            break
        print("    Inserisci un numero intero (0 = tutte).")

    print("  Sovrascrivere le celle 'Funzioni AI' gia' compilate?")
    for k, v in OVERWRITE_LABELS.items():
        print(f"     {k} = {v}")
    while True:
        a = _inp(f"  Scelta [A/S/N, Invio = {p.overwrite}]: ").upper()
        if not a:
            break
        if a in OVERWRITE_LABELS:
            p.overwrite = a
            break

    a = _inp(f"  FUNC ID da cui partire "
             f"[Invio = {p.start or 'inizio foglio'}]: ")
    if a:
        p.start = a

    choices = frs_choices()
    if choices:
        print("  FRS disponibili (foglio CONFIG, col B):")
        for i, d in enumerate(choices, 1):
            print(f"    {i:3d}) {d}")
    while True:
        a = _inp("  FRS da compilare (numeri o nomi separati da virgola) "
                 f"[Invio = {', '.join(p.frs) or 'tutti'}]: ")
        if not a:
            break
        chosen, unknown = resolve_frs(a, choices)
        if unknown:
            print(f"    Non riconosciuti: {', '.join(unknown)}")
            continue
        p.frs = chosen
        break

    p.reqs_not_matched = ask_yes_no(
        "Aggiornare il foglio 'Reqs not matched' al termine?", p.reqs_not_matched)
    return p


# ---------------------------------------------------------------------------
# Celle aggiornate
# ---------------------------------------------------------------------------

class UpdateTracker:
    """Celle scritte dall'esecuzione, per foglio e per gruppo."""

    def __init__(self) -> None:
        self.cells: dict[str, dict[str, list[str]]] = {}
        self.sheets_rebuilt: dict[str, str] = {}
        self.not_updated: dict[str, int] = {}

    def add(self, sheet: str, group: str, coord: str) -> None:
        lst = self.cells.setdefault(sheet, {}).setdefault(group, [])
        if coord not in lst:
            lst.append(coord)

    def rebuilt(self, sheet: str, ref: str) -> None:
        self.sheets_rebuilt[sheet] = ref

    def count(self, sheet: str | None = None) -> int:
        sheets = [sheet] if sheet else list(self.cells)
        return sum(len(v) for s in sheets for v in self.cells.get(s, {}).values())

    def lines(self, limit: int = 400) -> list[str]:
        out: list[str] = []
        for sheet, ref in self.sheets_rebuilt.items():
            out.append(f"  {sheet}: foglio ricreato per intero ({ref})")
        for sheet, groups in self.cells.items():
            n = sum(_n_cells(c) for v in groups.values() for c in v)
            out.append(f"  {sheet}: {n} celle")
            for g, coords in groups.items():
                out.append(f"    - {g}: {', '.join(coords)}")
        for sheet, n in self.not_updated.items():
            out.append(f"  {sheet}: {n} celle con testo precedente marcate con il "
                       f"commento '{NOT_UPDATED}' (fuori dall'ambito richiesto)")
        if len(out) > limit:
            out = out[:limit] + [f"  ... (altre {len(out) - limit} righe omesse)"]
        return out


def _n_cells(ref: str) -> int:
    if ":" not in ref:
        return 1
    from openpyxl.utils import range_boundaries
    c1, r1, c2, r2 = range_boundaries(ref)
    return (c2 - c1 + 1) * (r2 - r1 + 1)


tracker = UpdateTracker()


def reset_tracker() -> UpdateTracker:
    global tracker
    tracker = UpdateTracker()
    return tracker


# ---------------------------------------------------------------------------
# Commenti "Not updated"
# ---------------------------------------------------------------------------

def _is_ours(comment) -> bool:
    return comment is not None and str(comment.text or "").startswith(NOT_UPDATED)


def set_not_updated(cell, reason: str) -> bool:
    """Commento "Not updated" (non sovrascrive i commenti dell'utente)."""
    if cell.comment is not None and not _is_ours(cell.comment):
        return False
    c = Comment(f"{NOT_UPDATED}: cella non elaborata nell'esecuzione del "
                f"{datetime.now():%d/%m/%Y %H:%M} ({reason}).", COMMENT_AUTHOR)
    c.width, c.height = 260, 80
    cell.comment = c
    return True


def clear_not_updated(cell) -> None:
    if _is_ours(cell.comment):
        cell.comment = None


def mark_not_updated(ws_funz, ws_req, scope: set[tuple[int, int]],
                     processed_funcs: set[str], reasons: list[str],
                     partial: bool) -> None:
    """
    Funzioni: celle "Funzioni AI" fuori da 'scope' (riga, colonna) →
    commento "Not updated"; quelle elaborate perdono il commento.
    Requisiti: stessa logica sulla cella FUNC ID delle funzioni.
    Esecuzione completa (partial=False): si rimuovono tutti i commenti
    "Not updated" rimasti da esecuzioni parziali precedenti.
    """
    import excel_scanner
    reason = "; ".join(reasons) or "esecuzione parziale"
    n = 0
    for _f, _d, row, col, _c in excel_scanner.iter_funzioni_ai_cells(ws_funz):
        cell = ws_funz.cell(row, col)
        if not partial or (row, col) in scope:
            clear_not_updated(cell)
        elif cell.value in (None, ""):
            # Cella vuota (configurazione non applicabile o mai compilata):
            # nessun testo vecchio da segnalare
            clear_not_updated(cell)
        elif set_not_updated(cell, reason):
            n += 1
    if n:
        tracker.not_updated[ws_funz.title] = n

    if ws_req is None:
        return
    done = {_norm(f) for f in processed_funcs}
    n = 0
    for row in range(2, ws_req.max_row + 1):
        fid = ws_req.cell(row, cfg.REQ_FUNC_ID_COL).value
        if not fid or not str(fid).strip():
            continue
        cell = ws_req.cell(row, cfg.REQ_FUNC_ID_COL)
        if not partial or _norm(str(fid)) in done:
            clear_not_updated(cell)
        elif set_not_updated(cell, reason):
            n += 1
    if n:
        tracker.not_updated[ws_req.title] = n


def _norm(s: str) -> str:
    return " ".join(str(s).split()).lower()


# ---------------------------------------------------------------------------
# File RESULTS
# ---------------------------------------------------------------------------

def save_results(wb, option: str, sheets: list[str],
                 stamp: datetime | None = None) -> Path | None:
    """
    Scrive il file RESULTS con i soli fogli impattati, nello stesso layout
    del DB Flotte: le formule diventano valori (letti dal DB) perche' i
    fogli di origine non sono inclusi. Ritorna il percorso del file.
    """
    out = results_path(option, stamp)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".tmp.xlsx")
    try:
        wb.save(str(tmp))
        rb = load_workbook(str(tmp))
        keep = [s for s in sheets if s in rb.sheetnames]
        if not keep:
            log.warning("  [RESULTS] Nessun foglio da esportare.")
            return None
        cached = None
        try:
            cached = load_workbook(str(cfg.EXCEL_PATH), data_only=True)
        except Exception as exc:
            log.warning(f"  [RESULTS] Valori delle formule non leggibili: {exc}")
        for name in list(rb.sheetnames):
            if name not in keep:
                del rb[name]
        for name in keep:
            _formulas_to_values(rb[name], cached[name]
                                if cached is not None and name in cached.sheetnames
                                else None)
        _drop_external_refs(rb)
        _write_info_sheet(rb, option, keep)
        rb.active = 0
        rb.save(str(out))
        log.info(f"  📄 File RESULTS salvato (DB Flotte NON modificato): {out}")
        return out
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _formulas_to_values(ws, ws_cached) -> None:
    for row in ws.iter_rows():
        for c in row:
            v = c.value
            if isinstance(v, ArrayFormula) or (isinstance(v, str) and v.startswith("=")):
                c.value = (ws_cached[c.coordinate].value
                           if ws_cached is not None else None)


def _drop_external_refs(wb) -> None:
    """Nomi definiti, convalide e formattazioni che puntano ad altri fogli."""
    try:
        for name in list(wb.defined_names):
            del wb.defined_names[name]
    except Exception:
        try:
            wb.defined_names.definedName = []
        except Exception:
            pass
    for ws in wb.worksheets:
        try:
            ws.defined_names.clear()
        except Exception:
            pass
        dvs = ws.data_validations.dataValidation
        ws.data_validations.dataValidation = [
            dv for dv in dvs if "!" not in str(dv.formula1 or "")
            and "!" not in str(dv.formula2 or "")]
        cf = ws.conditional_formatting
        for rng in list(cf._cf_rules):
            rules = [r for r in cf._cf_rules[rng]
                     if not any("!" in str(f) for f in (r.formula or []))]
            if rules:
                cf._cf_rules[rng] = rules
            else:
                del cf._cf_rules[rng]


def _write_info_sheet(wb, option: str, sheets: list[str]) -> None:
    import old_archive
    if RESULTS_INFO_SHEET in wb.sheetnames:
        del wb[RESULTS_INFO_SHEET]
    ws = wb.create_sheet(RESULTS_INFO_SHEET)
    bold = Font(bold=True)
    lines = [
        ("AskTrainMind — file RESULTS", bold),
        (f"Creato il {datetime.now():%d/%m/%Y %H:%M:%S} dall'opzione {option}. "
         f"Il file DB Flotte NON e' stato modificato.", None),
        (f"DB Flotte: {cfg.EXCEL_PATH}", None),
        (f"Fogli esportati (stesso layout del DB Flotte): {', '.join(sheets)}", None),
        ("Copiare nel DB Flotte le celle elencate qui sotto.", None),
        ("", None),
        ("Parametri della richiesta", bold),
    ]
    for k, v in old_archive.details().items():
        lines.append((f"  {k}: {v}", None))
    lines += [("", None), ("Celle aggiornate", bold)]
    lines += [(ln, None) for ln in (tracker.lines(limit=5000) or ["  nessuna"])]
    for i, (text, font) in enumerate(lines, 1):
        c = ws.cell(i, 1, text)
        if font:
            c.font = font
    ws.column_dimensions["A"].width = 160


def interactive() -> bool:
    return sys.stdin is not None and sys.stdin.isatty() and \
        not os.environ.get("ASKTRAINMIND_NONINTERACTIVE")
