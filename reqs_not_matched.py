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
AI_PENDING_MARK = ("[Nota AI non generata: limite REQS_NOT_MATCHED_AI_MAX_CALLS "
                   "raggiunto, rieseguire l'opzione 5]")

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
FILL_SIMILAR = PatternFill("solid", fgColor="FFFFF2CC")   # requisiti simili affiancati
FILL_NO_LINK = PatternFill("solid", fgColor="FFFCE4D6")   # link documentale mancante

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
    """
    Description memorizzate del requisito: prima quelle della funzione,
    poi quelle registrate sotto qualsiasi altra funzione (lo stesso ID puo'
    essere stato estratto anche per una funzione diversa).
    """
    load_descriptions()
    k = id_key(req_id)
    out = dict(_desc.get(_n(func_id), {}).get(k, {}))
    for by_req in _desc.values():
        for c, d in (by_req.get(k) or {}).items():
            out.setdefault(c, d)
    return out


# ---------------------------------------------------------------------------
# Lettura del foglio Requisiti
# ---------------------------------------------------------------------------

@dataclass
class ReqRow:
    func_id: str
    func_desc: str
    req_id: str
    listed: set[str]                         # configurazioni in col E (normalizzate)
    cells: dict[str, str] = field(default_factory=dict)   # {config: testo cella}
    frs: str = ""                            # FRS (DOC ID) del requisito


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
    func_id = func_desc = func_frs = ""
    for r in range(cfg.REQ_HEADER_ROW + 1, ws.max_row + 1):
        fid = _s(ws.cell(r, cfg.REQ_FUNC_ID_COL).value)
        if fid:
            func_id, func_desc = fid, _s(ws.cell(r, cfg.REQ_DESC_COL).value)
            func_frs = _s(ws.cell(r, cfg.REQ_FRS_COL).value)
            continue
        req = _s(ws.cell(r, cfg.REQ_NUMBER_COL).value)
        if not req or not func_id:
            continue
        req = re.sub(r"^\s*\d+\)\s*", "", req)
        listed = {_n(x) for x in _s(ws.cell(r, cfg.REQ_CONFIG_COL).value).split(",") if x.strip()}
        cells = {c: _s(ws.cell(r, col).value) for c, col in cols.items()}
        frs = _s(ws.cell(r, cfg.REQ_FRS_COL).value) or func_frs
        rows.append(ReqRow(func_id, func_desc, req, listed, cells, frs))
    return list(cols), rows


def read_doc_links(ws, configs: list[str]) -> dict[str, dict[str, set[str]]]:
    """
    {FUNC ID normalizzato: {DOC ID (FRS) : {configurazioni con il link}}}
    dal foglio Funzioni (righe "Link" sotto ogni funzione).
    """
    cols: dict[int, str] = {}
    known = {_n(c): c for c in configs}
    for col in range(6, ws.max_column + 1):
        h = _s(ws.cell(1, col).value)
        if h:
            cols[col] = known.get(_n(h), h)
    out: dict[str, dict[str, set[str]]] = {}
    cur = None
    for r in range(2, ws.max_row + 1):
        fid = _s(ws.cell(r, 1).value)
        if fid:
            cur = out.setdefault(_n(fid), {})
            continue
        if cur is None or _s(ws.cell(r, 5).value).lower() != "link":
            continue
        doc = _s(ws.cell(r, 4).value)
        if not doc:
            continue
        have = cur.setdefault(doc, set())
        for col, cname in cols.items():
            cell = ws.cell(r, col)
            v = cell.value
            if (v is not None and not isinstance(v, str)) or _s(v) or \
                    (cell.hyperlink is not None and cell.hyperlink.target):
                have.add(cname)
    return out


def missing_link_docs(links: dict[str, dict[str, set[str]]], func_id: str,
                      frs: str, config: str) -> list[str]:
    """
    FRS (DOC ID) della funzione privi del link documentale per la
    configurazione. Lista vuota = il link c'e' (o la funzione non ha
    documenti nel foglio Funzioni).
    """
    docs = links.get(_n(func_id)) or {}
    if not docs:
        return []
    if frs:
        for d, have in docs.items():
            if _n(d) == _n(frs):
                return [] if config in have else [d]
    if any(config in have for have in docs.values()):
        return []
    linked = [d for d, have in docs.items() if have]
    # i requisiti provengono dagli FRS: gli altri documenti (FS, FD...) solo se unici
    return [d for d in linked if d.upper().startswith("FRS")] or linked


# ---------------------------------------------------------------------------
# Requisiti simili con ID diverso
# ---------------------------------------------------------------------------

