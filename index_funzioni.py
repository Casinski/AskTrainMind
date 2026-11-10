"""
index_funzioni.py
-----------------
Opzione 2 del menu di funzioni_ai_filter.py: "Ricerca Funzioni".

Crea (o rigenera) il foglio "Index Funzioni" con l'elenco delle funzioni
presenti nei documenti FRS di ogni configurazione di rotabile.

SORGENTE
  Foglio CONFIG, sezione "Functional Requirement Specification (FRS)",
  righe da INDEX_FUNC_FIRST_DOC_ID a INDEX_FUNC_LAST_DOC_ID (col B = DOC ID).
  Per ogni configurazione (riga 1, gruppi di colonne):
      1a colonna del gruppo  → File/Codice del documento
      3a colonna del gruppo  → nota (es. "manca"), solo se il gruppo ha
                               almeno 3 colonne

COME SI TROVA UNA FUNZIONE
  Si legge il SOMMARIO del PDF (prime pagine) e si individua il capitolo
  "Functional requirements" (es. "3"). Sono funzioni i suoi figli diretti
  (3.1 Coupling, 3.2 Decoupling, ...) e, con INDEX_FUNC_MAX_DEPTH = 2, le
  sotto-funzioni (3.2.1 Pantograph - Lifting) escluse le voci generiche
  ("Function Design", "Requirements", ...).

STRUTTURA DEL FOGLIO
  Riga 1        : A = intestazione, B = "Paragrafo", C.. = configurazioni
  Per ogni DOC ID:
    riga titolo : A = DOC ID, C.. = documento di riferimento
    righe sotto : A = funzione, B = paragrafo dell'indice (es. 3.1, 3.2.1)
                  nel documento da cui la funzione e' stata presa,
                  C.. = MATCHED / NOT FOUND / N/A
  Le funzioni di VZI_Base vengono elencate per prime; poi, configurazione
  per configurazione, si aggiungono in coda solo quelle non ancora presenti.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import config as cfg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parametri (con valori di riserva se config.py non e' aggiornato)
# ---------------------------------------------------------------------------

SHEET_NAME   = getattr(cfg, "SHEET_INDEX_FUNZIONI", "Index Funzioni")
FIRST_DOC_ID = getattr(cfg, "INDEX_FUNC_FIRST_DOC_ID", "FRS_Drive Control")
LAST_DOC_ID  = getattr(cfg, "INDEX_FUNC_LAST_DOC_ID", "FRS_EMS")
BASE_CONFIG  = getattr(cfg, "REQ_BASE_CONFIG", "VZI_Base")
MAX_DEPTH    = getattr(cfg, "INDEX_FUNC_MAX_DEPTH", 2)
FUZZY        = getattr(cfg, "INDEX_FUNC_FUZZY_MATCH", 0.92)
TOC_PAGES    = getattr(cfg, "INDEX_FUNC_TOC_MAX_PAGES", 12)
CHAPTER_TITLES = getattr(cfg, "INDEX_FUNC_CHAPTER_TITLES",
                         ["Functional requirements", "Functional requirement"])
GENERIC_TITLES = {
    t.lower() for t in getattr(cfg, "INDEX_FUNC_GENERIC_TITLES", [
        "function design", "functional design", "requirements",
        "requirement", "general", "description", "overview",
        "normal condition", "normal conditions", "failure cases",
        "failure detection", "failure handling", "degraded mode",
        "degraded modes", "introduction", "definitions",
    ])
}
MISSING_NOTE = getattr(cfg, "INDEX_FUNC_MISSING_NOTE", "manca")

FIRST_CFG_COL = 3          # A = funzione, B = paragrafo, C.. = configurazioni

TXT_MATCHED   = "MATCHED"
TXT_NOT_FOUND = "NOT FOUND"
TXT_NA        = "N/A"

FONT_HEADER  = Font(bold=True, color="FFFFFFFF")
FILL_HEADER  = PatternFill("solid", fgColor="FF1F4E78")
FONT_DOC     = Font(bold=True, color="FF000000")
FILL_DOC     = PatternFill("solid", fgColor="FFDDEBF7")
FONT_FUNC    = Font(bold=True, color="FF000000")
FONT_SUBFUNC = Font(bold=False, color="FF000000")
FONT_MATCHED = Font(bold=True, color="FF008000")
FONT_MISSING = Font(bold=False, color="FFC00000")
FONT_NA      = Font(italic=True, color="FF888888")
FONT_DOC_KO  = Font(bold=True, color="FFC00000")

_INVALID_CODES = {"", "\\", "/", "_", "-", "–", "tbd", "#n/a", "n/a", "ref", "rev"}


# ---------------------------------------------------------------------------
# Modello dati
# ---------------------------------------------------------------------------

@dataclass
class TocEntry:
    index: str
    title: str
    page: int
    x: float = 0.0          # rientro del titolo nel sommario
    pdf_page: int = 0

    @property
    def depth(self) -> int:
        return self.index.count(".") + 1


@dataclass
class FuncEntry:
    index: str
    title: str
    page: int
    level: int            # 1 = funzione, 2 = sotto-funzione


@dataclass
class DocResult:
    """Esito dell'analisi di UN documento per UNA configurazione."""
    code: str = ""                  # codice letto da CONFIG
    note: str = ""                  # nota della 3a colonna (es. "manca")
    path: Optional[Path] = None
    status: str = ""                # ok | no_code | missing | not_found | no_index | error
    functions: list = field(default_factory=list)

    def label(self) -> str:
        """Testo della cella documento (riga titolo del blocco)."""
        if self.status == "no_code":
            return self.code or "\\"
        if self.status == "ok":
            return self.code
        reason = {
            "missing":   MISSING_NOTE,
            "not_found": "file non trovato",
            "no_index":  "indice 'Functional requirements' non trovato",
            "error":     "errore di lettura",
        }.get(self.status, self.status)
        return f"{self.code} ({reason})"


