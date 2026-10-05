"""
requirements_extractor.py
-------------------------
Estrae gli ID dei requisiti (e i relativi campi) dal testo di una sezione
PDF già isolata da document_handler.extract_page_text().

Gli ID non hanno una struttura rigida. Euristica principale:
  token separato da punti che contiene la stringa "Zefiro"
  es. 2F_05.01.Zefiro-Europe.TRS.184
      2F_05.01.Zefiro-Europe.CONCEPT.185
Fallback: pattern generici in cfg.REQ_ID_FALLBACK_PATTERNS.

DUE LAYOUT DI TABELLA SUPPORTATI

  A) ORIZZONTALE (una riga per requisito)
     ID | Description | Type | Derived to | User Interface | SIL

  B) VERTICALE (una tabella per requisito, etichette in colonna 1)
     ID            | 2F_05.01.Zefiro-Europe.TRS.184
     Description   | ...
     Safety Level  | SIL2
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field

import config as cfg

log = logging.getLogger(__name__)


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
    layout: str = ""        # "H" orizzontale | "V" verticale | "inline"

    def key(self) -> str:
        return self.req_id.strip().lower()

    def fingerprint(self) -> str:
        """Impronta usata per rilevare modifiche storiche del requisito."""
        import hashlib
        base = "|".join([
            self.req_id, _norm(self.description), self.req_type,
            self.derived_to, self.user_interface, self.sil,
        ])
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Riconoscimento ID
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]*(?:\.[A-Za-z0-9_\-]+)+")

_LABELS = {
    "id":              "req_id",
    "requirement id":  "req_id",
    "req id":          "req_id",
    "description":     "description",
    "descrizione":     "description",
    "type":            "req_type",
    "tipo":            "req_type",
    "derived to":      "derived_to",
    "derived from":    "derived_to",
    "user interface":  "user_interface",
    "sil":             "sil",
    "safety level":    "sil",
    "safety integrity level": "sil",
}


def is_req_id(token: str) -> bool:
    """True se il token sembra un ID requisito."""
    t = token.strip().strip(".,;:()[]")
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
    """Tutti gli ID requisito presenti nel testo, in ordine di apparizione."""
    seen, out = set(), []
    for m in _TOKEN_RE.finditer(text or ""):
        tok = m.group().strip().strip(".,;:()[]")
        if is_req_id(tok) and tok.lower() not in seen:
            seen.add(tok.lower())
            out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Estrazione principale
# ---------------------------------------------------------------------------

def extract(
    text: str,
    config_name: str,
    page_hint: int = 0,
) -> list[Requirement]:
    """
    Estrae tutti i requisiti dalla sezione di testo fornita.
    Strategia: prima prova il layout verticale, poi quello orizzontale,
    infine raccoglie gli ID rimasti come 'inline'.
    """
    if not text or not text.strip():
        return []

    lines = [ln.rstrip() for ln in text.splitlines()]
    found: dict[str, Requirement] = {}

    _extract_vertical(lines, config_name, page_hint, found)
    _extract_horizontal(lines, config_name, page_hint, found)
    _extract_inline(text, config_name, page_hint, found)

    reqs = list(found.values())
    if reqs:
        log.info(
            f"    [Requisiti/{config_name}] {len(reqs)} ID estratti "
            f"(es. {[r.req_id for r in reqs[:3]]})"
        )
    return reqs


# ── Layout VERTICALE ───────────────────────────────────────────────────────

def _extract_vertical(lines, config_name, page_hint, found) -> None:
    """
    Riconosce blocchi in cui l'etichetta è a inizio riga e il valore segue
    sulla stessa riga (separato da spazi/tab/':') o sulla riga successiva.
    """
    current: dict[str, str] = {}

    def flush():
        rid = current.get("req_id", "").strip()
        if rid and is_req_id(rid) and rid.lower() not in found:
            found[rid.lower()] = Requirement(
                req_id=rid,
                description=current.get("description", "").strip(),
                req_type=current.get("req_type", "").strip(),
                derived_to=current.get("derived_to", "").strip(),
                user_interface=current.get("user_interface", "").strip(),
                sil=current.get("sil", "").strip(),
                config_name=config_name,
                page_hint=page_hint,
                layout="V",
            )
        current.clear()

    i = 0
    while i < len(lines):
        label, value = _split_label(lines[i])
        if label:
            field_name = _LABELS[label]
            if field_name == "req_id" and current.get("req_id"):
                flush()
            if not value and i + 1 < len(lines):
                nxt_label, _ = _split_label(lines[i + 1])
                if not nxt_label:
                    value = lines[i + 1].strip()
                    i += 1
            current[field_name] = (current.get(field_name, "") + " " + value).strip()
        i += 1
    flush()


def _split_label(line: str):
    """('description', 'testo') se la riga inizia con un'etichetta nota."""
    s = line.strip()
    if not s or len(s) > 300:
        return None, ""
    for lbl in sorted(_LABELS, key=len, reverse=True):
        if s.lower().startswith(lbl):
            rest = s[len(lbl):].lstrip(" \t:|-")
            if len(s) == len(lbl) or not s[len(lbl)].isalnum():
                return lbl, rest.strip()
    return None, ""


# ── Layout ORIZZONTALE ─────────────────────────────────────────────────────

_SIL_RE   = re.compile(r"\bSIL\s*[0-4]\b|\bbasic\s+integrity\b", re.I)
_TYPE_RE  = re.compile(r"\b(derived|original|allocated|inherited|parent|child)\b", re.I)
_UI_RE    = re.compile(r"\b(yes|no|si|sì|n/?a|event)\b", re.I)


def _extract_horizontal(lines, config_name, page_hint, found) -> None:
    """
    Nella tabella orizzontale fitz emette tipicamente una riga di testo
    che inizia con l'ID, seguita dalla description e dagli altri campi.
    La description può proseguire sulle righe successive finché non
    compare un nuovo ID.
    """
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue

        first = s.split()[0].strip(".,;:()[]") if s.split() else ""
        if not is_req_id(first):
            i += 1
            continue
        if first.lower() in found:
            i += 1
            continue

        body = s[len(first):].strip(" \t|-")
        j = i + 1
        while j < len(lines):
            nxt = lines[j].strip()
            if not nxt:
                j += 1
                continue
            tok = nxt.split()[0].strip(".,;:()[]") if nxt.split() else ""
            if is_req_id(tok) or _split_label(nxt)[0] == "id":
                break
            body += " " + nxt
            j += 1

        found[first.lower()] = Requirement(
            req_id=first,
            description=_clean_desc(body),
            req_type=_first(_TYPE_RE, body),
            derived_to=_derived(body, first),
            user_interface=_first(_UI_RE, body[-80:]),
            sil=_first(_SIL_RE, body),
            config_name=config_name,
            page_hint=page_hint,
            layout="H",
        )
        i = j


def _extract_inline(text, config_name, page_hint, found) -> None:
    """ID citati nel corpo del testo ma non catturati dalle tabelle."""
    for rid in find_req_ids(text):
        if rid.lower() not in found:
            found[rid.lower()] = Requirement(
                req_id=rid, config_name=config_name,
                page_hint=page_hint, layout="inline",
            )


# ── Helper ─────────────────────────────────────────────────────────────────

def _first(rx, s: str) -> str:
    m = rx.search(s or "")
    return m.group().strip() if m else ""


def _derived(body: str, own_id: str) -> str:
    """Altri ID requisito citati nella riga → candidati 'Derived to'."""
    others = [r for r in find_req_ids(body) if r.lower() != own_id.lower()]
    return ", ".join(others[:3])


def _clean_desc(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:900]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())