def _desc_norm(text: str) -> str:
    t = (text or "").lower().replace("\u2013", "-").replace("\u2014", "-")
    t = re.sub(r"[^\w\s%./-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def desc_similarity(a: str, b: str) -> float:
    """Somiglianza 0-1 fra due Description (stessa logica delle opzioni 1 e 4)."""
    try:
        from confronto_reqs import desc_key
        ka, kb = desc_key(a), desc_key(b)
        if ka and ka == kb:
            return 1.0
    except Exception:
        pass
    na, nb = _desc_norm(a), _desc_norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    sm = SequenceMatcher(None, na, nb, autojunk=False)
    if sm.real_quick_ratio() < 0.5 or sm.quick_ratio() < 0.5:
        return 0.0
    return sm.ratio()


def link_similar(findings: list[Finding]) -> int:
    """
    Cerca, all'interno di ogni funzione, requisiti non MATCHED con ID diverso
    ma Description simile (es. lo stesso requisito rinumerato in un'altra
    configurazione). Le coppie trovate vengono rese contigue e annotate.
    Ritorna il numero di requisiti coinvolti.
    """
    soglia = float(getattr(cfg, "REQS_NOT_MATCHED_SIMILAR_MIN", 0.80))
    if soglia <= 0 or soglia > 1:
        return 0
    by_func: dict[str, list[Finding]] = {}
    for f in findings:
        by_func.setdefault(f.row.func_id, []).append(f)
    linked = 0
    new_order: list[Finding] = []
    for fid in dict.fromkeys(f.row.func_id for f in findings):
        group = by_func[fid]
        partners: dict[int, list[tuple[int, float]]] = {}
        for i in range(len(group)):
            a = group[i]
            for j in range(i + 1, len(group)):
                b = group[j]
                if id_key(a.row.req_id) == id_key(b.row.req_id):
                    continue
                # lo stesso requisito con ID diverso compare in configurazioni diverse
                if set(a.present) == set(b.present):
                    continue
                sim = desc_similarity(a.description, b.description)
                if sim >= soglia:
                    partners.setdefault(i, []).append((j, sim))
                    partners.setdefault(j, []).append((i, sim))
        placed: set[int] = set()
        for i in range(len(group)):
            if i in placed:
                continue
            stack, cluster = [i], []
            while stack:
                k = stack.pop()
                if k in placed:
                    continue
                placed.add(k)
                cluster.append(k)
                stack.extend(j for j, _ in sorted(partners.get(k, []), key=lambda x: -x[1]))
            cluster.sort()
            for k in cluster:
                f = group[k]
                for j, sim in sorted(partners.get(k, []), key=lambda x: -x[1]):
                    o = group[j]
                    f.similar_to.append((o.row.req_id, sim))
                    pct = f"{sim * 100:.0f}%"
                    tipo = ("stessa Description con ID diverso" if sim >= 0.999
                            else f"somiglianza della Description {pct}")
                    f.lines.insert(0, f"Requisito simile a {o.row.req_id} "
                                      f"({tipo}; presente in {', '.join(o.present)}).")
                if partners.get(k):
                    linked += 1
                new_order.append(f)
    findings[:] = new_order
    return linked


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
    ai_pending: bool = False   # nota AI non generata per il limite di chiamate
    link_missing: list[str] = field(default_factory=list)  # config senza link al documento
    similar_to: list[tuple[str, float]] = field(default_factory=list)  # (ID, somiglianza)

    def note(self) -> str:
        parts = list(self.lines)
        if self.ai_note:
            parts.append(self.ai_note)
        elif self.ai_pending:
            parts.append(AI_PENDING_MARK)
        txt = "\n".join(parts)
        limit = int(getattr(cfg, "REQS_NOT_MATCHED_NOTE_MAX_CHARS", 700))
        return txt if len(txt) <= limit else txt[:limit].rsplit(" ", 1)[0] + " […]"


def analyse(configs: list[str], rows: list[ReqRow],
            selected: list[str],
            links: Optional[dict[str, dict[str, set[str]]]] = None) -> list[Finding]:
    """Requisiti non MATCHED fra le configurazioni selezionate."""
    # configurazioni con almeno un requisito, per funzione
    func_cfgs: dict[str, set[str]] = {}
    for r in rows:
        s = func_cfgs.setdefault(_n(r.func_id), set())
        for c in configs:
            if cell_state(c, r.cells.get(c, ""), r.listed).kind != "absent":
                s.add(c)

    # Indice globale per ID: in quali funzioni compare per configurazione e
    # quali Description sono leggibili da QUALSIASI riga del foglio. Una
    # Description assente nella riga (es. "MISS VZI_BASE REQ, MATCHED")
    # viene cosi' recuperata dal dump della stessa ID sotto un'altra funzione.
    where: dict[str, dict[str, list[str]]] = {}
    gdesc: dict[str, dict[str, str]] = {}
    for r in rows:
        k = id_key(r.req_id)
        for c in configs:
            st = cell_state(c, r.cells.get(c, ""), r.listed)
            if st.kind == "absent":
                continue
            fl = where.setdefault(k, {}).setdefault(c, [])
            if r.func_id not in fl:
                fl.append(r.func_id)
            d = description_from_cell(st)
            if d:
                gdesc.setdefault(k, {}).setdefault(c, d)

    out: list[Finding] = []
    for r in rows:
        rk = id_key(r.req_id)
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
        for c, d in gdesc.get(rk, {}).items():
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
            no_link = missing_link_docs(links or {}, r.func_id, r.frs, c)
            if no_link:
                f.link_missing.append(c)
                f.lines.append(f"Mancanza link documentale per l'FRS "
                               f"{', '.join(no_link)} nella configurazione {c} "
                               f"(inserire il link nel foglio Funzioni).")
                continue
            line = f"Requisito non trovato per la configurazione {c}."
            altrove = [fid for fid in where.get(rk, {}).get(c, [])
                       if _n(fid) != _n(r.func_id)]
            if altrove:
                line = (f"Requisito non trovato per la configurazione {c} in "
                        f"questa funzione: in {c} e' nella funzione "
                        f"{', '.join(altrove[:2])} (probabile sconfinamento "
                        f"di sezione, verificare Rif. Pagina).")
            elif c not in func_cfgs.get(_n(r.func_id), set()):
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
        if f.link_missing and set(f.link_missing) == set(f.missing) and len(f.present) == 1 \
                and not f.diff_texts and not f.similar_to:
            continue   # manca solo il link: la nota e' gia' esaustiva
        p = build_prompt(f, selected)
        k = hashlib.sha1(f"{cfg.OLLAMA_MODEL}|{p}".encode("utf-8")).hexdigest()
        if k in _ai_cache:
            f.ai_note = _ai_cache[k]
        else:
            todo.append((f, p, k))
    # Requisiti con prompt identico (stessa ID sotto piu' funzioni con gli
    # stessi testi) -> una sola chiamata, nota condivisa.
    groups: dict[str, list[Finding]] = {}
    unique: list[tuple[Finding, str, str]] = []
    for f, p, k in todo:
        if k not in groups:
            unique.append((f, p, k))
        groups.setdefault(k, []).append(f)
    todo = unique
    max_calls = int(getattr(cfg, "REQS_NOT_MATCHED_AI_MAX_CALLS", 0) or 0)
    if max_calls > 0 and len(todo) > max_calls:
        skipped = todo[max_calls:]
        n_skip = sum(len(groups[k]) for _f, _p, k in skipped)
        log.warning(f"  [Reqs not matched] Note AI: {len(todo)} da generare ma "
                    f"REQS_NOT_MATCHED_AI_MAX_CALLS = {max_calls}: {n_skip} "
                    f"righe restano senza nota AI (marcate nel foglio). Tutte "
                    f"le righe sono comunque scritte; impostare 0 per "
                    f"generare tutte le note.")
        for _f, _p, k in skipped:
            for g in groups[k]:
                g.ai_pending = True
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
                _ai_cache[k] = nota
                for g in groups[k]:
                    g.ai_note = nota
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
    first_cfg = 5
    col_desc = first_cfg + len(selected)
    col_note = col_desc + 1
    headers = ["FUNC ID", "DESCRIZIONE FUNZIONE",
               getattr(cfg, "REQ_FRS_HEADER", "FRS"), "REQUISITO"]
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
        f"Requisiti non MATCHED: {len(findings)}"
        + (f"\nRighe senza Nota AI (limite REQS_NOT_MATCHED_AI_MAX_CALLS): "
           f"{sum(1 for f in findings if f.ai_pending)}"
           if any(f.ai_pending for f in findings) else ""), "AskTrainMind")

    row, prev = 2, None
    for f in findings:
        first = f.row.func_id != prev
        prev = f.row.func_id
        _cell(ws, row, 1, f.row.func_id, FONT_FUNC if first else None)
        _cell(ws, row, 2, f.row.func_desc)
        _cell(ws, row, 3, f.row.frs)
        _cell(ws, row, 4, f.row.req_id)
        _cell(ws, row, 4, f.row.req_id, fill=FILL_SIMILAR if f.similar_to else None)
        for j, c in enumerate(selected, start=first_cfg):
            if c in f.present:
                _cell(ws, row, j, MARK,
                      Font(bold=True, color="FF" + config_colors.color_for(c)[-6:]),
                      align=ALIGN_MARK)
            elif c in f.link_missing:
                _cell(ws, row, j, None, fill=FILL_NO_LINK).comment = Comment(
                    "Link documentale mancante nel foglio Funzioni", "AskTrainMind")
        if f.description:
            _cell(ws, row, col_desc, f.description)
        else:
            _cell(ws, row, col_desc, "(Description non presente nel foglio "
                                     "Requisiti per nessuna configurazione: "
                                     "rieseguire l'opzione 1 per la funzione)",
                  FONT_INFO)
        _cell(ws, row, col_note, f.note(), FONT_NOTE)
        row += 1

    ws.freeze_panes = ws.cell(2, first_cfg)
    ws.auto_filter.ref = f"A1:{get_column_letter(col_note)}{max(row - 1, 1)}"
    for col, w in ((1, 42), (2, 50), (3, 26), (4, 40), (col_desc, 80), (col_note, 70)):
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

