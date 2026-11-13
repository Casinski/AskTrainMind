"""
rif_pagina.py
-------------
Calcolo DINAMICO del "Rif. Pagina" del foglio "Funzioni".

Il riferimento di pagina che alimenta il frammento "#page=N" degli
Hyperlink non viene piu' digitato a mano: viene ricavato dall'indice
(Content / Table of Contents) del PDF associato a ogni configurazione,
abbinando FUNC ID + DESCRIZIONE FUNZIONE al paragrafo corretto.

ALGORITMO (validato su 246 confronti, 239 coincidenti con il valore
inserito storicamente a mano, 7 divergenze dovute a celle non aggiornate
dopo una revisione del documento):

  1. Lettura dell'indice             -> read_toc()
     - segnalibri nativi del PDF, se presenti
     - altrimenti parsing testuale in 4 formati, compreso quello con
       numero+titolo sulla stessa riga e pagina su quella successiva
     - parser di riserva per gli indici privi di numerazione, dove il
       layer testuale espone solo i capitoli di primo livello
  2. Abbinamento funzione -> paragrafo  -> match_function()
     punteggio F1 bidirezionale, ancorato al capitolo "Functional
     requirements" per non agganciare la panoramica di "System Overview"
  3. Conferma della pagina nel corpo    -> confirm_page_in_body()
  4. Interpolazione ordinale            -> interpolate_weak_matches()
     per le sezioni rinominate da una configurazione all'altra

SCRITTURA NELLE CELLE (run_pass):
  - dinamico == statico            -> scrive il numero, VERDE
  - statico assente                -> scrive il numero, VERDE
  - dinamico != statico            -> "32 utente - 34 dinamico", ROSSO
  - dinamico non calcolabile       -> la cella non viene toccata
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from openpyxl.styles import Font

import config as cfg
import document_handler
import interrupt_guard
import url_builder
from support_loader import SupportData

log = logging.getLogger(__name__)

FONT_RIF_OK   = Font(color="00AA00", bold=False)
FONT_RIF_DIFF = Font(color="CC0000", bold=False)

# ═══════════════════════════════════════════════════════════════════════════
# MOTORE: LETTURA INDICE E ABBINAMENTO
# ═══════════════════════════════════════════════════════════════════════════
GENERIC_TITLES = {
    "function design", "requirements", "introduction", "content",
    "contents", "general", "overview", "revision log", "scope",
    "definitions and abbreviations", "references", "abbreviations",
}
# Sotto-paragrafi standard presenti in ogni funzione: non delimitano mai
# la funzione stessa.
SUBHEADING_TITLES = {
    "function design", "functional design", "design description",
    "requirements", "normal condition", "normal conditions",
    "failure cases", "failure condition", "failure detection",
    "failure handling", "failure supervision",
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
    # True quando l'indice e' ricostruito (documento senza numerazione dei
    # paragrafi, p.es. FA020022675): nel corpo la sezione si riconosce
    # dal solo TITOLO, non dal numero.
    synthetic: bool = False
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
        entries.append(TocEntry(f"{chapter}.{counters[chapter]}", title, page,
                                synthetic=True))
    return entries


# ── Parser alternativi del sommario ─────────────────────────────────────────
# Alcuni documenti (stile Hitachi: FA020026053, FA020025252, FA020025419,
# FA020026562, FA020026563) scrivono l'indice su una riga e
# "Titolo ........ 8" sulla successiva; altri (VSI: FA020022675) non hanno
# alcun numero di paragrafo e la gerarchia e' data solo dal rientro.
# Il parser storico resta il primo candidato; questi entrano in gioco
# solo se producono un indice sensibilmente piu' completo.

def _max_depth(entries: list[TocEntry]) -> int:
    return max((e.depth for e in entries), default=0)


def _alt_toc_is_better(alt: list[TocEntry], cur: list[TocEntry]) -> bool:
    """
    Decide se l'indice di un parser alternativo sostituisce quello attuale.
    Conservativo: l'indice storico resta finche' l'alternativo non e'
    sensibilmente piu' completo, oppure piu' gerarchico a parita' di voci
    (indice piatto "1, 2, ... 26" o "3.1 ... 3.19" ricostruito dai soli
    titoli contro la gerarchia vera ricavata dal rientro).
    """
    if len(alt) < 2:
        return False
    if len(cur) < 2:
        return True
    flat_cur = _max_depth(cur) <= 1 or all(e.synthetic for e in cur)
    if flat_cur and _max_depth(alt) > _max_depth(cur):
        return len(alt) >= len(cur) - 1
    return len(alt) > len(cur) + max(2, len(cur) // 10)


def _text_parser_entries(pdf, marker_page: int, limit: int
                         ) -> tuple[list[TocEntry], list[int]]:
    """Indice letto dal testo semplice con il parser dell'opzione 2."""
    import index_funzioni as IF
    out: list[TocEntry] = []
    pages: list[int] = []
    for p in range(marker_page, limit):
        page_entries = []
        for e in IF.parse_toc_text(pdf[p].get_text()):
            idx = e.index.rstrip(".")
            title = _clean_title(e.title)
            if _is_index_token(idx) and _is_valid_title(title) and e.page > 0:
                page_entries.append(TocEntry(idx, title, e.page))
        if not page_entries:
            if out:
                break
            continue
        if out and _idx_key(page_entries[0].index) < _idx_key(out[-1].index) \
                and page_entries[0].printed_page <= out[-1].printed_page:
            break                       # inizia il corpo del documento
        out.extend(page_entries)
        pages.append(p + 1)
    return out, pages


