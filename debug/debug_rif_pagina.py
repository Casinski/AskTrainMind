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
ANSI_YELLOW= "\033[93m"
ANSI_GREY  = "\033[90m"
ANSI_BOLD  = "\033[1m"
ANSI_OFF   = "\033[0m"
# Titoli di paragrafo troppo generici per identificare una funzione.
GENERIC_TITLES = {
    "function design", "requirements", "introduction", "content",
    "contents", "general", "overview", "revision log", "scope",
    "definitions and abbreviations", "references", "abbreviations",
}
# Sinonimi: stessa funzione, titolo diverso da una configurazione all'altra.
# La chiave e' una parola del FUNC ID, i valori i termini equivalenti nei
# titoli di paragrafo. Es. VZI_Base usa "LIM", VZI-6_R1 usa "HVSP".
TITLE_ALIASES = {
    "lim":       {"hvsp", "interference"},
    "hvsp":      {"lim", "interference"},
    "optional":  {"included"},
    "urgency":   {"urgency"},
    "add":       {"dropping"},
    "als":       {"lateral"},
    "dnra":      {"rotating"},
    "cbm":       {"maintenance"},
}
# Doc ID che NON sono specifiche funzionali con indice di paragrafo
# (liste segnali, schemi, manuali): per questi il Rif. Pagina non e'
# deducibile da un indice e il confronto va marcato come non applicabile.
NON_FUNCTIONAL_DOC_PREFIXES = ("FS_", "FPD_", "DIA_", "FD_", "PBC_")
# Punteggio F1 minimo per considerare l'abbinamento per titolo attendibile.
# Sotto questa soglia il risultato viene riaffidato all'interpolazione
# ordinale del secondo passaggio.
STRONG_MATCH_F1 = 0.55
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
    functional_chapter: str = ""
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
    pdf_path: str = ""
    strong: bool = False
    confirmed: bool = False
    skipped: bool = False
    note: str = ""
    @property
    def status(self) -> str:
        """OK | OBS | DIFF | N/D | --"""
        # "--" = confronto non applicabile: documento senza indice
        # funzionale, funzione assente da quel documento, oppure cella
        # "Rif. Pagina" non compilata. Non e' un errore dell'algoritmo e
        # non va conteggiato fra i rossi.
        if self.skipped:
            return "--"
        if self.dynamic_page <= 0:
            return "N/D"
        if self.static_page <= 0:
            return "--"
        if self.dynamic_page == self.static_page:
            return "OK"
        # Divergenza con intestazione verificata nel corpo del PDF:
        # il dinamico e' dimostrabilmente giusto, lo statico e' obsoleto.
        return "OBS" if self.confirmed else "DIFF"
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
        # ── Casi C e D: indice all'inizio di riga, pagina piu' avanti ────
        #   C) "3.12"        / "Towing" / "224"
        #   D) "3.12 Towing" / "224"
        # Il caso D e' quello di FRS_Brake Control: le voci di 2o livello
        # da 3.10 in poi hanno numero e titolo sulla stessa riga ma la
        # pagina su quella successiva. Trattandole solo come caso C le si
        # perdeva tutte (Sanding, Brake Test, Towing, Fire Safety,
        # Magnetic Track Brake risultavano "non trovate nell'indice").
        m_idx = re.match(r"^(\d+(?:\.\d+){0,5})\.?(?:\s+(.*))?$", line)
        if m_idx and _is_index_token(m_idx.group(1)):
            idx = m_idx.group(1).rstrip(".")
            title_parts: list[str] = []
            inline = _clean_title(m_idx.group(2) or "")
            if inline and len(inline) <= 90 and re.search(r"[a-zA-Z]", inline):
                title_parts.append(inline)
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
def _parse_toc_titles_page(text: str, start_after_marker: bool,
                           chapter: str) -> tuple[list[tuple[str, str, int]], str]:
    """
    Parser di riserva per gli indici SENZA numeri di sezione.

    In alcuni PDF (p.es. FRS_Bogies VZI-6_R1) il layer testuale contiene
    solo i numeri di capitolo di primo livello: "1", "2", "3". I numeri
    "2.1", "3.1.2" ... non vengono estratti affatto e l'indice si riduce a
    una sequenza TITOLO / PAGINA:

        "3" / "Functional requirements" / "11" / "Flange Lubrication" / "11"

    Il parser numerato scambia allora le PAGINE per indici e produce voci
    assurde come "6 Flange Lubrication -> pag. 5".

    Qui si sfrutta l'alternanza stretta del layout:
      - NUMERO seguito da TESTO  -> e' un numero di capitolo
      - TESTO  seguito da NUMERO -> e' una coppia titolo + pagina
    Restituisce le coppie e il capitolo corrente, da propagare alla
    pagina successiva del sommario.
    """
    normalized = text.replace("\xa0", " ").replace("\t", " ")
    lines = [ln.strip() for ln in normalized.splitlines() if ln.strip()]
    start = 0
    if start_after_marker:
        for i, ln in enumerate(lines):
            if ln.lower().strip(" :.") in TOC_MARKERS:
                start = i + 1
                break
    out: list[tuple[str, str, int]] = []
    i = start
    while i < len(lines) - 1:
        cur, nxt = lines[i], lines[i + 1]
        cur_num = re.fullmatch(r"\d{1,4}", cur) is not None
        nxt_num = re.fullmatch(r"\d{1,4}", nxt) is not None
        if cur_num and not nxt_num:
            chapter = cur
            i += 1
            continue
        if not cur_num and nxt_num:
            title = _clean_title(cur)
            # Prima del primo capitolo c'e' solo l'intestazione di pagina
            # ("Page / 4 / di / 47"): si scarta.
            if chapter and _is_valid_title(title) and not title.endswith(":"):
                out.append((chapter, title, int(nxt)))
            i += 2
            continue
        i += 1
    return out, chapter