# ---------------------------------------------------------------------------
# Lettura del foglio CONFIG
# ---------------------------------------------------------------------------

def _str(v) -> str:
    return "" if v is None else str(v).strip()


def read_config_rows(ws) -> tuple[list[str], list[tuple[str, dict]]]:
    """
    Restituisce (configurazioni, righe) dove righe = [(doc_id, {config: (codice, nota)})]
    per i DOC ID da FIRST_DOC_ID a LAST_DOC_ID inclusi.
    """
    skip = {"doc description", "doc id", "doc ext", "doe ext", ""}
    starts: list[tuple[int, str]] = []
    for col in range(1, ws.max_column + 1):
        v = _str(ws.cell(1, col).value)
        if v and v.lower() not in skip:
            starts.append((col, v))

    groups: list[tuple[str, int, int]] = []   # (config, col_codice, larghezza)
    for i, (col, name) in enumerate(starts):
        nxt = starts[i + 1][0] if i + 1 < len(starts) else ws.max_column + 1
        groups.append((name, col, nxt - col))

    rows: list[tuple[str, dict]] = []
    inside = False
    for r in range(2, ws.max_row + 1):
        doc_id = _str(ws.cell(r, 2).value)
        if not inside:
            if doc_id.lower() == FIRST_DOC_ID.lower():
                inside = True
            else:
                continue
        if not doc_id:
            continue
        data: dict[str, tuple[str, str]] = {}
        for name, col, width in groups:
            code = _str(ws.cell(r, col).value)
            note = _str(ws.cell(r, col + 2).value) if width >= 3 else ""
            data[name] = (code, note)
        rows.append((doc_id, data))
        if doc_id.lower() == LAST_DOC_ID.lower():
            break

    if not inside:
        log.error(f"  [Index] DOC ID iniziale '{FIRST_DOC_ID}' non trovato in CONFIG")
    elif rows and rows[-1][0].lower() != LAST_DOC_ID.lower():
        log.warning(f"  [Index] DOC ID finale '{LAST_DOC_ID}' non trovato: "
                    f"analizzati fino a fine foglio")
    return [g[0] for g in groups], rows


