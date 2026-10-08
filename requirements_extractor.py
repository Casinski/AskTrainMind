"""
requirements_extractor.py
-------------------------
Estrae i requisiti dalle tabelle dei PDF tecnici ETR1000.

STRATEGIA PRIMARIA — parsing di matrice (find_tables)
  Il testo lineare di get_text() non è utilizzabile: le colonne sono
  strette e il PDF manda a capo gli ID anche più volte
      "2F_04.01.Zefiro-\\nEurope.CONCEPT.\\n1013"
      "4S_09.03.05.-.TCMS\\nSoftware"
  I frammenti finiscono su righe separate e l'ID non è ricostruibile.
  Nella matrice di celle di find_tables() ogni ID sta in UNA sola cella.

STRATEGIA DI RISERVA — parsing testuale
  Usata per i DOCX e per i PDF in cui find_tables() non rileva tabelle.

DUE LAYOUT
  VERTICALE   colonna etichetta (ID / Description / Safety level) +
              colonna valore. Un blocco per requisito.
  ORIZZONTALE testata (Nr | Description | Type | Derived to |
              User Interface | SIL), poi UNA RIGA PER REQUISITO.

CLASSIFICAZIONE
  ACCETTATO  ID dalla colonna "Nr" o dal campo "ID", contenente "Zefiro"
  SCARTATO   ID dalla colonna "Derived to": è la PROVENIENZA del
             requisito, non un requisito a sé. Viene conservato nel campo
             derived_to ma non genera mai una voce nel foglio "Requisiti".
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

import config as cfg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modello dati — invariato: history_tracker usa fingerprint()
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
    layout: str = ""        # "H" orizzontale | "V" verticale | "T" testuale
    derived_ids: list = field(default_factory=list)

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
# Normalizzazione e riconoscimento degli ID
# ---------------------------------------------------------------------------

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_]*(?:[.\-]+[A-Za-z0-9_]+){2,}")

# Prefisso canonico: cifre + lettere ("2F", "4S")
_PREFIX_RE = re.compile(r"^(\d+[A-Za-z]+)")

# Forma attesa DOPO canon(): "2F_04.01..." oppure "2F.04..."
_PREFIX_SHAPE = re.compile(r"^\d+[A-Za-z]+[._]")


def squeeze(c) -> str:
    """Contenuto della cella con TUTTI gli spazi rimossi."""
    return re.sub(r"\s+", "", c or "")


def flat(c) -> str:
    """Contenuto di una cella di testo: a-capo → spazio."""
    return re.sub(r"\s+", " ", c or "").strip()


def canon(tok: str) -> str:
    """
    Forma canonica di un ID.

    PyMuPDF concatena gli span di testo spostando l'underscore:
        "2F04.01.Zefiro-_Europe.CONCEPT.775"
    Si rimuovono tutte le '_' e se ne reinserisce UNA dopo il prefisso
    cifre+lettere iniziale:
        → "2F_04.01.Zefiro-Europe.CONCEPT.775"
    """
    t = (tok or "").strip(".,;:()[]|")
    if not t:
        return ""
    t = t.replace("_", "")
    m = _PREFIX_RE.match(t)
    if m:
        t = m.group(1) + "_" + t[m.end():]
    return t


def is_id(tok: str) -> bool:
    """
    Forma di ID valida.

    ATTENZIONE: va invocata su una stringa GIÀ passata per canon().
    Il filtro sul prefisso richiede il separatore ("2F_04") che nella
    forma grezza ("2F04") non esiste: invertire l'ordine azzera
    l'estrazione.

    Due filtri contro la prosa, che privata degli spazi somiglia a un ID:
      - prefisso cifre+lettere seguito da '.' o '_'
      - nessun blocco alfabetico oltre REQ_MAX_ALPHA_RUN caratteri
    """
    t = (tok or "").strip(".,;:()[]|")
    if len(t) < 8 or len(t) > 150:
        return False
    if t.lower().startswith(tuple(cfg.REQ_PROSE_PREFIXES)):
        return False
    if not _PREFIX_SHAPE.match(t):
        return False
    if re.search(rf"[A-Za-z]{{{cfg.REQ_MAX_ALPHA_RUN},}}", t):
        return False
    return bool(ID_RE.fullmatch(t))


def cell_ids(c) -> list:
    """
    Tutti gli ID contenuti in una cella.
    Ordine obbligatorio: squeeze → canon → is_id.
    """
    s = squeeze(c)
    if not s:
        return []

    # Caso normale: la cella contiene SOLO l'ID, spezzato su più righe
    whole = canon(s)
    if is_id(whole):
        return [whole]

    out, seen = [], set()
    for m in ID_RE.finditer(s):
        t = canon(m.group())
        if is_id(t) and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def find_req_ids(text: str) -> list:
    """ID presenti in un testo libero. Usato dalla strategia di riserva."""
    out, seen = [], set()
    for m in ID_RE.finditer(text or ""):
        t = canon(m.group())
        if is_id(t) and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def classify(req_id: str, source: str) -> tuple:
    """
    (accettato, motivo). Due criteri, entrambi necessari.

      POSIZIONE — colonna "Nr" (orizzontale) o campo "ID" (verticale).
                  La colonna "Derived to" indica la PROVENIENZA.
      MARCATORE — l'ID deve contenere "Zefiro".
    """
    if source == "derived_to":
        return False, "colonna 'Derived to' → ID di provenienza"
    if source != "req_id":
        return False, f"campo '{source}' non è una colonna ID"
    if cfg.REQ_ID_MARKER not in (req_id or "").lower():
        return False, f"ID privo del marcatore '{cfg.REQ_ID_MARKER}'"
    if len(req_id.split(".")) < 3:
        return False, "ID incompleto"
    return True, "OK"


# ---------------------------------------------------------------------------
# Riconoscimento delle testate
# ---------------------------------------------------------------------------

H_HEADERS = {
    "nr": "req_id", "nr.": "req_id", "n.": "req_id", "number": "req_id",
    "description": "description", "descrizione": "description",
    "type": "req_type", "tipo": "req_type",
    "derived to": "derived_to", "derived from": "derived_to",
    "derivedto": "derived_to",
    "user interface": "user_interface", "userinterface": "user_interface",
    "ui": "user_interface",
    "sil": "sil", "safety integrity level": "sil",
}

V_LABELS = {
    "id": "req_id", "requirement id": "req_id", "req id": "req_id",
    "description": "description", "descrizione": "description",
    "safety level": "sil", "safetylevel": "sil",
    "safety integrity level": "sil", "sil": "sil",
    "derived to": "derived_to", "derived from": "derived_to",
    "type": "req_type", "tipo": "req_type",
    "user interface": "user_interface", "ui": "user_interface",
}

_INLINE_LABEL_RE = re.compile(
    r"^\s*(ID|Requirement\s*ID|Description|Descrizione|Safety\s*level|"
    r"Safety\s*Integrity\s*Level|SIL|Derived\s*to|Type|User\s*Interface)\b"
    r"\s*[:\-|]?\s*",
    re.I,
)


def header_map(row) -> dict:
    """
    {indice_colonna: campo} se la riga è una testata orizzontale.
    Richiede la colonna "Nr" e almeno REQ_H_HEADER_MIN_MATCH intestazioni.
    """
    if not row:
        return {}
    out = {}
    for i, c in enumerate(row):
        k = flat(c).lower().strip(":|")
        if k in H_HEADERS:
            out[i] = H_HEADERS[k]
        elif k.replace(" ", "") in H_HEADERS:
            out[i] = H_HEADERS[k.replace(" ", "")]
    ok = "req_id" in out.values() and len(out) >= cfg.REQ_H_HEADER_MIN_MATCH
    return out if ok else {}


def label_of(cell) -> str:
    """Campo corrispondente all'etichetta della cella, o '' se non lo è."""
    k = flat(cell).lower().strip(":|-")
    if k in V_LABELS:
        return V_LABELS[k]
    if k.replace(" ", "") in V_LABELS:
        return V_LABELS[k.replace(" ", "")]
    return ""


