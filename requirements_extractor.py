"""
requirements_extractor.py
-------------------------
Estrae i requisiti dal testo di una sezione PDF isolata da
document_handler.extract_page_text().

DUE LAYOUT DI TABELLA, ENTRAMBI GUIDATI DALLE INTESTAZIONI

  1) TABELLA VERTICALE — si sviluppa in verticale.
     Col 1 = nome campo, Col 2 = valore. Un blocco per requisito.

         ID            | 2F_05.01.Zefiro-Europe.TRS.184
         Description   | Il sistema deve ...
         Safety Level  | SIL2

     L'etichetta "ID" identifica l'ID del requisito.

  2) TABELLA ORIZZONTALE — si sviluppa in orizzontale.
     Riga 1 = intestazioni, poi una riga per requisito.

         Nr | Description | Type | Derived to | User Interface | SIL

     ATTENZIONE: SOLO il valore in "Nr" è l'ID del requisito.
     Il valore in "Derived to" è l'ID del requisito DA CUI questo
     deriva: va conservato come informazione ma NON deve mai generare
     una voce nel foglio "Requisiti".

PRINCIPIO DI SICUREZZA
  Un ID diventa requisito solo se compare nella posizione di ID di una
  tabella riconosciuta (col "Nr" orizzontale o campo "ID" verticale).
  Tutti gli ID trovati in "Derived to" finiscono in una lista di
  esclusione che ha la precedenza: anche se lo stesso token comparisse
  altrove nel testo discorsivo, non verrà promosso a requisito.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

import config as cfg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modello dati
# ---------------------------------------------------------------------------

@dataclass
class Requirement:
    req_id: str
    description: str = ""
    req_type: str = ""
    derived_to: str = ""
    user_interface: str = ""
    sil: str = ""
    config_name: str = ""
    page_hint: int = 0
    layout: str = ""        # "H" orizzontale | "V" verticale

    def key(self) -> str:
        return self.req_id.strip().lower()

    def fingerprint(self) -> str:
        """Impronta per rilevare modifiche storiche del requisito."""
        base = "|".join([
            self.req_id, _norm(self.description), _norm(self.req_type),
            _norm(self.derived_to), _norm(self.user_interface), _norm(self.sil),
        ])
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Riconoscimento token ID
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]*(?:\.[A-Za-z0-9_\-]+)+")
_SPLIT_RE = re.compile(r"\s{2,}|\t+|\s*\|\s*")      # separatori di colonna


def is_req_id(token: str) -> bool:
    """True se il token ha la forma di un ID requisito."""
    t = (token or "").strip().strip(".,;:()[]")
    if len(t) < 6 or len(t) > 120:
        return False
    low = t.lower()
    if any(b in low for b in cfg.REQ_ID_BLACKLIST_SUBSTR):
        return False
    if cfg.REQ_ID_MARKER in low:
        return t.count(".") >= 1
    for pat in cfg.REQ_ID_FALLBACK_PATTERNS:
        if re.fullmatch(pat, t):
            return t.count(".") >= cfg.REQ_ID_MIN_SEGMENTS - 1
    return False


def find_req_ids(text: str) -> list[str]:
    """Tutti i token con forma di ID presenti nel testo, in ordine."""
    seen, out = set(), []
    for m in _TOKEN_RE.finditer(text or ""):
        tok = m.group().strip().strip(".,;:()[]")
        if is_req_id(tok) and tok.lower() not in seen:
            seen.add(tok.lower())
            out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def extract(text: str, config_name: str, page_hint: int = 0) -> list[Requirement]:
    """
    Estrae TUTTI i requisiti della sezione.
    Firma invariata: nessuna modifica in funzioni_ai_filter.py.
    """
    if not text or not text.strip():
        return []

    lines = [ln.rstrip() for ln in text.splitlines()]

    found:   dict[str, Requirement] = {}
    derived: set[str] = set()

    _parse_horizontal(lines, config_name, page_hint, found, derived)
    _parse_vertical(lines, config_name, page_hint, found)

    # Recupero: righe che iniziano con un ID ma la cui tabella non è stata
    # riconosciuta (testata destrutturata da fitz).
    if cfg.REQ_ID_ANCHORED_FALLBACK:
        _parse_id_anchored(lines, config_name, page_hint, found, derived)

    if cfg.REQ_ACCEPT_LOOSE_IDS:
        _parse_loose(text, config_name, page_hint, found, derived)

    # Rete di sicurezza: nessun ID "Derived to" può diventare requisito
    for d in derived:
        found.pop(d, None)

    reqs = list(found.values())
    if reqs:
        n_h = sum(1 for r in reqs if r.layout == "H")
        n_v = sum(1 for r in reqs if r.layout == "V")
        n_a = sum(1 for r in reqs if r.layout == "A")
        log.info(
            f"    [Requisiti/{config_name}] {len(reqs)} requisiti "
            f"(H:{n_h} V:{n_v} ancorati:{n_a}) — "
            f"derivati esclusi: {len(derived)}"
        )
        if cfg.REQ_DEBUG_LOG_EACH:
            for r in reqs:
                log.info(f"      • [{r.layout}] {r.req_id}")
    else:
        log.info(
            f"    [Requisiti/{config_name}] nessun requisito estratto "
            f"({len(lines)} righe analizzate, {len(derived)} ID solo derivati)"
        )
    return reqs




# ===========================================================================
# TABELLA ORIZZONTALE
# ===========================================================================

def _parse_horizontal(lines, config_name, page_hint, found, derived) -> None:
    """
    Individua le testate (Nr | Description | Type | Derived to |
    User Interface | SIL) e consuma TUTTE le righe dati successive.

    Il ciclo garantisce sempre un avanzamento dell'indice: se il consumo
    non progredisce, l'indice viene incrementato manualmente per evitare
    il loop infinito su una testata degenere.
    """
    i = 0
    n_tables = 0
    while i < len(lines):
        order = _match_header_row(lines[i])
        if not order:
            i += 1
            continue

        n_tables += 1
        log.debug(f"    [Tab.orizzontale #{n_tables}] testata riga {i}: {order}")
        before = len(found)
        new_i = _consume_horizontal_rows(
            lines, i + 1, order, config_name, page_hint, found, derived
        )
        log.debug(
            f"    [Tab.orizzontale #{n_tables}] righe {i+1}..{new_i} → "
            f"{len(found) - before} requisiti"
        )
        i = new_i if new_i > i else i + 1


def _match_header_row(line: str) -> list[str] | None:
    """
    Se la riga è una testata di tabella orizzontale, restituisce l'ordine
    dei campi, es. ['req_id', 'description', 'req_type', 'derived_to',
    'user_interface', 'sil']. Altrimenti None.
    """
    s = (line or "").strip()
    if not s or len(s) > 250:
        return None

    cells = [c.strip() for c in _SPLIT_RE.split(s) if c.strip()]
    if len(cells) < cfg.REQ_H_HEADER_MIN_MATCH:
        # Testata compattata su una riga sola senza separatori larghi
        cells = s.split()

    order, matched = [], 0
    j = 0
    while j < len(cells):
        # Prova prima le etichette di due parole ("derived to", "user interface")
        two = f"{cells[j]} {cells[j+1]}".lower() if j + 1 < len(cells) else ""
        one = cells[j].lower()

        field = _header_field(two) if two else None
        if field:
            j += 2
        else:
            field = _header_field(one)
            j += 1

        if field:
            order.append(field)
            matched += 1
        else:
            order.append(None)

    # Deve esserci la colonna Nr e almeno REQ_H_HEADER_MIN_MATCH campi noti
    if "req_id" not in order or matched < cfg.REQ_H_HEADER_MIN_MATCH:
        return None
    return order


def _header_field(label: str) -> str | None:
    """Nome interno del campo corrispondente all'intestazione, o None."""
    l = label.strip().strip(":|").lower()
    if not l:
        return None
    for variants, field in (
        (cfg.REQ_H_HEADER_ID,          "req_id"),
        (cfg.REQ_H_HEADER_DESCRIPTION, "description"),
        (cfg.REQ_H_HEADER_TYPE,        "req_type"),
        (cfg.REQ_H_HEADER_DERIVED,     "derived_to"),
        (cfg.REQ_H_HEADER_UI,          "user_interface"),
        (cfg.REQ_H_HEADER_SIL,         "sil"),
    ):
        if l in [v.lower() for v in variants]:
            return field
    return None