# ---------------------------------------------------------------------------
# Ricerca del file su disco
# ---------------------------------------------------------------------------

_file_index: Optional[dict[str, list[Path]]] = None


def _build_file_index(root: Path) -> dict[str, list[Path]]:
    """Indice {nome_file_minuscolo_senza_estensione: [percorsi]} costruito una volta."""
    idx: dict[str, list[Path]] = {}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".pdf", ".docx", ".doc"):
            idx.setdefault(p.stem.lower(), []).append(p)
    log.info(f"  [Index] Indicizzati {sum(map(len, idx.values()))} file in {root}")
    return idx


def find_file(code: str, config_name: str, prefix: str = "FRS",
              root: Optional[Path] = None) -> Optional[Path]:
    """
    Cerca il documento:
      1. percorso standard  ROOT/<config>/CONFIG/<prefix>/<codice>.pdf
      2. ricerca per nome in tutta ROOT (indice costruito una sola volta),
         preferendo i percorsi che contengono il nome della configurazione
    """
    global _file_index
    root = root or cfg.ONEDRIVE_DOCS_ROOT
    if not root.exists():
        return None
    for ext in (".pdf", ".PDF"):
        p = root / config_name / "CONFIG" / prefix / f"{code}{ext}"
        if p.exists():
            return p
    if _file_index is None:
        _file_index = _build_file_index(root)
    matches = _file_index.get(code.lower(), [])
    if not matches:
        return None
    matches = sorted(matches, key=lambda m: (config_name not in m.parts,
                                             m.suffix.lower() != ".pdf"))
    return matches[0]


def _codes(raw: str) -> list[str]:
    """Una cella puo' contenere piu' codici separati da a-capo o spazi."""
    out = []
    for tok in re.split(r"[\s;,]+", raw or ""):
        tok = tok.strip()
        if tok and tok.lower() not in _INVALID_CODES and len(tok) > 3:
            out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Lettura del sommario
# ---------------------------------------------------------------------------

_IDX_ONLY  = re.compile(r"^(\d+(?:\.\d+)*)\.?$")
_IDX_TITLE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*\S)$")
_PAGE_ONLY = re.compile(r"^\d{1,4}$")
_TRAIL_PG  = re.compile(r"^(.*?\S)\s*(?:\.{2,}|…+|\s)\s*(\d{1,4})$")


def parse_toc_text(text: str) -> list[TocEntry]:
    """
    Voci (indice, titolo, pagina) dal testo di una pagina di sommario.

    Gestisce i formati prodotti da PyMuPDF:
        "3" / "Functional requirements" / "7"
        "4.1.1.1 Function Design" / "31"
        "3.1 Coupling ........ 5"
    e i titoli che vanno a capo su piu' righe.
    """
    lines = [re.sub(r"\s+", " ", ln.replace("\xa0", " ")).strip()
             for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]
    out: list[TocEntry] = []
    cur_idx, cur_title = None, []

    def close(page: int) -> None:
        nonlocal cur_idx, cur_title
        title = " ".join(cur_title).strip(" .")
        if cur_idx and title and re.search(r"[A-Za-z]", title):
            out.append(TocEntry(cur_idx, title, page))
        cur_idx, cur_title = None, []

    for ln in lines:
        if cur_idx is not None and cur_title and _PAGE_ONLY.match(ln):
            close(int(ln))
            continue
        m = _IDX_ONLY.match(ln)
        if m and cur_idx is None:
            cur_idx, cur_title = m.group(1), []
            continue
        m = _IDX_TITLE.match(ln)
        if m and (cur_idx is None or cur_title):
            cur_idx, cur_title = m.group(1), []
            rest = m.group(2)
            t = _TRAIL_PG.match(rest)
            if t and re.search(r"[A-Za-z]", t.group(1)):
                cur_title = [t.group(1).rstrip(" .")]
                close(int(t.group(2)))
            else:
                cur_title = [rest]
            continue
        if cur_idx is not None:
            t = _TRAIL_PG.match(ln)
            if t and re.search(r"[A-Za-z]", t.group(1)):
                cur_title.append(t.group(1).rstrip(" ."))
                close(int(t.group(2)))
            elif m and not cur_title:
                cur_idx = m.group(1)            # due indici di fila: vale l'ultimo
            else:
                cur_title.append(ln)
            if len(cur_title) > 4:              # non e' un sommario
                cur_idx, cur_title = None, []
    return out