def split_inline(cell):
    """
    ('campo', 'valore') se la cella contiene etichetta E valore insieme,
    es. "ID 2F_04.01.Zefiro-Europe.TRS.619". Altrimenti ('', '').
    """
    s = flat(cell)
    m = _INLINE_LABEL_RE.match(s)
    if not m:
        return "", ""
    key = re.sub(r"\s+", " ", m.group(1)).lower()
    field_name = V_LABELS.get(key) or V_LABELS.get(key.replace(" ", ""))
    value = s[m.end():].strip()
    if not field_name or not value:
        return "", ""
    return field_name, value


def find_label_col(data):
    """
    Indice della colonna con le etichette verticali, oppure None.
    La colonna etichetta non è sempre la 0: find_tables può restituire
    una colonna vuota iniziale.

    Due vincoli contro i falsi positivi:
      - le righe di testata orizzontale sono ESCLUSE dal conteggio;
      - la colonna deve contenere l'etichetta 'ID'.
    """
    n_col = max((len(r) for r in data), default=0)
    rows = [r for r in data if not header_map(r)]
    if not rows:
        return None

    best, best_hits = None, 0
    for ci in range(min(3, n_col)):
        hits, has_id = 0, False
        for row in rows:
            if ci >= len(row):
                continue
            f = label_of(row[ci])
            if f:
                hits += 1
                if f == "req_id":
                    has_id = True
        if has_id and hits > best_hits:
            best, best_hits = ci, hits
    return best if best_hits >= 2 else None


