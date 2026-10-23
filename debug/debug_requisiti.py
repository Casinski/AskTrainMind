"""
debug_requisiti.py
------------------
Estrae e classifica i requisiti dalle tabelle di un PDF tecnico ETR1000.
Versione allineata a requirements_extractor.py.

PRINCIPIO
  Il testo lineare di get_text() è inutilizzabile come strategia primaria:
  le colonne sono strette e gli ID vanno a capo più volte. Si lavora sulla
  MATRICE DI CELLE di find_tables(), dove ogni ID sta in una sola cella.

DUE LAYOUT
  VERTICALE   colonna etichetta (ID / Description / Safety level) + colonna
              valore. Un blocco per requisito.
  ORIZZONTALE riga di testata (Nr | Description | Type oppure
              ApplicabilityDetails | Derived to | User Interface | SIL),
              poi UNA RIGA PER REQUISITO.

QUATTRO INSIDIE DEI PDF ETR1000, TUTTE GESTITE QUI
  1. L'etichetta verticale NON sta sempre nella stessa colonna:
         riga 0  ['', 'ID', '2F_04...']            → col 1
         riga 1  ['Description', None, 'The ...']  → col 0
     Cercare solo in label_col fa perdere la Description.
  2. La testata orizzontale è spezzata su due righe
         ['Nr','Description','','Applicability','','Derived to','','User',...]
         [None,None,None,'Details',None,None,None,'Interface',...]
     e i valori stanno nelle colonne di separazione: serve un
     riallineamento della testata sui dati.
  3. Un'intestazione può comparire DUE volte ('SIL' in col 9 e 10): vale
     la prima, l'ultima è la colonna vuota.
  4. find_tables() riconosce la CORNICE di un blocco verticale senza
     estrarne le celle: la matrice è vuota ma il requisito esiste. Va
     recuperato dal testo contenuto nel riquadro (caso TRS.772 a pag.7
     di 3EGH489028-2358).

CLASSIFICAZIONE
  ACCETTATO  ID dalla colonna "Nr" o dal campo "ID", contenente "Zefiro"
  SCARTATO   ID dalla colonna "Derived to" → provenienza, non requisito

USO
  python debug/debug_requisiti.py <pdf>                           → scansione completa
  python debug/debug_requisiti.py <pdf> <pag_in> <pag_fin>        → analisi dettagliata
  python debug/debug_requisiti.py <pdf> <pag_in> <pag_fin> -raw   → dump celle grezze
"""
import sys
import os
import re
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = "debug_requisiti.log"


# ═══════════════════════════════════════════════════════════════════════════
# MODELLO DATI (autonomo: nessuna dipendenza da requirements_extractor)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Req:
    req_id: str
    description: str = ""
    req_type: str = ""
    derived_to: str = ""
    user_interface: str = ""
    sil: str = ""
    page: int = 0
    layout: str = ""          # "H" orizzontale | "V" verticale | "T" testuale
    derived_ids: list = field(default_factory=list)

    def key(self) -> str:
        return self.req_id.lower()


# ═══════════════════════════════════════════════════════════════════════════
# STAMPA DEI CAMPI DI UN REQUISITO
# ═══════════════════════════════════════════════════════════════════════════

# "req_type" copre sia "Type" (VZI_Base) sia "ApplicabilityDetails"
# (altre configurazioni): è la stessa colonna con nome diverso.
FIELD_LABELS = [
    ("description",    "Description"),
    ("req_type",       "Type / ApplicabilityDetails"),
    ("derived_to",     "Derived to"),
    ("user_interface", "User Interface"),
    ("sil",            "SIL / Safety level"),
]

# Campi attesi per layout: quelli non previsti non sono segnalati mancanti.
EXPECTED_BY_LAYOUT = {
    "H": ("description", "req_type", "derived_to", "user_interface", "sil"),
    "V": ("description", "sil"),
    "T": ("description",),
}

VAL_WIDTH = 300


def _wrap(s: str, width: int) -> list:
    """Spezza una stringa su più righe senza tagliare le parole."""
    parole, righe, cur = s.split(), [], ""
    for p in parole:
        if len(cur) + len(p) + 1 > width:
            righe.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        righe.append(cur)
    return righe or [""]