def _layout_parser_entries(pdf, marker_page: int
                           ) -> tuple[list[TocEntry], list[int]]:
    """
    Indice letto dal layout (righe visive): [indice] titolo .... pagina.
    Se la numerazione non e' gerarchica il livello si ricava dal rientro
    del titolo e l'indice viene sintetizzato (voci con synthetic=True).
    """
    import index_funzioni as IF
    raw = [e for e in IF._layout_entries(pdf) if e.pdf_page >= marker_page]
    raw = [e for e in raw if _is_valid_title(_clean_title(e.title)) and e.page > 0]
    if not raw:
        return [], []
    # Solo le pagine di sommario consecutive: piu' avanti c'e' il corpo.
    first = raw[0].pdf_page
    seen_pages = sorted({e.pdf_page for e in raw})
    last = first
    for pg in seen_pages[1:]:
        if pg != last + 1:
            break
        last = pg
    raw = [e for e in raw if e.pdf_page <= last]
    pages = sorted({e.pdf_page + 1 for e in raw})
    dotted = sum(1 for e in raw if "." in e.index.rstrip("."))
    if dotted >= 0.5 * len(raw):
        out = [TocEntry(e.index.rstrip("."), _clean_title(e.title), e.page)
               for e in raw if e.index and _is_index_token(e.index)]
        return out, pages
    # Numerazione assente o solo di primo livello: gerarchia dal rientro.
    clusters: list[float] = []
    for x in sorted(round(e.x) for e in raw):
        if not clusters or x - clusters[-1] > 4:
            clusters.append(x)
    if len(clusters) > 6:
        return [], pages
    def level(e) -> int:
        return 1 + max(k for k, cx in enumerate(clusters) if round(e.x) >= cx - 4)
    # I numeri presenti si usano solo se compaiono sui soli capitoli
    # (FRS_Bogies: "1", "2", "3"); una numerazione progressiva su tutte le
    # voci (FA020026347: 1 ... 26) non e' un indice di paragrafo.
    numbered_chapters = all(level(e) == 1 for e in raw if e.index)
    out: list[TocEntry] = []
    counters: list[int] = []
    for e in raw:
        lvl = level(e)
        counters = (counters + [0] * lvl)[:lvl]
        if lvl == 1 and numbered_chapters and e.index.rstrip(".").isdigit():
            counters[0] = int(e.index.rstrip("."))
        else:
            counters[lvl - 1] += 1
        idx = ".".join(str(n) for n in counters)
        out.append(TocEntry(idx, _clean_title(e.title), e.page, synthetic=True))
    return out, pages


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
    # Titoli con spaziatura spuria: "Fu n c tio n a l re q u ire m e n ts".
    for e in entries:
        if "functionalrequirement" in _title_key(e.title):
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
def _title_key(text: str) -> str:
    """'HVAC Cab – Off mode' -> 'hvacaboffmode' (solo lettere e cifre)."""
    return re.sub(r"[\W_]+", "", str(text).lower())


