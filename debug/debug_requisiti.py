"""
debug_requisiti.py
------------------
Estrae e classifica i requisiti dalle tabelle di un PDF tecnico ETR1000.

PRINCIPIO
  Il testo lineare di get_text() è inutilizzabile: le colonne sono strette
  e gli ID vanno a capo più volte. Si lavora sulla MATRICE DI CELLE di
  find_tables(), dove ogni ID sta in una sola cella.

DUE LAYOUT
  VERTICALE   colonna etichetta (ID / Description / Safety level) + colonna
              valore. Un blocco per requisito.
  ORIZZONTALE riga di testata (Nr | Description | Type | Derived to |
              User Interface | SIL), poi UNA RIGA PER REQUISITO.

ORDINE DI VALUTAZIONE — il punto critico
  Le intestazioni della tabella orizzontale (Description, Type, Derived to,
  User Interface, SIL) compaiono ANCHE tra le etichette verticali. Se si
  valutasse prima il layout verticale, una tabella orizzontale verrebbe
  scambiata per verticale e tutti i suoi requisiti andrebbero persi.
  Perciò la testata orizzontale ha SEMPRE la precedenza.

SEGMENTAZIONE
  find_tables() può restituire in UNA sola matrice sia il blocco verticale
  sia la tabella orizzontale che lo segue (pagina 7: TRS.772 seguito dai
  quattro CONCEPT). La matrice viene spezzata sulle righe di testata.

NORMALIZZAZIONE DEGLI ID — l'ordine conta
  1. squeeze()  rimuove TUTTI gli spazi, ricomponendo gli a-capo:
       "2F_04.01.Zefiro-\\nEurope.CONCEPT.\\n1013" → "2F04.01.Zefiro-_Europe.CONCEPT.1013"
  2. canon()    ricostruisce l'underscore spostato da PyMuPDF:
       → "2F_04.01.Zefiro-Europe.CONCEPT.1013"
  3. is_id()    valida la forma — SOLO sulla stringa già canonicalizzata,
                perché il filtro sul prefisso richiede il separatore dopo
                il prefisso ("2F_" o "2F."), assente nella forma grezza.

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
    layout: str = ""          # "H" orizzontale | "V" verticale
    derived_ids: list = field(default_factory=list)

    def key(self) -> str:
        return self.req_id.lower()


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

    Oltre alla struttura a segmenti, due filtri contro la prosa:
      - prefisso cifre+lettere seguito da '.' o '_'
      - nessun blocco alfabetico di 28+ caratteri (tipico della prosa
        privata degli spazi)
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

    # Caso normale: la cella contiene SOLO l'ID, spezzato su più righe
    whole = canon(s)
    if is_id(whole):
        return [whole]

    # Altrimenti cerca le occorrenze interne, canonicalizzando ognuna
    out, seen = [], set()
    for m in ID_RE.finditer(s):
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

INLINE_LABEL_RE = re.compile(
    r"^\s*(ID|Requirement\s*ID|Description|Descrizione|Safety\s*level|"
    r"Safety\s*Integrity\s*Level|SIL|Derived\s*to|Type|User\s*Interface)\b"
    r"\s*[:\-|]?\s*",
    re.I,
)


def header_map(row) -> dict:
    """
    {indice_colonna: campo} se la riga è una testata orizzontale.
    Richiede la colonna "Nr" e almeno 3 intestazioni note.
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
    return out if "req_id" in out.values() and len(out) >= 3 else {}


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

    DUE vincoli contro i falsi positivi:
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
    """
    True se le celle contengono etichetta e valore insieme.
    Richiede almeno un'etichetta 'ID'.
    """
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


# ═══════════════════════════════════════════════════════════════════════════
# PARSING
# ═══════════════════════════════════════════════════════════════════════════