def _line_text(line: dict) -> str:
    """
    Testo di una riga 'rawdict'. Gli spazi vengono tenuti solo se c'e' un
    vero distacco tra i caratteri: alcuni PDF inseriscono spazi fittizi
    dentro le parole ("In tro d u c tio n" -> "Introduction").
    """
    chars = [c for s in line["spans"] for c in s["chars"]]
    size = max((s["size"] for s in line["spans"]), default=10) or 10
    out, prev_x1, pending_space = [], None, False
    for c in chars:
        ch = c["c"]
        if ch.isspace():
            pending_space = True
            continue
        if pending_space and prev_x1 is not None and c["bbox"][0] - prev_x1 > 0.20 * size:
            out.append(" ")
        pending_space = False
        out.append(ch)
        prev_x1 = c["bbox"][2]
    return "".join(out).strip()


def _page_rows(page) -> list[list[tuple[float, str]]]:
    """Righe visive della pagina: [(x0, testo)] ordinate per x, raggruppate per y."""
    items = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            t = _line_text(ln)
            if t:
                items.append((round(ln["bbox"][1], 0), ln["bbox"][0], t))
    items.sort()
    rows: list[list[tuple[float, str]]] = []
    last_y = None
    for y, x, t in items:
        if last_y is None or abs(y - last_y) > 3:
            rows.append([])
            last_y = y
        rows[-1].append((x, t))
    return [sorted(r) for r in rows]


def _layout_entries(pdf) -> list[TocEntry]:
    """
    Voci di sommario lette dal layout delle prime pagine:
      [indice]  titolo ...................  pagina (allineata a destra)
    Il livello si ricava dalla x del titolo (rientro), utile quando
    la numerazione non e' gerarchica (documenti VSI: 1, 2, 3, ...).
    """
    out: list[TocEntry] = []
    for i in range(min(TOC_PAGES, pdf.page_count)):
        page = pdf[i]
        w = page.rect.width
        for row in _page_rows(page):
            if len(row) < 2:
                continue
            px, pt = row[-1]
            m = re.match(r"^(?:\.{2,}\s*)?(\d{1,4})$", pt)
            if not m or px < 0.75 * w:
                continue
            left = [(x, t) for x, t in row[:-1] if x < 0.6 * w]
            if not left:
                continue
            idx = ""
            mi = _IDX_ONLY.match(left[0][1])
            if mi and len(left) > 1:
                idx, left = mi.group(1), left[1:]
            else:
                mt = _IDX_TITLE.match(left[0][1])
                if mt:
                    idx = mt.group(1)
                    left = [(left[0][0], mt.group(2))] + left[1:]
            title = " ".join(t for _, t in left)
            title = re.sub(r"\s*\.{2,}.*$", "", title).strip(" .")
            if not re.search(r"[A-Za-z]{2}", title):
                continue
            out.append(TocEntry(idx, title, int(m.group(1)), row[0][0], i))
    return _drop_page_headers(out)