def has_inline_labels(data) -> bool:
    """True se le celle contengono etichetta e valore insieme."""
    hits, has_id = 0, False
    for row in data:
        if header_map(row):
            continue
        for c in row:
            f, _ = split_inline(c)
            if f:
                hits += 1
                if f == "req_id":
                    has_id = True
                break
    return has_id and hits >= 2


# ---------------------------------------------------------------------------
# Segmentazione della matrice
# ---------------------------------------------------------------------------

def segment(data):
    """
    Spezza la matrice sulle righe di testata orizzontale.

    find_tables() può restituire in UNA matrice sia il blocco verticale
    sia la tabella orizzontale che lo segue: senza segmentazione uno dei
    due verrebbe perso.

    Ritorna una lista di (tipo, righe) con tipo 'H' oppure '?'.
    """
    heads = [i for i, row in enumerate(data) if header_map(row)]
    if not heads:
        return [("?", data)]

    segs = []
    if heads[0] > 0:
        segs.append(("?", data[:heads[0]]))
    for k, h in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(data)
        segs.append(("H", data[h:end]))
    return segs


# ---------------------------------------------------------------------------
# Parsing dei due layout
# ---------------------------------------------------------------------------

def _parse_horizontal(rows, config_name, page, hmap, hrow):
    """Tabella orizzontale: una riga per requisito, tutte le righe."""
    reqs = []
    cols = {f: i for i, f in hmap.items()}
    col_id = cols["req_id"]

    for ri in range(hrow + 1, len(rows)):
        row = rows[ri]
        if col_id >= len(row):
            continue
        ids = cell_ids(row[col_id])
        if not ids:
            continue                      # riga di continuazione

        rid = ids[0]
        r = Requirement(
            req_id=rid, config_name=config_name,
            page_hint=page, layout="H",
        )
        for field_name, ci in cols.items():
            if field_name == "req_id" or ci >= len(row):
                continue
            setattr(r, field_name, flat(row[ci])[:900])

        ci = cols.get("derived_to")
        if ci is not None and ci < len(row):
            r.derived_ids = cell_ids(row[ci])

        if classify(rid, "req_id")[0]:
            reqs.append(r)
            if cfg.REQ_DEBUG_LOG_EACH:
                log.info(f"      [H] {rid}  SIL={r.sil!r}")
    return reqs


def _parse_vertical(rows, config_name, page, label_col, inline):
    """
    Tabella verticale. Supporta PIÙ requisiti consecutivi: una nuova
    etichetta 'ID' chiude il blocco precedente e ne apre uno nuovo.
    """
    reqs = []
    cur, cur_derived = {}, []

    def flush():
        rid = cur.get("req_id", "")
        if not rid:
            cur.clear()
            cur_derived.clear()
            return
        if classify(rid, "req_id")[0]:
            r = Requirement(
                req_id=rid,
                description=cur.get("description", "")[:900],
                req_type=cur.get("req_type", ""),
                derived_to=cur.get("derived_to", ""),
                user_interface=cur.get("user_interface", ""),
                sil=cur.get("sil", ""),
                config_name=config_name, page_hint=page, layout="V",
                derived_ids=list(cur_derived),
            )
            reqs.append(r)
            if cfg.REQ_DEBUG_LOG_EACH:
                log.info(f"      [V] {rid}  SIL={r.sil!r}")
        cur.clear()
        cur_derived.clear()

    def put(field_name, raw_value):
        if field_name == "req_id":
            ids = cell_ids(raw_value)
            if not ids:
                return
            if cur.get("req_id"):
                flush()
            cur["req_id"] = ids[0]
            for extra in ids[1:]:
                if classify(extra, "req_id")[0]:
                    reqs.append(Requirement(
                        req_id=extra, config_name=config_name,
                        page_hint=page, layout="V",
                    ))
        elif field_name == "derived_to":
            cur["derived_to"] = flat(raw_value)
            cur_derived.extend(cell_ids(raw_value))
        else:
            cur[field_name] = (cur.get(field_name, "") + " "
                               + flat(raw_value)).strip()

    for row in rows:
        if not row or header_map(row):
            continue

        # Caso A: etichetta in una colonna, valore nelle successive
        if label_col is not None and label_col < len(row):
            field_name = label_of(row[label_col])
            if field_name:
                value = ""
                for ci in range(label_col + 1, len(row)):
                    if flat(row[ci]):
                        value = row[ci]
                        break
                put(field_name, value)
                continue

        # Caso B: etichetta e valore nella stessa cella
        if inline:
            for c in row:
                field_name, value = split_inline(c)
                if field_name:
                    put(field_name, value)
                    break

    flush()
    return reqs


