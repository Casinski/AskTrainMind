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
  Riga 1        : A = intestazione, B = "Paragrafo",
                  C = "FUNC ID", D = "DESCRIZIONE FUNZIONE" (solo con
                  INDEX_FUNC_PROPOSE_IDS = True), poi le configurazioni
  Per ogni DOC ID:
    riga titolo : A = DOC ID, C = prefisso FUNC ID, configurazioni =
                  documento di riferimento
    righe sotto : A = funzione, B = paragrafo dell'indice (es. 3.1, 3.2.1)
                  nel documento da cui la funzione e' stata presa,
                  C/D = FUNC ID e DESCRIZIONE FUNZIONE da riportare nelle
                  colonne A e B del foglio "Funzioni" (ricopiati se la
                  funzione c'e' gia', altrimenti proposti: vedi
                  func_id_proposer.py),
                  configurazioni = MATCHED / NOT FOUND / N/A
  Le funzioni di VZI_Base vengono elencate per prime; poi, configurazione
  per configurazione, si aggiungono in coda solo quelle non ancora presenti.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import config as cfg
import func_id_proposer
import interrupt_guard

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
PROPOSE_IDS  = getattr(cfg, "INDEX_FUNC_PROPOSE_IDS", True)
# Analisi dei PDF salvate su disco (solo con SAVE_PROGRESS = True): alla
# ripartenza dopo un'interruzione i documenti gia' letti non si rileggono.
DOC_CACHE_FILE = getattr(
    cfg, "INDEX_FUNC_DOC_CACHE_FILE",
    Path.home() / "AppData" / "Local" / "FunzioniAI" / "index_doc_cache.json",
)
_DOC_CACHE_VERSION = 1

COL_FUNC_ID   = 3          # C = FUNC ID              (solo con PROPOSE_IDS)
COL_FUNC_DESC = 4          # D = DESCRIZIONE FUNZIONE (solo con PROPOSE_IDS)

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
FONT_COPIED  = Font(bold=False, color="FF000000")
FONT_PROPOSED = Font(bold=False, italic=True, color="FF0070C0")

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
    parent: str = ""      # titolo del paragrafo padre (solo sotto-funzioni)


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
    parent = ""
    for e, level in items:
        if level == 1:
            parent = e.title
        if level < 1 or level > MAX_DEPTH:
            continue
        key = title_key(e.title)
        if key in GENERIC_KEYS or key in seen:
            continue
        seen.add(key)
        out.append(FuncEntry(e.index, e.title, e.page, level,
                             parent if level > 1 else ""))
    return out


# ---------------------------------------------------------------------------
# Testo del paragrafo (per la descrizione proposta)
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+\S")


def _opens_section(line: str, func: FuncEntry) -> bool:
    words = set(norm_title(func.title).split())
    if norm_title(line) == norm_title(func.title):
        return True
    if not func.index or not re.match(re.escape(func.index) + r"\.?(\s|$)", line):
        return False
    found = set(norm_title(line).split())
    return len(words & found) >= max(1, int(len(words) * 0.6))


def _ends_section(line: str, func: FuncEntry) -> bool:
    """Intestazione di un paragrafo fratello o superiore (es. 3.10 dopo 3.9.x)."""
    m = _HEADING.match(line)
    if not m or not func.index or "." not in func.index:
        return False
    idx = m.group(1)
    if idx == func.index or idx.startswith(func.index + "."):
        return False
    return (idx.split(".")[0] == func.index.split(".")[0]
            and idx.count(".") <= func.index.count("."))