def _drop_page_headers(entries: list[TocEntry]) -> list[TocEntry]:
    """Scarta le righe d'intestazione ripetute identiche su piu' pagine (es. 'Page 3 di 48')."""
    pages: dict[tuple, set] = {}
    for e in entries:
        pages.setdefault((e.title, e.page, round(e.x)), set()).add(e.pdf_page)
    return [e for e in entries if len(pages[(e.title, e.page, round(e.x))]) == 1]


def _children(entries: list[TocEntry]) -> list[tuple[TocEntry, int]]:
    """
    Voci sotto il capitolo 'Functional requirements' con livello relativo
    (1 = figlio diretto). Usa la numerazione se gerarchica, altrimenti il rientro.
    """
    pos = next((k for k, e in enumerate(entries)
                if title_key(e.title) in CHAPTER_KEYS), None)
    if pos is None:
        return []
    chap = entries[pos]
    prefix = chap.index + "." if chap.index else None
    numbered = prefix is not None and any(
        e.index.startswith(prefix) for e in entries[pos + 1:pos + 4])
    out: list[tuple[TocEntry, int]] = []
    if numbered:
        for e in entries[pos + 1:]:
            if not e.index:
                continue
            if not e.index.startswith(prefix):
                break
            out.append((e, e.depth - chap.depth))
        return out

    tail = []
    for e in entries[pos + 1:]:
        if e.x <= chap.x + 2:
            break
        tail.append(e)
    levels = sorted({round(e.x) for e in tail})
    clusters: list[int] = []
    for x in levels:
        if not clusters or x - clusters[-1] > 4:
            clusters.append(x)
    # Numerazione assente o solo progressiva (documenti VSI): il paragrafo
    # viene ricostruito contando i capitoli allo stesso rientro e i figli.
    chap_no = sum(1 for e in entries[:pos + 1]
                  if abs(e.x - chap.x) <= 2 and e.pdf_page >= chap.pdf_page - 1)
    counters: list[int] = []
    for e in tail:
        lvl = 1 + max(k for k, cx in enumerate(clusters) if round(e.x) >= cx - 4)
        counters = (counters + [0] * lvl)[:lvl]
        counters[lvl - 1] += 1
        idx = ".".join(str(n) for n in [chap_no] + counters)
        out.append((TocEntry(idx, e.title, e.page, e.x, e.pdf_page), lvl))
    return out


def _children_text(pdf) -> list[tuple[TocEntry, int]]:
    """Riserva: sommario letto dal testo semplice (solo numerazione gerarchica)."""
    entries: list[TocEntry] = []
    for i in range(min(TOC_PAGES, pdf.page_count)):
        entries.extend(parse_toc_text(pdf[i].get_text()))
    return _children(entries)


def functions_from_pdf(pdf) -> list[FuncEntry]:
    """Funzioni sotto il capitolo 'Functional requirements' del sommario."""
    items = _children(_layout_entries(pdf)) or _children_text(pdf)
    out: list[FuncEntry] = []
    seen: set[str] = set()
    for e, level in items:
        if level < 1 or level > MAX_DEPTH:
            continue
        key = title_key(e.title)
        if key in GENERIC_KEYS or key in seen:
            continue
        seen.add(key)
        out.append(FuncEntry(e.index, e.title, e.page, level))
    return out


_doc_cache: dict[str, tuple[str, list]] = {}


def analyze_document(path: Path) -> tuple[str, list[FuncEntry]]:
    """(stato, funzioni) di un documento. Cache per percorso: stesso file, stesso esito."""
    key = str(path).lower()
    if key in _doc_cache:
        return _doc_cache[key]
    if path.suffix.lower() != ".pdf":
        res = ("no_index", [])
    else:
        try:
            import fitz
            with fitz.open(str(path)) as pdf:
                funcs = functions_from_pdf(pdf)
            res = ("ok", funcs) if funcs else ("no_index", [])
        except Exception as exc:
            log.error(f"  [Index] Errore lettura '{path.name}': {exc}")
            res = ("error", [])
    _doc_cache[key] = res
    return res