def _consume_horizontal_rows(
    lines, start, order, config_name, page_hint, found, derived
) -> int:
    """
    Legge TUTTE le righe dati della tabella. Ritorna l'indice della prima
    riga non consumata.

    REGOLE DI TERMINAZIONE (corrette rispetto alla versione precedente)
      - Le righe vuote NON chiudono più la tabella dopo 3 occorrenze:
        fitz le intercala normalmente. Si esce solo dopo
        REQ_H_MAX_BLANK_LINES righe vuote consecutive E solo se nessun
        requisito è aperto.
      - Un'etichetta verticale NON chiude più la tabella: una descrizione
        che inizia con "Description"/"ID" faceva uscire al primo requisito.
        Si esce solo su un vero marcatore di fine (nuovo indice di sezione,
        didascalia di tabella/figura).
      - La testata ripetuta a ogni cambio pagina viene saltata senza
        chiudere la tabella in corso.

    Ogni riga che inizia con un ID valido apre un nuovo requisito e chiude
    il precedente: è questo che permette di raccoglierne molti per funzione.
    """
    i = start
    current: Requirement | None = None
    tail = ""
    blanks = 0
    count = 0

    def flush():
        nonlocal current, tail, count
        if current is None:
            return
        _assign_horizontal_fields(current, tail, order, derived)
        if current.key() not in derived and current.key() not in found:
            found[current.key()] = current
            count += 1
            if cfg.REQ_DEBUG_LOG_EACH:
                log.debug(
                    f"      → [H] {current.req_id} | "
                    f"SIL={current.sil or '-'} | "
                    f"derived={current.derived_to or '-'}"
                )
        current, tail = None, ""

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        # ── Riga vuota: non chiude la tabella se un requisito è aperto ────
        if not s:
            blanks += 1
            if current is None and blanks >= cfg.REQ_H_MAX_BLANK_LINES:
                break
            i += 1
            continue
        blanks = 0

        # ── Fine reale della tabella ─────────────────────────────────────
        if _is_table_end(s):
            break

        # ── Testata ripetuta a cambio pagina: salta, non chiudere ────────
        if _match_header_row(raw):
            if cfg.REQ_H_SKIP_REPEATED_HEADER:
                i += 1
                continue
            break

        # ── Riga dati: inizia con l'ID della colonna "Nr" ────────────────
        first = s.split()[0].strip(".,;:()[]|") if s.split() else ""
        if is_req_id(first):
            flush()                       # chiude il requisito precedente
            current = Requirement(
                req_id=first, config_name=config_name,
                page_hint=page_hint, layout="H",
            )
            tail = s[len(first):]
        elif current is not None:
            tail += " " + s               # continuazione multi-riga

        i += 1

    flush()
    return i



