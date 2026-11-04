"""
debug_rif_pagina.py
-------------------
Calcola il "Rif. Pagina" in modo DINAMICO leggendo l'indice (Content /
Table of Contents / Indice) del PDF, e lo confronta con il valore STATICO
scritto a mano dall'utente nel foglio "Funzioni".
IDEA
  Oggi la riga di secondo livello "Rif. Pagina" del foglio "Funzioni"
  contiene un numero inserito a mano: serve a costruire il frammento
  "#page=N" dell'Hyperlink della riga "Link" soprastante (ed e' lo stesso
  riferimento usato dal foglio "Requisiti").
  Quel numero, pero', e' deducibile dal documento stesso: ogni PDF tecnico
  ETR1000 ha un indice numerato del tipo
      Content
      1    Introduction                        8
      1.1  Train Configuration                 8
      ...
      3.1  Country code selection             12
      3.2  Pantograph Control                 13
      3.2.1 Pantograph -  Lifting             13
  Basta abbinare FUNC ID (+ DESCRIZIONE FUNZIONE) al titolo di paragrafo
  piu' simile per ottenere la pagina di inizio della funzione.
  Esempio: FUNC ID "LV_Country_code_selection", DESCRIZIONE "Selezione su
  IDU del paese corrente..." -> paragrafo "3.1 Country code selection"
  -> pagina 12 nel documento FA020022045 (configurazione VZI-6_R1).
COSA FA QUESTO SCRIPT
  1. Scansiona il foglio "Funzioni" con la stessa logica a 3 livelli di
     excel_scanner.py (LIVELLO 1 funzione, LIVELLO 2 documento,
     LIVELLO 3 "Rif. Pagina").
  2. Per ogni configurazione con un link, risolve il PDF locale
     (url_builder + document_handler, con fallback su una cartella locale).
  3. Legge l'indice del PDF, lo normalizza e calcola l'offset fra la
     numerazione stampata nell'indice e la pagina fisica del PDF.
  4. Abbina la funzione al paragrafo e ricava il Rif. Pagina DINAMICO.
  5. Scrive un log con, per ogni funzione:
       - riga 1: FUNC ID + DESCRIZIONE FUNZIONE (se presente)
       - righe successive: nome configurazione, pagina STATICA,
         pagina DINAMICA; VERDE se coincidono, ROSSO se divergono.
  NON modifica l'Excel: e' un file di sola diagnostica.
OUTPUT
  debug_rif_pagina.log    testo semplice (marcatori OK / DIFF)
  debug_rif_pagina.html   stessa cosa ma con i colori reali (verde/rosso)
  console                 colorata con codici ANSI
USO
  python debug/debug_rif_pagina.py
  python debug/debug_rif_pagina.py --func LV_Country_code_selection
  python debug/debug_rif_pagina.py --excel "C:/path/DB Flotte.xlsx"
  python debug/debug_rif_pagina.py --docs-dir "C:/path/PDF" --limit 10
  python debug/debug_rif_pagina.py --verbose
"""
from __future__ import annotations
import argparse
import html
import logging
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg                      # noqa: E402
import document_handler                   # noqa: E402
import support_loader                     # noqa: E402
import url_builder                        # noqa: E402
LOG_TXT  = "debug_rif_pagina.log"
LOG_HTML = "debug_rif_pagina.html"
log = logging.getLogger("debug_rif_pagina")
# ── Colori ANSI per la console ────────────────────────────────────────────
ANSI_GREEN = "\033[92m"
ANSI_RED   = "\033[91m"
ANSI_GREY  = "\033[90m"
ANSI_BOLD  = "\033[1m"
ANSI_OFF   = "\033[0m"
# Titoli di paragrafo troppo generici per identificare una funzione.
GENERIC_TITLES = {
    "function design", "requirements", "introduction", "content",
    "contents", "general", "overview", "revision log", "scope",
    "definitions and abbreviations", "references", "abbreviations",
}
# Marcatori che aprono la pagina di indice.
TOC_MARKERS = (
    "table of contents", "content", "contents", "indice", "index",
    "inhaltsverzeichnis", "sommario",
)
# ═══════════════════════════════════════════════════════════════════════════
# MODELLO DATI
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class TocEntry:
    """Una voce dell'indice: indice numerico, titolo, pagina stampata."""
    index: str
    title: str
    printed_page: int
    @property
    def key(self) -> tuple[int, ...]:
        return tuple(int(p) for p in self.index.split(".") if p.isdigit())
    @property
    def depth(self) -> int:
        return self.index.count(".") + 1