def dump_req(r, log, prefix="            "):
    """
    Stampa TUTTI i campi della tabella associati al requisito.

    Un campo vuoto ma atteso per quel layout viene marcato '(vuoto) ⚠':
    è il segnale che l'estrazione ha perso un dato ed è esattamente
    l'informazione che serve in debug.
    """
    attesi = EXPECTED_BY_LAYOUT.get(r.layout, ())
    log(f"{prefix}layout   : {r.layout}  (pagina {r.page})")

    for attr, label in FIELD_LABELS:
        val = (getattr(r, attr, "") or "").strip()
        if val:
            testo = val[:VAL_WIDTH] + (" […]" if len(val) > VAL_WIDTH else "")
            righe = _wrap(testo, 92)
            log(f"{prefix}{label:<28}: {righe[0]}")
            for extra in righe[1:]:
                log(f"{prefix}{'':<28}  {extra}")
        elif attr in attesi:
            log(f"{prefix}{label:<28}: (vuoto)  ⚠")
        else:
            log(f"{prefix}{label:<28}: —")

    for d in getattr(r, "derived_ids", []) or []:
        log(f"{prefix}{'ID di provenienza':<28}: ❌ {d}  (colonna 'Derived to')")


# ═══════════════════════════════════════════════════════════════════════════
# NORMALIZZAZIONE E RICONOSCIMENTO DEGLI ID
# ═══════════════════════════════════════════════════════════════════════════

ID_MARKER = "zefiro"

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_]*(?:[.\-]+[A-Za-z0-9_]+){2,}")

# Prefisso canonico: cifre + lettere ("2F", "4S")
PREFIX_RE = re.compile(r"^(\d+[A-Za-z]+)")

# Forma attesa DOPO canon(): "2F_04.01..." oppure "2F.04..."
ID_PREFIX_SHAPE = re.compile(r"^\d+[A-Za-z]+[._]")

# Inizi tipici di prosa che, privata degli spazi, somiglia a un ID
PROSE_PREFIXES = ("e.g.", "i.e.", "etc.", "ref.", "fig.", "cfr.", "n.a.")

# Prefissi spuri che PyMuPDF antepone al testo delle celle verticali
JUNK_PREFIX_RE = re.compile(r"^[_\s\u2217*\u2212\-–•]+")


def squeeze(c) -> str:
    """Contenuto della cella con TUTTI gli spazi rimossi."""
    return re.sub(r"\s+", "", c or "")


def flat(c) -> str:
    """Contenuto di una cella di testo: a-capo → spazio."""
    return re.sub(r"\s+", " ", c or "").strip()


def clean(s: str) -> str:
    """Testo normalizzato, privo dei prefissi spuri del PDF."""
    return JUNK_PREFIX_RE.sub("", re.sub(r"\s+", " ", s or "")).strip(" \t|")


def canon(tok: str) -> str:
    """
    Forma canonica di un ID.

    PyMuPDF concatena gli span di testo spostando l'underscore:
        "2F04.01.Zefiro-_Europe.CONCEPT.775"
    Si rimuovono tutte le '_' e se ne reinserisce UNA dopo il prefisso
    numerico-alfabetico iniziale:
        → "2F_04.01.Zefiro-Europe.CONCEPT.775"
    """
    t = (tok or "").strip(".,;:()[]|")
    if not t:
        return ""
    t = t.replace("_", "")
    m = PREFIX_RE.match(t)
    if m:
        t = m.group(1) + "_" + t[m.end():]
    return t


def is_id(tok: str) -> bool:
    """
    Forma di ID valida. ATTENZIONE: va invocata su una stringa GIÀ passata
    per canon(), perché il filtro sul prefisso richiede il separatore
    ("2F_04") che nella forma grezza ("2F04") non c'è.
    """
    t = (tok or "").strip(".,;:()[]|")
    if len(t) < 8 or len(t) > 150:
        return False
    if t.lower().startswith(PROSE_PREFIXES):
        return False
    if not ID_PREFIX_SHAPE.match(t):
        return False
    if re.search(r"[A-Za-z]{28,}", t):
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
    if ID_MARKER not in (req_id or "").lower():
        return False, f"ID privo del marcatore '{ID_MARKER}'"
    if len(req_id.split(".")) < 3:
        return False, "ID incompleto"
    return True, "OK"


# ═══════════════════════════════════════════════════════════════════════════
# RICONOSCIMENTO DELLE TESTATE
# ═══════════════════════════════════════════════════════════════════════════