def parse_matrix(data, config_name, page, carry=None):
    """
    Interpreta UNA tabella, segmentandola se contiene più blocchi.

    ORDINE DI VALUTAZIONE — punto critico
      Le intestazioni della tabella orizzontale (Description, Type,
      Derived to, User Interface, SIL) compaiono ANCHE tra le etichette
      verticali. Se si valutasse prima il layout verticale, una tabella
      orizzontale verrebbe scambiata per verticale e tutti i suoi
      requisiti andrebbero persi. La testata orizzontale ha quindi
      SEMPRE la precedenza: è un pattern molto più specifico.

    Ritorna (requisiti, testata_da_propagare).
    """
    reqs = []
    if not data:
        return reqs, None

    new_carry = None

    for kind, rows in segment(data):
        if not rows:
            continue

        # Segmento con testata orizzontale propria
        if kind == "H":
            hmap = header_map(rows[0])
            if hmap:
                reqs.extend(_parse_horizontal(rows, config_name, page, hmap, 0))
                new_carry = hmap
            continue

        # Segmento senza testata: verticale o continuazione
        label_col = find_label_col(rows)
        inline = has_inline_labels(rows)

        if label_col is not None or inline:
            reqs.extend(_parse_vertical(
                rows, config_name, page, label_col, inline
            ))
            continue

        # Continuazione di tabella orizzontale dalla pagina precedente.
        # Non si applica mai alle tabelle verticali.
        if carry:
            col_id = [i for i, f in carry.items() if f == "req_id"][0]
            n_col = max(len(r) for r in rows)
            if n_col > col_id and any(
                col_id < len(r) and cell_ids(r[col_id]) for r in rows
            ):
                reqs.extend(_parse_horizontal(
                    [[]] + list(rows), config_name, page, carry, 0
                ))

    return reqs, new_carry


def parse_page(page, page_no, config_name, carry=None):
    """Tutte le tabelle di una pagina. → (reqs, scartati, n_tab, carry)."""
    reqs, derived, n_tab, seen = [], set(), 0, set()

    try:
        tables = page.find_tables().tables
    except Exception as exc:
        log.debug(f"    find_tables pag.{page_no}: {exc}")
        return reqs, derived, 0, carry

    for t in tables:
        try:
            data = t.extract()
        except Exception:
            continue
        if not data:
            continue
        n_tab += 1
        found, new_carry = parse_matrix(data, config_name, page_no, carry)
        if new_carry:
            carry = new_carry
        for r in found:
            derived.update(r.derived_ids)
            if r.key() not in seen:
                seen.add(r.key())
                reqs.append(r)

    # Un ID che compare anche come 'Derived to' non è un requisito
    low = {d.lower() for d in derived}
    reqs = [r for r in reqs if r.key() not in low]
    return reqs, derived, n_tab, carry


# ---------------------------------------------------------------------------
# API pubblica — strategia primaria
# ---------------------------------------------------------------------------