_SIL_RE  = re.compile(r"\bSIL\s*[0-4]\b|\bbasic\s+integrity\b|\bnone\b", re.I)
_TYPE_RE = re.compile(
    r"\b(derived|original|allocated|inherited|parent|child|functional|safety)\b", re.I
)
_UI_RE   = re.compile(r"\b(yes|no|si|sì|n/?a|event|none)\b", re.I)


def _assign_horizontal_fields(req, tail: str, order: list, derived: set) -> None:
    """
    Distribuisce il testo che segue l'ID nei campi, seguendo l'ordine
    letto dalla testata.

    Strategia 1 — split per separatori di colonna (2+ spazi, tab, pipe):
        è il caso in cui fitz preserva la struttura della tabella.
    Strategia 2 — euristica su testo compattato: SIL e User Interface si
        riconoscono da pattern chiusi in coda, Derived to dai token-ID,
        il resto è Description.

    In entrambi i casi gli ID finiti in "Derived to" vengono aggiunti
    all'insieme di esclusione.
    """
    tail = (tail or "").strip(" \t|-")
    fields = [f for f in order if f and f != "req_id"]

    cells = [c.strip() for c in _SPLIT_RE.split(tail) if c.strip()]
    if len(cells) == len(fields):
        # ── Strategia 1: allineamento perfetto con la testata ─────────────
        for field, value in zip(fields, cells):
            setattr(req, field, _clean(value))
    else:
        # ── Strategia 2: euristica ────────────────────────────────────────
        rest = tail

        if "sil" in fields:
            m = _SIL_RE.search(rest)
            if m:
                req.sil = _clean(m.group())
                rest = rest[:m.start()] + " " + rest[m.end():]

        if "user_interface" in fields:
            m = None
            for m in _UI_RE.finditer(rest):
                pass            # tieni l'ultima occorrenza (coda riga)
            if m:
                req.user_interface = _clean(m.group())
                rest = rest[:m.start()] + " " + rest[m.end():]

        if "derived_to" in fields:
            others = [t for t in find_req_ids(rest)
                      if t.lower() != req.key()]
            if others:
                req.derived_to = ", ".join(others)
                for t in others:
                    rest = rest.replace(t, " ")

        if "req_type" in fields:
            m = _TYPE_RE.search(rest)
            if m:
                req.req_type = _clean(m.group())
                rest = rest[:m.start()] + " " + rest[m.end():]

        if "description" in fields:
            req.description = _clean(rest)[:900]

    # ── Esclusione definitiva degli ID derivati ──────────────────────────
    for t in find_req_ids(req.derived_to):
        if t.lower() != req.key():
            derived.add(t.lower())