@dataclass
class DocToc:
    """Indice completo di un documento + offset pagina stampata -> fisica."""
    path: Path
    entries: list[TocEntry] = field(default_factory=list)
    offset: int = 0
    total_pages: int = 0
    toc_pages: list[int] = field(default_factory=list)
    error: str = ""
    @property
    def ok(self) -> bool:
        return bool(self.entries) and not self.error
@dataclass
class ConfigResult:
    """Esito del confronto per una singola configurazione."""
    config_name: str
    doc_id: str
    doc_cartella: str
    static_page: int
    static_raw: str
    dynamic_page: int = 0
    matched_index: str = ""
    matched_title: str = ""
    score: float = 0.0
    offset: int = 0
    pdf_name: str = ""
    note: str = ""
    @property
    def status(self) -> str:
        """OK | DIFF | N/D"""
        if self.dynamic_page <= 0:
            return "N/D"
        if self.static_page <= 0:
            return "DIFF"
        return "OK" if self.dynamic_page == self.static_page else "DIFF"
@dataclass
class FunctionResult:
    func_id: str
    func_desc: str
    row: int
    results: list[ConfigResult] = field(default_factory=list)
# ═══════════════════════════════════════════════════════════════════════════
# 1. LETTURA DELL'INDICE DEL PDF
# ═══════════════════════════════════════════════════════════════════════════
def _norm_words(text: str) -> set[str]:
    """
    "LV_Pantograph_Lifting" -> {"pantograph", "lifting"}
    Scarta parole corte (<=3) che generano falsi positivi.
    """
    cleaned = re.sub(r"[_\-/\\.,;:()\[\]]", " ", str(text).lower())
    cleaned = re.sub(r"[^a-z\u00e0-\u00ff\s]", " ", cleaned)
    return {w for w in cleaned.split() if len(w) >= 4}