def _numbered_parse_is_degenerate(entries: list[TocEntry]) -> bool:
    """
    True quando le voci numerate sono in realta' numeri di pagina letti
    per errore come indici: nessun indice gerarchico e indice uguale alla
    pagina in buona parte delle voci.
    """
    if not entries:
        return True
    dotted = sum(1 for e in entries if "." in e.index)
    same = sum(1 for e in entries if e.index == str(e.printed_page))
    return dotted == 0 and same >= max(2, 0.4 * len(entries))


def _entries_from_titles(pairs: list[tuple[str, str, int]]) -> list[TocEntry]:
    """Sintetizza indici progressivi per le voci prive di numerazione."""
    counters: dict[str, int] = {}
    entries: list[TocEntry] = []
    for chapter, title, page in pairs:
        counters[chapter] = counters.get(chapter, 0) + 1
        entries.append(TocEntry(f"{chapter}.{counters[chapter]}", title, page))
    return entries


def _detect_functional_chapter(entries: list[TocEntry]) -> str:
    """
    Numero del capitolo "Functional requirements".

    Il Rif. Pagina punta SEMPRE dentro questo capitolo. I documenti ETR1000
    elencano pero' le stesse funzioni due volte: una in "System Overview"
    (una riga di presentazione) e una nei requisiti veri e propri. Senza
    questo ancoraggio FRS_Bogies abbina "Flange Lubrication" alla
    panoramica (pag. 6) invece che al capitolo 3 (pag. 11).
    """
    for e in entries:
        words = _norm_words(e.title)
        if "functional" in words and (
            "requirements" in words or "requirement" in words
        ):
            return e.index.split(".")[0]
    return ""


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
def read_toc(pdf_path: Path, max_scan_pages: int = 60) -> DocToc:
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
                doc.functional_chapter = _detect_functional_chapter(doc.entries)
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
        # Il sommario di un documento lungo (FRS_Brake Control: 270 pagine)
        # puo' occupare piu' di 8 pagine. Con la vecchia finestra fissa
        # tutte le sezioni da 3.10 in poi venivano perse e le funzioni
        # corrispondenti risultavano "non trovate nell'indice".
        # Ora si prosegue finche' le pagine continuano a produrre voci,
        # tollerando una pagina vuota isolata, e ci si ferma quando inizia
        # il corpo del documento (una voce senza numero di pagina a destra
        # non viene prodotta: la pagina risulta vuota due volte di fila).
        collected: list[TocEntry] = []
        title_pairs: list[tuple[str, str, int]] = []
        chapter = ""
        blank_streak = 0
        for p in range(marker_page, min(len(pdf), max_scan_pages)):
            page_text = pdf[p].get_text()
            first = (p == marker_page)
            page_entries = _parse_toc_page(page_text, start_after_marker=first)
            page_pairs, chapter = _parse_toc_titles_page(
                page_text, start_after_marker=first, chapter=chapter
            )
            if not page_entries and not page_pairs:
                if not collected:
                    continue
                blank_streak += 1
                if blank_streak >= 2:
                    break
                continue
            # Il corpo del documento riparte dalla sezione 1: se la prima
            # voce della pagina torna indietro rispetto all'ultima raccolta,
            # il sommario e' finito.
            if collected and page_entries \
                    and _idx_key(page_entries[0].index) < _idx_key(collected[-1].index) \
                    and page_entries[0].printed_page <= collected[-1].printed_page:
                break
            # Stessa regola per le coppie titolo/pagina: il corpo del
            # documento produce coppie spurie che tornano indietro.
            if title_pairs and page_pairs and not page_entries \
                    and page_pairs[0][2] < title_pairs[-1][2]:
                break
            blank_streak = 0
            collected.extend(page_entries)
            title_pairs.extend(page_pairs)
            doc.toc_pages.append(p + 1)
        # Se le voci numerate sono in realta' numeri di pagina, si passa
        # all'indice ricostruito dalle sole coppie titolo/pagina.
        if _numbered_parse_is_degenerate(collected) and len(title_pairs) >= 4:
            collected = _entries_from_titles(title_pairs)
        if not collected:
            doc.error = "indice non trovato nel documento"
            return doc
        doc.entries = _longest_consistent_chain(collected)
        if len(doc.entries) < 2:
            doc.error = "indice riconosciuto ma incoerente"
            return doc
        doc.offset = _detect_offset(pdf, doc.entries)
        doc.functional_chapter = _detect_functional_chapter(doc.entries)
        return doc
    finally:
        pdf.close()