def extract_from_tables(
    doc_path,
    page_start: int,
    page_end: int,
    config_name: str,
) -> list:
    """
    Estrae i requisiti dalle tabelle delle pagine indicate.

    Args:
        doc_path    : percorso del PDF
        page_start  : prima pagina 1-based
        page_end    : ultima pagina 1-based (inclusa)
        config_name : configurazione di appartenenza

    Returns:
        Lista di Requirement accettati, deduplicati, con gli ID della
        colonna "Derived to" esclusi. Lista vuota se il formato non è PDF,
        se find_tables() non rileva tabelle o in caso di errore.
    """
    if not getattr(cfg, "REQ_USE_MATRIX_PARSER", True):
        return []
    if not doc_path or str(doc_path).lower().rsplit(".", 1)[-1] != "pdf":
        return []

    try:
        import fitz
    except ImportError:
        log.error("  PyMuPDF non installato: pip install -U pymupdf")
        return []

    try:
        pdf = fitz.open(str(doc_path))
    except Exception as exc:
        log.warning(f"  [Requisiti] PDF non apribile '{doc_path}': {exc}")
        return []

    all_reqs, all_derived, tot_tab = [], set(), 0
    carry = None

    try:
        first = max(1, page_start)
        last = min(max(page_end, page_start), pdf.page_count)
        for n in range(first, last + 1):
            reqs, derived, n_tab, carry = parse_page(
                pdf[n - 1], n, config_name, carry
            )
            tot_tab += n_tab
            all_derived |= derived
            all_reqs.extend(reqs)
    except Exception as exc:
        log.warning(f"  [Requisiti] Errore estrazione tabelle: {exc}")
    finally:
        pdf.close()

    # Deduplica globale ed esclusione definitiva dei derivati
    low = {d.lower() for d in all_derived}
    seen, uniq = set(), []
    for r in all_reqs:
        if r.key() in low or r.key() in seen:
            continue
        seen.add(r.key())
        uniq.append(r)

    n_h = sum(1 for r in uniq if r.layout == "H")
    n_v = sum(1 for r in uniq if r.layout == "V")
    if uniq:
        log.info(
            f"    [Requisiti/{config_name}] {len(uniq)} requisiti da "
            f"{tot_tab} tabelle (H:{n_h} V:{n_v}) — "
            f"{len(all_derived)} ID esclusi come 'Derived to'"
        )
    else:
        log.debug(
            f"    [Requisiti/{config_name}] nessun requisito da "
            f"{tot_tab} tabelle (pag.{page_start}-{page_end})"
        )
    return uniq


# ---------------------------------------------------------------------------
# API pubblica — strategia di riserva (testo lineare)
# ---------------------------------------------------------------------------

def extract(text: str, config_name: str, page_hint: int = 0) -> list:
    """
    Estrazione dal testo lineare. Firma invariata per compatibilità.

    Usata solo quando il parsing di matrice non produce risultati: DOCX,
    oppure PDF le cui tabelle find_tables() non riesce a rilevare.
    Accuratezza inferiore: gli ID spezzati a metà colonna non sono
    ricostruibili da questo livello.
    """
    if not text or not text.strip():
        return []

    lines = [ln.rstrip() for ln in text.splitlines()]
    found, derived = {}, set()

    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            continue

        # Etichetta verticale "ID <valore>"
        field_name, value = split_inline(s)
        if field_name == "req_id":
            for rid in find_req_ids(value):
                if rid.lower() not in found and classify(rid, "req_id")[0]:
                    found[rid.lower()] = Requirement(
                        req_id=rid, config_name=config_name,
                        page_hint=page_hint, layout="T",
                    )
            continue
        if field_name == "derived_to":
            derived.update(t.lower() for t in find_req_ids(value))
            continue

        # Riga che INIZIA con un ID: posizione di colonna "Nr"
        tok = canon(s.split()[0]) if s.split() else ""
        if is_id(tok) and tok.lower() not in found:
            if classify(tok, "req_id")[0]:
                body = s[len(s.split()[0]):].strip()
                r = Requirement(
                    req_id=tok, config_name=config_name,
                    page_hint=page_hint, layout="T",
                )
                others = [t for t in find_req_ids(body)
                          if t.lower() != tok.lower()]
                if others:
                    r.derived_to = ", ".join(others)
                    derived.update(t.lower() for t in others)
                    for t in others:
                        body = body.replace(t, " ")
                r.description = _clean(body)[:900]
                found[tok.lower()] = r

    for d in derived:
        found.pop(d, None)

    reqs = list(found.values())
    if reqs:
        log.info(
            f"    [Requisiti/{config_name}] {len(reqs)} requisiti dal testo "
            f"lineare (strategia di riserva)"
        )
    return reqs


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip(" \t|-")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())