# ===========================================================================
# TABELLA VERTICALE
# ===========================================================================

def _parse_vertical(lines, config_name, page_hint, found) -> None:
    """
    Riconosce blocchi etichetta/valore. Il valore sta sulla stessa riga
    dell'etichetta (separato da spazi, tab, ':' o '|') oppure sulle righe
    immediatamente successive (fino a REQ_V_LOOKAHEAD).

    Una nuova etichetta "ID" chiude il blocco precedente e ne apre uno nuovo.
    """
    current: dict[str, str] = {}

    def flush():
        rid = current.get("req_id", "").strip()
        if rid:
            rid = rid.split()[0].strip(".,;:()[]|") if rid.split() else ""
        if rid and is_req_id(rid) and rid.lower() not in found:
            found[rid.lower()] = Requirement(
                req_id=rid,
                description=_clean(current.get("description", ""))[:900],
                sil=_clean(current.get("sil", "")),
                config_name=config_name,
                page_hint=page_hint,
                layout="V",
            )
        current.clear()

    i = 0
    while i < len(lines):
        label, value = _vertical_label(lines[i])

        if label:
            if label == "req_id" and current.get("req_id"):
                flush()

            # Valore sulle righe seguenti
            k = 1
            while not value and k <= cfg.REQ_V_LOOKAHEAD and i + k < len(lines):
                nxt = lines[i + k].strip()
                if nxt and not _vertical_label(lines[i + k])[0]:
                    value = nxt
                    i += k
                    break
                k += 1

            current[label] = (current.get(label, "") + " " + value).strip()

        elif current.get("req_id") and current.get("description") is not None:
            # Continuazione di una description multi-riga
            s = lines[i].strip()
            if s and not is_req_id(s.split()[0] if s.split() else ""):
                if "description" in current:
                    current["description"] += " " + s

        i += 1

    flush()