# ═══════════════════════════════════════════════════════════════════════════
# 2. ABBINAMENTO FUNZIONE -> PARAGRAFO
# ═══════════════════════════════════════════════════════════════════════════
def _expand_aliases(words: set[str]) -> set[str]:
    """Aggiunge i sinonimi noti alle parole della funzione."""
    extra: set[str] = set()
    for w in words:
        extra |= TITLE_ALIASES.get(w, set())
    return words | extra
def match_function(
    doc: DocToc, func_id: str, func_desc: str
) -> tuple[Optional[TocEntry], float]:
    """
    Abbina FUNC ID + DESCRIZIONE FUNZIONE al paragrafo piu' probabile.
    PUNTEGGIO F1 BIDIREZIONALE
      Il vecchio punteggio contava solo le parole in comune: "Manual Brake
      Test" e "Brake Test" ottenevano lo stesso valore per BRK_Brake_Test,
      e vinceva il piu' profondo (3.11.3, pagina sbagliata).
      Ora conta anche quanto il titolo e' COPERTO dalla funzione:
        precision = |comuni| / |parole del titolo|
        recall    = |comuni| / |parole della funzione|
        F1        = media armonica
      "Brake Test" ha F1 = 1.0, "Manual Brake Test" 0.8 -> vince il primo.
    PARITA'
      1. sezione piu' ALTA (3.11 batte 3.11.3): il Rif. Pagina punta
         all'inizio della funzione, non a un suo sotto-paragrafo;
      2. sezione con l'ESTENSIONE maggiore: nei documenti che elencano le
         funzioni due volte (capitolo 2 "System Overview" + capitolo 3
         "Functional requirements") vince il capitolo che le discute
         davvero, perche' le sue sezioni occupano piu' pagine.
    """
    id_words   = _expand_aliases(_norm_words(func_id))
    desc_words = _expand_aliases(_norm_words(func_desc)) - id_words
    func_words = id_words | desc_words
    if not func_words:
        return None, 0.0
    # Estensione in pagine di ogni voce: serve come criterio di parita'.
    spans: dict[int, int] = {}
    for i, e in enumerate(doc.entries):
        nxt = doc.entries[i + 1].printed_page if i + 1 < len(doc.entries) else e.printed_page
        spans[id(e)] = max(0, nxt - e.printed_page)
    best: Optional[TocEntry] = None
    best_rank: tuple = ()
    for e in doc.entries:
        if e.title.lower() in GENERIC_TITLES:
            continue
        tw = _norm_words(e.title)
        if not tw:
            continue
        common = len(tw & func_words)
        if common == 0:
            continue
        # PRECISION su tutte le parole (ID + descrizione), RECALL sul solo
        # FUNC ID: la descrizione e' italiana e discorsiva, metterla al
        # denominatore del recall affossa anche gli abbinamenti perfetti
        # ("LV_Key_interlocking" vs "Key interlocking" scendeva a F1 0.22).
        ref_words = id_words or desc_words
        precision = common / len(tw)
        recall    = len(tw & ref_words) / len(ref_words)
        if recall == 0:
            continue
        f1 = 2 * precision * recall / (precision + recall)
        # Il Rif. Pagina punta dentro il capitolo "Functional requirements":
        # a parita' di titolo la panoramica di "System Overview" perde.
        in_func = (
            1 if doc.functional_chapter
            and e.index.split(".")[0] == doc.functional_chapter else 0
        )
        rank = (round(f1, 4), in_func, -e.depth, spans[id(e)], -e.printed_page)
        if not best_rank or rank > best_rank:
            best_rank, best = rank, e
    if best is None:
        return None, 0.0
    return best, float(best_rank[0])