H_HEADERS = {
    "nr": "req_id", "nr.": "req_id", "n.": "req_id", "number": "req_id",
    "description": "description", "descrizione": "description",
    "type": "req_type", "tipo": "req_type",
    "applicability details": "req_type", "applicabilitydetails": "req_type",
    "applicability detail": "req_type", "applicability": "req_type",
    "derived to": "derived_to", "derived from": "derived_to",
    "derivedto": "derived_to",
    "user interface": "user_interface", "userinterface": "user_interface",
    "user": "user_interface", "ui": "user_interface",
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

INLINE_LABEL_RE = re.compile(
    r"^\s*(ID|Requirement\s*ID|Description|Descrizione|Safety\s*level|"
    r"Safety\s*Integrity\s*Level|SIL|Derived\s*to|Type|"
    r"Applicability\s*Details?|User\s*Interface)\b"
    r"\s*[:\-|]?\s*",
    re.I,
)

# Frammenti della seconda riga di una testata spezzata
HEADER_TAIL_WORDS = ("details", "interface", "level", "to", "requirement")


def header_map(row) -> dict:
    """
    {indice_colonna: campo} se la riga è una testata orizzontale.
    Richiede la colonna "Nr" e almeno 3 intestazioni note.

    A parità di campo vale la PRIMA occorrenza: un'intestazione ripetuta
    ("SIL" in col 9 e col 10) assegnava altrimenti il campo alla colonna
    vuota di destra, perdendo il valore.
    """
    if not row:
        return {}
    out = {}
    for i, c in enumerate(row):
        k = flat(c).lower().strip(":|")
        field_name = H_HEADERS.get(k) or H_HEADERS.get(k.replace(" ", ""))
        if not field_name:
            continue
        if field_name in out.values():
            continue
        out[i] = field_name
    return out if "req_id" in out.values() and len(out) >= 3 else {}


def realign_header(hmap: dict, rows: list, hrow: int, log=None) -> dict:
    """
    Riallinea la testata sulle colonne che contengono davvero i dati.

    PyMuPDF genera colonne di separazione vuote e spezza le intestazioni
    su due righe ("Applicability"/"Details", "User"/"Interface"):
    l'etichetta finisce in una colonna, il valore in quella accanto.
    Per ogni campo si verifica se la colonna mappata contiene almeno un
    valore nelle righe dati; in caso contrario si cerca la colonna
    adiacente (prima a sinistra, poi a destra) non ancora assegnata.
    """
    data_rows = [r for r in rows[hrow + 1:] if r]
    if not data_rows:
        return hmap

    def has_data(ci: int) -> bool:
        return any(ci < len(r) and flat(r[ci]) for r in data_rows)

    out, taken = {}, set()
    for ci in sorted(hmap):
        if has_data(ci) and ci not in taken:
            out[ci] = hmap[ci]
            taken.add(ci)

    n_col = max((len(r) for r in data_rows), default=0)

    for ci in sorted(hmap):
        field_name = hmap[ci]
        if ci in out or field_name in out.values():
            continue
        for cand in (ci - 1, ci + 1, ci - 2, ci + 2):
            if 0 <= cand < n_col and cand not in taken and has_data(cand):
                out[cand] = field_name
                taken.add(cand)
                if log:
                    log(f"      testata riallineata: '{field_name}' "
                        f"col {ci} → col {cand}")
                break

    return out or hmap


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
    m = INLINE_LABEL_RE.match(s)
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

    Si scandiscono TUTTE le colonne: find_tables restituisce matrici
    irregolari e la colonna etichetta può stare oltre l'indice 2.
    Soglia: 1 sola etichetta purché sia 'ID'. Un blocco minimo
    (ID / Description / Safety level) con i valori su righe di
    continuazione produce un solo hit, e una soglia di 2 lo scartava.
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

    # Blocco verticale privo di ID reali: è una cornice vuota, gestita
    # separatamente da is_empty_vertical_frame().
    if not any(cell_ids(c) for row in rows for c in row):
        return None

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


def is_empty_vertical_frame(rows) -> bool:
    """
    True per una cornice di tabella verticale priva di contenuto:
    le etichette ID / Description / Safety level sono presenti ma
    nessuna cella contiene un ID di requisito.

    find_tables() riconosce i bordi del riquadro senza estrarne le celle
    (blocchi senza linee interne). Il requisito esiste nel PDF ma non
    entra nella matrice: va recuperato dal testo del riquadro.
    """
    if not rows:
        return False
    etichette = {label_of(c) for row in rows for c in row if label_of(c)}
    if "req_id" not in etichette:
        return False
    return not any(cell_ids(c) for row in rows for c in row)


# ═══════════════════════════════════════════════════════════════════════════
# SEGMENTAZIONE DELLA MATRICE
# ═══════════════════════════════════════════════════════════════════════════

def segment(data):
    """
    Spezza la matrice sulle righe di testata orizzontale.
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


# ── CONTINUAZIONE DI TABELLA TRA PAGINE ────────────────────────────────────
FIELD_ORDER = ["req_id", "description", "req_type", "derived_to",
               "user_interface", "sil"]


def remap_header(hmap, n_col):
    """
    Riproietta una testata ereditata su una matrice con un numero di
    colonne diverso (continuazioni di pagina, dove PyMuPDF non genera le
    colonne vuote di separazione).

    I campi iniziali si ancorano a SINISTRA, 'sil' e 'user_interface' a
    DESTRA: sono sempre le ultime colonne delle tabelle ETR1000.
    """
    fields = [f for f in FIELD_ORDER if f in hmap.values()]
    if not fields:
        return {}
    if max(hmap.keys()) < n_col:          # la testata ci sta già: invariata
        return dict(hmap)

    tail = [f for f in ("sil", "user_interface") if f in fields]
    head = [f for f in fields if f not in tail]

    out = {}
    for i, f in enumerate(head):
        if i < n_col:
            out[i] = f
    for j, f in enumerate(tail):
        ci = n_col - 1 - j
        if ci >= len(head):
            out[ci] = f
    return out


# ═══════════════════════════════════════════════════════════════════════════
# PARSING — TABELLA ORIZZONTALE
# ═══════════════════════════════════════════════════════════════════════════

def parse_horizontal(rows, page, log, hmap, hrow):
    """Tabella orizzontale: una riga per requisito."""
    reqs = []
    cols = {f: i for i, f in hmap.items()}
    log(f"      tabella ORIZZONTALE (testata riga {hrow}): {sorted(cols)}")
    col_id = cols["req_id"]

    for ri in range(hrow + 1, len(rows)):
        row = rows[ri]

        # Seconda riga di una testata spezzata ("Applicability"/"Details",
        # "User"/"Interface"): frammenti di intestazione, mai un ID.
        # Accodarla al requisito precedente ne inquinava i campi.
        if ri == hrow + 1 and not any(cell_ids(c) for c in row):
            if any(label_of(c) or flat(c).lower() in HEADER_TAIL_WORDS
                   for c in row):
                log("      seconda riga di testata saltata")
                continue

        if col_id >= len(row):
            continue

        ids = cell_ids(row[col_id])
        if not ids:
            # Riga di continuazione: la cella "Nr" è vuota perché il
            # requisito precedente prosegue. Il testo va accodato.
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
        r = Req(req_id=rid, page=page, layout="H")
        for field_name, ci in cols.items():
            if field_name == "req_id" or ci >= len(row):
                continue
            setattr(r, field_name, clean(row[ci])[:900])

        ci = cols.get("derived_to")
        if ci is not None and ci < len(row):
            r.derived_ids = cell_ids(row[ci])

        ok, why = classify(rid, "req_id")
        if ok:
            reqs.append(r)
            log(f"      ✅ [H riga {ri}] {rid}")
            dump_req(r, log)
            log("")
        else:
            log(f"      ❌ [H riga {ri}] {rid}  → {why}")

    return reqs


# ═══════════════════════════════════════════════════════════════════════════
# PARSING — TABELLA VERTICALE
# ═══════════════════════════════════════════════════════════════════════════

def parse_vertical(rows, page, log, label_col, inline):
    """
    Tabella verticale. Supporta PIÙ requisiti consecutivi: una nuova
    etichetta 'ID' chiude il blocco precedente e ne apre uno nuovo.
    """
    reqs = []
    log(f"      tabella VERTICALE "
        f"(colonna etichette: {label_col if label_col is not None else 'inline'})")

    cur, cur_derived = {}, []

    def flush():
        rid = cur.get("req_id", "")
        if not rid:
            cur.clear()
            cur_derived.clear()
            return
        ok, why = classify(rid, "req_id")
        if ok:
            r = Req(
                req_id=rid,
                description=clean(cur.get("description", ""))[:900],
                req_type=clean(cur.get("req_type", "")),
                derived_to=clean(cur.get("derived_to", "")),
                user_interface=clean(cur.get("user_interface", "")),
                sil=clean(cur.get("sil", "")),
                page=page, layout="V",
                derived_ids=list(cur_derived),
            )
            reqs.append(r)
            log(f"      ✅ [V] {rid}")
            dump_req(r, log)
            log("")
        else:
            log(f"      ❌ [V] {rid}  → {why}")
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
                    reqs.append(Req(req_id=extra, page=page, layout="V"))
                    log(f"      ✅ [V] {extra}   (ID aggiuntivo nella cella)")
        elif field_name == "derived_to":
            cur["derived_to"] = flat(raw_value)
            cur_derived.extend(cell_ids(raw_value))
        else:
            v = flat(raw_value)
            if not v:
                # Etichetta senza valore: il campo resta "aperto" e verrà
                # alimentato dalla riga successiva.
                cur.setdefault(field_name, "")
                return
            v = JUNK_PREFIX_RE.sub("", v).strip()
            if v:
                cur[field_name] = (cur.get(field_name, "") + " " + v).strip()

    # Campo aperto: le righe prive di etichetta ne sono la continuazione
    pending = [""]

    def row_label(row):
        """
        (campo, indice_colonna) dell'etichetta presente nella riga.

        L'etichetta NON sta sempre nella stessa colonna. Si prende quella
        PIÙ A DESTRA: il valore la segue sempre, e quando l'etichetta è
        ripetuta ('Description' in col 0 e col 1) il valore sta oltre la
        seconda.
        """
        best_field, best_ci = "", -1
        limit = min(len(row), max((label_col or 0) + 1, 3) + 1)
        for ci in range(limit):
            f = label_of(row[ci])
            if f:
                best_field, best_ci = f, ci
        return best_field, best_ci

    def row_value(row, from_col):
        """Concatena le celle a destra dell'etichetta, saltando le etichette."""
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

        field_name, ci_lab = row_label(row)

        # Caso A: etichetta trovata in una qualsiasi colonna della riga
        if field_name:
            put(field_name, row_value(row, ci_lab + 1))
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

        # Caso C: riga senza etichetta → continuazione del campo aperto
        if pending[0] and pending[0] != "req_id":
            extra = row_value(row, 0)
            if extra:
                put(pending[0], extra)

    flush()
    return reqs


# ═══════════════════════════════════════════════════════════════════════════
# PARSING — STRATEGIA DI RISERVA SU TESTO LINEARE
# ═══════════════════════════════════════════════════════════════════════════

def parse_text(text: str, page: int, log) -> list:
    """
    Estrazione dal testo lineare, usata per recuperare le cornici
    verticali vuote.

    DUE FORME DI BLOCCO VERTICALE
      Inline     "ID 2F_04.01.Zefiro-Europe.TRS.772"
      Su righe   "ID"
      separate   "2F_04.01.Zefiro-Europe.TRS.772"

    I campi letti dopo un ID vengono ASSEGNATI al requisito aperto: la
    versione precedente li leggeva e li scartava, lasciando il requisito
    con la sola Description vuota.
    """
    if not text or not text.strip():
        return []

    lines = [ln.rstrip() for ln in text.splitlines()]
    found = {}
    derived = set()

    pending_label = ""     # etichetta vista sulla riga precedente
    current = None         # requisito aperto
    pending_field = ""     # campo aperto, riceve le continuazioni
    i = 0

    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if not s:
            continue

        if re.match(r"^\[Pagina\s+\d+\]$", s):
            pending_label = ""
            continue

        # Etichetta isolata su riga propria
        lab = label_of(s)
        if lab and not split_inline(s)[0]:
            pending_label = lab
            continue

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
                        found[rid.lower()] = Req(
                            req_id=rid, page=page, layout="V",
                        )
                    current = found[rid.lower()]
                    pending_field = ""
            continue

        if field_name == "derived_to":
            derived.update(t.lower() for t in find_req_ids(value))
            if current is not None:
                current.derived_to = clean(
                    (current.derived_to + " " + value).strip()
                )[:900]
            continue

        if field_name:
            if current is not None and value.strip():
                v = clean(value)
                if v:
                    old = getattr(current, field_name, "") or ""
                    setattr(current, field_name, (old + " " + v).strip()[:900])
                    pending_field = field_name
            continue

        # Continuazione del campo aperto: la Description prosegue su più
        # righe, spesso con elenchi puntati ("− Italy, Austria, ...").
        if current is not None and pending_field:
            tok0 = canon(s.split()[0]) if s.split() else ""
            if not is_id(tok0):
                v = clean(s)
                if v:
                    old = getattr(current, pending_field, "") or ""
                    setattr(current, pending_field,
                            (old + " " + v).strip()[:900])
                continue

        # Riga che INIZIA con un ID: posizione di colonna "Nr"
        tok = canon(s.split()[0]) if s.split() else ""
        if is_id(tok) and tok.lower() not in found:
            if classify(tok, "req_id")[0]:
                body = s[len(s.split()[0]):].strip()
                r = Req(req_id=tok, page=page, layout="T")
                others = [t for t in find_req_ids(body)
                          if t.lower() != tok.lower()]
                if others:
                    r.derived_to = ", ".join(others)
                    r.derived_ids = list(others)
                    derived.update(t.lower() for t in others)
                    for t in others:
                        body = body.replace(t, " ")
                r.description = clean(body)[:900]
                found[tok.lower()] = r
                current = r
                pending_field = "description"

    for d in derived:
        found.pop(d, None)

    return list(found.values())


# ═══════════════════════════════════════════════════════════════════════════
# INTERPRETAZIONE DI UNA MATRICE
# ═══════════════════════════════════════════════════════════════════════════

def parse_matrix(data, page, log, carry=None):
    """
    Interpreta UNA tabella, segmentandola se contiene più blocchi.

    ORDINE DI VALUTAZIONE — punto critico
      Le intestazioni della tabella orizzontale (Description, Type,
      Derived to, User Interface, SIL) compaiono ANCHE tra le etichette
      verticali. Se si valutasse prima il layout verticale, una tabella
      orizzontale verrebbe scambiata per verticale e tutti i suoi
      requisiti andrebbero persi: la testata orizzontale ha SEMPRE la
      precedenza.

    Ritorna (requisiti, testata_da_propagare).
    """
    reqs = []
    if not data:
        return reqs, None

    new_carry = None

    for kind, rows in segment(data):
        if not rows:
            continue

        # ── Segmento con testata orizzontale propria ──────────────────
        if kind == "H":
            hmap = header_map(rows[0])
            if hmap:
                hmap = realign_header(hmap, rows, 0, log)
                reqs.extend(parse_horizontal(rows, page, log, hmap, 0))
                new_carry = hmap
                carry = hmap
            continue

        # ── Segmento senza testata: verticale o continuazione ─────────
        label_col = find_label_col(rows)
        inline = has_inline_labels(rows)

        if label_col is not None or inline:
            reqs.extend(parse_vertical(rows, page, log, label_col, inline))
            continue

        # ── Cornice verticale riconosciuta ma VUOTA ───────────────────
        # Gestita dal chiamante, che dispone del bbox per rileggere il
        # testo del riquadro.
        if is_empty_vertical_frame(rows):
            log("      cornice verticale VUOTA — recupero dal testo del riquadro")
            continue

        # ── Continuazione di tabella orizzontale dalla pagina precedente ──
        if carry:
            n_col = max((len(r) for r in rows), default=0)
            cmap = remap_header(carry, n_col)
            col_id = next((i for i, f in cmap.items() if f == "req_id"), None)
            if col_id is not None and any(
                col_id < len(r) and cell_ids(r[col_id]) for r in rows
            ):
                log(f"      testata EREDITATA (continuazione di tabella, "
                    f"{n_col} colonne) → {sorted(cmap.items())}")
                reqs.extend(parse_horizontal(
                    [[]] + list(rows), page, log, cmap, 0
                ))
                new_carry = carry

    return reqs, new_carry


def frame_text(page, t) -> str:
    """Testo contenuto nel riquadro di una tabella."""
    try:
        import fitz
        return page.get_text("text", clip=fitz.Rect(t.bbox))
    except Exception:
        return ""


def recover_empty_frame(page, t, data, page_no, log):
    """
    Recupera i requisiti di una cornice verticale vuota rileggendo il
    testo del riquadro. È il caso di TRS.772 a pag.7 di 3EGH489028-2358:
    find_tables vede i bordi ma non il contenuto.
    """
    testo = frame_text(page, t)
    if not testo.strip():
        return []
    recuperati = parse_text(testo, page_no, lambda *a: None)
    for r in recuperati:
        r.layout = "V"
    if recuperati:
        log(f"      ♻ {len(recuperati)} requisiti RECUPERATI dal testo "
            f"del riquadro:")
        for r in recuperati:
            log(f"      ✅ [V-recuperato] {r.req_id}")
            dump_req(r, log)
            log("")
    else:
        log("      ⚠ cornice vuota e testo non interpretabile:")
        for ln in testo.splitlines()[:12]:
            if ln.strip():
                log(f"         | {ln}")
    return recuperati


def is_page_furniture(data) -> bool:
    """Intestazione/piè di pagina ripetuta su ogni foglio."""
    if not data or len(data) > 3:
        return False
    if any(cell_ids(c) for row in data for c in row):
        return False
    joined = " ".join(flat(c) for row in data for c in row).lower()
    if not joined:
        return True
    hints = ("document state", "revision", "language", "page", "pagina",
             "all rights reserved", "bombardier", "confidential")
    return sum(h in joined for h in hints) >= 2


def parse_page(page, page_no, log, carry=None):
    """Tutte le tabelle di una pagina, con deduplica."""
    reqs, derived, n_tab, seen = [], set(), 0, set()

    try:
        tables = page.find_tables().tables
    except Exception:
        return reqs, derived, 0, carry

    for t in tables:
        data = t.extract()
        if not data:
            continue
        if is_page_furniture(data):
            continue

        n_tab += 1
        found, new_carry = parse_matrix(data, page_no, log, carry)

        if not found and is_empty_vertical_frame(data):
            found = recover_empty_frame(page, t, data, page_no, log)

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


# ═══════════════════════════════════════════════════════════════════════════
# ANALISI DETTAGLIATA
# ═══════════════════════════════════════════════════════════════════════════

def main(pdf_path: str, p_start: int, p_end: int, raw: bool = False):
    import fitz

    pdf = fitz.open(pdf_path)
    out = open(OUT, "w", encoding="utf-8")

    def w(s=""):
        print(s)
        out.write(str(s) + "\n")

    w(f"PDF    : {pdf_path}")
    w(f"Pagine : {p_start}-{p_end} di {pdf.page_count}")
    w("=" * 78)

    all_reqs, all_derived, tot_tab = [], set(), 0
    carry = None

    for n in range(p_start, min(p_end, pdf.page_count) + 1):
        page = pdf[n - 1]
        w(f"\n{'=' * 78}")
        w(f"PAGINA {n}")
        w("=" * 78)

        try:
            tables = page.find_tables().tables
        except Exception as exc:
            w(f"  find_tables errore: {exc}")
            continue

        if not tables:
            w("  nessuna tabella")
            continue

        for ti, t in enumerate(tables, 1):
            data = t.extract()
            if not data:
                continue
            tot_tab += 1
            segs = segment(data)
            w(f"\n  --- Tabella {ti}/{len(tables)}: {len(data)} righe x "
              f"{max(len(r) for r in data)} colonne"
              f"{f' — {len(segs)} segmenti' if len(segs) > 1 else ''} ---")
            for ri, row in enumerate(data[:12]):
                if raw:
                    w(f"      [{ri:2d}] {[repr(c)[:46] for c in row]}")
                else:
                    w(f"      [{ri:2d}] {[flat(c)[:34] for c in row]}")
            if len(data) > 12:
                w(f"      ... altre {len(data) - 12} righe")

            # Dump del testo del riquadro quando la matrice è priva di
            # contenuto: è l'unico modo per vedere se il requisito c'è.
            if raw and not any(flat(c) for row in data for c in row):
                w("      ── matrice VUOTA, testo del riquadro ──")
                for ln in frame_text(page, t).splitlines()[:20]:
                    if ln.strip():
                        w(f"         | {ln}")

            found, new_carry = parse_matrix(data, n, w, carry)

            if not found and is_empty_vertical_frame(data):
                found = recover_empty_frame(page, t, data, n, w)

            if new_carry:
                carry = new_carry
            for r in found:
                all_derived.update(r.derived_ids)
                all_reqs.append(r)

    pdf.close()

    low = {d.lower() for d in all_derived}
    seen, uniq = set(), []
    for r in all_reqs:
        if r.key() in low or r.key() in seen:
            continue
        seen.add(r.key())
        uniq.append(r)
    all_reqs = uniq
    own = {r.key() for r in all_reqs}
    all_derived = {d for d in all_derived if d.lower() not in own}

    w("\n" + "=" * 78)
    w("CLASSIFICAZIONE DEI REQUISITI")
    w("=" * 78)

    n_h = sum(1 for r in all_reqs if r.layout == "H")
    n_v = sum(1 for r in all_reqs if r.layout != "H")
    w(f"\n  ACCETTATI ({len(all_reqs)})   orizzontali: {n_h}  verticali: {n_v}")

    for r in all_reqs:
        tipo = "orizzontale" if r.layout == "H" else "verticale"
        w(f"\n    ✅ {r.req_id}")
        w(f"         pagina {r.page} — tabella {tipo}")
        dump_req(r, w, prefix="         ")

    incompleti = [
        r for r in all_reqs
        if any(not (getattr(r, a, "") or "").strip()
               for a in EXPECTED_BY_LAYOUT.get(r.layout, ()))
    ]
    if incompleti:
        w(f"\n  ⚠ REQUISITI CON CAMPI MANCANTI ({len(incompleti)}):")
        for r in incompleti:
            vuoti = [
                lbl for a, lbl in FIELD_LABELS
                if a in EXPECTED_BY_LAYOUT.get(r.layout, ())
                and not (getattr(r, a, "") or "").strip()
            ]
            w(f"    • [{r.layout}] {r.req_id} (pag.{r.page}) → "
              f"manca: {', '.join(vuoti)}")

    w(f"\n  SCARTATI ({len(all_derived)}) — colonna 'Derived to':")
    for d in sorted(all_derived):
        w(f"    ❌ {d}")

    w("\n" + "=" * 78)
    w(f"  Tabelle analizzate  : {tot_tab}")
    w(f"  REQUISITI ACCETTATI : {len(all_reqs)}  (H: {n_h}, V: {n_v})")
    w(f"  ID scartati         : {len(all_derived)}")
    w(f"  Con campi mancanti  : {len(incompleti)}")
    w("=" * 78)
    w(f"\nLog salvato in: {OUT}")
    out.close()


# ═══════════════════════════════════════════════════════════════════════════
# SCANSIONE COMPLETA
# ═══════════════════════════════════════════════════════════════════════════

def scan_all(pdf_path: str):
    import fitz

    pdf = fitz.open(pdf_path)
    print(f"PDF    : {pdf_path}")
    print(f"Pagine : {pdf.page_count}")
    print("=" * 78)
    print("Scansione completa — requisiti per pagina\n")

    tot_h, tot_v, tot_tab, tot_rej, pages = 0, 0, 0, set(), []
    carry, seen_global = None, set()

    for i in range(pdf.page_count):
        reqs, derived, n_tab, carry = parse_page(
            pdf[i], i + 1, lambda *a: None, carry
        )
        tot_tab += n_tab
        if not reqs and not derived:
            continue

        nuovi = [r for r in reqs if r.key() not in seen_global]
        for r in nuovi:
            seen_global.add(r.key())
            if r.layout == "H":
                tot_h += 1
            else:
                tot_v += 1

        tot_rej |= derived
        pages.append(i + 1)

        print(f"  pag.{i+1:4d} | tabelle: {n_tab} | "
              f"ACCETTATI: {len(nuovi)} | scartati: {len(derived)}")
        for r in nuovi:
            vuoti = [
                lbl for a, lbl in FIELD_LABELS
                if a in EXPECTED_BY_LAYOUT.get(r.layout, ())
                and not (getattr(r, a, "") or "").strip()
            ]
            flag = f"   ⚠ manca: {', '.join(vuoti)}" if vuoti else ""
            print(f"             ✅ [{r.layout}] {r.req_id}{flag}")
        for d in sorted(derived):
            print(f"             ❌ {d}   (Derived to)")

    pdf.close()
    print("\n" + "=" * 78)
    print(f"Tabelle analizzate                  : {tot_tab}")
    print(f"REQUISITI ACCETTATI (distinti)      : {tot_h + tot_v}")
    print(f"   da tabelle orizzontali           : {tot_h}")
    print(f"   da tabelle verticali             : {tot_v}")
    print(f"ID distinti scartati ('Derived to') : {len(tot_rej)}")
    for d in sorted(tot_rej):
        print(f"    ❌ {d}")

    if tot_h == 0 or tot_v == 0:
        mancante = "orizzontali" if tot_h == 0 else "verticali"
        print(f"\n⚠ NESSUN requisito da tabelle {mancante}.")
        print("  Esegui il dump grezzo per vedere come arrivano le celle:")
        print(f'    python debug/debug_requisiti.py "{pdf_path}" 7 7 -raw')

    if pages:
        print(f"\nPagine con requisiti : da {pages[0]} a {pages[-1]}")
        print("\nAnalisi dettagliata:")
        print(f'  python debug/debug_requisiti.py "{pdf_path}" '
              f'{pages[0]} {min(pages[0] + 3, pages[-1])}')


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python debug/debug_requisiti.py <pdf>")
        print("  python debug/debug_requisiti.py <pdf> <pag_in> <pag_fin> [-raw]")
        sys.exit(1)

    if len(sys.argv) == 2:
        scan_all(sys.argv[1])
    else:
        main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
             raw="-raw" in sys.argv)