# ---------------------------------------------------------------------------
# Confronto dei titoli
# ---------------------------------------------------------------------------

def norm_title(s: str) -> str:
    t = (s or "").lower().replace("–", "-").replace("—", "-")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_key(s: str) -> str:
    """Chiave senza spazi ne' punteggiatura: 'Pantograph - Lifting' -> 'pantographlifting'."""
    return re.sub(r"[\W_]+", "", (s or "").lower())


GENERIC_KEYS = {title_key(t) for t in GENERIC_TITLES}
CHAPTER_KEYS = {title_key(t) for t in CHAPTER_TITLES}


def find_match(title: str, funcs: list[FuncEntry]) -> Optional[FuncEntry]:
    """Funzione con lo stesso titolo (normalizzato o quasi identico)."""
    k = norm_title(title)
    tk = title_key(title)
    best, best_r = None, 0.0
    for f in funcs:
        fk = norm_title(f.title)
        if fk == k or title_key(f.title) == tk:
            return f
        r = SequenceMatcher(None, k, fk).ratio()
        if r > best_r:
            best, best_r = f, r
    return best if best_r >= FUZZY else None


# ---------------------------------------------------------------------------
# Analisi completa
# ---------------------------------------------------------------------------

def analyze_row(doc_id: str, data: dict, configs: list[str]) -> dict[str, DocResult]:
    prefix = doc_id.split("_")[0] if "_" in doc_id else "FRS"
    out: dict[str, DocResult] = {}
    for cname in configs:
        raw, note = data.get(cname, ("", ""))
        res = DocResult(code=raw.replace("\n", " / "), note=note)
        codes = _codes(raw)
        if not codes:
            res.status = "no_code"
            out[cname] = res
            continue
        for code in codes:
            p = find_file(code, cname, prefix)
            if p:
                res.path, res.code = p, code
                break
        if res.path is None:
            noted_missing = MISSING_NOTE.lower() in note.lower()
            res.status = "missing" if noted_missing else "not_found"
            log.info(f"  [{cname}] {raw!r}: "
                     f"{'segnato ' + MISSING_NOTE if noted_missing else 'file non trovato'}")
        else:
            res.status, res.functions = analyze_document(res.path)
            log.info(f"  [{cname}] {res.path.name}: {len(res.functions)} funzioni"
                     + ("" if res.status == "ok" else f" ({res.status})"))
        out[cname] = res
    return out


def ordered_functions(results: dict[str, DocResult], configs: list[str]) -> list[tuple[FuncEntry, str]]:
    """
    Elenco unico delle funzioni del blocco: prima quelle di VZI_Base, poi
    quelle delle altre configurazioni non ancora presenti.
    Ritorna [(funzione, configurazione_di_origine)].
    """
    order = sorted(configs, key=lambda c: c.lower() != BASE_CONFIG.lower())
    rows: list[tuple[FuncEntry, str]] = []
    for cname in order:
        res = results.get(cname)
        if not res or res.status != "ok":
            continue
        for f in res.functions:
            if find_match(f.title, [r[0] for r in rows]) is None:
                rows.append((f, cname))
    return rows


# ---------------------------------------------------------------------------
# Scrittura del foglio
# ---------------------------------------------------------------------------

def _prepare_sheet(wb):
    """Rigenera il foglio: lo elimina se esiste e lo ricrea nella stessa posizione."""
    pos = None
    if SHEET_NAME in wb.sheetnames:
        pos = wb.sheetnames.index(SHEET_NAME)
        del wb[SHEET_NAME]
    return wb.create_sheet(SHEET_NAME, pos)


def _cell(ws, r, c, value, font=None, fill=None, indent=0):
    cell = ws.cell(r, c, value)
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    cell.alignment = Alignment(vertical="top", wrap_text=True, indent=indent)
    return cell