def _idx_key(index: str) -> tuple[int, ...]:
    return tuple(int(p) for p in index.split(".") if p.isdigit())
def _page_opens_section(pdf, page: int, entry: TocEntry) -> bool:
    """True se la pagina fisica indicata contiene l'intestazione di sezione."""
    title_words = _norm_words(entry.title)
    idx_re = re.compile(r"^" + re.escape(entry.index) + r"\.?(\s|$)")
    lines = [
        ln.strip()
        for ln in pdf[page - 1].get_text().replace("\xa0", " ").splitlines()
    ]
    for k, ln in enumerate(lines):
        if not idx_re.match(ln):
            continue
        window = _norm_words(" ".join([ln] + lines[k + 1:k + 4]))
        if not title_words:
            return True
        if len(title_words & window) >= max(1, int(len(title_words) * 0.6)):
            return True
    return False
def confirm_page_in_body(
    pdf, entry: TocEntry, toc_pages: set[int], window: int = 3
) -> int:
    """
    Verifica nel CORPO del documento la pagina dichiarata dall'indice.
    POLITICA CONSERVATIVA — indispensabile:
      1. la pagina dell'indice ha ragione finche' non si dimostra il
         contrario: la si prova per prima;
      2. solo se NON contiene l'intestazione si cerca nell'intorno
         (+1, -1, +2, -2, ...), partendo dalle pagine successive;
      3. le pagine di sommario sono sempre escluse, altrimenti si
         riaggancia il sommario stesso invece del corpo;
      4. se nessuna pagina conferma si restituisce 0 e il chiamante
         tiene il valore dell'indice.
    Senza il punto 1 un riferimento incrociato nella pagina precedente
    farebbe arretrare il risultato di una pagina (caso 3.4.3 "Isolate
    High Voltage": corpo a pag.45, citazione a pag.44).
    """
    start = entry.printed_page
    if 1 <= start <= len(pdf) and start not in toc_pages \
            and _page_opens_section(pdf, start, entry):
        return start
    for off in range(1, window + 1):
        for cand in (start + off, start - off):
            if 1 <= cand <= len(pdf) and cand not in toc_pages \
                    and _page_opens_section(pdf, cand, entry):
                return cand
    return 0
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
            if doc_id.startswith(NON_FUNCTIONAL_DOC_PREFIXES):
                res.note = "documento senza indice funzionale — non applicabile"
                res.skipped = True
                current.results.append(res)
                continue
            url = url_builder.build(sd, doc_id, cname, 0,
                                    doc_cartella=doc_cartella)
            if not url:
                res.note = "URL non costruibile (documento segnaposto)"
                res.skipped = True
                current.results.append(res)
                continue
            pdf_path = resolve_pdf(url, docs_dir)
            if not pdf_path:
                res.note = f"PDF non trovato ({Path(url).name})"
                current.results.append(res)
                continue
            res.pdf_name = pdf_path.name
            res.pdf_path = str(pdf_path)
            doc = get_toc(pdf_path)
            if not doc.ok:
                res.note = doc.error or "indice non leggibile"
                current.results.append(res)
                continue
            entry, score = match_function(doc, current.func_id,
                                          current.func_desc)
            if entry is None:
                res.note = "funzione non trovata nell'indice"
            else:
                res.score  = score
                res.strong = score >= STRONG_MATCH_F1
                _apply_entry(res, doc, entry)
                if not res.strong:
                    res.note = "match debole"
            current.results.append(res)
    if current and current.results:
        out.append(current)
    _interpolate_weak_matches(out, toc_cache)
    return out