LAST_SELECTED: list[str] = []


def run(wb, selection: str = "", interactive: bool = False,
        ai: Optional[bool] = None, scope=None) -> Optional[int]:
    """
    Ricrea il foglio "Reqs not matched". selection vuota = tutte le
    configurazioni. Ritorna il numero di requisiti non MATCHED, None se il
    foglio non e' stato scritto.

    scope (analysis_scope.Scope): solo i requisiti degli FRS e delle funzioni
    scelti; le configurazioni dell'ambito valgono se selection e' vuota.
    """
    import sheet_setup
    ws_req = sheet_setup.ensure_requisiti(wb)
    requisiti_sorter.ensure_frs_column(ws_req)
    configs, rows = read_requisiti(ws_req)
    if not rows:
        log.warning(f"  [Reqs not matched] Il foglio '{cfg.SHEET_REQUISITI}' non contiene "
                    "requisiti: compilarlo con l'opzione 1; il foglio viene creato vuoto.")
    if not configs:
        log.error("  [Reqs not matched] Nessuna configurazione nell'intestazione "
                  f"del foglio '{cfg.SHEET_REQUISITI}'.")
        return None

    if scope is not None:
        rows = [r for r in rows if scope.func_ok(r.func_id) and scope.frs_ok(r.frs)]
        if not selection.strip() and scope.configs:
            selection = ", ".join(c for c in scope.configs
                                  if _n(c) in {_n(x) for x in configs})
            if not selection:
                log.error("  [Reqs not matched] Nessuna delle configurazioni scelte "
                          f"e' presente nel foglio '{cfg.SHEET_REQUISITI}'.")
                return None
        if not scope.is_full:
            log.info(f"  [Reqs not matched] Ambito: {len(rows)} requisiti "
                     f"({'; '.join(scope.partial_reasons())})")

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
    global LAST_SELECTED
    LAST_SELECTED = list(selected)

    links = (read_doc_links(wb[cfg.SHEET_FUNZIONI], configs)
             if cfg.SHEET_FUNZIONI in wb.sheetnames else {})
    findings = analyse(configs, rows, selected, links)

    # Ordine del foglio Funzioni (LV, AUX, BAT, ...), poi ordine del foglio
    if cfg.SHEET_FUNZIONI in wb.sheetnames:
        order = requisiti_sorter.funzioni_order(wb[cfg.SHEET_FUNZIONI])
        funcs = list(dict.fromkeys(f.row.func_id for f in findings))
        rank = {funcs[i]: k for k, i in
                enumerate(requisiti_sorter.order_positions(funcs, order))}
        findings.sort(key=lambda f: rank[f.row.func_id])

    n_sim = link_similar(findings)
    n_link = sum(1 for f in findings if f.link_missing)
    if n_sim:
        log.info(f"  [Reqs not matched] {n_sim} requisiti con ID diverso ma Description "
                 f"simile: affiancati e annotati.")
    if n_link:
        log.info(f"  [Reqs not matched] {n_link} righe con link documentale mancante "
                 f"nel foglio Funzioni.")

    use_ai = getattr(cfg, "REQS_NOT_MATCHED_AI_NOTES", True) if ai is None else ai
    if use_ai:
        add_ai_notes(findings, selected)

    with interrupt_guard.protected():
        n = write_sheet(wb, selected, findings)
    log.info(f"  [Reqs not matched] Foglio '{SHEET_NAME}' ricreato: {n} requisiti "
             f"non MATCHED su {len(rows)} ({', '.join(selected)}).")
    return n