def _vertical_label(line: str):
    """
    ('req_id' | 'description' | 'sil', valore) se la riga inizia con
    un'etichetta della tabella verticale. Altrimenti (None, '').
    """
    s = (line or "").strip()
    if not s or len(s) > 400:
        return None, ""

    candidates = []
    for variants, field in (
        (cfg.REQ_V_HEADER_ID,          "req_id"),
        (cfg.REQ_V_HEADER_DESCRIPTION, "description"),
        (cfg.REQ_V_HEADER_SAFETY,      "sil"),
    ):
        for v in variants:
            candidates.append((v.lower(), field))

    # Etichette più lunghe per prime ("safety level" prima di "sil")
    for label, field in sorted(candidates, key=lambda x: -len(x[0])):
        if s.lower().startswith(label):
            after = s[len(label):]
            # L'etichetta deve essere una parola intera
            if after and after[0].isalnum():
                continue
            return field, after.lstrip(" \t:|-").strip()
    return None, ""


# ===========================================================================
# ID fuori tabella (disattivato per default)
# ===========================================================================

def _parse_loose(text, config_name, page_hint, found, derived) -> None:
    """Attivo solo con cfg.REQ_ACCEPT_LOOSE_IDS = True. Sconsigliato."""
    for rid in find_req_ids(text):
        k = rid.lower()
        if k not in found and k not in derived:
            found[k] = Requirement(
                req_id=rid, config_name=config_name,
                page_hint=page_hint, layout="loose",
            )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_TABLE_END_RE = [re.compile(p, re.I) for p in cfg.REQ_TABLE_END_PATTERNS]


def _is_table_end(line: str) -> bool:
    """
    True solo su un marcatore di fine tabella REALE: nuovo indice di
    sezione numerato, didascalia di tabella/figura, appendice.
    Sostituisce i vecchi criteri (3 righe vuote, etichetta verticale)
    che troncavano la tabella dopo il primo requisito.
    """
    s = (line or "").strip()
    if not s:
        return False
    # Una riga che inizia con un ID è sempre una riga dati, mai una fine
    first = s.split()[0].strip(".,;:()[]|") if s.split() else ""
    if is_req_id(first):
        return False
    return any(rx.match(s) for rx in _TABLE_END_RE)


def _parse_id_anchored(lines, config_name, page_hint, found, derived) -> None:
    """
    Fallback: ogni riga che INIZIA con un ID valido genera un requisito.

    Richiedere l'ID in prima posizione equivale a richiedere che occupi
    la cella "Nr" della tabella, quindi non raccoglie né gli ID citati nel
    testo discorsivo né quelli della colonna "Derived to" (che non sono
    mai a inizio riga). Recupera i requisiti delle tabelle la cui testata
    fitz non riesce a ricostruire.
    """
    i = 0
    added = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue

        first = s.split()[0].strip(".,;:()[]|") if s.split() else ""
        if not is_req_id(first):
            i += 1
            continue

        k = first.lower()
        if k in found or k in derived:
            i += 1
            continue

        # Accumula la descrizione fino alla riga-ID successiva
        body = s[len(first):].strip(" \t|-")
        j = i + 1
        while j < len(lines):
            nxt = lines[j].strip()
            if not nxt:
                j += 1
                continue
            tok = nxt.split()[0].strip(".,;:()[]|") if nxt.split() else ""
            if is_req_id(tok) or _is_table_end(nxt):
                break
            body += " " + nxt
            j += 1

        req = Requirement(
            req_id=first, config_name=config_name,
            page_hint=page_hint, layout="A",
        )
        others = [t for t in find_req_ids(body) if t.lower() != k]
        if others:
            req.derived_to = ", ".join(others)
            for t in others:
                derived.add(t.lower())
                body = body.replace(t, " ")
        m = _SIL_RE.search(body)
        if m:
            req.sil = _clean(m.group())
            body = body[:m.start()] + " " + body[m.end():]
        req.description = _clean(body)[:900]

        found[k] = req
        added += 1
        i = j

    if added:
        log.debug(f"    [Fallback ancorato] {added} requisiti recuperati")











def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip(" \t|-")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())