def _clean_title(raw: str) -> str:
    """Toglie leader di puntini, bullet e spazi multipli dal titolo."""
    t = re.sub(r"^[\+\-\u2013\u2014\u2022\*\u00b7\uf02a\uf0b7\s]+", "", raw)
    t = re.sub(r"[.\u2026\s]{3,}$", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .\u2026\t")
def _is_valid_title(title: str) -> bool:
    """
    Scarta i falsi titoli prodotti dalle intestazioni di pagina.
    Tipico: il pie' di pagina "Page 8 di 90" verrebbe letto come la voce
    "8 -> di -> pag. 90". Un titolo vero ha almeno una parola di 3+ lettere.
    """
    if not title or len(title) < 3:
        return False
    words = re.findall(r"[A-Za-z\u00e0-\u00ff]{3,}", title)
    return bool(words)
def _is_index_token(line: str) -> bool:
    """True per '3', '3.1', '3.2.1.1' (massimo 6 livelli)."""
    if not re.fullmatch(r"\d+(?:\.\d+){0,5}\.?", line):
        return False
    parts = [p for p in line.rstrip(".").split(".") if p != ""]
    return 1 <= len(parts) <= 6 and all(len(p) <= 3 for p in parts)
def _parse_toc_page(text: str, start_after_marker: bool) -> list[TocEntry]:
    """
    Estrae le voci di indice dal testo di UNA pagina.
    Gestisce i tre modi in cui PyMuPDF restituisce una riga di indice:
      A) tutto su una riga          "3.1 Country code selection 12"
      B) con leader di puntini      "3.1 Country code selection ...... 12"
      C) spezzata su piu' righe     "3.1" / "Country code selection" / "12"
         (e' il caso dei PDF ETR1000)
    """
    normalized = text.replace("\xa0", " ").replace("\t", " ")
    lines = [ln.strip() for ln in normalized.splitlines()]
    start = 0
    if start_after_marker:
        for i, ln in enumerate(lines):
            if ln.lower().strip(" :.") in TOC_MARKERS:
                start = i + 1
                break
    entries: list[TocEntry] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue
        # ── Casi A e B: indice + titolo + pagina sulla stessa riga ───────
        m = re.match(
            r"^(\d+(?:\.\d+){0,5})\.?\s+(.+?)[\s.\u2026]+(\d{1,4})$", line
        )
        if m and _is_index_token(m.group(1)):
            title = _clean_title(m.group(2))
            if _is_valid_title(title):
                entries.append(TocEntry(m.group(1).rstrip("."), title,
                                        int(m.group(3))))
                i += 1
                continue
        # ── Caso C: indice su riga dedicata ──────────────────────────────
        if _is_index_token(line):
            idx = line.rstrip(".")
            title_parts: list[str] = []
            page_num = 0
            j = i + 1
            # Il titolo occupa al massimo 3 righe; righe lunghe = corpo del
            # documento, non indice -> si abbandona il candidato.
            while j < len(lines) and j - i <= 4:
                nxt = lines[j]
                if not nxt:
                    j += 1
                    continue
                if re.fullmatch(r"\d{1,4}", nxt):
                    if title_parts:
                        page_num = int(nxt)
                    break
                if len(nxt) > 90 or _is_index_token(nxt):
                    break
                if re.search(r"[a-zA-Z]", nxt):
                    title_parts.append(_clean_title(nxt))
                j += 1
            if page_num > 0 and title_parts:
                title = _clean_title(" ".join(title_parts))
                if _is_valid_title(title):
                    entries.append(TocEntry(idx, title, page_num))
                    i = j + 1
                    continue
        i += 1
    return entries
def _longest_consistent_chain(entries: list[TocEntry]) -> list[TocEntry]:
    """
    Tiene solo la catena piu' lunga di voci coerenti: indice crescente e
    pagina non decrescente.
    Serve a buttare via il rumore di intestazione/pie' di pagina, per es.
    "Rev 5.0" seguito da "Content 1" che altrimenti verrebbe letto come
    la voce di indice "5.0 Content -> pag. 1" e falserebbe tutto il resto.
    """
    n = len(entries)
    if n <= 1:
        return list(entries)
    best_len = [1] * n
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if (entries[j].key < entries[i].key
                    and entries[j].printed_page <= entries[i].printed_page
                    and best_len[j] + 1 > best_len[i]):
                best_len[i] = best_len[j] + 1
                prev[i] = j
    end = max(range(n), key=lambda k: best_len[k])
    chain: list[TocEntry] = []
    while end != -1:
        chain.append(entries[end])
        end = prev[end]
    return list(reversed(chain))
def _find_heading_physical_page(
    pdf, entry: TocEntry, search_from: int, search_to: int
) -> int:
    """
    Cerca fisicamente il titolo di paragrafo nelle pagine indicate
    (1-based, estremi inclusi). Restituisce la pagina fisica o 0.
    """
    title_words = _norm_words(entry.title)
    if not title_words:
        return 0
    idx_re = re.compile(
        r"^" + re.escape(entry.index) + r"\.?(\s|$)"
    )
    for phys in range(max(1, search_from), min(len(pdf), search_to) + 1):
        lines = [
            ln.strip()
            for ln in pdf[phys - 1].get_text().replace("\xa0", " ").splitlines()
        ]
        for k, ln in enumerate(lines):
            if not idx_re.match(ln):
                continue
            # Titolo sulla stessa riga oppure nelle 3 righe seguenti.
            window = " ".join([ln] + [x for x in lines[k + 1:k + 4]])
            found = _norm_words(window)
            if len(title_words & found) >= max(1, int(len(title_words) * 0.6)):
                return phys
    return 0
def _detect_offset(pdf, entries: list[TocEntry]) -> int:
    """
    Calcola lo scarto fra numerazione stampata nell'indice e pagina fisica
    del PDF (il frammento "#page=N" dell'Hyperlink usa la pagina FISICA).
    Campiona fino a 10 voci profonde con titolo distintivo e prende lo
    scarto piu' ricorrente. Se non trova riscontri, restituisce 0.
    """
    candidates = [
        e for e in entries
        if e.depth >= 2
        and e.title.lower() not in GENERIC_TITLES
        and len(_norm_words(e.title)) >= 1
    ] or entries
    step = max(1, len(candidates) // 10)
    sample = candidates[::step][:10]
    offsets: Counter[int] = Counter()
    for e in sample:
        phys = _find_heading_physical_page(
            pdf, e, e.printed_page - 4, e.printed_page + 6
        )
        if phys:
            offsets[phys - e.printed_page] += 1
    if not offsets:
        log.debug("  offset non determinabile -> 0")
        return 0
    offset, votes = offsets.most_common(1)[0]
    log.debug(f"  offset indice->pagina fisica = {offset:+d} ({votes} riscontri)")
    return offset
def read_toc(pdf_path: Path, max_scan_pages: int = 30) -> DocToc:
    """Legge e normalizza l'indice di un PDF."""
    doc = DocToc(path=pdf_path)
    try:
        import pymupdf as fitz
    except ImportError:                                   # pragma: no cover
        try:
            import fitz
        except ImportError:
            doc.error = "PyMuPDF non installato (pip install pymupdf)"
            return doc
    if pdf_path.suffix.lower() != ".pdf":
        doc.error = f"formato non supportato: {pdf_path.suffix}"
        return doc
    try:
        pdf = fitz.open(str(pdf_path))
    except Exception as exc:                              # pragma: no cover
        doc.error = f"apertura fallita: {exc}"
        return doc
    try:
        doc.total_pages = len(pdf)
        limit = min(len(pdf), max_scan_pages)
        # ── Indice incorporato (segnalibri): la fonte piu' affidabile ────
        try:
            native = pdf.get_toc() or []
        except Exception:
            native = []
        if native:
            numbered: list[TocEntry] = []
            for level, title, page in native:
                t = _clean_title(str(title))
                m = re.match(r"^(\d+(?:\.\d+){0,5})\.?\s+(.*)$", t)
                if m and _is_index_token(m.group(1)) and m.group(2).strip():
                    numbered.append(
                        TocEntry(m.group(1).rstrip("."),
                                 _clean_title(m.group(2)), int(page))
                    )
            if len(numbered) >= 3:
                doc.entries = _longest_consistent_chain(numbered)
                doc.offset = 0          # get_toc() restituisce gia' il fisico
                log.debug(f"  indice nativo: {len(doc.entries)} voci")
                return doc
        # ── Indice testuale: trova la pagina che apre il sommario ───────
        marker_page = 0
        for p in range(limit):
            lines = [
                ln.strip().lower().strip(" :.")
                for ln in pdf[p].get_text().splitlines()
            ]
            if any(ln in TOC_MARKERS for ln in lines):
                marker_page = p
                break
        if marker_page == 0 and not any(
            _parse_toc_page(pdf[0].get_text(), False) for _ in (0,)
        ):
            # Nessun marcatore: si prova comunque dalle prime pagine.
            marker_page = 0
        collected: list[TocEntry] = []
        for p in range(marker_page, min(marker_page + 8, limit)):
            page_entries = _parse_toc_page(
                pdf[p].get_text(), start_after_marker=(p == marker_page)
            )
            # Una pagina senza voci chiude il sommario: oltre si entra nel
            # corpo del documento, dove le intestazioni generano rumore.
            if not page_entries:
                if collected:
                    break
                continue
            collected.extend(page_entries)
            doc.toc_pages.append(p + 1)
        if not collected:
            doc.error = "indice non trovato nel documento"
            return doc
        doc.entries = _longest_consistent_chain(collected)
        if len(doc.entries) < 2:
            doc.error = "indice riconosciuto ma incoerente"
            return doc
        doc.offset = _detect_offset(pdf, doc.entries)
        return doc
    finally:
        pdf.close()
# ═══════════════════════════════════════════════════════════════════════════
# 2. ABBINAMENTO FUNZIONE -> PARAGRAFO
# ═══════════════════════════════════════════════════════════════════════════
def match_function(
    doc: DocToc, func_id: str, func_desc: str
) -> tuple[Optional[TocEntry], float]:
    """
    Abbina FUNC ID + DESCRIZIONE FUNZIONE al paragrafo piu' probabile.
    Il FUNC ID pesa il doppio della descrizione: il primo e' in inglese come
    i titoli del PDF, la seconda e' spesso in italiano.
    """
    id_words   = _norm_words(func_id)
    desc_words = _norm_words(func_desc) - id_words
    if not id_words and not desc_words:
        return None, 0.0
    best: Optional[TocEntry] = None
    best_rank: tuple = ()
    for e in doc.entries:
        if e.title.lower() in GENERIC_TITLES:
            continue
        tw = _norm_words(e.title)
        if not tw:
            continue
        hits_id   = len(id_words & tw)
        hits_desc = len(desc_words & tw)
        raw = hits_id * 2 + hits_desc
        if raw == 0:
            continue
        coverage = len(tw & (id_words | desc_words)) / len(tw)
        rank = (raw, coverage, e.depth, -e.printed_page)
        if not best_rank or rank > best_rank:
            best_rank, best = rank, e
    if best is None:
        return None, 0.0
    return best, float(best_rank[0]) + best_rank[1]
# ═══════════════════════════════════════════════════════════════════════════
# 3. RISOLUZIONE DEL FILE PDF
# ═══════════════════════════════════════════════════════════════════════════
def resolve_pdf(url: str, docs_dir: Optional[Path]) -> Optional[Path]:
    """
    Risolve il PDF locale a partire dall'URL SharePoint.
    1. document_handler.download() (cartella OneDrive sincronizzata)
    2. fallback: ricerca ricorsiva per nome file in --docs-dir
    """
    path = None
    try:
        if cfg.ONEDRIVE_DOCS_ROOT.exists():
            path = document_handler.download(url)
    except Exception as exc:
        log.debug(f"  download() fallito: {exc}")
    if path and Path(path).exists():
        return Path(path)
    if docs_dir and docs_dir.exists():
        name = Path(re.sub(r"#page=\d+$", "", url)).name
        from urllib.parse import unquote
        name = unquote(name)
        matches = list(docs_dir.rglob(name))
        if not matches:
            matches = [
                p for p in docs_dir.rglob("*.pdf")
                if p.name.lower() == name.lower()
            ]
        if matches:
            return matches[0]
    return None
# ═══════════════════════════════════════════════════════════════════════════
# 4. SCANSIONE DEL FOGLIO "Funzioni"
# ═══════════════════════════════════════════════════════════════════════════
def _cell_str(ws, row: int, col: int) -> str:
    val = ws.cell(row, col).value
    if val is None:
        return ""
    if "ormula" in type(val).__name__:
        return ""
    return str(val).strip()
def _build_header_map(ws) -> dict[str, int]:
    raw: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        v = ws.cell(1, col).value
        if v:
            raw[str(v).strip().lower().replace("\n", " ")] = col
    return {
        "id":           raw.get("func id", raw.get("id", 1)),
        "funzione":     raw.get("descrizione funzione", raw.get("funzione", 2)),
        "doc_cartella": raw.get("doc cartella", 3),
        "doc_id":       raw.get("doc id", 4),
        "info_doc":     raw.get("info doc", 5),
    }
def _parse_page(value: str) -> int:
    nums = re.findall(r"\d+", str(value or ""))
    return int(nums[0]) if nums else 0
def analyze(
    excel_path: Path,
    docs_dir: Optional[Path],
    only_func: str = "",
    limit: int = 0,
) -> list[FunctionResult]:
    """Scansione completa del foglio Funzioni e confronto statico/dinamico."""
    from openpyxl import load_workbook
    log.info(f"Apertura Excel: {excel_path}")
    wb_write = load_workbook(str(excel_path), data_only=False)
    wb_data  = load_workbook(str(excel_path), data_only=True)
    ws_write = wb_write[cfg.SHEET_FUNZIONI]
    ws_data  = wb_data[cfg.SHEET_FUNZIONI]
    sd = support_loader.load(wb_data)
    cm         = _build_header_map(ws_write)
    id_col     = cm["id"]
    label_col  = cm["funzione"]
    cart_col   = cm["doc_cartella"]
    doc_id_col = cm["doc_id"]
    info_col   = cm["info_doc"]
    gen_col    = ws_write.max_column
    config_cols = list(range(info_col + 1, gen_col))
    config_names = {
        col: (str(ws_write.cell(1, col).value).strip().replace("\n", " / ")
              if ws_write.cell(1, col).value else f"CONF_{col}")
        for col in config_cols
    }
    log.info(f"Configurazioni: {list(config_names.values())}")
    toc_cache: dict[str, DocToc] = {}
    def get_toc(pdf_path: Path) -> DocToc:
        key = str(pdf_path)
        if key not in toc_cache:
            log.info(f"  Lettura indice di {pdf_path.name} ...")
            toc_cache[key] = read_toc(pdf_path)
            d = toc_cache[key]
            if d.ok:
                log.info(
                    f"    {len(d.entries)} voci, offset {d.offset:+d}, "
                    f"pagine indice {d.toc_pages or 'native'}"
                )
            else:
                log.warning(f"    indice non utilizzabile: {d.error}")
        return toc_cache[key]
    out: list[FunctionResult] = []
    current: Optional[FunctionResult] = None
    doc_id = doc_cartella = ""
    doc_row = 0
    configs_with_link: set[str] = set()
    for row in range(2, ws_write.max_row + 1):
        v_id   = _cell_str(ws_write, row, id_col)
        v_cart = _cell_str(ws_write, row, cart_col)
        v_doc  = _cell_str(ws_write, row, doc_id_col)
        v_info = _cell_str(ws_write, row, info_col)
        # ── LIVELLO 1: nuova funzione ───────────────────────────────────
        if v_id:
            if current and current.results:
                out.append(current)
            if limit and len(out) >= limit:
                current = None
                break
            skip = bool(only_func) and v_id.strip().lower() != only_func.strip().lower()
            current = None if skip else FunctionResult(
                func_id=v_id,
                func_desc=_cell_str(ws_write, row, label_col),
                row=row,
            )
            doc_id = doc_cartella = ""
            doc_row = 0
            configs_with_link = set()
            continue
        if current is None:
            continue
        # ── LIVELLO 2: nuovo documento ──────────────────────────────────
        INVALID_DOC = {"", "\\", "/", "tbd"}
        if v_cart and v_doc and v_doc.strip().lower() not in INVALID_DOC:
            doc_id, doc_cartella, doc_row = v_doc, v_cart, row
            configs_with_link = {
                config_names[c] for c in config_cols
                if url_builder.cell_has_valid_link(
                    ws_data, row, c, ws_write=ws_write)
            }
            continue
        # ── LIVELLO 3: riga "Rif. Pagina" ───────────────────────────────
        if not (v_info and doc_id and not v_cart):
            continue
        label = v_info.lower().strip()
        if not (label.startswith("rif") or label == "pagina"):
            continue
        log.info(
            f"\n[riga {row}] {current.func_id} | doc '{doc_id}' "
            f"({doc_cartella}) | {len(configs_with_link)} config con link"
        )
        for col in config_cols:
            cname = config_names[col]
            static_raw = _cell_str(ws_write, row, col)
            if cname not in configs_with_link and not static_raw:
                continue
            res = ConfigResult(
                config_name=cname,
                doc_id=doc_id,
                doc_cartella=doc_cartella,
                static_page=_parse_page(static_raw),
                static_raw=static_raw,
            )
            url = url_builder.build(sd, doc_id, cname, 0,
                                    doc_cartella=doc_cartella)
            if not url:
                res.note = "URL non costruibile"
                current.results.append(res)
                continue
            pdf_path = resolve_pdf(url, docs_dir)
            if not pdf_path:
                res.note = f"PDF non trovato ({Path(url).name})"
                current.results.append(res)
                continue
            res.pdf_name = pdf_path.name
            doc = get_toc(pdf_path)
            if not doc.ok:
                res.note = doc.error or "indice non leggibile"
                current.results.append(res)
                continue
            res.offset = doc.offset
            entry, score = match_function(doc, current.func_id,
                                          current.func_desc)
            if entry is None:
                res.note = "funzione non trovata nell'indice"
            else:
                res.matched_index = entry.index
                res.matched_title = entry.title
                res.score = score
                res.dynamic_page = max(1, entry.printed_page + doc.offset)
                # Un solo termine in comune: l'abbinamento e' fragile e va
                # verificato a mano prima di fidarsi del valore dinamico.
                if int(score) <= 2:
                    res.note = "match debole"
            current.results.append(res)
    if current and current.results:
        out.append(current)
    return out
# ═══════════════════════════════════════════════════════════════════════════
# 5. REPORT
# ═══════════════════════════════════════════════════════════════════════════
def _fmt_line(r: ConfigResult) -> str:
    static  = str(r.static_page) if r.static_page else "-"
    dynamic = str(r.dynamic_page) if r.dynamic_page else "-"
    ref = f"  [{r.matched_index} {r.matched_title}]" if r.matched_index else ""
    if r.offset:
        ref += f" (offset {r.offset:+d})"
    note = f"  {r.note}" if r.note else ""
    return (
        f"  {r.config_name:<16} doc:{r.doc_id:<22} "
        f"statico:{static:>5}   dinamico:{dynamic:>5}   "
        f"{r.status:<4}{ref}{note}"
    )
def write_report(results: Iterable[FunctionResult], out_dir: Path) -> tuple[Path, Path]:
    results = list(results)
    txt_path  = out_dir / LOG_TXT
    html_path = out_dir / LOG_HTML
    tot = ok = diff = nd = 0
    txt_lines: list[str] = []
    html_rows: list[str] = []
    header = (
        "RIFERIMENTO PAGINA DINAMICO — confronto con il valore statico\n"
        "VERDE = i due valori coincidono | ROSSO = divergono o non calcolabili\n"
        + "=" * 110
    )
    txt_lines.append(header)
    print(ANSI_BOLD + header + ANSI_OFF)
    for fr in results:
        title = fr.func_id + (f" — {fr.func_desc}" if fr.func_desc else "")
        txt_lines.append("")
        txt_lines.append(title)
        print()
        print(ANSI_BOLD + title + ANSI_OFF)
        html_rows.append(
            f'<div class="fn"><div class="h">{html.escape(title)}</div>'
        )
        for r in fr.results:
            tot += 1
            line = _fmt_line(r)
            if r.status == "OK":
                ok += 1
                css, ansi = "ok", ANSI_GREEN
            elif r.status == "DIFF":
                diff += 1
                css, ansi = "diff", ANSI_RED
            else:
                nd += 1
                css, ansi = "nd", ANSI_RED
            txt_lines.append(line)
            print(ansi + line + ANSI_OFF)
            html_rows.append(f'<div class="{css}">{html.escape(line)}</div>')
        html_rows.append("</div>")
    summary = (
        "\n" + "=" * 110 + "\n"
        f"Funzioni analizzate : {len(results)}\n"
        f"Confronti totali    : {tot}\n"
        f"  VERDE  (coincide) : {ok}\n"
        f"  ROSSO  (diverso)  : {diff}\n"
        f"  ROSSO  (N/D)      : {nd}\n"
    )
    txt_lines.append(summary)
    print(ANSI_BOLD + summary + ANSI_OFF)
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>Rif. Pagina — statico vs dinamico</title>"
        "<style>body{background:#1e1e1e;color:#ddd;font:13px/1.5 Consolas,"
        "monospace;padding:20px}.h{color:#fff;font-weight:bold;margin-top:14px}"
        ".ok{color:#4ec94e;white-space:pre}.diff{color:#ff5f5f;white-space:pre}"
        ".nd{color:#ff5f5f;white-space:pre;opacity:.8}"
        "pre{white-space:pre-wrap}</style>"
        f"<pre>{html.escape(header)}</pre>"
        + "".join(html_rows)
        + f"<pre>{html.escape(summary)}</pre>",
        encoding="utf-8",
    )
    return txt_path, html_path
# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Confronta il Rif. Pagina statico con quello ricavato "
                    "dall'indice del PDF."
    )
    ap.add_argument("--excel", default=str(cfg.EXCEL_PATH),
                    help="file Excel DB Flotte (default: config.EXCEL_PATH)")
    ap.add_argument("--docs-dir", default="",
                    help="cartella locale con i PDF, usata come fallback "
                         "se OneDrive non e' disponibile")
    ap.add_argument("--func", default="",
                    help="analizza solo questo FUNC ID")
    ap.add_argument("--limit", type=int, default=0,
                    help="ferma l'analisi dopo N funzioni")
    ap.add_argument("--out-dir", default=".",
                    help="cartella di destinazione dei log")
    ap.add_argument("--toc", default="",
                    help="stampa solo l'indice del PDF indicato ed esce")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(message)s",
    )
    log.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    # ── Modalita' ispezione indice ───────────────────────────────────────
    if args.toc:
        d = read_toc(Path(args.toc))
        if not d.ok:
            print(f"Indice non leggibile: {d.error}")
            return 1
        print(f"{d.path.name}: {d.total_pages} pagine, "
              f"offset {d.offset:+d}, pagine indice {d.toc_pages or 'native'}")
        for e in d.entries:
            print(f"  {e.index:<10} {e.title:<60} "
                  f"stampata {e.printed_page:>4} -> fisica "
                  f"{e.printed_page + d.offset:>4}")
        return 0
    excel_path = Path(args.excel)
    if not excel_path.exists():
        print(f"❌ Excel non trovato: {excel_path}")
        return 1
    docs_dir = Path(args.docs_dir) if args.docs_dir else None
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = analyze(excel_path, docs_dir, only_func=args.func,
                      limit=args.limit)
    if not results:
        print("Nessuna riga 'Rif. Pagina' analizzabile.")
        return 1
    txt_path, html_path = write_report(results, out_dir)
    print(f"Log testuale : {txt_path.resolve()}")
    print(f"Log colorato : {html_path.resolve()}")
    return 0

    
if __name__ == "__main__":
    sys.exit(main())