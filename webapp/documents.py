"""
webapp/documents.py
-------------------
Documenti PDF per la web app:
  - indice dei nomi dei file nelle cartelle documenti (costruito in
    background, salvato su disco, nessuna scansione per richiesta);
  - risoluzione DOC ID + configurazione -> file locale;
  - testo di una sezione, rendering di pagine e ritagli in PNG (cache);
  - individuazione di figure e tabelle nelle pagine di una sezione;
  - indice full-text (SQLite FTS5) incrementale delle pagine dei PDF,
    usato dalla sezione "Chiedi" per cercare nei documenti del computer.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Optional

import config as cfg

from .workbook import PROGRAM_DIR, cache_dir

log = logging.getLogger(__name__)

DOC_EXT = (".pdf", ".docx", ".doc")


def _fitz():
    try:
        import pymupdf as fitz  # PyMuPDF >= 1.24
    except ImportError:
        import fitz
    return fitz


def doc_roots() -> list[Path]:
    roots = []
    for p in [getattr(cfg, "ONEDRIVE_DOCS_ROOT", None), PROGRAM_DIR / "docs",
              getattr(cfg, "CACHE_DIR", None), *(getattr(cfg, "WEB_EXTRA_DOC_DIRS", []) or [])]:
        if not p:
            continue
        p = Path(p)
        try:
            if p.is_dir() and p.resolve() not in [r.resolve() for r in roots]:
                roots.append(p)
        except OSError:
            continue
    return roots


# ---------------------------------------------------------------------------
# Indice dei file
# ---------------------------------------------------------------------------

class FileIndex:
    """{nome file minuscolo: [percorsi]} di tutti i documenti delle cartelle."""

    def __init__(self):
        self.by_name: dict[str, list[str]] = {}
        self.by_id: dict[str, str] = {}
        self.built_at = 0.0
        self.building = False
        self._lock = threading.Lock()
        self._file = cache_dir() / "file_index.json"
        self._load()

    @staticmethod
    def fid(path: str) -> str:
        return hashlib.sha1(os.path.normcase(path).encode("utf-8")).hexdigest()[:16]

    def _set(self, by_name: dict[str, list[str]], built_at: float) -> None:
        with self._lock:
            self.by_name = by_name
            self.by_id = {self.fid(p): p for ps in by_name.values() for p in ps}
            self.built_at = built_at

    def _load(self) -> None:
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            if data.get("roots") == [str(r) for r in doc_roots()]:
                self._set(data["files"], data["built_at"])
        except (OSError, ValueError, KeyError):
            pass

    def build_async(self, force: bool = False) -> None:
        if self.building or (self.by_name and not force and time.time() - self.built_at < 6 * 3600):
            return
        self.building = True
        threading.Thread(target=self._build, daemon=True).start()

    def _build(self) -> None:
        try:
            t0 = time.time()
            files: dict[str, list[str]] = {}
            for root in doc_roots():
                for dirpath, _dirs, names in os.walk(root):
                    for n in names:
                        if n.lower().endswith(DOC_EXT) and not n.startswith("~$"):
                            files.setdefault(n.lower(), []).append(os.path.join(dirpath, n))
            self._set(files, time.time())
            try:
                self._file.write_text(json.dumps({"roots": [str(r) for r in doc_roots()],
                                                  "files": files, "built_at": self.built_at}),
                                      encoding="utf-8")
            except OSError:
                pass
            log.info(f"Indice documenti: {sum(len(v) for v in files.values())} file "
                     f"in {time.time() - t0:.1f} s")
        finally:
            self.building = False

    def wait(self, timeout: float = 20) -> None:
        if not self.by_name:
            self.build_async()
            t0 = time.time()
            while self.building and time.time() - t0 < timeout:
                time.sleep(0.1)

    def find(self, code: str, config_name: str = "", folder_hint: str = "") -> Optional[str]:
        """File il cui nome inizia con il codice; preferisce il percorso che
        contiene la configurazione (e la cartella, es. CONFIG/FRS)."""
        code = re.sub(r"\s*\(.*$", "", (code or "").strip()).lower()
        if not code:
            return None
        self.wait()
        cands: list[str] = []
        for name, paths in self.by_name.items():
            stem = name.rsplit(".", 1)[0]
            if stem == code or stem.startswith(code + "_") or stem.startswith(code + " ") \
                    or (name.startswith(code) and len(stem) - len(code) <= 3):
                cands.extend(paths)
        if not cands:
            return None

        def score(p: str) -> tuple:
            parts = [x.lower() for x in Path(p).parts]
            return (config_name.lower() in parts,
                    bool(folder_hint) and folder_hint.lower() in parts,
                    p.lower().endswith(".pdf"),
                    Path(p).stem.lower() == code,
                    "_old" not in p.lower())
        return max(cands, key=score)

    def path(self, fid: str) -> Optional[str]:
        return self.by_id.get(fid)

    def register(self, path: str) -> str:
        f = self.fid(path)
        self.by_id.setdefault(f, path)
        return f


FILES = FileIndex()


def resolve_doc(model: dict, doc_id: str, config_name: str) -> Optional[str]:
    code = ((model.get("config_map") or {}).get(doc_id) or {}).get(config_name) \
        or ((model.get("man_cpr_map") or {}).get(doc_id) or {}).get(config_name)
    if not code or code.strip() in ("\\", "-", "N/A"):
        return None
    prefix = doc_id.split("_")[0] if "_" in doc_id else ""
    return FILES.find(code, config_name, prefix)


def doc_code(model: dict, doc_id: str, config_name: str) -> str:
    return ((model.get("config_map") or {}).get(doc_id) or {}).get(config_name, "") \
        or ((model.get("man_cpr_map") or {}).get(doc_id) or {}).get(config_name, "")


# ---------------------------------------------------------------------------
# PDF: testo, pagine, ritagli
# ---------------------------------------------------------------------------

_open_lock = threading.RLock()


@lru_cache(maxsize=24)
def _open(path: str, mtime: float):
    return _fitz().open(path)


def open_pdf(path: str):
    with _open_lock:
        return _open(path, os.path.getmtime(path))


def page_count(path: str) -> int:
    try:
        return open_pdf(path).page_count
    except Exception:
        return 0


def page_text(path: str, page: int) -> str:
    """Testo della pagina (1-based)."""
    try:
        d = open_pdf(path)
        if 1 <= page <= d.page_count:
            with _open_lock:
                return d[page - 1].get_text()
    except Exception:
        pass
    return ""


def render_png(path: str, page: int, clip: Optional[tuple] = None, dpi: int = 110) -> Optional[bytes]:
    key = hashlib.sha1(f"{path}|{os.path.getmtime(path)}|{page}|{clip}|{dpi}".encode()).hexdigest()
    out = cache_dir() / "png" / f"{key}.png"
    if out.is_file():
        return out.read_bytes()
    fitz = _fitz()
    try:
        d = open_pdf(path)
        if not 1 <= page <= d.page_count:
            return None
        with _open_lock:
            pg = d[page - 1]
            rect = fitz.Rect(*clip) & pg.rect if clip else pg.rect
            pix = pg.get_pixmap(dpi=dpi, clip=rect)
            data = pix.tobytes("png")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return data
    except Exception as exc:
        log.warning(f"Rendering non riuscito {path} p.{page}: {exc}")
        return None


_RANGE_RE = re.compile(r"Pag\.\s*iniziale:\s*(?:parte di\s*)?pag\.?\s*(\d+).*?"
                       r"Pag\.\s*finale:\s*(?:parte di\s*)?pag\.?\s*(\d+)", re.I | re.S)


def section_range(ai_text: str, start_page: int) -> tuple[int, int]:
    """Pagine (iniziale, finale) della trattazione: dalla cella "Funzioni AI"
    ("Pag. iniziale: ... Pag. finale: ...") o, in mancanza, Rif. Pagina."""
    m = _RANGE_RE.search(ai_text or "")
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b >= a:
            return a, b
    if start_page:
        return start_page, start_page + 2
    return 0, 0


def section_text(path: str, first: int, last: int, max_chars: int = 12000) -> str:
    out = []
    n = 0
    last = min(last, first + int(getattr(cfg, "WEB_QA_MAX_SECTION_PAGES", 12)) - 1)
    for p in range(first, last + 1):
        t = page_text(path, p)
        out.append(f"[pag. {p}]\n{t}")
        n += len(t)
        if n > max_chars:
            break
    return "\n".join(out)[:max_chars]


# ---------------------------------------------------------------------------
# Figure e tabelle
# ---------------------------------------------------------------------------

_CAP_RE = re.compile(r"^\s*(figure|figura|fig\.|table|tabella|tab\.)\s*\d+[\w.\-]*\s*[:.\-–]?\s*(.*)$", re.I)


@lru_cache(maxsize=64)
def _logo_xrefs(path: str, mtime: float) -> frozenset:
    """Immagini ripetute su molte pagine (loghi, intestazioni)."""
    d = open_pdf(path)
    cnt: Counter = Counter()
    with _open_lock:
        for pg in d:
            for x in {im[0] for im in pg.get_images()}:
                cnt[x] += 1
    lim = max(3, int(d.page_count * 0.3))
    return frozenset(x for x, c in cnt.items() if c >= lim)


def _overlap(a, b) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    area = (a[2] - a[0]) * (a[3] - a[1]) or 1
    return (x1 - x0) * (y1 - y0) / area


def _caption_near(lines: list[tuple], bbox, kinds: tuple) -> str:
    best, dist = "", 1e9
    for (x0, y0, x1, y1, text) in lines:
        m = _CAP_RE.match(text)
        if not m or not m.group(1).lower().startswith(kinds):
            continue
        d = min(abs(y0 - bbox[3]), abs(bbox[1] - y1))
        if d < dist and d < 80:
            best, dist = text.strip(), d
    return best


def figures_tables(path: str, first: int, last: int) -> dict:
    """Figure (immagini e disegni vettoriali) e tabelle nelle pagine indicate."""
    key = hashlib.sha1(f"ft4|{path}|{os.path.getmtime(path)}|{first}|{last}".encode()).hexdigest()
    cf = cache_dir() / "figtab" / f"{key}.json"
    if cf.is_file():
        try:
            return json.loads(cf.read_text(encoding="utf-8"))
        except ValueError:
            pass
    d = open_pdf(path)
    logos = _logo_xrefs(path, os.path.getmtime(path))
    figs, tabs, reqtabs = [], [], 0
    last = min(last, d.page_count, first + int(getattr(cfg, "WEB_QA_MAX_SECTION_PAGES", 12)) - 1)
    for pno in range(max(1, first), last + 1):
        with _open_lock:
            pg = d[pno - 1]
            W, H = pg.rect.width, pg.rect.height
            top, bottom = H * 0.11, H * 0.93
            lines = []
            for b in pg.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    t = "".join(s["text"] for s in ln["spans"]).strip()
                    if t:
                        lines.append((*ln["bbox"], t))
            try:
                found = pg.find_tables().tables
            except Exception:
                found = []
            tboxes = []
            for t in found:
                bb = tuple(t.bbox)
                if bb[3] < top or bb[1] > bottom:
                    continue
                tboxes.append(bb)
                try:
                    data = t.extract()
                except Exception:
                    data = []
                head_txt = " ".join(str(c or "") for r in data[:3] for c in (r or [])[:3]).lower()
                body_txt = " ".join(str(c or "") for r in data[:8] for c in (r or [])).lower()
                if re.search(r"\bid\b|description|\bnr\b|concept|zefiro|\.trs\b", head_txt) or \
                        re.search(r"concept\.\d|zefiro|derived requirement|\.trs\b|\bsil\s?\d", body_txt):
                    reqtabs += 1
                    continue
                rows = [[re.sub(r"\s+", " ", str(c or "")).strip() for c in r] for r in data[:30]]
                tabs.append({"page": pno, "bbox": [round(v, 1) for v in bb],
                             "caption": _caption_near(lines, bb, ("tab",)),
                             "rows": rows, "n_rows": t.row_count, "n_cols": t.col_count})
            boxes = []
            for im in pg.get_image_info(xrefs=True):
                bb = tuple(im["bbox"])
                if im.get("xref") in logos or bb[3] < top or bb[1] > bottom:
                    continue
                if (bb[2] - bb[0]) < 60 or (bb[3] - bb[1]) < 40:
                    continue
                boxes.append(bb)
            try:
                clusters = pg.cluster_drawings() if hasattr(pg, "cluster_drawings") else []
            except Exception:
                clusters = []
            for r in clusters:
                bb = (r.x0, r.y0, r.x1, r.y1)
                if (bb[2] - bb[0]) < 120 or (bb[3] - bb[1]) < 80 or bb[3] < top or bb[1] > bottom:
                    continue
                if any(_overlap(bb, t) > 0.4 for t in tboxes):
                    continue
                if (bb[2] - bb[0]) > W * 0.95 and (bb[3] - bb[1]) > H * 0.8:
                    continue
                boxes.append(bb)
            boxes = [b for i, b in enumerate(boxes)
                     if not any(j != i and _overlap(b, o) > 0.8 and
                                (o[2] - o[0]) * (o[3] - o[1]) > (b[2] - b[0]) * (b[3] - b[1])
                                for j, o in enumerate(boxes))]
            for bb in boxes:
                pad = 6
                figs.append({"page": pno, "bbox": [round(max(0, bb[0] - pad), 1), round(max(0, bb[1] - pad), 1),
                                                   round(min(W, bb[2] + pad), 1), round(min(H, bb[3] + pad), 1)],
                             "caption": _caption_near(lines, bb, ("fig",))})
    res = {"figures": figs, "tables": tabs, "requirement_tables": reqtabs,
           "first": first, "last": last}
    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return res


# ---------------------------------------------------------------------------
# Ricerca full-text nei PDF (SQLite FTS5, incrementale)
# ---------------------------------------------------------------------------

class TextIndex:
    def __init__(self):
        self.db_path = cache_dir() / "pdf_fulltext.sqlite"
        self.running = False
        self.progress = {"done": 0, "total": 0, "current": "", "finished_at": 0.0}
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER)")
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(path UNINDEXED, page UNINDEXED, "
                      "text, tokenize='unicode61 remove_diacritics 2')")

    def _conn(self):
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def stats(self) -> dict:
        with self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        return {"indexed_files": n, "running": self.running, **self.progress}

    def update_async(self) -> None:
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self) -> None:
        try:
            FILES.wait(120)
            pdfs = sorted({p for ps in FILES.by_name.values() for p in ps if p.lower().endswith(".pdf")})
            self.progress.update(done=0, total=len(pdfs), current="")
            max_pages = int(getattr(cfg, "WEB_PDF_INDEX_MAX_PAGES", 0) or 0)
            fitz = _fitz()
            c = self._conn()
            known = {p: (m, s) for p, m, s in c.execute("SELECT path, mtime, size FROM files")}
            for i, p in enumerate(pdfs, 1):
                self.progress.update(done=i - 1, current=Path(p).name)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if known.get(p) == (st.st_mtime, st.st_size):
                    continue
                try:
                    d = fitz.open(p)
                    rows = []
                    for k, pg in enumerate(d, 1):
                        if max_pages and k > max_pages:
                            break
                        rows.append((p, k, pg.get_text()))
                    d.close()
                except Exception as exc:
                    log.debug(f"PDF non indicizzato {p}: {exc}")
                    rows = []
                with c:
                    c.execute("DELETE FROM pages WHERE path = ?", (p,))
                    c.executemany("INSERT INTO pages(path, page, text) VALUES (?,?,?)", rows)
                    c.execute("INSERT OR REPLACE INTO files VALUES (?,?,?)", (p, st.st_mtime, st.st_size))
            gone = set(known) - set(pdfs)
            with c:
                for p in gone:
                    c.execute("DELETE FROM pages WHERE path = ?", (p,))
                    c.execute("DELETE FROM files WHERE path = ?", (p,))
            c.close()
            self.progress.update(done=len(pdfs), current="", finished_at=time.time())
        except Exception:
            log.exception("Indicizzazione PDF fallita")
        finally:
            self.running = False

    def search(self, terms: list[str], limit: int = 12, phrase: str = "") -> list[dict]:
        toks = [re.sub(r"[^\w\-]", " ", t).strip() for t in terms]
        toks = [t for t in toks if len(t) > 1]
        if not toks and not phrase:
            return []
        parts = []
        if phrase:
            parts.append('"' + phrase.replace('"', " ") + '"')
        parts.extend('"' + t + '"' for t in toks)
        q = " OR ".join(parts) if len(parts) > 1 else parts[0]
        try:
            with self._conn() as c:
                res = c.execute(
                    "SELECT path, page, snippet(pages, 2, '[[', ']]', ' … ', 18), bm25(pages) "
                    "FROM pages WHERE pages MATCH ? ORDER BY bm25(pages) LIMIT ?", (q, limit)).fetchall()
        except sqlite3.Error as exc:
            log.debug(f"Ricerca FTS non riuscita: {exc}")
            return []
        return [{"path": p, "file": Path(p).name, "fid": FILES.register(p), "page": int(pg),
                 "snippet": sn} for p, pg, sn, _s in res]


_TEXT_INDEX: Optional[TextIndex] = None


def text_index() -> TextIndex:
    global _TEXT_INDEX
    if _TEXT_INDEX is None:
        _TEXT_INDEX = TextIndex()
    return _TEXT_INDEX