def _apply_entry(res: ConfigResult, doc: DocToc, entry: TocEntry) -> None:
    """
    Fissa indice, titolo e pagina dinamica di un risultato, confermando la
    pagina nel corpo del PDF. L'offset globale resta solo come ripiego
    quando il corpo non conferma nulla.
    """
    res.matched_index = entry.index
    res.matched_title = entry.title
    page = 0
    try:
        import pymupdf as fitz
    except ImportError:                                   # pragma: no cover
        fitz = None
    if fitz is not None and res.pdf_path:
        try:
            pdf = fitz.open(res.pdf_path)
            try:
                page = confirm_page_in_body(pdf, entry, set(doc.toc_pages))
            finally:
                pdf.close()
        except Exception as exc:
            log.debug(f"  conferma nel corpo fallita: {exc}")
    if page:
        res.dynamic_page = page
        res.offset = 0
        res.confirmed = True
    else:
        res.offset = doc.offset
        res.dynamic_page = max(1, entry.printed_page + doc.offset)
        res.confirmed = False
def _interpolate_weak_matches(
    results: list[FunctionResult], toc_cache: dict[str, DocToc]
) -> None:
    """
    SECONDO PASSAGGIO — interpolazione ordinale.
    Le funzioni sono elencate nel foglio "Funzioni" nello STESSO ORDINE in
    cui compaiono nei documenti. Quando una configurazione ha rinominato
    una sezione, il confronto per titolo fallisce, ma la POSIZIONE no.
    Esempio reale (FA020022045, configurazione VZI-6_R1):
        LV_Line_Current_Supervision    -> 3.3.2   (match forte)
        LV_Line_Interference_Monitor   -> ???     ("High Voltage System
                                                   Protection": titolo
                                                   completamente diverso)
        LV_LIM_50Hz_protection_bypass  -> 3.3.4   (match forte)
      Fra 3.3.2 e 3.3.4 c'e' una sola sezione, 3.3.3, a pagina 39:
      esattamente il Rif. Pagina statico inserito dall'utente.
    Si interviene SOLO sui risultati deboli o assenti, mai su quelli forti.
    """
    # Raggruppa per (documento, configurazione) mantenendo l'ordine Excel.
    groups: dict[tuple[str, str], list[ConfigResult]] = {}
    for fr in results:
        for r in fr.results:
            if r.pdf_path:
                groups.setdefault((r.pdf_path, r.config_name), []).append(r)
    for (pdf_path, _cfg), items in groups.items():
        doc = toc_cache.get(pdf_path)
        if not doc or not doc.ok:
            continue
        for i, r in enumerate(items):
            if r.strong:
                continue
            prev = next((x for x in reversed(items[:i]) if x.strong), None)
            nxt  = next((x for x in items[i + 1:] if x.strong), None)
            if prev is None or nxt is None:
                continue
            lo, hi = _idx_key(prev.matched_index), _idx_key(nxt.matched_index)
            if not lo < hi:
                continue
            # Sezioni gia' attribuite con certezza ad altre funzioni: non
            # possono essere riassegnate, altrimenti un buco nell'indice
            # (voci generiche come "Function Design"/"Requirements" che il
            # filtro scarta) farebbe ricadere la funzione su una sezione
            # altrui.
            claimed = {x.matched_index for x in items if x.strong}
            between = [
                e for e in doc.entries
                if lo < _idx_key(e.index) < hi
                and e.title.lower() not in GENERIC_TITLES
                and e.index not in claimed
            ]
            # Una sola sezione nel buco: l'attribuzione e' certa.
            if len(between) != 1:
                # Piu' candidate: si tiene quella allo stesso livello dei vicini.
                depth = len(lo)
                same = [e for e in between if len(_idx_key(e.index)) == depth]
                if len(same) != 1:
                    continue
                between = same
            _apply_entry(r, doc, between[0])
            r.strong = True
            r.note = "ricavato per posizione fra "
            r.note += f"{prev.matched_index} e {nxt.matched_index}"
    # Cio' che resta debole e' un abbinamento inventato: meglio dichiarare
    # la funzione assente che proporre una pagina sbagliata. E' il caso di
    # BRK_Magnetic_Track_Brake, che in VZ_ES e VZI-6_R1 non esiste e che
    # altrimenti verrebbe agganciato a "3.4 Urgency Brake (Optional)".
    for fr in results:
        for r in fr.results:
            if r.matched_index and not r.strong:
                r.dynamic_page = 0
                r.matched_index = ""
                r.matched_title = ""
                r.skipped = True
                r.note = "funzione non presente in questo documento"
    return
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
    tot = ok = diff = nd = obs = na = 0
    txt_lines: list[str] = []
    html_rows: list[str] = []
    header = (
        "RIFERIMENTO PAGINA DINAMICO — confronto con il valore statico\n"
        "VERDE = i due valori coincidono | GIALLO = statico obsoleto, dinamico\n"
        "verificato nel corpo del PDF | ROSSO = divergenza da indagare\n"
        "GRIGIO = confronto non applicabile\n"
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
            elif r.status == "OBS":
                obs += 1
                css, ansi = "obs", ANSI_YELLOW
            elif r.status == "DIFF":
                diff += 1
                css, ansi = "diff", ANSI_RED
            elif r.status == "--":
                na += 1
                css, ansi = "na", ANSI_GREY
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
        f"Confronti applicabili : {tot - na}\n"
        f"  VERDE  (coincide)   : {ok}\n"
        f"  GIALLO (statico obsoleto, dinamico verificato) : {obs}\n"
        f"  ROSSO  (diverso)    : {diff}\n"
        f"  ROSSO  (N/D)        : {nd}\n"
        f"  GRIGIO (non applicabile) : {na}\n"
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
        ".obs{color:#e0c33c;white-space:pre}"
        ".na{color:#7a7a7a;white-space:pre}"
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