def section_text(path: Path, func: FuncEntry, max_chars: int = 3000) -> str:
    """
    Testo del paragrafo della funzione: si cerca l'intestazione nel corpo
    del PDF intorno alla pagina dell'indice (le pagine del sommario sono
    escluse) e si legge fino al paragrafo successivo o a max_chars.
    """
    if path is None or path.suffix.lower() != ".pdf":
        return ""
    import fitz
    with fitz.open(str(path)) as pdf:
        toc = {e.pdf_page for e in _layout_entries(pdf)}
        start = func.page - 1
        order = [start + d for d in (0, 1, 2, 3, 4, 5, 6, -1, -2, 7, 8, 9, 10)]
        for p in order:
            if p < 0 or p >= pdf.page_count or p in toc:
                continue
            lines = [re.sub(r"\s+", " ", ln.replace("\xa0", " ")).strip()
                     for ln in pdf[p].get_text().splitlines()]
            k = next((i for i, ln in enumerate(lines) if ln and _opens_section(
                " ".join([ln] + lines[i + 1:i + 3]) if _IDX_ONLY.match(ln) else ln,
                func)), None)
            if k is None:
                continue
            out: list[str] = []
            page, chars = p, 0
            while page < pdf.page_count and chars < max_chars:
                body = lines[k:] if page == p else [
                    re.sub(r"\s+", " ", ln.replace("\xa0", " ")).strip()
                    for ln in pdf[page].get_text().splitlines()]
                for i, ln in enumerate(body):
                    if (page != p or i > 0) and _ends_section(ln, func):
                        return "\n".join(out)[:max_chars]
                    if ln:
                        out.append(ln)
                        chars += len(ln) + 1
                page += 1
            return "\n".join(out)[:max_chars]
    return ""


_doc_cache: dict[str, tuple[str, list]] = {}
_disk_cache: Optional[dict] = None


def _disk_cache_on() -> bool:
    return bool(interrupt_guard.ENABLED and DOC_CACHE_FILE)


def _file_stamp(path: Path) -> str:
    try:
        st = path.stat()
        return f"{st.st_size}:{st.st_mtime_ns}"
    except OSError:
        return ""


def _load_disk_cache() -> dict:
    global _disk_cache
    if _disk_cache is None:
        _disk_cache = {}
        try:
            raw = json.loads(Path(DOC_CACHE_FILE).read_text(encoding="utf-8"))
            if raw.get("version") == _DOC_CACHE_VERSION:
                _disk_cache = raw.get("docs", {})
                log.info(f"  [Index] Cache analisi: {len(_disk_cache)} documenti "
                         f"gia' analizzati ({DOC_CACHE_FILE})")
        except (OSError, ValueError, AttributeError):
            pass
    return _disk_cache


