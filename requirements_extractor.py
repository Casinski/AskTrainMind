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
    "applicability details": "req_type", "applicabilitydetails": "req_type",
    "applicability detail": "req_type", "applicability": "req_type",
    "derived to": "derived_to", "derived from": "derived_to",
    "derivedto": "derived_to",
    "user interface": "user_interface", "userinterface": "user_interface",
    "ui": "user_interface",
    "sil": "sil", "safety integrity level": "sil",
}

V_LABELS = {
    "id": "req_id", "requirement id": "req_id", "req id": "req_id",
    "identifier": "req_id",
    "description": "description", "descrizione": "description",
    "safety level": "sil", "safetylevel": "sil",
    "safety integrity level": "sil", "sil": "sil",
    "derived to": "derived_to", "derived from": "derived_to",
    "type": "req_type", "tipo": "req_type",
    "applicability details": "req_type", "applicabilitydetails": "req_type",
    "applicability": "req_type",
    "user interface": "user_interface", "ui": "user_interface",
}

_INLINE_LABEL_RE = re.compile(
    r"^\s*(ID|Requirement\s*ID|Description|Descrizione|Safety\s*level|"
    r"Safety\s*Integrity\s*Level|SIL|Derived\s*to|Type|"
    r"Applicability\s*Details?|User\s*Interface)\b"
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
        field = H_HEADERS.get(k) or H_HEADERS.get(k.replace(" ", ""))
        if not field:
            continue
        # Intestazione ripetuta su due colonne ("SIL" | "SIL"): vale la
        # PRIMA. Tenere l'ultima assegnava il campo alla colonna vuota.
        if field in out.values():
            continue
        out[i] = field
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

    Si scandiscono TUTTE le colonne (non le prime 3): find_tables puo'
    restituire piu' colonne vuote iniziali su tabelle con bordi irregolari.
    La soglia e' 1 sola etichetta purche' sia 'ID': un blocco verticale
    minimo (ID / Description / Safety level) in cui Description e Safety
    level finiscono su righe di continuazione produce un solo hit, e la
    vecchia soglia di 2 lo faceva scartare in blocco.
    """
    n_col = max((len(r) for r in data), default=0)
    rows = [r for r in data if not header_map(r)]
    if not rows:
        return None

    best, best_hits = None, 0
    for ci in range(n_col):
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

    if best is None or best_hits < 1:
        return None

    # Un blocco verticale senza alcun ID valido e' un residuo di cornice
    # (es. la tabella vuota 'ID | Description | Safety level' a pag.7):
    # trattarlo come verticale genera requisiti fantasma e consuma il carry.
    if not any(cell_ids(c) for row in rows for c in row):
        log.debug("      blocco verticale privo di ID reali — ignorato")
        return None

    if cfg.REQ_DEBUG_LOG_EACH:
        log.debug(f"      colonna etichette verticali = {best} "
                  f"({best_hits} etichette)")
    return best


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
# Continuazione di tabella orizzontale tra pagine
# ---------------------------------------------------------------------------
#
# Una tabella di requisiti prosegue quasi sempre sulla pagina successiva
# SENZA ripetere la testata (es. CONCEPT.735 a pag.8, CONCEPT.1099 e
# CONCEPT.1096 a pag.9 dello stesso documento). PyMuPDF, sulla pagina di
# continuazione, non genera le colonne vuote di separazione: la matrice ha
# 6 colonne invece di 8. Usare la testata ereditata con gli indici originali
# fa perdere i campi di coda (User Interface, SIL).

FIELD_ORDER = ["req_id", "description", "req_type", "derived_to",
               "user_interface", "sil"]


def remap_header(hmap: dict, n_col: int) -> dict:
    """
    Riproietta una testata ereditata su una matrice con un numero di
    colonne diverso.

    Sulla pagina di continuazione PyMuPDF non genera le colonne vuote di
    separazione: la matrice ha 6 colonne invece di 8. I campi iniziali si
    ancorano a SINISTRA, 'user_interface' e 'sil' a DESTRA, perche' nelle
    tabelle ETR1000 sono sempre le ultime colonne.
    """
    fields = [f for f in FIELD_ORDER if f in hmap.values()]
    if not fields:
        return {}
    if max(hmap.keys()) < n_col:          # la testata ci sta gia': invariata
        return dict(hmap)

    tail = [f for f in ("sil", "user_interface") if f in fields]
    head = [f for f in fields if f not in tail]

    out = {}
    for i, f in enumerate(head):
        if i < n_col:
            out[i] = f
    for j, f in enumerate(tail):          # da destra: 'sil' e' l'ultima
        ci = n_col - 1 - j
        if ci >= len(head):
            out[ci] = f
    return out


def realign_header(hmap: dict, rows: list, hrow: int) -> dict:
    """
    Riallinea la testata sulle colonne che contengono davvero i dati.

    PyMuPDF genera colonne di separazione vuote e spezza le intestazioni
    su due righe ("Applicability" / "Details", "User" / "Interface"):
    l'etichetta finisce in una colonna, il valore in quella accanto.
    In piu' un'intestazione puo' comparire DUE volte ("SIL" in col 9 e 10)
    e l'ultima occorrenza, quella vuota, sovrascriveva la buona.

    Per ogni campo si verifica se la colonna mappata contiene almeno un
    valore nelle righe dati; in caso contrario si cerca la colonna
    adiacente (prima a sinistra, poi a destra) non ancora assegnata.
    """
    data_rows = [r for r in rows[hrow + 1:] if r]
    if not data_rows:
        return hmap

    def has_data(ci: int) -> bool:
        return any(ci < len(r) and flat(r[ci]) for r in data_rows)

    # Colonne gia' valide: si tengono ferme e non vanno riusate
    out, taken = {}, set()
    for ci in sorted(hmap):
        if has_data(ci) and ci not in taken:
            out[ci] = hmap[ci]
            taken.add(ci)

    n_col = max((len(r) for r in data_rows), default=0)

    for ci in sorted(hmap):
        field = hmap[ci]
        if ci in out:
            continue
        if field in out.values():          # duplicato gia' risolto (SIL)
            continue
        for cand in (ci - 1, ci + 1, ci - 2, ci + 2):
            if 0 <= cand < n_col and cand not in taken and has_data(cand):
                out[cand] = field
                taken.add(cand)
                log.debug(
                    f"      testata riallineata: '{field}' "
                    f"col {ci} → col {cand}"
                )
                break

    return out or hmap



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

        # Seconda riga di una testata spezzata ("Applicability"/"Details",
        # "User"/"Interface"): contiene solo frammenti di intestazione,
        # mai un ID. Accodarla al requisito precedente ne inquinava i campi.
        if ri == hrow + 1 and not any(cell_ids(c) for c in row):
            if any(label_of(c) or flat(c).lower() in
                   ("details", "interface", "level") for c in row):
                log.debug("      seconda riga di testata saltata")
                continue

        if col_id >= len(row):
            continue

        ids = cell_ids(row[col_id])
        if not ids:
            # Riga di continuazione: la cella "Nr" e' vuota perche' il
            # requisito precedente prosegue. Il testo va accodato, non perso.
            if reqs:
                prev = reqs[-1]
                for field_name, ci in cols.items():
                    if field_name == "req_id" or ci >= len(row):
                        continue
                    extra = flat(row[ci])
                    if not extra:
                        continue
                    cur_val = getattr(prev, field_name, "") or ""
                    setattr(prev, field_name,
                            (cur_val + " " + extra).strip()[:900])
                ci = cols.get("derived_to")
                if ci is not None and ci < len(row):
                    prev.derived_ids.extend(
                        d for d in cell_ids(row[ci])
                        if d not in prev.derived_ids
                    )
            continue
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
                description=_clean(cur.get("description", ""))[:900],
                req_type=_clean(cur.get("req_type", "")),
                derived_to=_clean(cur.get("derived_to", "")),
                user_interface=_clean(cur.get("user_interface", "")),
                sil=_clean(cur.get("sil", "")),
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
            v = flat(raw_value)
            if not v:
                # Etichetta senza valore: si registra comunque il campo
                # come "aperto" senza sporcare il contenuto.
                cur.setdefault(field_name, "")
                return
            # PyMuPDF antepone un underscore isolato al testo delle celle
            # verticali ("_ The architecture of..."): va rimosso, altrimenti
            # inquina la Description e falsa il confronto fra configurazioni.
            v = re.sub(r"^[_\s\u2217*]+", "", v).strip()
            cur[field_name] = (cur.get(field_name, "") + " " + v).strip()

        # Campo aperto: le righe prive di etichetta sono la continuazione
    # del suo valore (Description lunghe spezzate su piu' righe).
    pending: list[str] = [""]

    def _row_label(row) -> tuple[str, int]:
        """
        (campo, indice_colonna) dell'etichetta presente nella riga.

        L'etichetta NON sta sempre nella stessa colonna: find_tables
        restituisce matrici irregolari e la stessa tabella puo' avere
            riga 0  ['', 'ID', '2F_04...']            → etichetta in col 1
            riga 1  ['Description', None, 'The ...']  → etichetta in col 0
            riga 2  ['', 'Safety level', 'N/A']       → etichetta in col 1
        Cercare solo in 'label_col' faceva perdere la Description: e' la
        causa dei campi verticali vuoti.

        Si restituisce l'etichetta PIU' A DESTRA fra quelle trovate: il
        valore sta sempre dopo di essa, e quando l'etichetta e' ripetuta
        ('Description' in col 0 e col 1) il valore e' oltre la seconda.
        """
        best_field, best_ci = "", -1
        limit = min(len(row), max((label_col or 0) + 1, 3) + 1)
        for ci in range(limit):
            f = label_of(row[ci])
            if f:
                best_field, best_ci = f, ci
        return best_field, best_ci

    def _row_value(row, from_col: int) -> str:
        """
        Concatena TUTTE le celle a destra dell'etichetta, saltando quelle
        che ripetono l'etichetta stessa.
        """
        vals = []
        for ci in range(from_col, len(row)):
            v = flat(row[ci])
            if not v or label_of(row[ci]):
                continue
            vals.append(v)
        return " ".join(vals).strip()

    for row in rows:
        if not row or header_map(row):
            continue

        field_name, ci_lab = _row_label(row)

        # Caso A: etichetta trovata in una qualsiasi colonna della riga
        if field_name:
            value = _row_value(row, ci_lab + 1)
            # Etichetta senza valore: il valore e' sulla riga successiva.
            # Si apre comunque il campo, cosi' la riga dopo lo alimenta.
            put(field_name, value)
            pending[0] = field_name
            continue

        # Caso B: etichetta e valore nella stessa cella
        if inline:
            hit = False
            for c in row:
                f2, v2 = split_inline(c)
                if f2:
                    put(f2, v2)
                    pending[0] = f2
                    hit = True
                    break
            if hit:
                continue

        # Caso C: riga priva di etichetta → continuazione del campo aperto
        if pending[0] and pending[0] != "req_id":
            extra = _row_value(row, 0)
            if extra:
                put(pending[0], extra)

    flush()

    if cfg.REQ_DEBUG_LOG_EACH:
        for r in reqs:
            if not r.description:
                log.warning(
                    f"      [V] {r.req_id}: Description VUOTA — "
                    f"label_col={label_col} inline={inline} "
                    f"righe={len(rows)}; esegui il dump con "
                    f"REQ_DEBUG_DUMP_VERTICAL=True"
                )
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
                hmap = realign_header(hmap, rows, 0)
                reqs.extend(_parse_horizontal(rows, config_name, page, hmap, 0))
                new_carry = hmap
                carry = hmap
            continue

        # Segmento senza testata: verticale o continuazione
        label_col = find_label_col(rows)
        inline = has_inline_labels(rows)

        if label_col is not None or inline:
            reqs.extend(_parse_vertical(
                rows, config_name, page, label_col, inline
            ))
            continue

        # Cornice verticale RICONOSCIUTA ma VUOTA: PyMuPDF ha trovato i
        # bordi della tabella senza estrarne le celle (tipico dei blocchi
        # ID/Description/Safety level senza linee interne). Il requisito
        # esiste nel PDF ma non entra nella matrice: va recuperato dal
        # testo contenuto nel riquadro. E' il caso di TRS.772 a pag.7 di
        # 3EGH489028-2358.
        if _is_empty_vertical_frame(rows):
            log.debug(f"    pag.{page}: cornice verticale vuota — "
                      f"recupero dal testo del riquadro")
            continue

        # Continuazione di tabella orizzontale dalla pagina precedente.
        # Non si applica mai alle tabelle verticali.

        if carry:
            n_col = max((len(r) for r in rows), default=0)
            cmap = remap_header(carry, n_col)
            col_id = next((i for i, f in cmap.items() if f == "req_id"), None)
            if col_id is not None and any(
                col_id < len(r) and cell_ids(r[col_id]) for r in rows
            ):
                log.debug(
                    f"    pag.{page}: testata EREDITATA su {n_col} colonne "
                    f"→ {sorted(cmap.items())}"
                )
                reqs.extend(_parse_horizontal(
                    [[]] + list(rows), config_name, page, cmap, 0
                ))
                # La testata resta valida oltre: una tabella puo' proseguire
                # su tre o piu' pagine consecutive.
                new_carry = carry

    return reqs, new_carry


def parse_page(page, page_no, config_name, carry=None,
               y_min=None, y_max=None):
    """
    Tutte le tabelle di una pagina che rientrano nei confini verticali
    della sezione. → (reqs, scartati, n_tab, carry).

    ORDINE DI VALUTAZIONE DELLE TABELLE
      Le tabelle vengono ordinate per coordinata Y: find_tables() non
      garantisce l'ordine di lettura e la continuazione di una tabella
      deve essere processata prima di qualunque tabella successiva, altrimenti
      la testata ereditata verrebbe sostituita da quella sbagliata.

    CONSERVAZIONE DELLA TESTATA EREDITATA
      L'intestazione ripetuta di pagina e le tabelle fuori sezione NON
      azzerano piu' il carry: solo una tabella REALE con testata propria
      lo sostituisce. Azzerarlo sull'intestazione di pagina 9 era la causa
      della perdita di CONCEPT.1099 / CONCEPT.1096.
    """
    reqs, derived, n_tab, seen = [], set(), 0, set()

    try:
        tables = page.find_tables().tables
    except Exception as exc:
        log.debug(f"    find_tables pag.{page_no}: {exc}")
        return reqs, derived, 0, carry

    # Ordinamento per posizione verticale
    def _y0(t):
        try:
            return t.bbox[1]
        except Exception:
            return 0.0

    tables = sorted(tables, key=_y0)

    # La prima tabella utile della pagina e' candidata a continuazione
    first_useful = True

    for t in tables:
        try:
            data = t.extract()
        except Exception:
            continue
        if not data:
            continue

        # Intestazione / pie' di pagina: si ignora SENZA toccare il carry
        if _is_page_furniture(data):
            log.debug(
                f"    pag.{page_no}: intestazione di pagina ignorata "
                f"(carry conservato)"
            )
            continue

        # La prima tabella reale della pagina puo' essere la prosecuzione
        # di quella iniziata nella pagina precedente: in quel caso il
        # bordo superiore della sezione non si applica.
        is_continuation = bool(carry) and first_useful and not any(
            header_map(row) for row in data
        )

        if not _table_in_bounds(t, y_min, y_max, allow_top=is_continuation):
            log.debug(
                f"    pag.{page_no}: tabella fuori sezione — scartata "
                f"(bbox y={getattr(t, 'bbox', ('?', '?'))[1]})"
            )
            # Il carry si azzera SOLO se la tabella scartata ha una testata
            # propria: e' una tabella di un'altra funzione, non un residuo.
            if any(header_map(row) for row in data):
                carry = None
            first_useful = False
            continue

        first_useful = False
        n_tab += 1

        found, new_carry = parse_matrix(data, config_name, page_no, carry)

        # Recupero delle cornici verticali vuote: il testo c'e', ma fuori
        # dalle celle restituite da find_tables.
        if not found and _is_empty_vertical_frame(data):
            try:
                import fitz
                clip = fitz.Rect(t.bbox)
                testo = page.get_text("text", clip=clip)
            except Exception:
                testo = ""
            if testo.strip():
                recuperati = extract(testo, config_name, page_no)
                for r in recuperati:
                    r.layout = "V"
                if recuperati:
                    log.info(
                        f"    pag.{page_no}: {len(recuperati)} requisiti "
                        f"recuperati dal testo di una cornice vuota: "
                        f"{', '.join(x.req_id for x in recuperati)}"
                    )
                found = recuperati

        if new_carry:
            carry = new_carry



        
        for r in found:
            derived.update(r.derived_ids)
            if r.key() not in seen:
                seen.add(r.key())
                reqs.append(r)

    low = {d.lower() for d in derived}
    reqs = [r for r in reqs if r.key() not in low]
    own = {r.key() for r in reqs}
    derived = {d for d in derived if d.lower() not in own}
    return reqs, derived, n_tab, carry

# ---------------------------------------------------------------------------
# API pubblica — strategia primaria
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Confini verticali della sezione
# ---------------------------------------------------------------------------
#
# Una sezione inizia e finisce quasi sempre A METÀ PAGINA: sulla pagina
# finale, sotto l'ultima tabella della nostra funzione, comincia già la
# funzione successiva con le SUE tabelle di requisiti.
# Senza un ritaglio verticale quelle tabelle verrebbero attribuite alla
# funzione sbagliata (è il caso di TRS.619 e CONCEPT.735, che appartengono
# a LV_Pantograph_Lifting ma finivano sotto LV_Country_code_selection).
#
# Si individua quindi la coordinata Y del titolo di sezione che delimita
# la nostra funzione e si scartano le tabelle che stanno oltre.
# ---------------------------------------------------------------------------
# Confini verticali della sezione
# ---------------------------------------------------------------------------
#
# Una sezione inizia e finisce quasi sempre A METÀ PAGINA: sotto l'ultima
# tabella della nostra funzione comincia già la funzione successiva con le
# SUE tabelle di requisiti. Senza ritaglio verticale quelle tabelle
# verrebbero attribuite alla funzione sbagliata (TRS.619 e CONCEPT.735
# appartengono a 3.2 Pantograph Control ma finivano sotto 3.1).
#
# DUE FORMATI DI TITOLO — entrambi presenti negli stessi documenti
#   Formato A  "3.1 Country code selection"    indice e titolo sulla stessa riga
#   Formato B  "3.2"                            indice da solo, titolo sotto
#              "Pantograph Control"
# Il Formato B è quello che compare a pagina 8 del documento di riferimento:
# gestirlo è indispensabile, altrimenti il confine non viene mai trovato.
#
# VINCOLO ANTI-FALSI-POSITIVI
# Si richiede almeno un punto nell'indice (≥ 2 livelli). Senza questo
# vincolo le righe della tabella dei country-code ("1 Italy", "2 Austria")
# verrebbero lette come titoli di sezione, fissando un confine sbagliato.

_SEC_WITH_TITLE = re.compile(r"^(\d+(?:\.\d+){1,5})\.?\s+(\S.*)$")
_SEC_ALONE      = re.compile(r"^(\d+(?:\.\d+){1,5})\.?\s*$")

# Parole che segnalano un riferimento incrociato, non un titolo
_XREF_WORDS = ("see", "chapter", "refer", "section", "vedi", "cfr")


def _page_headings(page):
    """
    [(indice, y)] dei titoli di sezione della pagina, ordinati per y.

    Usa get_text("dict") per avere la coordinata verticale di OGNI RIGA:
    con i blocchi l'intero blocco erediterebbe la y del suo inizio e il
    confine risulterebbe spostato verso l'alto.
    """
    out = []
    try:
        d = page.get_text("dict")
    except Exception:
        return out

    for block in d.get("blocks", []):
        if block.get("type") != 0:          # 0 = blocco di testo
            continue
        for line in block.get("lines", []):
            txt = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if not txt or len(txt) > 120:
                continue
            low = txt.lower()
            if any(w in low for w in _XREF_WORDS):
                continue

            m = _SEC_WITH_TITLE.match(txt) or _SEC_ALONE.match(txt)
            if m:
                idx = m.group(1).rstrip(".")
                parts = idx.split(".")
                if len(parts) < 2 or not all(p.isdigit() for p in parts):
                    continue
                if len(parts) == 2 and parts[1] == "0":   # "5.0" = revisione
                    continue
                # un titolo di sezione è quasi sempre in grassetto / corpo maggiore
                sz = max((s.get("size", 0) for s in line.get("spans", [])), default=0)
                bold = any("Bold" in (s.get("font", "")) for s in line.get("spans", []))
                if not (bold or sz >= 11):
                    continue
                out.append((idx, line.get("bbox", (0, 0, 0, 0))[1]))

    out.sort(key=lambda t: t[1])
    return out



def _section_bounds(page, section_index: str, is_first: bool, is_last: bool):
    """
    (y_min, y_max) della sezione sulla pagina.
    Il ritaglio viene applicato SEMPRE quando l'indice di sezione è noto:
    una sezione può iniziare e finire nella stessa pagina (es. 3.1.2 a pag.7)
    senza che start/end siano segnalati come parziali.
    """
    if not section_index:
        return None, None

    sec = section_index.rstrip(".")
    heads = _page_headings(page)
    if not heads:
        # Nessun titolo: pagina interamente interna alla sezione
        return None, None

    y_min, y_max = None, None

    for idx, y in heads:
        # Titolo nostro o di un discendente
        if idx == sec or idx.startswith(sec + "."):
            if y_min is None:
                y_min = y
            y_max = None          # riapre la sezione: eventuale confine precedente non vale
            continue

        if _is_sibling_or_higher(idx, sec):
            if y_min is not None and y > y_min and y_max is None:
                y_max = y         # primo titolo estraneo DOPO l'inizio
            elif y_min is None:
                # titolo estraneo prima del nostro: la sezione inizia dopo
                y_min = None if is_first is False else y_min

    # Se la nostra sezione non compare su questa pagina ma stiamo
    # proseguendo da quella precedente, il primo titolo estraneo chiude tutto
    if y_min is None and not is_first:
        # Su una pagina intermedia il confine inferiore vale solo se il
        # titolo estraneo e' un successore plausibile: un riferimento
        # incrociato dentro una cella non deve amputare la pagina e far
        # perdere le tabelle sottostanti.
        for idx, y in heads:
            if _is_sibling_or_higher(idx, sec) and _is_close_successor(idx, sec):
                y_max = y
                break

    log.debug(f"    ritaglio '{sec}': y_min={y_min} y_max={y_max}")
    return y_min, y_max


def _is_sibling_or_higher(idx: str, sec: str) -> bool:
    """
    True se idx è un fratello di sec o appartiene a un livello superiore.

      sec = "3.1"
        "3.2"   → True   (fratello: inizia la funzione successiva)
        "4.1"   → True   (altro capitolo)
        "3.1.2" → False  (figlio: ancora nostra sezione)
        "3.1"   → False  (noi stessi)
    """
    a = idx.split(".")
    b = sec.split(".")
    if len(a) > len(b):
        return False
    return a != b[:len(a)]

def _is_close_successor(idx: str, sec: str) -> bool:
    """
    True se idx e' un successore immediato di sec, non un riferimento lontano.

      sec = "3.2.1"
        "3.2.2" → True    "3.3"   → True
        "3.3.5" → False   "3.1.2" → False
    """
    MAX_FORWARD_GAP = 2
    try:
        a = [int(x) for x in idx.rstrip(".").split(".")]
        b = [int(x) for x in sec.rstrip(".").split(".")]
    except ValueError:
        return False
    for d in range(min(len(a), len(b))):
        if a[d] == b[d]:
            continue
        if a[d] < b[d]:
            return False
        if a[d] - b[d] > MAX_FORWARD_GAP:
            return False
        return len(a) <= d + 2
    return True

# Tolleranza verticale (punti) sui confini di sezione: una tabella che
# sfora di poco il confine appartiene ancora alla sezione.
_BOUNDS_TOL = 12.0


def _table_in_bounds(t, y_min, y_max, allow_top: bool = False) -> bool:
    """
    True se la tabella rientra nei confini verticali della sezione.

    CRITERIO DI SOVRAPPOSIZIONE, non di centro
      Una tabella che prosegue dalla pagina precedente parte in cima al
      foglio e può essere molto alta: valutandone il centro verrebbe
      respinta non appena sotto di essa inizia la sezione successiva,
      perdendo righe che appartengono alla nostra tabella.

    allow_top
      Quando la tabella è la PRIMA della pagina e si sta proseguendo una
      tabella iniziata nella pagina precedente, il bordo superiore non va
      applicato: la continuazione inizia sempre sopra qualunque titolo.
    """
    if y_min is None and y_max is None:
        return True
    try:
        x0, y0, x1, y1 = t.bbox
    except Exception:
        return True

    if y_min is not None and not allow_top:
        if y1 < y_min - _BOUNDS_TOL:          # tutta sopra il confine
            return False
    if y_max is not None:
        if y0 > y_max + _BOUNDS_TOL:          # tutta sotto il confine
            return False
    return True

def extract_from_tables(
    doc_path,
    page_start: int,
    page_end: int,
    config_name: str,
    section_index: str = "",
    start_is_partial: bool = False,
    end_is_partial: bool = False,
) -> list:
    """
    Estrae i requisiti dalle tabelle delle pagine indicate.

    RITAGLIO VERTICALE
      Una sezione puo' iniziare E finire a meta' della stessa pagina
      (es. 3.1.2 "Country code selection" a pag.7). I flag
      start_is_partial / end_is_partial NON sono affidabili per decidere
      se ritagliare: quando la pagina successiva inizia gia' con una
      sezione estranea, document_handler non la include e segnala
      end_is_partial=False, lasciando la pagina finale intera.
      Il ritaglio viene quindi applicato SEMPRE che section_index sia
      noto; i flag restano nella firma per compatibilita' e vengono usati
      solo a scopo diagnostico.

    Args:
        doc_path         : percorso del PDF
        page_start       : prima pagina 1-based
        page_end         : ultima pagina 1-based (inclusa)
        config_name      : configurazione di appartenenza
        section_index    : indice di sezione della funzione (es. "3.1.2")
        start_is_partial : diagnostico — la sezione inizia a meta' pagina
        end_is_partial   : diagnostico — la sezione finisce a meta' pagina

    Returns:
        Lista di Requirement accettati, deduplicati, con gli ID presenti
        SOLO nella colonna "Derived to" esclusi.
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

    all_reqs, all_derived, tot_tab, n_cut = [], set(), 0, 0
    carry = None

    if not section_index:
        log.info(
            f"    [Requisiti/{config_name}] nessun indice di sezione — "
            f"pagine {page_start}-{page_end} lette per intero "
            f"(possibile sovra-estrazione)"
        )

    try:
        first = max(1, page_start)
        last = min(max(page_end, page_start), pdf.page_count)
        log.info(
            f"    [Requisiti/{config_name}] scansione pagine {first}-{last} "
            f"({last - first + 1} pagine)"
            + (f" — sezione '{section_index}'" if section_index else "")
        )

        for n in range(first, last + 1):
            page = pdf[n - 1]

            # Il ritaglio NON dipende piu' dai flag di parzialita':
            # viene tentato su ogni pagina dell'intervallo.
            y_min, y_max = _section_bounds(
                page,
                section_index,
                is_first=(n == first),
                is_last=(n == last),
            )

            if y_min is not None or y_max is not None:
                n_cut += 1
                log.debug(
                    f"    pag.{n}: ritaglio sezione '{section_index}' "
                    f"y_min={y_min} y_max={y_max}"
                )
            elif section_index:
                log.debug(
                    f"    pag.{n}: nessun confine per '{section_index}' — "
                    f"pagina interamente interna alla sezione"
                )

            # Una pagina ritagliata in testa interrompe la continuita' di
            # una tabella orizzontale iniziata nella pagina precedente.
            # Il carry si azzera solo se la sezione INIZIA davvero qui:
            # sulla prima pagina dell'intervallo non c'è nulla da ereditare,
            # sulle pagine successive un y_min indica solo un sotto-titolo
            # interno e la tabella può comunque proseguire.
            if y_min is not None and n == first:
                carry = None

            reqs, derived, n_tab, carry = parse_page(
                page, n, config_name, carry, y_min, y_max
            )
            tot_tab += n_tab
            all_derived |= derived
            all_reqs.extend(reqs)
    except Exception as exc:
        log.warning(f"  [Requisiti] Errore estrazione tabelle: {exc}")
    finally:
        pdf.close()

    # ── Deduplica ────────────────────────────────────────────────────────
    seen, uniq = set(), []
    for r in all_reqs:
        if r.key() in seen:
            continue
        seen.add(r.key())
        uniq.append(r)

    # ── Esclusione "Derived to" ──────────────────────────────────────────
    # Si eliminano SOLO gli ID che non compaiono mai in colonna "Nr"/"ID".
    # Il filtro globale precedente scartava anche requisiti legittimi che,
    # in un'altra tabella della stessa sezione, figuravano come provenienza:
    # era una delle cause dei requisiti mancanti.
    own = {r.key() for r in uniq}
    real_derived = {d for d in all_derived if d.lower() not in own}

    n_h = sum(1 for r in uniq if r.layout == "H")
    n_v = sum(1 for r in uniq if r.layout == "V")

    if uniq:
        log.info(
            f"    [Requisiti/{config_name}] {len(uniq)} requisiti da "
            f"{tot_tab} tabelle (H:{n_h} V:{n_v}) — "
            f"{len(real_derived)} esclusi come 'Derived to'"
            + (f", {n_cut} pagine ritagliate" if n_cut else "")
            + (f" — sezione '{section_index}'" if section_index else "")
        )
        if cfg.REQ_DEBUG_LOG_EACH:
            for r in uniq:
                log.info(f"      → pag.{r.page_hint} [{r.layout}] {r.req_id}")
    else:
        log.debug(
            f"    [Requisiti/{config_name}] nessun requisito da "
            f"{tot_tab} tabelle (pag.{page_start}-{page_end}, "
            f"sezione '{section_index or 'n/d'}')"
        )

    return uniq





# ---------------------------------------------------------------------------
# API pubblica — strategia di riserva (testo lineare)
# ---------------------------------------------------------------------------
def extract(text: str, config_name: str, page_hint: int = 0) -> list:
    """
    Estrazione dal testo lineare. Firma invariata per compatibilità.

    Non è più solo una riserva: viene ora invocata SEMPRE e fusa con il
    risultato del parsing di matrice (vedi funzioni_ai_filter.run()).
    I blocchi verticali a bordo pagina, privi di cornice, sfuggono a
    find_tables() anche quando nella stessa sezione esiste una tabella
    orizzontale regolarmente rilevata: era la causa della perdita di
    requisiti come 2F_04.01.Zefiro-Europe.TRS.772.

    DUE FORME DI BLOCCO VERTICALE
      Inline     "ID 2F_04.01.Zefiro-Europe.TRS.772"
      Su righe   "ID"
      separate   "2F_04.01.Zefiro-Europe.TRS.772"
    La seconda è quella prodotta da PyMuPDF sui PDF ETR1000 e richiede
    di ricordare l'etichetta vista sulla riga precedente.

    ID SPEZZATO SU PIÙ RIGHE
      "2F_04.01.Zefiro-"
      "Europe.CONCEPT.775"
    Dopo un'etichetta 'ID' le righe successive vengono concatenate finché
    non si ottiene un ID valido (massimo 2 righe di lookahead).
    """
    if not text or not text.strip():
        return []

    lines = [ln.rstrip() for ln in text.splitlines()]
    found, derived = {}, set()

    pending_label = ""          # etichetta vista sulla riga precedente
    current = None              # requisito aperto: riceve i campi successivi
    pending_field = ""          # campo aperto: riceve le righe di continuazione
    i = 0

    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if not s:
            continue

        # Marcatore di pagina inserito da document_handler: azzera lo stato
        if re.match(r"^\[Pagina\s+\d+\]$", s):
            pending_label = ""
            continue

        # ── Etichetta isolata su riga propria ("ID", "Derived to", ...) ───
        lab = label_of(s)
        if lab and not split_inline(s)[0]:
            pending_label = lab
            continue

        # ── Valore associato all'etichetta della riga precedente ──────────
        if pending_label:
            field_name, value = pending_label, s
            pending_label = ""

            # ID spezzato su più righe: concatena finché non è valido
            if field_name == "req_id" and not find_req_ids(value):
                joined = value
                for look in range(i, min(i + 2, len(lines))):
                    joined += lines[look].strip()
                    if find_req_ids(joined):
                        value = joined
                        i = look + 1
                        break
        else:
            field_name, value = split_inline(s)

        if field_name == "req_id":
            for rid in find_req_ids(value):
                if classify(rid, "req_id")[0]:
                    if rid.lower() not in found:
                        found[rid.lower()] = Requirement(
                            req_id=rid, config_name=config_name,
                            page_hint=page_hint, layout="V",
                        )
                    # Requisito corrente: i campi che seguono sono suoi.
                    # Senza questo riferimento description e sil venivano
                    # letti e poi BUTTATI, lasciando il requisito nudo:
                    # era la causa di "Description assente in <config>".
                    current = found[rid.lower()]
            continue

        if field_name == "derived_to":
            derived.update(t.lower() for t in find_req_ids(value))
            if current is not None:
                current.derived_to = _clean(
                    (current.derived_to + " " + value).strip()
                )[:900]
            continue

        if field_name:
            # description / sil / type / user_interface del requisito aperto
            if current is not None and value.strip():
                v = re.sub(r"^[_\s\u2217*\-–]+", "", _clean(value)).strip()
                if v:
                    old = getattr(current, field_name, "") or ""
                    setattr(current, field_name,
                            (old + " " + v).strip()[:900])
                    pending_field = field_name
            continue


        # ── Continuazione del campo aperto ────────────────────────────────
        # La Description di un blocco verticale prosegue su piu' righe,
        # spesso con elenchi puntati ("− Italy, Austria, ..."). Senza
        # questo recupero si conserva solo la prima riga.
        if (current is not None and pending_field
                and not label_of(s) and not split_inline(s)[0]):
            tok0 = canon(s.split()[0]) if s.split() else ""
            if not is_id(tok0):
                v = re.sub(r"^[_\s\u2217*]+", "", _clean(s)).strip()
                if v:
                    old = getattr(current, pending_field, "") or ""
                    setattr(current, pending_field,
                            (old + " " + v).strip()[:900])
                continue

        # ── Riga che INIZIA con un ID: posizione di colonna "Nr" ──────────

        # ── Riga che INIZIA con un ID: posizione di colonna "Nr" ──────────
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
                current = r
                pending_field = "description"

    # Esclude SOLO gli ID che non compaiono mai come requisito proprio
    for d in derived:
        found.pop(d, None)

    reqs = list(found.values())
    if reqs:
        log.info(
            f"    [Requisiti/{config_name}] {len(reqs)} requisiti dal testo "
            f"lineare: {', '.join(r.req_id for r in reqs)}"
        )
    return reqs
# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip(" \t|-")

# Marcatori dell'intestazione/piè di pagina ripetuta su ogni foglio
_FURNITURE_HINTS = (
    "document state", "documentstate", "revision", "language",
    "page", "pagina", "all rights reserved", "bombardier",
    "confidential", "proprietary",
)


def _is_page_furniture(data) -> bool:
    """
    True per la tabellina di intestazione/piè di pagina del documento
    ("Document state: Released | Language: en | Revision: C | Page: 9 | ...").

    Compare su OGNI pagina, è la prima tabella restituita da find_tables()
    e sta fuori dai confini verticali della sezione. Se non la si riconosce
    esplicitamente viene scartata come "tabella fuori sezione" e azzera la
    testata ereditata, facendo perdere l'intera continuazione della tabella
    di requisiti (caso CONCEPT.735 a pag.8 / CONCEPT.1099 a pag.9).

    Criteri: poche righe, nessun ID di requisito, almeno due marcatori tipici.
    """
    if not data or len(data) > 3:
        return False
    if any(cell_ids(c) for row in data for c in row):
        return False
    joined = " ".join(flat(c) for row in data for c in row).lower()
    if not joined:
        return True
    return sum(h in joined for h in _FURNITURE_HINTS) >= 2


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _is_empty_vertical_frame(rows) -> bool:
    """
    True per una cornice di tabella verticale priva di contenuto:
    le etichette ID / Description / Safety level sono presenti ma
    nessuna cella contiene un ID di requisito.
    """
    if not rows:
        return False
    etichette = {label_of(c) for row in rows for c in row if label_of(c)}
    if "req_id" not in etichette:
        return False
    return not any(cell_ids(c) for row in rows for c in row)