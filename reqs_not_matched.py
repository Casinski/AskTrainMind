"""
reqs_not_matched.py
-------------------
Opzione 5 "REQUISITI NON MATCHED TRA CONFIGURAZIONI": foglio "Reqs not matched".

Legge il foglio "Requisiti" (compilato dall'opzione 1) e, per le
configurazioni scelte dall'utente (es. VZI_Base, VZI_New14, VZ_FR) oppure
per tutte le configurazioni, elenca i requisiti che NON sono MATCHED fra
quelle configurazioni:

  - requisito presente in alcune configurazioni e assente in altre;
  - requisito presente in tutte ma con testo (Description) diverso.

Il foglio "Reqs not matched" viene CANCELLATO e RICREATO a ogni chiamata.
Viene richiamato di default al termine dell'opzione 1 con tutte le
configurazioni (REQS_NOT_MATCHED_AFTER_OPTION1).

Colonne del foglio:
    FUNC ID | DESCRIZIONE FUNZIONE | REQUISITO | <una colonna per
    configurazione: "X" se il requisito e' presente> | Descrizione | Note AI

"Note AI": per ogni configurazione la differenza rilevata (es. "Requisito
non trovato per la configurazione VZ_FR.") seguita da una breve
spiegazione in italiano del requisito e delle differenze funzionali,
tecniche od operative, generata da Ollama (REQS_NOT_MATCHED_AI_NOTES).
Senza Ollama la nota contiene solo le differenze rilevate.

Le Description dei requisiti vengono memorizzate dall'opzione 1 in
REQ_DESC_CACHE_FILE: servono a riportare il testo anche quando nel foglio
Requisiti compare solo "MATCHED" / "MISS VZI_BASE REQ, MATCHED".
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import config as cfg
import interrupt_guard
import requisiti_sorter
from requirements_extractor import id_key

log = logging.getLogger(__name__)

SHEET_NAME: str = getattr(cfg, "SHEET_REQS_NOT_MATCHED", "Reqs not matched")
BASE: str = getattr(cfg, "REQ_BASE_CONFIG", "VZI_Base")
MARK = "X"

_HISTORY = Path(getattr(cfg, "HISTORY_DIR",
                        Path.home() / "AppData" / "Local" / "FunzioniAI"))
DESC_FILE = Path(getattr(cfg, "REQ_DESC_CACHE_FILE", _HISTORY / "req_desc_cache.json"))
AI_FILE = Path(getattr(cfg, "REQS_NOT_MATCHED_AI_CACHE_FILE",
                       _HISTORY / "reqs_not_matched_ai_cache.json"))

TXT_MATCHED = getattr(cfg, "REQ_TXT_MATCHED", "MATCHED").strip().upper()
TXT_MISS_MATCHED = getattr(cfg, "REQ_TXT_MISS_MATCHED", "MISS VZI_BASE REQ, MATCHED").strip().upper()
TXT_MISS_DIFF = getattr(cfg, "REQ_TXT_MISS_DIFF", "MISS VZI_BASE REQ, FOUND DIFF").strip().upper()
TXT_MISS_ONLY = getattr(cfg, "REQ_TXT_MISS_ONLY", "MISS VZI_BASE REQ").strip().upper()

FONT_HEADER = Font(bold=True, color="FFFFFFFF")
FILL_HEADER = PatternFill("solid", fgColor="FF1F4E79")
FONT_FUNC = Font(bold=True)
FONT_INFO = Font(italic=True, color="FF808080")
FONT_NOTE = Font(color="FFC00000")
ALIGN_TOP = Alignment(vertical="top", wrap_text=True)
ALIGN_MARK = Alignment(horizontal="center", vertical="top")

_DESC_RE = re.compile(r"Description:\s*(.*?)(?:\n\s*[—-]{5,}|\Z)", re.S)


def _s(v) -> str:
    return requisiti_sorter._s(v)


def _n(s: str) -> str:
    return " ".join((s or "").split()).lower()


# ---------------------------------------------------------------------------
# Archivio delle Description (alimentato dall'opzione 1)
# ---------------------------------------------------------------------------

_desc: dict[str, dict[str, dict[str, str]]] = {}
_desc_loaded = False


def load_descriptions() -> None:
    global _desc_loaded
    if _desc_loaded:
        return
    _desc_loaded = True
    try:
        if DESC_FILE.exists():
            _desc.update(json.loads(DESC_FILE.read_text(encoding="utf-8")))
    except Exception as exc:
        log.warning(f"  [Reqs not matched] Archivio Description non leggibile: {exc}")


def save_descriptions() -> None:
    if not _desc:
        return
    try:
        DESC_FILE.parent.mkdir(parents=True, exist_ok=True)
        DESC_FILE.write_text(json.dumps(_desc, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.warning(f"  [Reqs not matched] Archivio Description non salvabile: {exc}")


def remember(func_id: str, req_id: str, config_name: str, description: str) -> None:
    """Memorizza la Description di un requisito per una configurazione."""
    description = (description or "").strip()
    if not (func_id and req_id and config_name and description):
        return
    load_descriptions()
    _desc.setdefault(_n(func_id), {}).setdefault(id_key(req_id), {})[config_name] = description


def stored_descriptions(func_id: str, req_id: str) -> dict[str, str]:
    load_descriptions()
    return dict(_desc.get(_n(func_id), {}).get(id_key(req_id), {}))


# ---------------------------------------------------------------------------
# Lettura del foglio Requisiti
# ---------------------------------------------------------------------------

@dataclass
class ReqRow:
    func_id: str
    func_desc: str
    req_id: str
    listed: set[str]                         # configurazioni in col D (normalizzate)
    cells: dict[str, str] = field(default_factory=dict)   # {config: testo cella}


def read_config_columns(ws) -> dict[str, int]:
    """{nome configurazione: colonna} dalla riga di intestazione."""
    out: dict[str, int] = {}
    for col in range(cfg.REQ_CONFIG_COLS_START, ws.max_column + 1):
        name = _s(ws.cell(cfg.REQ_HEADER_ROW, col).value)
        if name:
            out[name] = col
    return out


def read_requisiti(ws) -> tuple[list[str], list[ReqRow]]:
    """(configurazioni, righe requisito) del foglio Requisiti."""
    cols = read_config_columns(ws)
    rows: list[ReqRow] = []
    func_id = func_desc = ""
    for r in range(cfg.REQ_HEADER_ROW + 1, ws.max_row + 1):
        fid = _s(ws.cell(r, cfg.REQ_FUNC_ID_COL).value)
        if fid:
            func_id, func_desc = fid, _s(ws.cell(r, cfg.REQ_DESC_COL).value)
            continue
        req = _s(ws.cell(r, cfg.REQ_NUMBER_COL).value)
        if not req or not func_id:
            continue
        req = re.sub(r"^\s*\d+\)\s*", "", req)
        listed = {_n(x) for x in _s(ws.cell(r, cfg.REQ_CONFIG_COL).value).split(",") if x.strip()}
        cells = {c: _s(ws.cell(r, col).value) for c, col in cols.items()}
        rows.append(ReqRow(func_id, func_desc, req, listed, cells))
    return list(cols), rows


# ---------------------------------------------------------------------------
# Classificazione delle celle
# ---------------------------------------------------------------------------

@dataclass
class CellState:
    kind: str      # absent | ref | match_base | match_nobase | diff_base | diff_nobase | only | unknown
    text: str = ""


def cell_state(config: str, text: str, listed: set[str]) -> CellState:
    t = (text or "").strip()
    if not t and _n(config) not in listed:
        return CellState("absent")
    if not t:
        return CellState("unknown")
    first = t.split("\n", 1)[0].strip().upper()
    if _n(config) == _n(BASE):
        return CellState("ref", t)
    if first == TXT_MATCHED:
        return CellState("match_base")
    if first == TXT_MISS_MATCHED:
        return CellState("match_nobase")
    if first == TXT_MISS_DIFF:
        return CellState("diff_nobase", t.split("\n", 1)[1] if "\n" in t else "")
    if first == TXT_MISS_ONLY:
        return CellState("only", t.split("\n", 1)[1] if "\n" in t else "")
    if t.startswith("Description:"):
        return CellState("unknown", t)
    return CellState("diff_base", t)


def description_from_cell(state: CellState) -> str:
    if state.kind == "only":
        d = state.text.strip()
        return "" if d.startswith("[") else d
    if state.kind in ("ref", "diff_nobase", "unknown"):
        m = _DESC_RE.search(state.text)
        return m.group(1).strip() if m else ""
    return ""


def _similar(a: str, b: str) -> bool:
    na, nb = _n(re.sub(r"[^\w%./-]+", " ", a)), _n(re.sub(r"[^\w%./-]+", " ", b))
    if not na or not nb:
        return False
    if na == nb:
        return True
    soglia = getattr(cfg, "REQ_DESC_SIMILARITY_MATCH", 0.94)
    return SequenceMatcher(None, na, nb).ratio() >= soglia


def _first_sentence(text: str, limit: int = 180) -> str:
    t = " ".join((text or "").split())
    m = re.search(r"^(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m else t
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + " […]"


# ---------------------------------------------------------------------------
# Analisi
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    row: ReqRow
    present: list[str]
    missing: list[str]
    reference: str = ""
    description: str = ""
    lines: list[str] = field(default_factory=list)       # differenze rilevate
    descriptions: dict[str, str] = field(default_factory=dict)
    diff_texts: dict[str, str] = field(default_factory=dict)
    ai_note: str = ""

    def note(self) -> str:
        parts = list(self.lines)
        if self.ai_note:
            parts.append(self.ai_note)
        txt = "\n".join(parts)
        limit = int(getattr(cfg, "REQS_NOT_MATCHED_NOTE_MAX_CHARS", 700))
        return txt if len(txt) <= limit else txt[:limit].rsplit(" ", 1)[0] + " […]"


def analyse(configs: list[str], rows: list[ReqRow],
            selected: list[str]) -> list[Finding]:
    """Requisiti non MATCHED fra le configurazioni selezionate."""
    # configurazioni con almeno un requisito, per funzione
    func_cfgs: dict[str, set[str]] = {}
    for r in rows:
        s = func_cfgs.setdefault(_n(r.func_id), set())
        for c in configs:
            if cell_state(c, r.cells.get(c, ""), r.listed).kind != "absent":
                s.add(c)

    out: list[Finding] = []
    for r in rows:
        states = {c: cell_state(c, r.cells.get(c, ""), r.listed) for c in selected}
        present = [c for c in selected if states[c].kind != "absent"]
        if not present:
            continue
        missing = [c for c in selected if states[c].kind == "absent"]

        stored = stored_descriptions(r.func_id, r.req_id)
        descs: dict[str, str] = {}
        for c in configs:
            d = description_from_cell(cell_state(c, r.cells.get(c, ""), r.listed))
            if d:
                descs[c] = d
        for c, d in stored.items():
            descs.setdefault(c, d)

        # Classi di equivalenza fra le configurazioni presenti
        cls: dict[str, str] = {}
        for c in present:
            k = states[c].kind
            if k in ("ref", "match_base"):
                cls[c] = "BASE"
            elif k == "match_nobase":
                cls[c] = "NOBASE"
            else:
                cls[c] = f"{k}:{c}"
        _merge_by_description(present, states, cls, descs)

        groups = set(cls.values())
        if not missing and len(groups) <= 1:
            continue

        f = Finding(r, present, missing, descriptions=descs)
        ref = next((c for c in present if cls[c] == "BASE"), None) \
            or next((c for c in present if cls[c] == "NOBASE"), None) \
            or present[0]
        f.reference = ref
        f.description = (descs.get(ref) or descs.get(BASE)
                         or next((descs[c] for c in present if c in descs), "")
                         or next(iter(descs.values()), ""))

        for c in missing:
            line = f"Requisito non trovato per la configurazione {c}."
            if c not in func_cfgs.get(_n(r.func_id), set()):
                line = (f"Requisito non trovato per la configurazione {c} "
                        f"(nessun requisito della funzione in {c}: verificare "
                        f"documento/Rif. Pagina).")
            f.lines.append(line)

        for c in present:
            if cls[c] == cls[ref]:
                continue
            st = states[c]
            if st.kind == "unknown":
                f.lines.append(f"{c}: confronto non disponibile nel foglio "
                               f"Requisiti, verifica manuale.")
                continue
            dettaglio = ""
            if st.kind == "diff_base":
                f.diff_texts[c] = st.text
                dettaglio = _first_sentence(st.text)
            elif st.kind == "diff_nobase":
                m = re.search(r"Differenze vs [^:]+:\s*(.*?)(?:\n\s*[—-]{5,}|\Z)", st.text, re.S)
                if m:
                    f.diff_texts[c] = m.group(1).strip()
                    dettaglio = _first_sentence(m.group(1))
            line = f"{c}: requisito diverso da {ref}"
            if states[ref].kind == "diff_base" and st.kind == "diff_base":
                line += f" (entrambe diverse da {BASE})"
            f.lines.append(f"{line} — {dettaglio}" if dettaglio else f"{line}.")
        out.append(f)
    return out


def _merge_by_description(present: list[str], states: dict[str, CellState],
                          cls: dict[str, str], descs: dict[str, str]) -> None:
    """
    Il foglio Requisiti confronta ogni configurazione con VZI_Base: due
    configurazioni entrambe diverse dalla base possono pero' essere uguali
    fra loro. In quel caso (Description memorizzate simili) vengono unite
    nella stessa classe. L'esito scritto nel foglio (MATCHED / diverso da
    VZI_Base) non viene mai contraddetto.
    """
    fixed = ("BASE", "NOBASE")
    for i, c in enumerate(present):
        for o in present[i + 1:]:
            if cls[c] == cls[o] or c not in descs or o not in descs:
                continue
            a_fixed, b_fixed = cls[c] in fixed, cls[o] in fixed
            if a_fixed and b_fixed:
                continue
            # una sola classe "fissata": si unisce solo una cella non decisa
            if a_fixed and states[o].kind != "unknown":
                continue
            if b_fixed and states[c].kind != "unknown":
                continue
            if not _similar(descs[c], descs[o]):
                continue
            keep, drop = (cls[c], cls[o]) if not b_fixed else (cls[o], cls[c])
            for k in present:
                if cls[k] == drop:
                    cls[k] = keep


# ---------------------------------------------------------------------------
# Note AI (Ollama)
# ---------------------------------------------------------------------------

_ai_cache: dict[str, str] = {}


def _load_ai_cache() -> None:
    try:
        if AI_FILE.exists():
            _ai_cache.update(json.loads(AI_FILE.read_text(encoding="utf-8")))
    except Exception as exc:
        log.warning(f"  [Reqs not matched] Cache note AI non leggibile: {exc}")


def _save_ai_cache() -> None:
    try:
        AI_FILE.parent.mkdir(parents=True, exist_ok=True)
        AI_FILE.write_text(json.dumps(_ai_cache, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.warning(f"  [Reqs not matched] Cache note AI non salvabile: {exc}")


def build_prompt(f: Finding, selected: list[str]) -> str:
    max_chars = int(getattr(cfg, "REQS_NOT_MATCHED_AI_MAX_CHARS", 350))
    testi = []
    for c in selected:
        if c in f.descriptions:
            testi.append(f"[{c}] {f.descriptions[c][:1500]}")
        elif c in f.missing:
            testi.append(f"[{c}] REQUISITO ASSENTE")
    for c, d in f.diff_texts.items():
        testi.append(f"[Differenze gia' rilevate per {c}] {d[:800]}")
    return (
        "Sei un tecnico ferroviario esperto di treni ETR1000.\n"
        f"Funzione: {f.row.func_id} - {f.row.func_desc}\n"
        f"Requisito: {f.row.req_id}\n"
        f"Configurazioni confrontate: {', '.join(selected)}\n\n"
        + "\n".join(testi) + "\n\n"
        "Differenze rilevate:\n" + "\n".join(f.lines) + "\n\n"
        "Scrivi in ITALIANO una nota BREVE (massimo "
        f"{max_chars} caratteri, 1-3 frasi) che:\n"
        "1. spieghi in parole semplici che cosa prescrive il requisito;\n"
        "2. indichi la differenza funzionale, tecnica od operativa fra le "
        "configurazioni (presenza/assenza del requisito, valori, condizioni, "
        "comportamento del treno).\n"
        "Non ripetere l'identificativo del requisito, non usare elenchi, non "
        "inventare informazioni non presenti nei testi.\n"
        'Rispondi SOLO con il JSON: {"nota": "..."}'
    )


def _ask_ai(prompt: str) -> str:
    from ai_synthesizer import _call_ollama, _e_errore_ai, _token_budget, _chiudi_frase
    from llm_json import parse_json_relaxed
    max_chars = int(getattr(cfg, "REQS_NOT_MATCHED_AI_MAX_CHARS", 350))
    raw = _call_ollama(prompt, num_predict=_token_budget(max_chars + 100))
    if _e_errore_ai(raw):
        return ""
    rec = parse_json_relaxed(raw, campi_testo=("nota",))
    nota = str((rec.data.get("nota") if rec else "") or "").strip()
    nota = " ".join(nota.split())
    if len(nota) > max_chars:
        nota = _chiudi_frase(nota[:max_chars])
    return nota


def add_ai_notes(findings: list[Finding], selected: list[str]) -> int:
    """Genera le note AI (con cache su disco). Ritorna le note nuove."""
    if not getattr(cfg, "REQS_NOT_MATCHED_AI_NOTES", True) or not findings:
        return 0
    _load_ai_cache()
    todo: list[tuple[Finding, str, str]] = []
    for f in findings:
        p = build_prompt(f, selected)
        k = hashlib.sha1(f"{cfg.OLLAMA_MODEL}|{p}".encode("utf-8")).hexdigest()
        if k in _ai_cache:
            f.ai_note = _ai_cache[k]
        else:
            todo.append((f, p, k))
    max_calls = int(getattr(cfg, "REQS_NOT_MATCHED_AI_MAX_CALLS", 200) or 0)
    if max_calls > 0 and len(todo) > max_calls:
        log.info(f"  [Reqs not matched] Note AI: {len(todo)} da generare, "
                 f"limite REQS_NOT_MATCHED_AI_MAX_CALLS = {max_calls} per "
                 f"esecuzione (le altre alla prossima chiamata).")
        todo = todo[:max_calls]
    if not todo:
        return 0

    import ai_synthesizer
    if not ai_synthesizer.check_ollama():
        log.warning("  [Reqs not matched] Ollama non disponibile: le Note AI "
                    "riportano solo le differenze rilevate.")
        return 0

    log.info(f"  [Reqs not matched] Generazione di {len(todo)} note AI...")
    workers = max(1, int(getattr(cfg, "LLM_PARALLEL_WORKERS", 3)))
    n = 0
    ex = ThreadPoolExecutor(max_workers=workers)
    try:
        futs = {ex.submit(_ask_ai, p): (f, k) for f, p, k in todo}
        for fut in as_completed(futs):
            f, k = futs[fut]
            try:
                nota = fut.result()
            except Exception as exc:
                log.warning(f"  [Reqs not matched] Nota AI non generata per "
                            f"{f.row.req_id}: {exc}")
                continue
            if nota:
                f.ai_note = _ai_cache[k] = nota
                n += 1
                if n % 25 == 0:
                    log.info(f"  [Reqs not matched] Note AI: {n}/{len(todo)}")
                    _save_ai_cache()
    except KeyboardInterrupt as exc:
        ex.shutdown(wait=False, cancel_futures=True)
        interrupt_guard.handle(exc, "Reqs not matched, Note AI")
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
        _save_ai_cache()
    return n


# ---------------------------------------------------------------------------
# Scrittura del foglio
# ---------------------------------------------------------------------------

def _prepare_sheet(wb):
    """Cancella e ricrea il foglio, subito dopo "Requisiti"."""
    pos = None
    if SHEET_NAME in wb.sheetnames:
        pos = wb.sheetnames.index(SHEET_NAME)
        del wb[SHEET_NAME]
    elif cfg.SHEET_REQUISITI in wb.sheetnames:
        pos = wb.sheetnames.index(cfg.SHEET_REQUISITI) + 1
    return wb.create_sheet(SHEET_NAME, pos)


def _cell(ws, r, c, value, font=None, fill=None, align=ALIGN_TOP):
    cell = ws.cell(r, c, value)
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    cell.alignment = align
    return cell


def write_sheet(wb, selected: list[str], findings: list[Finding]) -> int:
    import config_colors
    ws = _prepare_sheet(wb)
    first_cfg = 4
    col_desc = first_cfg + len(selected)
    col_note = col_desc + 1
    headers = ["FUNC ID", "DESCRIZIONE FUNZIONE", "REQUISITO"]
    for j, h in enumerate(headers, start=1):
        _cell(ws, 1, j, h, FONT_HEADER, FILL_HEADER)
    for j, c in enumerate(selected, start=first_cfg):
        _cell(ws, 1, j, c, FONT_HEADER,
              PatternFill("solid", fgColor="FF" + config_colors.color_for(c)[-6:]),
              Alignment(horizontal="center", vertical="top", wrap_text=True))
    _cell(ws, 1, col_desc, "Descrizione", FONT_HEADER, FILL_HEADER)
    _cell(ws, 1, col_note, "Note AI", FONT_HEADER, FILL_HEADER)
    ws.cell(1, 1).comment = Comment(
        f"Generato il {datetime.now():%d/%m/%Y %H:%M} da AskTrainMind.\n"
        f"Configurazioni: {', '.join(selected)}\n"
        f"Requisiti non MATCHED: {len(findings)}", "AskTrainMind")

    row, prev = 2, None
    for f in findings:
        first = f.row.func_id != prev
        prev = f.row.func_id
        _cell(ws, row, 1, f.row.func_id, FONT_FUNC if first else None)
        _cell(ws, row, 2, f.row.func_desc)
        _cell(ws, row, 3, f.row.req_id)
        for j, c in enumerate(selected, start=first_cfg):
            if c in f.present:
                _cell(ws, row, j, MARK,
                      Font(bold=True, color="FF" + config_colors.color_for(c)[-6:]),
                      align=ALIGN_MARK)
        if f.description:
            _cell(ws, row, col_desc, f.description)
        else:
            _cell(ws, row, col_desc, "(Description non disponibile: rieseguire "
                                     "l'opzione 1 per la funzione)", FONT_INFO)
        _cell(ws, row, col_note, f.note(), FONT_NOTE)
        row += 1

    ws.freeze_panes = ws.cell(2, first_cfg)
    ws.auto_filter.ref = f"A1:{get_column_letter(col_note)}{max(row - 1, 1)}"
    for col, w in ((1, 42), (2, 50), (3, 40), (col_desc, 80), (col_note, 70)):
        ws.column_dimensions[get_column_letter(col)].width = w
    for j in range(first_cfg, col_desc):
        ws.column_dimensions[get_column_letter(j)].width = 12
    return len(findings)


# ---------------------------------------------------------------------------
# Scelta delle configurazioni
# ---------------------------------------------------------------------------

def resolve_configs(selection: str, configs: list[str]) -> tuple[list[str], list[str]]:
    """Configurazioni scelte (nomi o numeri dell'elenco, separati da virgola)."""
    if not selection.strip():
        return list(configs), []
    by_norm = {_n(c): c for c in configs}
    chosen, unknown = [], []
    for tok in re.split(r"[,;]", selection):
        t = tok.strip()
        if not t:
            continue
        if t.isdigit() and 1 <= int(t) <= len(configs):
            c = configs[int(t) - 1]
        else:
            c = by_norm.get(_n(t))
        if c is None:
            unknown.append(t)
        elif c not in chosen:
            chosen.append(c)
    return [c for c in configs if c in chosen], unknown


def ask_configs(configs: list[str], default: str) -> str:
    print("\n  Configurazioni del foglio Requisiti:")
    for i, c in enumerate(configs, 1):
        print(f"    {i:>2}) {c}")
    hint = default or "tutte"
    try:
        ans = input(f"\n  Configurazioni da confrontare, separate da virgola "
                    f"(nomi o numeri) [{hint}]: ").strip()
    except EOFError:
        ans = ""
    return ans or default


# ---------------------------------------------------------------------------
# Esecuzione
# ---------------------------------------------------------------------------

def run(wb, selection: str = "", interactive: bool = False,
        ai: Optional[bool] = None) -> Optional[int]:
    """
    Ricrea il foglio "Reqs not matched". selection vuota = tutte le
    configurazioni. Ritorna il numero di requisiti non MATCHED, None se il
    foglio non e' stato scritto.
    """
    if cfg.SHEET_REQUISITI not in wb.sheetnames:
        log.error(f"  [Reqs not matched] Foglio '{cfg.SHEET_REQUISITI}' non trovato.")
        return None
    ws_req = wb[cfg.SHEET_REQUISITI]
    configs, rows = read_requisiti(ws_req)
    if not configs:
        log.error("  [Reqs not matched] Nessuna configurazione nell'intestazione "
                  f"del foglio '{cfg.SHEET_REQUISITI}'.")
        return None

    default = ", ".join(getattr(cfg, "REQS_NOT_MATCHED_CONFIGS", []) or [])
    if interactive and not selection.strip():
        selection = ask_configs(configs, default)
    elif not selection.strip():
        selection = default
    selected, unknown = resolve_configs(selection, configs)
    if unknown:
        log.warning(f"  [Reqs not matched] Configurazioni non riconosciute: "
                    f"{', '.join(unknown)} (disponibili: {', '.join(configs)})")
    if len(selected) < 2:
        log.error("  [Reqs not matched] Servono almeno due configurazioni da confrontare.")
        return None
    log.info(f"  [Reqs not matched] Configurazioni: {', '.join(selected)}")

    findings = analyse(configs, rows, selected)

    # Ordine del foglio Funzioni (LV, AUX, BAT, ...), poi ordine del foglio
    if cfg.SHEET_FUNZIONI in wb.sheetnames:
        order = requisiti_sorter.funzioni_order(wb[cfg.SHEET_FUNZIONI])
        funcs = list(dict.fromkeys(f.row.func_id for f in findings))
        rank = {funcs[i]: k for k, i in
                enumerate(requisiti_sorter.order_positions(funcs, order))}
        findings.sort(key=lambda f: rank[f.row.func_id])

    use_ai = getattr(cfg, "REQS_NOT_MATCHED_AI_NOTES", True) if ai is None else ai
    if use_ai:
        add_ai_notes(findings, selected)

    with interrupt_guard.protected():
        n = write_sheet(wb, selected, findings)
    log.info(f"  [Reqs not matched] Foglio '{SHEET_NAME}' ricreato: {n} requisiti "
             f"non MATCHED su {len(rows)} ({', '.join(selected)}).")
    return n