def _save_disk_cache() -> None:
    if _disk_cache is None:
        return
    try:
        path = Path(DOC_CACHE_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({"version": _DOC_CACHE_VERSION, "docs": _disk_cache},
                                  ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.warning(f"  [Index] Cache analisi non salvata: {exc}")


def analyze_document(path: Path) -> tuple[str, list[FuncEntry]]:
    """
    (stato, funzioni) di un documento. Cache per percorso: stesso file,
    stesso esito. Con SAVE_PROGRESS l'esito e' salvato anche su disco
    (valido finche' dimensione e data del file non cambiano).
    """
    key = str(path).lower()
    if key in _doc_cache:
        return _doc_cache[key]
    stamp = _file_stamp(path) if _disk_cache_on() else ""
    if stamp:
        hit = _load_disk_cache().get(key)
        if hit and hit.get("stamp") == stamp:
            res = (hit["status"], [FuncEntry(**f) for f in hit["functions"]])
            _doc_cache[key] = res
            return res
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
    if stamp and res[0] != "error":
        _load_disk_cache()[key] = {"stamp": stamp, "status": res[0],
                                   "functions": [asdict(f) for f in res[1]]}
        _save_disk_cache()          # salvataggio progressivo
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


def write_sheet(wb, configs: list[str], blocks: list[tuple[str, dict]],
                proposals: Optional[list] = None,
                prefixes: Optional[dict] = None) -> int:
    """
    proposals = per ogni blocco, una func_id_proposer.Proposal per funzione
    (stesso ordine di ordered_functions); None = colonne FUNC ID e
    DESCRIZIONE FUNZIONE omesse.
    """
    ws = _prepare_sheet(wb)
    with_ids = proposals is not None
    first_cfg = COL_FUNC_DESC + 1 if with_ids else 3
    _cell(ws, 1, 1, "DOC ID / Funzione", FONT_HEADER, FILL_HEADER)
    _cell(ws, 1, 2, "Paragrafo", FONT_HEADER, FILL_HEADER)
    if with_ids:
        _cell(ws, 1, COL_FUNC_ID, "FUNC ID", FONT_HEADER, FILL_HEADER)
        _cell(ws, 1, COL_FUNC_DESC, "DESCRIZIONE FUNZIONE", FONT_HEADER, FILL_HEADER)
    colors = getattr(cfg, "CONFIG_COLOR_MAP", {})
    for j, cname in enumerate(configs, start=first_cfg):
        fill = (PatternFill("solid", fgColor="FF" + colors[cname])
                if cname in colors else FILL_HEADER)
        _cell(ws, 1, j, cname, FONT_HEADER, fill)

    row, n_func = 2, 0
    for b, (doc_id, results) in enumerate(blocks):
        _cell(ws, row, 1, doc_id, FONT_DOC, FILL_DOC)
        _cell(ws, row, 2, None, FONT_DOC, FILL_DOC)
        if with_ids:
            prefix = (prefixes or {}).get(doc_id)
            c = _cell(ws, row, COL_FUNC_ID, prefix[0] if prefix else None,
                      FONT_DOC, FILL_DOC)
            if prefix:
                c.comment = Comment(f"Prefisso FUNC ID: {prefix[1]}", "AskTrainMind")
            _cell(ws, row, COL_FUNC_DESC, None, FONT_DOC, FILL_DOC)
        for j, cname in enumerate(configs, start=first_cfg):
            res = results[cname]
            font = FONT_DOC if res.status in ("ok", "no_code") else FONT_DOC_KO
            c = _cell(ws, row, j, res.label(), font, FILL_DOC)
            if res.path:
                c.comment = Comment(str(res.path), "AskTrainMind")
        row += 1

        for k, (func, origin) in enumerate(ordered_functions(results, configs)):
            _cell(ws, row, 1, func.title,
                  FONT_FUNC if func.level == 1 else FONT_SUBFUNC,
                  indent=0 if func.level == 1 else 2)
            c = _cell(ws, row, 2, func.index or None,
                      FONT_FUNC if func.level == 1 else FONT_SUBFUNC)
            c.number_format = "@"
            c.comment = Comment(f"Paragrafo nel documento {origin} "
                                f"({results[origin].code}) — pag. {func.page}",
                                "AskTrainMind")
            if with_ids:
                prop = proposals[b][k]
                font = FONT_COPIED if prop.existing else FONT_PROPOSED
                c = _cell(ws, row, COL_FUNC_ID, prop.func_id, font)
                c.comment = Comment(prop.note, "AskTrainMind")
                _cell(ws, row, COL_FUNC_DESC, prop.description or None, font)
            for j, cname in enumerate(configs, start=first_cfg):
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
    if with_ids:
        ws.column_dimensions[get_column_letter(COL_FUNC_ID)].width = 45
        ws.column_dimensions[get_column_letter(COL_FUNC_DESC)].width = 70
    for j in range(first_cfg, len(configs) + first_cfg):
        ws.column_dimensions[get_column_letter(j)].width = 22
    ws.freeze_panes = ws.cell(2, first_cfg).coordinate
    return n_func


def propose_ids(wb_data, configs: list[str], blocks: list[tuple[str, dict]],
                use_llm: bool = True):
    """
    FUNC ID e DESCRIZIONE FUNZIONE per ogni funzione dei blocchi
    (vedi func_id_proposer). Ritorna (proposte, {doc_id: (prefisso, origine)}).

    use_llm=False (dopo un'interruzione): nessuna chiamata a Ollama, le
    descrizioni gia' generate vengono riprese dalla cache, le altre dal
    modello INDEX_FUNC_DESC_TEMPLATE.
    """
    sheet = getattr(cfg, "SHEET_FUNZIONI", "Funzioni")
    existing = []
    if sheet in wb_data.sheetnames:
        existing = func_id_proposer.read_existing_functions(wb_data[sheet])
    else:
        log.warning(f"  [Index] Foglio '{sheet}' non trovato: "
                    f"nessuna funzione esistente da cui apprendere")
    log.info(f"\n  [Index] FUNC ID / DESCRIZIONE: {len(existing)} funzioni "
             f"esistenti nel foglio '{sheet}'")

    mode = func_id_proposer.DESC_MODE.lower()
    llm = func_id_proposer.ollama_llm() if mode == "ai" and use_llm else None
    if mode == "ai" and llm is None and use_llm:
        log.warning("  [Index] Ollama non disponibile: descrizioni dal modello "
                    "INDEX_FUNC_DESC_TEMPLATE")
    proposer = func_id_proposer.FuncIdProposer(existing, desc_mode=mode, llm=llm,
                                               cache_only=not use_llm)

    items = [(doc_id, ordered_functions(results, configs)) for doc_id, results in blocks]
    origin_path = {id(f): results[o].path
                   for (_, results), (_, funcs) in zip(blocks, items)
                   for f, o in funcs}

    def text_for(_doc_id: str, func: FuncEntry) -> str:
        try:
            return section_text(origin_path.get(id(func)), func,
                                func_id_proposer.DESC_INPUT_CHARS)
        except Exception as exc:
            log.debug(f"  [Index] testo di '{func.title}' non estratto: {exc}")
            return ""

    proposals = proposer.resolve(
        [(doc_id, [f for f, _ in funcs]) for doc_id, funcs in items], text_for)
    prefixes = {doc_id: (proposer.prefix_for(doc_id), proposer.prefix_source[doc_id])
                for doc_id, _ in blocks}
    n_new = sum(1 for block in proposals for p in block if not p.existing)
    n_all = sum(len(block) for block in proposals)
    log.info(f"  [Index] FUNC ID: {n_all - n_new} ricopiati, {n_new} proposti")
    return proposals, prefixes


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

    # Con SAVE_PROGRESS, su Ctrl+C il foglio viene comunque scritto con i
    # DOC ID analizzati fino a quel momento (vedi interrupt_guard.py).
    blocks = []
    stopped_at = ""
    try:
        for doc_id, data in rows:
            log.info(f"\n{'─' * 55}\n  {doc_id}\n{'─' * 55}")
            stopped_at = doc_id
            blocks.append((doc_id, analyze_row(doc_id, data, configs)))
        stopped_at = ""
    except KeyboardInterrupt as exc:
        interrupt_guard.handle(exc, f"Ricerca Funzioni, DOC ID '{stopped_at}'")

    proposals = prefixes = None
    if PROPOSE_IDS:
        try:
            proposals, prefixes = propose_ids(wb_data, configs, blocks,
                                              use_llm=not stopped_at)
        except KeyboardInterrupt as exc:
            interrupt_guard.handle(exc, "Ricerca Funzioni, FUNC ID / DESCRIZIONE")
            stopped_at = stopped_at or "proposte FUNC ID"
            proposals, prefixes = propose_ids(wb_data, configs, blocks, use_llm=False)
    with interrupt_guard.protected():
        n = write_sheet(wb_write, configs, blocks, proposals, prefixes)
        if stopped_at:
            ws = wb_write[SHEET_NAME]
            ws.cell(1, 1).comment = Comment(
                f"Elenco PARZIALE: esecuzione interrotta ({stopped_at}). "
                f"Rilancia l'opzione 2 per completarlo: i documenti gia' "
                f"analizzati vengono ripresi dalla cache.", "AskTrainMind")
    log.info(f"\n  [Index] Foglio '{SHEET_NAME}': {len(blocks)} DOC ID, {n} funzioni"
             + (" (PARZIALE: esecuzione interrotta)" if stopped_at else ""))
    return n