def find_title_line(lines: list[str], title: str, start: int = 0) -> int:
    """
    Indice della prima riga (da start) che coincide con il titolo, oppure
    -1. L'eventuale numero di paragrafo in testa alla riga e' ignorato
    ("4.3 HVAC Cab – Off mode" vale "HVAC Cab – Off mode"); un titolo che
    va a capo viene ricomposto con la riga successiva. Serve per i
    documenti senza numerazione dei paragrafi (FA020022675): nel corpo la
    sezione e' identificata solo dal titolo ("Car ID and Vehicle Type").
    """
    want = _title_key(title)
    if len(want) < 4:
        return -1
    for k in range(max(0, start), len(lines)):
        ln = lines[k]
        if not ln or len(ln) > len(title) + 20:
            continue
        cur = _title_key(re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", ln))
        if cur == want:
            return k
        if len(cur) >= 4 and want.startswith(cur) and k + 1 < len(lines):
            nxt = _title_key(lines[k + 1])
            if cur + nxt == want:
                return k
    return -1


def _lines_have_title(lines: list[str], entry: TocEntry) -> bool:
    return find_title_line(lines, entry.title) >= 0


def _page_lines(pdf, phys: int) -> list[str]:
    return [ln.strip() for ln in
            pdf[phys - 1].get_text().replace("\xa0", " ").splitlines()]


def _find_heading_physical_page(
    pdf, entry: TocEntry, search_from: int, search_to: int,
    skip_pages: Optional[set[int]] = None,
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
        if skip_pages and phys in skip_pages:
            continue
        lines = _page_lines(pdf, phys)
        if entry.synthetic:
            if _lines_have_title(lines, entry):
                return phys
            continue
        for k, ln in enumerate(lines):
            if not idx_re.match(ln):
                continue
            # Titolo sulla stessa riga oppure nelle 3 righe seguenti.
            window = " ".join([ln] + [x for x in lines[k + 1:k + 4]])
            found = _norm_words(window)
            if len(title_words & found) >= max(1, int(len(title_words) * 0.6)):
                return phys
    return 0
def _detect_offset(pdf, entries: list[TocEntry],
                   skip_pages: Optional[set[int]] = None) -> int:
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
            pdf, e, e.printed_page - 4, e.printed_page + 6, skip_pages
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
        chain = _longest_consistent_chain(collected)
        toc_pages = list(doc.toc_pages)
        # Parser alternativi (layout / indice su riga separata): vincono
        # solo se l'indice storico manca o e' sensibilmente piu' povero.
        for name, (alt, alt_pages) in (
            ("testo", _text_parser_entries(pdf, marker_page, limit)),
            ("layout", _layout_parser_entries(pdf, marker_page)),
        ):
            alt_chain = _longest_consistent_chain(alt)
            if _alt_toc_is_better(alt_chain, chain):
                log.debug(f"  indice: parser '{name}' ({len(alt_chain)} voci) "
                          f"preferito al precedente ({len(chain)})")
                chain, toc_pages = alt_chain, alt_pages
        doc.toc_pages = toc_pages
        if not collected and not chain:
            doc.error = "indice non trovato nel documento"
            return doc
        doc.entries = chain
        if len(doc.entries) < 2:
            doc.error = "indice riconosciuto ma incoerente"
            return doc
        doc.offset = _detect_offset(pdf, doc.entries, set(doc.toc_pages))
        doc.functional_chapter = _detect_functional_chapter(doc.entries)
        return doc
    finally:
        pdf.close()
# ═══════════════════════════════════════════════════════════════════════════
# 2. ABBINAMENTO FUNZIONE -> PARAGRAFO
# ═══════════════════════════════════════════════════════════════════════════
def _num_tokens(text: str) -> set[str]:
    """Numeri isolati: "BOG_Level_1_Alarm" -> {"1"}; "Level 2 Alarm" -> {"2"}."""
    return set(re.findall(r"(?<![\w.])\d{1,2}(?![\w.])",
                          re.sub(r"[_\-/()]", " ", str(text))))


def _expand_aliases(words: set[str]) -> set[str]:
    """Aggiunge i sinonimi noti alle parole della funzione."""
    extra: set[str] = set()
    for w in words:
        extra |= TITLE_ALIASES.get(w, set())
    return words | extra
def match_function(
    doc: DocToc, func_id: str, func_desc: str, near_page: int = 0
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
    fnums = _num_tokens(func_id)
    # Estensione in pagine di ogni voce: serve come criterio di parita'.
    spans: dict[int, int] = {}
    for i, e in enumerate(doc.entries):
        nxt = doc.entries[i + 1].printed_page if i + 1 < len(doc.entries) else e.printed_page
        spans[id(e)] = max(0, nxt - e.printed_page)
    by_index = {e.index: e for e in doc.entries}
    best: Optional[TocEntry] = None
    best_rank: tuple = ()
    for e in doc.entries:
        if e.title.lower() in GENERIC_TITLES:
            continue
        # near_page: solo le voci che iniziano intorno alla pagina fisica
        # indicata (uso dall'opzione 1, che parte dal Rif. Pagina).
        if near_page and abs(e.printed_page + doc.offset - near_page) > 1:
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
        # Sottoparagrafo con titolo breve ("3.1.9 Events") di una funzione
        # nominata come "<titolo padre>_<titolo figlio>"
        # (AUX_Electrical_Auxiliary_System_(3~_400V_AC)_Events): si valuta
        # anche il titolo composto padre + figlio.
        parent = by_index.get(e.index.rsplit(".", 1)[0]) if "." in e.index else None
        if parent is not None:
            pw = _norm_words(parent.title) - tw
            if pw & func_words:
                cw = tw | pw
                c_common = len(cw & func_words)
                c_prec = c_common / len(cw)
                c_rec = len(cw & ref_words) / len(ref_words)
                if c_prec and c_rec:
                    f1 = max(f1, 2 * c_prec * c_rec / (c_prec + c_rec))
        # Le cifre non entrano nelle parole: "Level 1 Alarm" e "Level 2
        # Alarm" risultavano equivalenti per BOG_Level_1_Alarm. Numeri
        # discordanti escludono la voce, numeri concordanti la premiano.
        tnums = _num_tokens(e.title)
        num_ok = 0
        if fnums and tnums:
            if not (fnums & tnums):
                continue
            num_ok = 1
        # Il Rif. Pagina punta dentro il capitolo "Functional requirements":
        # a parita' di titolo la panoramica di "System Overview" perde.
        in_func = (
            1 if doc.functional_chapter
            and e.index.split(".")[0] == doc.functional_chapter else 0
        )
        rank = (round(f1, 4), num_ok, in_func, -e.depth, spans[id(e)],
                -e.printed_page)
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
    lines = _page_lines(pdf, page)
    if entry.synthetic:
        return _lines_have_title(lines, entry)
    idx_re = re.compile(r"^" + re.escape(entry.index) + r"\.?(\s|$)")
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


# ═══════════════════════════════════════════════════════════════════════════
# LOCALIZZAZIONE DI UNA SEZIONE (opzione 1 / estrazione requisiti)
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class SectionLocation:
    """Sezione di una funzione ricavata dall'indice del documento."""
    entry: TocEntry
    page: int                      # pagina fisica di inizio
    end_titles: list[str]          # titoli che chiudono la sezione
    end_index: str = ""            # indice della voce successiva (se reale)


_LOCATE_CACHE: dict[str, DocToc] = {}


def _cached_toc(pdf_path: Path) -> DocToc:
    try:
        st = pdf_path.stat()
        key = f"{pdf_path}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        key = str(pdf_path)
    if key not in _LOCATE_CACHE:
        _LOCATE_CACHE[key] = read_toc(pdf_path)
    return _LOCATE_CACHE[key]


def locate_section(pdf_path: Path, page_number: int, func_id: str,
                   func_desc: str = "") -> Optional[SectionLocation]:
    """
    Paragrafo della funzione che inizia intorno a page_number, letto
    dall'indice del documento. Serve quando nel corpo manca il numero di
    paragrafo (documenti VSI come FA020022675) o ha un formato diverso:
    la sezione va dal titolo della funzione al titolo della prima voce
    successiva di livello uguale o superiore (3.3.4 -> 3.3.5 o 3.4); i
    sotto-paragrafi (Function Design, Requirements, ...) sono inclusi.
    """
    if not pdf_path or Path(pdf_path).suffix.lower() != ".pdf" or page_number < 1:
        return None
    doc = _cached_toc(Path(pdf_path))
    if not doc.ok:
        return None
    entry, score = match_function(doc, func_id, func_desc, near_page=page_number)
    if entry is None or score < 0.5:
        return None
    pos = next(i for i, e in enumerate(doc.entries) if e is entry)
    # "Function Design" / "Requirements" ricorrono in ogni funzione: come
    # confine chiuderebbero la sezione al primo sotto-paragrafo.
    following = [e for e in doc.entries[pos + 1:] if e.depth <= entry.depth
                 and e.title.lower() not in GENERIC_TITLES
                 and e.title.lower() not in SUBHEADING_TITLES]
    return SectionLocation(
        entry=entry,
        page=entry.printed_page + doc.offset,
        end_titles=[e.title for e in following[:3]],
        end_index="" if not following or following[0].synthetic
        else following[0].index,
    )


# ═══════════════════════════════════════════════════════════════════════════
# RISULTATI
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class ConfigRef:
    """Esito del calcolo per una singola configurazione."""
    config_name: str
    row: int                       # riga della cella "Rif. Pagina"
    col: int
    doc_id: str
    doc_cartella: str
    static_page: int
    static_raw: str
    dynamic_page: int = 0
    matched_index: str = ""
    matched_title: str = ""
    pdf_path: str = ""
    strong: bool = False
    skipped: bool = False
    note: str = ""

    @property
    def status(self) -> str:
        """OK | DIFF | N/D | --"""
        if self.skipped:
            return "--"
        if self.dynamic_page <= 0:
            return "N/D"
        if self.static_page <= 0:
            return "OK"          # solo dinamico: si scrive e si colora verde
        return "OK" if self.dynamic_page == self.static_page else "DIFF"


@dataclass
class FunctionRefs:
    func_id: str
    func_desc: str
    row: int
    refs: list[ConfigRef] = field(default_factory=list)


@dataclass
class RifPaginaStats:
    written: int = 0
    equal: int = 0
    divergent: int = 0
    only_dynamic: int = 0
    unresolved: int = 0
    skipped: int = 0
    interrupted: bool = False
    interrupted_at: str = ""      # funzione da cui riprendere se interrotto
    # Riferimenti da verificare, mostrati all'utente a fine esecuzione.
    not_found: list["RefIssue"] = field(default_factory=list)
    divergences: list["RefIssue"] = field(default_factory=list)


@dataclass
class RefIssue:
    """Riferimento non trovato o divergente (report di fine opzione 3)."""
    func_id: str
    config_name: str
    doc_id: str
    user_page: int
    dynamic_page: int
    section: str
    note: str


# ═══════════════════════════════════════════════════════════════════════════
# RISOLUZIONE DEL PDF
# ═══════════════════════════════════════════════════════════════════════════
def resolve_pdf(url: str) -> Optional[Path]:
    """Percorso locale del PDF a partire dall'URL SharePoint."""
    try:
        path = document_handler.download(url)
    except Exception as exc:
        log.debug(f"  download fallito: {exc}")
        return None
    if not path:
        return None
    path = Path(path)
    return path if path.exists() and path.suffix.lower() == ".pdf" else None


# ═══════════════════════════════════════════════════════════════════════════
# APPLICAZIONE E SECONDO PASSAGGIO
# ═══════════════════════════════════════════════════════════════════════════
def apply_entry(ref: ConfigRef, doc: DocToc, entry: TocEntry) -> None:
    """
    Fissa indice, titolo e pagina dinamica, confermando l'intestazione nel
    corpo del PDF. L'offset globale dell'indice resta solo come ripiego
    quando il corpo non conferma nulla.
    """
    ref.matched_index = entry.index
    ref.matched_title = entry.title
    page = 0
    try:
        import pymupdf as fitz
    except ImportError:                                   # pragma: no cover
        try:
            import fitz
        except ImportError:
            fitz = None
    if fitz is not None and ref.pdf_path:
        try:
            pdf = fitz.open(ref.pdf_path)
            try:
                page = confirm_page_in_body(pdf, entry, set(doc.toc_pages))
            finally:
                pdf.close()
        except Exception as exc:
            log.debug(f"  conferma nel corpo fallita: {exc}")
    if page:
        ref.dynamic_page = page
    else:
        ref.dynamic_page = max(1, entry.printed_page + doc.offset)


def interpolate_weak_matches(
    functions: list[FunctionRefs], toc_cache: dict[str, DocToc]
) -> None:
    """
    Secondo passaggio per gli abbinamenti deboli.

    Le funzioni del foglio "Funzioni" compaiono nello stesso ordine in cui
    compaiono nei documenti. Se il vicino precedente e quello successivo
    hanno un abbinamento forte e fra i due indici resta UNA SOLA sezione
    libera, quella sezione e' la funzione cercata anche quando e' stata
    rinominata (p.es. "Line Interference Monitor" diventato "High Voltage
    System Protection" in VZI-6_R1).

    Cio' che resta debole viene dichiarato assente: meglio nessun valore
    che una pagina sbagliata.
    """
    by_doc: dict[tuple[str, str], list[ConfigRef]] = {}
    for fr in functions:
        for r in fr.refs:
            if r.pdf_path:
                by_doc.setdefault((r.pdf_path, r.config_name), []).append(r)

    for (pdf_path, _cfg_name), items in by_doc.items():
        doc = toc_cache.get(pdf_path)
        if not doc or not doc.ok:
            continue
        for i, r in enumerate(items):
            if r.strong or r.skipped:
                continue
            prev = next(
                (x for x in reversed(items[:i]) if x.strong and x.matched_index),
                None,
            )
            nxt = next(
                (x for x in items[i + 1:] if x.strong and x.matched_index), None
            )
            if not prev or not nxt:
                continue
            lo, hi = _idx_key(prev.matched_index), _idx_key(nxt.matched_index)
            if not lo < hi:
                continue
            claimed = {x.matched_index for x in items if x.strong}
            between = [
                e for e in doc.entries
                if lo < _idx_key(e.index) < hi
                and e.title.lower() not in GENERIC_TITLES
                and e.index not in claimed
            ]
            if len(between) != 1:
                depth = len(lo)
                same = [e for e in between if len(_idx_key(e.index)) == depth]
                if len(same) != 1:
                    continue
                between = same
            apply_entry(r, doc, between[0])
            r.strong = True
            r.note = (
                f"ricavato per posizione fra {prev.matched_index} "
                f"e {nxt.matched_index}"
            )

    _drop_weak(functions)


NOTE_NOT_IN_DOC = "funzione non presente in questo documento"


def _drop_weak(functions: list[FunctionRefs]) -> None:
    """Gli abbinamenti rimasti deboli vengono dichiarati assenti."""
    for fr in functions:
        for r in fr.refs:
            if r.matched_index and not r.strong:
                r.dynamic_page = 0
                r.matched_index = ""
                r.matched_title = ""
                r.skipped = True
                r.note = NOTE_NOT_IN_DOC


# ═══════════════════════════════════════════════════════════════════════════
# SCANSIONE DEL FOGLIO "Funzioni"
# ═══════════════════════════════════════════════════════════════════════════
def _is_rif_pagina_label(label: str) -> bool:
    low = label.lower().strip()
    return low.startswith("rif") or low == "pagina"


# FUNC ID in lavorazione quando l'ultimo scan_and_resolve e' stato interrotto
LAST_INTERRUPTED: bool = False
LAST_INTERRUPTED_AT: str = ""


def scan_and_resolve(
    ws_write,
    ws_data,
    sd: SupportData,
    start_from_func_id: str = "",
) -> list[FunctionRefs]:
    """
    Percorre il foglio "Funzioni" con la stessa struttura a 3 livelli usata
    da excel_scanner e calcola il Rif. Pagina dinamico di ogni cella.

    Su Ctrl+C (con SAVE_PROGRESS attivo) restituisce le funzioni elaborate
    fino a quel momento e annota in LAST_INTERRUPTED_AT la funzione in
    lavorazione, cosi' i riferimenti gia' trovati vengono comunque scritti.
    """
    global LAST_INTERRUPTED, LAST_INTERRUPTED_AT
    LAST_INTERRUPTED, LAST_INTERRUPTED_AT = False, ""
    functions: list[FunctionRefs] = []
    toc_cache: dict[str, DocToc] = {}
    try:
        _scan(ws_write, ws_data, sd, start_from_func_id, functions, toc_cache)
    except KeyboardInterrupt as exc:
        interrupt_guard.handle(exc, "Rif. Pagina")
        LAST_INTERRUPTED = True
        # Gli abbinamenti deboli non sono stati ancora interpolati: la
        # ripresa parte dalla prima funzione che ne contiene uno.
        weak = next((fr.func_id for fr in functions
                     if any(r.matched_index and not r.strong for r in fr.refs)),
                    "")
        LAST_INTERRUPTED_AT = (weak or (functions[-1].func_id if functions
                                        else start_from_func_id.strip()))
    if LAST_INTERRUPTED:
        _drop_weak(functions)
        return functions
    try:
        interpolate_weak_matches(functions, toc_cache)
    except KeyboardInterrupt as exc:
        interrupt_guard.handle(exc, "Rif. Pagina")
        LAST_INTERRUPTED = True
        LAST_INTERRUPTED_AT = functions[-1].func_id if functions else ""
        _drop_weak(functions)
    return functions


def _scan(ws_write, ws_data, sd: SupportData, start_from_func_id: str,
          functions: list[FunctionRefs], toc_cache: dict) -> None:
    from excel_scanner import _build_header_map, _cell_str, _parse_page

    col_map    = _build_header_map(ws_write)
    id_col     = col_map.get("id", 1)
    label_col  = col_map.get("funzione", 2)
    cart_col   = col_map.get("doc_cartella", 3)
    doc_id_col = col_map.get("doc_id", 4)
    info_col   = col_map.get("info_doc", 5)

    config_cols = list(range(info_col + 1, ws_write.max_column))
    config_names = {
        col: (
            str(ws_write.cell(1, col).value).strip().replace("\n", " / ")
            if ws_write.cell(1, col).value else f"CONF_{col}"
        )
        for col in config_cols
    }

    waiting = bool(start_from_func_id.strip())
    target_id = start_from_func_id.strip()

    current: Optional[FunctionRefs] = None
    doc_id = doc_cartella = ""
    doc_row = 0
    configs_with_link: set[str] = set()

    for row in range(2, ws_write.max_row + 1):
        v_id   = _cell_str(ws_write, row, id_col)
        v_cart = _cell_str(ws_write, row, cart_col)
        v_doc  = _cell_str(ws_write, row, doc_id_col)
        v_info = _cell_str(ws_write, row, info_col)

        # ── LIVELLO 1: nuova funzione ────────────────────────────────────
        if v_id:
            if waiting:
                if v_id == target_id:
                    waiting = False
                else:
                    current = None
                    doc_id = doc_cartella = ""
                    continue
            current = FunctionRefs(
                func_id=v_id,
                func_desc=_cell_str(ws_write, row, label_col),
                row=row,
            )
            functions.append(current)
            doc_id = doc_cartella = ""
            doc_row = 0
            configs_with_link = set()
            continue

        if current is None or waiting:
            continue

        # ── LIVELLO 2: nuovo documento ───────────────────────────────────
        INVALID_DOC = {"", "\\", "/", "tbd"}
        if v_cart and v_doc and v_doc.strip().lower() not in INVALID_DOC:
            doc_id       = v_doc
            doc_cartella = v_cart
            doc_row      = row
            configs_with_link = {
                config_names[col] for col in config_cols
                if url_builder.cell_has_valid_link(
                    ws_data, row, col, ws_write=ws_write
                )
            }
            continue

        # ── LIVELLO 3: riga "Rif. Pagina" ────────────────────────────────
        if not (v_info and doc_id and not v_cart):
            continue
        if not _is_rif_pagina_label(v_info):
            continue

        for col in config_cols:
            cname = config_names[col]
            if cname not in configs_with_link:
                continue
            static_raw = _cell_str(ws_write, row, col)
            ref = ConfigRef(
                config_name=cname,
                row=row,
                col=col,
                doc_id=doc_id,
                doc_cartella=doc_cartella,
                static_page=_parse_page(static_raw),
                static_raw=static_raw,
            )
            current.refs.append(ref)

            # I documenti senza indice funzionale (liste segnali, schemi,
            # manuali) non hanno un paragrafo da cui ricavare la pagina.
            if doc_id.startswith(NON_FUNCTIONAL_DOC_PREFIXES):
                ref.skipped = True
                ref.note = "documento senza indice funzionale"
                continue

            url = url_builder.build(
                sd, doc_id, cname, 0, doc_cartella=doc_cartella
            )
            if not url:
                ref.skipped = True
                ref.note = "URL non costruibile"
                continue

            pdf_path = resolve_pdf(url)
            if not pdf_path:
                ref.note = "PDF non disponibile"
                continue

            ref.pdf_path = str(pdf_path)
            doc = toc_cache.get(ref.pdf_path)
            if doc is None:
                doc = read_toc(pdf_path)
                toc_cache[ref.pdf_path] = doc
            if not doc.ok:
                ref.note = doc.error or "indice non leggibile"
                continue

            entry, score = match_function(
                doc, current.func_id, current.func_desc
            )
            if entry is None:
                ref.note = "funzione non trovata nell'indice"
                continue
            ref.strong = score >= STRONG_MATCH_F1
            apply_entry(ref, doc, entry)


# ═══════════════════════════════════════════════════════════════════════════
# SCRITTURA NELLE CELLE "Rif. Pagina"
# ═══════════════════════════════════════════════════════════════════════════
def format_cell_value(ref: ConfigRef) -> Optional[tuple]:
    """
    Valore e font da scrivere nella cella "Rif. Pagina".

      - dinamico == statico, oppure statico assente -> numero, VERDE
      - dinamico != statico -> "32 utente - 34 dinamico", ROSSO
      - dinamico non calcolabile -> None (la cella non si tocca)
    """
    if ref.dynamic_page <= 0:
        return None
    if ref.static_page > 0 and ref.static_page != ref.dynamic_page:
        return (
            f"{ref.static_page} utente - {ref.dynamic_page} dinamico",
            FONT_RIF_DIFF,
        )
    return ref.dynamic_page, FONT_RIF_OK


def write_refs(ws_write, functions: list[FunctionRefs]) -> RifPaginaStats:
    """Scrive i riferimenti calcolati e restituisce le statistiche."""
    stats = RifPaginaStats()
    for fr in functions:
        if not fr.refs:
            continue
        log.info(f"  {fr.func_id}")
        for ref in fr.refs:
            if ref.skipped:
                stats.skipped += 1
                log.debug(f"    [{ref.config_name}] {ref.note}")
                # Documento applicabile ma paragrafo assente: va segnalato
                # (es. valore utente che punta a una funzione inesistente).
                if ref.note == NOTE_NOT_IN_DOC:
                    stats.not_found.append(RefIssue(
                        fr.func_id, ref.config_name, ref.doc_id,
                        ref.static_page, 0, "", ref.note))
                continue
            formatted = format_cell_value(ref)
            if formatted is None:
                stats.unresolved += 1
                stats.not_found.append(RefIssue(
                    fr.func_id, ref.config_name, ref.doc_id, ref.static_page,
                    0, "", ref.note or "nessun abbinamento"))
                log.info(
                    f"    [{ref.config_name}] {ref.doc_id}: "
                    f"non calcolabile — {ref.note or 'nessun abbinamento'}; "
                    f"cella lasciata invariata"
                )
                continue
            value, font = formatted
            cell = ws_write.cell(ref.row, ref.col)
            cell.value = value
            cell.font = font
            stats.written += 1
            if ref.static_page <= 0:
                stats.only_dynamic += 1
                esito = "solo dinamico"
            elif ref.static_page == ref.dynamic_page:
                stats.equal += 1
                esito = "coincide"
            else:
                stats.divergent += 1
                esito = f"DIVERGENZA (utente {ref.static_page})"
                stats.divergences.append(RefIssue(
                    fr.func_id, ref.config_name, ref.doc_id, ref.static_page,
                    ref.dynamic_page,
                    f"{ref.matched_index} {ref.matched_title}".strip(),
                    "" if ref.strong else "abbinamento debole"))
            log.info(
                f"    [{ref.config_name}] {ref.doc_id}: "
                f"{ref.dynamic_page} — {esito} "
                f"[{ref.matched_index} {ref.matched_title}]"
            )
    return stats


def run_pass(
    ws_write,
    ws_data,
    sd: SupportData,
    start_from_func_id: str = "",
) -> RifPaginaStats:
    """
    Passaggio completo: calcola il Rif. Pagina dinamico di tutte le
    configurazioni e lo scrive nel foglio "Funzioni".

    Va eseguito PRIMA di excel_scanner.scan(), cosi' che gli URL dei
    FillTarget usino il frammento "#page=" aggiornato.
    """
    log.info(
        f"\n{'═' * 55}\n"
        f"  RIF. PAGINA DINAMICO — calcolo dall'indice dei PDF\n"
        f"{'═' * 55}"
    )
    functions = scan_and_resolve(ws_write, ws_data, sd, start_from_func_id)
    with interrupt_guard.protected():
        stats = write_refs(ws_write, functions)
    stats.interrupted = LAST_INTERRUPTED
    stats.interrupted_at = LAST_INTERRUPTED_AT
    log.info(
        f"\n  Rif. Pagina: {stats.written} celle scritte "
        f"({stats.equal} coincidenti, {stats.divergent} divergenti, "
        f"{stats.only_dynamic} solo dinamico)\n"
        f"  Non calcolabili: {stats.unresolved} | "
        f"Non applicabili: {stats.skipped}\n"
        f"{'═' * 55}"
    )
    return stats


def _table(headers: list[str], rows: list[list[str]], max_w: int = 48) -> list[str]:
    """Tabella di testo a colonne allineate (celle troncate a max_w)."""
    cut = lambda v: v if len(v) <= max_w else v[:max_w - 1] + "…"
    rows = [[cut(str(c)) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    line = lambda cells: "  " + " │ ".join(c.ljust(w) for c, w in zip(cells, widths))
    sep = "  " + "─┼─".join("─" * w for w in widths)
    return [line(headers), sep] + [line(r) for r in rows]


def format_report(stats: RifPaginaStats) -> str:
    """
    Riepilogo di fine esecuzione: riferimenti NON TROVATI (cella lasciata
    invariata; con l'opzione 1 la funzione non viene analizzata se manca
    anche il valore utente) e DIVERGENTI (valore utente diverso da quello
    ricavato dall'indice, cella scritta "X utente - Y dinamico" in rosso).
    """
    out: list[str] = []
    if not stats.not_found and not stats.divergences:
        return "  ✅ Tutti i riferimenti pagina sono stati trovati e coincidono."
    if stats.not_found:
        out.append(f"  ❌ RIFERIMENTI NON TROVATI ({len(stats.not_found)}) — "
                   f"cella lasciata invariata; senza Rif. Pagina l'opzione 1 "
                   f"non analizza funzione e requisiti")
        rows = [[i.func_id, i.config_name, i.doc_id,
                 str(i.user_page) if i.user_page > 0 else "—", i.note]
                for i in sorted(stats.not_found, key=lambda i: (i.user_page <= 0, i.doc_id))]
        out += _table(["FUNC ID", "Config", "DOC ID", "Pag. utente", "Motivo"], rows)
        out.append("")
    if stats.divergences:
        out.append(f"  ⚠ RIFERIMENTI DIVERGENTI ({len(stats.divergences)}) — "
                   f"verificare il valore corretto")
        rows = [[i.func_id, i.config_name, i.doc_id, str(i.user_page),
                 str(i.dynamic_page), i.section + (f" ({i.note})" if i.note else "")]
                for i in stats.divergences]
        out += _table(["FUNC ID", "Config", "DOC ID", "Utente", "Dinamico",
                       "Paragrafo trovato"], rows)
    n_na = stats.skipped - sum(i.note == NOTE_NOT_IN_DOC for i in stats.not_found)
    if n_na > 0:
        out.append(f"\n  ℹ Non applicabili (documenti senza indice funzionale "
                   f"o URL non costruibile): {n_na}")
    return "\n".join(out)