def write_sheet(wb, configs: list[str], blocks: list[tuple[str, dict]]) -> int:
    ws = _prepare_sheet(wb)
    _cell(ws, 1, 1, "DOC ID / Funzione", FONT_HEADER, FILL_HEADER)
    _cell(ws, 1, 2, "Paragrafo", FONT_HEADER, FILL_HEADER)
    colors = getattr(cfg, "CONFIG_COLOR_MAP", {})
    for j, cname in enumerate(configs, start=FIRST_CFG_COL):
        fill = (PatternFill("solid", fgColor="FF" + colors[cname])
                if cname in colors else FILL_HEADER)
        _cell(ws, 1, j, cname, FONT_HEADER, fill)

    row, n_func = 2, 0
    for doc_id, results in blocks:
        _cell(ws, row, 1, doc_id, FONT_DOC, FILL_DOC)
        _cell(ws, row, 2, None, FONT_DOC, FILL_DOC)
        for j, cname in enumerate(configs, start=FIRST_CFG_COL):
            res = results[cname]
            font = FONT_DOC if res.status in ("ok", "no_code") else FONT_DOC_KO
            c = _cell(ws, row, j, res.label(), font, FILL_DOC)
            if res.path:
                c.comment = Comment(str(res.path), "AskTrainMind")
        row += 1

        for func, origin in ordered_functions(results, configs):
            _cell(ws, row, 1, func.title,
                  FONT_FUNC if func.level == 1 else FONT_SUBFUNC,
                  indent=0 if func.level == 1 else 2)
            c = _cell(ws, row, 2, func.index or None,
                      FONT_FUNC if func.level == 1 else FONT_SUBFUNC)
            c.number_format = "@"
            c.comment = Comment(f"Paragrafo nel documento {origin} "
                                f"({results[origin].code}) — pag. {func.page}",
                                "AskTrainMind")
            for j, cname in enumerate(configs, start=FIRST_CFG_COL):
                res = results[cname]
                if res.status != "ok":
                    _cell(ws, row, j, TXT_NA, FONT_NA)
                    continue
                hit = find_match(func.title, res.functions)
                if hit:
                    c = _cell(ws, row, j, TXT_MATCHED, FONT_MATCHED)
                    note = f"§{hit.index} {hit.title} — pag. {hit.page}"
                    c.comment = Comment(note, "AskTrainMind")
                else:
                    _cell(ws, row, j, TXT_NOT_FOUND, FONT_MISSING)
            row += 1
            n_func += 1

    ws.column_dimensions["A"].width = 55
    ws.column_dimensions["B"].width = 11
    for j in range(FIRST_CFG_COL, len(configs) + FIRST_CFG_COL):
        ws.column_dimensions[get_column_letter(j)].width = 22
    ws.freeze_panes = "C2"
    return n_func


def run(wb_data, wb_write) -> int:
    """Esegue la Ricerca Funzioni. Ritorna il numero di righe funzione scritte."""
    if cfg.SHEET_CONFIG not in wb_data.sheetnames:
        log.error(f"Foglio '{cfg.SHEET_CONFIG}' non trovato.")
        return 0
    if not cfg.ONEDRIVE_DOCS_ROOT.exists():
        log.error(f"Cartella documenti non trovata: {cfg.ONEDRIVE_DOCS_ROOT}")
        return 0

    configs, rows = read_config_rows(wb_data[cfg.SHEET_CONFIG])
    log.info(f"  [Index] Configurazioni: {configs}")
    log.info(f"  [Index] DOC ID da analizzare: {len(rows)} "
             f"({FIRST_DOC_ID} → {LAST_DOC_ID})")

    blocks = []
    for doc_id, data in rows:
        log.info(f"\n{'─' * 55}\n  {doc_id}\n{'─' * 55}")
        blocks.append((doc_id, analyze_row(doc_id, data, configs)))

    n = write_sheet(wb_write, configs, blocks)
    log.info(f"\n  [Index] Foglio '{SHEET_NAME}': {len(blocks)} DOC ID, {n} funzioni")
    return n