def parse_horizontal(rows, page, log, hmap, hrow):
    """Tabella orizzontale: una riga per requisito."""
    reqs = []
    cols = {f: i for i, f in hmap.items()}
    log(f"      tabella ORIZZONTALE (testata riga {hrow}): {sorted(cols)}")
    col_id = cols["req_id"]

    for ri in range(hrow + 1, len(rows)):
        row = rows[ri]
        if col_id >= len(row):
            continue
        ids = cell_ids(row[col_id])
        if not ids:
            continue                      # riga di continuazione

        rid = ids[0]
        r = Req(req_id=rid, page=page, layout="H")
        for field_name, ci in cols.items():
            if field_name == "req_id" or ci >= len(row):
                continue
            setattr(r, field_name, flat(row[ci])[:900])

        ci = cols.get("derived_to")
        if ci is not None and ci < len(row):
            r.derived_ids = cell_ids(row[ci])

        ok, why = classify(rid, "req_id")
        if ok:
            reqs.append(r)
            log(f"      ✅ [H riga {ri}] {rid}")
            log(f"            desc : {r.description[:68]}")
            log(f"            type={r.req_type!r} UI={r.user_interface!r} "
                f"SIL={r.sil!r}")
            for d in r.derived_ids:
                log(f"            ❌ {d}   → 'Derived to', provenienza")
        else:
            log(f"      ❌ [H riga {ri}] {rid}  → {why}")

    return reqs


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
                description=cur.get("description", "")[:900],
                req_type=cur.get("req_type", ""),
                derived_to=cur.get("derived_to", ""),
                user_interface=cur.get("user_interface", ""),
                sil=cur.get("sil", ""),
                page=page, layout="V",
                derived_ids=list(cur_derived),
            )
            reqs.append(r)
            log(f"      ✅ [V] {rid}")
            log(f"            desc : {r.description[:68]}")
            log(f"            SIL={r.sil!r}")
            for d in r.derived_ids:
                log(f"            ❌ {d}   → 'Derived to', provenienza")
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


def parse_matrix(data, page, log, carry=None):
    """
    Interpreta UNA tabella, segmentandola se contiene più blocchi.
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
                reqs.extend(parse_horizontal(rows, page, log, hmap, 0))
                new_carry = hmap
            continue

        # ── Segmento senza testata: verticale o continuazione ─────────
        label_col = find_label_col(rows)
        inline = has_inline_labels(rows)

        if label_col is not None or inline:
            reqs.extend(parse_vertical(rows, page, log, label_col, inline))
            continue

        # Continuazione di tabella orizzontale dalla pagina precedente
        if carry:
            col_id = [i for i, f in carry.items() if f == "req_id"][0]
            n_col = max(len(r) for r in rows)
            if n_col > col_id and any(
                col_id < len(r) and cell_ids(r[col_id]) for r in rows
            ):
                log("      testata EREDITATA (continuazione di tabella)")
                reqs.extend(parse_horizontal(
                    [[]] + list(rows), page, log, carry, 0
                ))

    return reqs, new_carry


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
        n_tab += 1
        found, new_carry = parse_matrix(data, page_no, log, carry)
        if new_carry:
            carry = new_carry
        for r in found:
            derived.update(r.derived_ids)
            if r.key() not in seen:
                seen.add(r.key())
                reqs.append(r)

    low = {d.lower() for d in derived}
    reqs = [r for r in reqs if r.key() not in low]
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

            found, new_carry = parse_matrix(data, n, w, carry)
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

    w("\n" + "=" * 78)
    w("CLASSIFICAZIONE DEI REQUISITI")
    w("=" * 78)

    n_h = sum(1 for r in all_reqs if r.layout == "H")
    n_v = sum(1 for r in all_reqs if r.layout == "V")
    w(f"\n  ACCETTATI ({len(all_reqs)})   orizzontali: {n_h}  verticali: {n_v}")
    for r in all_reqs:
        tipo = "orizzontale" if r.layout == "H" else "verticale"
        w(f"\n    ✅ {r.req_id}")
        w(f"         pagina   : {r.page}   tabella: {tipo}")
        if r.description:
            w(f"         descr.   : {r.description[:100]}")
        if r.req_type:
            w(f"         type     : {r.req_type}")
        if r.derived_to:
            w(f"         derived  : {r.derived_to[:70]}")
        if r.user_interface:
            w(f"         UI       : {r.user_interface}")
        if r.sil:
            w(f"         SIL      : {r.sil}")

    w(f"\n  SCARTATI ({len(all_derived)}) — colonna 'Derived to':")
    for d in sorted(all_derived):
        w(f"    ❌ {d}")

    w("\n" + "=" * 78)
    w(f"  Tabelle analizzate  : {tot_tab}")
    w(f"  REQUISITI ACCETTATI : {len(all_reqs)}  (H: {n_h}, V: {n_v})")
    w(f"  ID scartati         : {len(all_derived)}")
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
            print(f"             ✅ [{r.layout}] {r.req_id}")
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
        print(f"\nAnalisi dettagliata:")
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