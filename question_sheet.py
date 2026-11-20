"""
question_sheet.py
-----------------
Addestramento rapido dell'AI con il foglio Excel «questionAI».

Invece di rispondere una domanda alla volta nel terminale (voce 7) il
developer:

    1. genera il foglio questionAI.xlsx con le domande in attesa (voce 15
       oppure  python asktrainmind_dev.py --questionai-export [percorso]);
    2. lo compila con calma in Excel: colonna «LA TUA RISPOSTA», testo libero
       (sì / no / correzione / spiegazione discorsiva);
    3. lo carica (voce 16 oppure
       python asktrainmind_dev.py --questionai-import percorso [--from-id N]).

Il caricamento legge e CATALOGA ogni risposta (classify): conferma,
conferma con aggiunte, rifiuto della proposta, correzione, spiegazione
discorsiva, «non so», «ignora». Dalle risposte discorsive ricava significato,
dettagli, elementi/sensori/centraline/tarature/eventi TCMS citati, note per
configurazione e nuove sigle (con la loro definizione se presente, altrimenti
come nuova domanda). Il testo originale della risposta e' conservato nella
scheda del concetto (knowledge.add_answer): Chiedi lo mostra e lo usa come
contesto, quindi capisce anche le risposte che non seguono uno schema.
Se l'AI locale (Ollama) e' disponibile e QUESTION_SHEET_USE_AI e' attivo, le
risposte discorsive sono anche strutturate dal modello (facoltativo: senza
Ollama vale la lettura euristica).

Resilienza
    * ogni risposta e' applicata e registrata (knowledge/questionari.json) e
      la conoscenza e' salvata ogni QUESTION_SHEET_SAVE_EVERY risposte;
    * se il caricamento si interrompe (Ctrl+C, chiusura, errore) quanto
      appreso fino a quel momento resta salvato e viene indicato l'ID da cui
      ricaricare il file; al nuovo caricamento lo stesso file riparte da li';
    * ricaricare un file gia' caricato non duplica nulla: le risposte gia'
      acquisite servono all'AI per APPROFONDIRE (nuove domande di
      approfondimento su quei concetti, da esportare in un nuovo questionAI).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

import config as cfg
import knowledge as K

log = logging.getLogger(__name__)

SHEET = "questionAI"
INFO_SHEET = "Istruzioni"
META_SHEET = "_meta"

# (intestazione, larghezza, chiave interna)
COLUMNS = [
    ("ID", 7, "id"),
    ("Termine / concetto", 22, "term"),
    ("Tipo di domanda", 20, "kind"),
    ("Domanda dell'AI", 62, "question"),
    ("Proposta dell'AI (se c'è)", 40, "proposal"),
    ("Dove l'ho trovato", 48, "context"),
    ("LA TUA RISPOSTA", 70, "answer"),
    ("Note (facoltative)", 30, "notes"),
    ("_qid", 10, "qid"),
    ("_campo", 16, "field"),
]
HIDDEN = {"qid", "field"}

INSTRUCTIONS = [
    "COME COMPILARE IL FOGLIO questionAI",
    "",
    "Scrivi la risposta nella colonna gialla «LA TUA RISPOSTA». Non serve seguire uno schema:",
    "  • per confermare la proposta dell'AI basta «sì» (oppure ok, corretto, esatto…);",
    "  • se la proposta è sbagliata scrivi «no» e, se puoi, la versione giusta: «No, è la Brake Control Unit»;",
    "  • puoi aggiungere dettagli dopo la conferma: «Sì, ed è installata sotto cassa nella M2»;",
    "  • alle domande discorsive rispondi liberamente, anche con più frasi. Se vuoi puoi usare righe",
    "    come «Sensori: …», «Centraline: …», «Tarature: …», «Eventi TCMS: …», «VZ_FR: …» (facoltativo);",
    "  • se citi nuove sigle scrivile con il significato tra parentesi, es. «la BCU (Brake Control Unit)»;",
    "  • «non so» o «?» = lascia la domanda in attesa;  «x» = non chiedere più questa domanda;",
    "    «xx» o «ignora» = il termine non interessa (nessuna altra domanda su di esso);",
    "  • le righe senza risposta sono semplicemente saltate: puoi compilare il foglio a più riprese.",
    "",
    "Non modificare le colonne ID, _qid e _campo (servono a collegare la risposta alla domanda).",
    "Puoi riordinare o filtrare le righe e salvare il file con un altro nome.",
    "",
    "CARICAMENTO: menu developer voce 16, oppure",
    "    python asktrainmind_dev.py --questionai-import \"percorso\\questionAI.xlsx\"",
    "Se il caricamento si interrompe, quanto appreso resta salvato: ricarica lo stesso file",
    "(riparte in automatico) oppure indica l'ID suggerito con --from-id.",
    "Ricaricare un file già caricato fa approfondire all'AI i concetti di cui hai parlato",
    "(nuove domande da esportare con la voce 15).",
]

KIND_LABEL = {"verify": "Verifica la proposta", "meaning": "Significato", "deepen": "Approfondimento",
              "followup": "Approfondimento", "category": "Categoria"}

# ---------------------------------------------------------------------------
# Lettura delle risposte libere
# ---------------------------------------------------------------------------

_P = r"[\s,.;:!\-–—]*"
YES_RX = re.compile(r"^(s[iì]+|s|yes|y|ok(?:ay)?|esatt[oa](?:mente)?|corrett[oa]|giust[oa]|confermo|"
                    r"certo|certamente|vero|affermativo|perfetto|va\s+bene|d['’]accordo|assolutamente\s+s[iì]|"
                    r"proprio\s+cos[iì]|esatto\s+cos[iì])\b" + _P + r"(.*)$", re.I | re.S)
NO_RX = re.compile(r"^(no+|nope|non\s+(?:è|e['’]?|e)\s+(?:corrett[oa]|giust[oa]|esatt[oa]|cos[iì]|vero)|"
                   r"sbagliat[oa]|errat[oa]|falso|negativo|non\s+proprio|non\s+esattamente|non\s+del\s+tutto|"
                   r"assolutamente\s+no|per\s+niente|niente\s+affatto)\b" + _P + r"(.*)$", re.I | re.S)
DUNNO_RX = re.compile(r"^(\?+|non\s+(?:lo\s+)?so|non\s+saprei|boh|n\.?\s?d\.?|da\s+verificare|"
                      r"non\s+ricordo|chiedi\s+(?:dopo|più\s+tardi)|dopo|skip|salta)\W*$", re.I)
IGNORE_TERM_RX = re.compile(r"^(xx|ignora(?:\s+(?:il\s+)?termine)?|non\s+(?:mi\s+)?interessa|"
                            r"non\s+(?:è|e['’]?)\s+(?:un\s+)?(?:termine|concetto)\s+tecnico|non\s+tecnico|"
                            r"irrilevante|non\s+serve)\W*$", re.I)
IGNORE_Q_RX = re.compile(r"^(x|non\s+chiedere(?:\s+più)?|domanda\s+inutile|non\s+applicabile|n\.?\s?a\.?)\W*$",
                         re.I)
# «significa / sta per / è …» davanti al significato
LEAD_RX = re.compile(r"^(?:(?:in\s+realt[àa]|invece|piuttosto|ma|bens[iì])\s*,?\s*)?"
                     r"(?:(?:la\s+sigla\s+)?(?:significa|sta\s+per|vuol\s+dire|indica|si\s+intende|rappresenta|"
                     r"(?:è|e['’])\s+(?:l['’]|il|lo|la|un['’]?|una|uno)?|=|:)\s*)?", re.I)

# Righe «etichetta: valori» riconosciute nelle risposte discorsive
LABELS = [
    (r"sensor[ie]|trasduttor[ie]", "relations.sensori"),
    (r"centralin[ae]|unit[àa]\s+di\s+controllo|ecu|controllor[ie]", "relations.centraline"),
    (r"component[ie]|elementi(?:\s+coinvolti)?|apparecchiature", "relations.componenti"),
    (r"taratur[ae]|sogli[ae]|valori(?:\s+di\s+taratura)?|parametri", "relations.tarature"),
    (r"eventi(?:\s+tcms)?|diagnostic[ah]e?|allarmi", "relations.eventi_tcms"),
    (r"correlat[io]|collegat[io]|vedi\s+anche|concetti\s+correlati", "relations.correlati"),
    (r"costruttore|fornitore|produttore", "facts.costruttore"),
    (r"anno|entrata\s+in\s+servizio", "facts.anno"),
    (r"treni|veicoli", "facts.treni"),
    (r"tratt[ae]|percors[io]|linee", "facts.tratte"),
    (r"posizione|dove\s+si\s+trova|installat[oa]", "facts.posizione"),
    (r"baseline(?:\s+software)?", "facts.baseline"),
    (r"note", "notes"),
]
_LABEL_LINE = re.compile(r"^\s*[-•*]?\s*(" + "|".join(p for p, _ in LABELS) + r")\s*[:=]\s*(.+)$", re.I)
_CFG_LINE = re.compile(r"^\s*[-•*]?\s*(VZ[\w\-]+|ETR\s?\d+[\w\-]*)\s*[:=]\s*(.+)$", re.I)
_CFG_NAME = re.compile(r"(?<![\w\-])(VZI?[_\-][A-Za-z0-9_\-]*[A-Za-z0-9])(?![\w\-])")
_DEF_LINE = re.compile(r"^\s*[-•*]?\s*([A-Z][A-Z0-9\-/_]{1,14})\s*(?:=|:|→|->|–|—)\s*(.{3,200})$")
_UNITS = r"(?:kPa|MPa|bar|°C|°|V|kV|mA|A|km/h|m/s|s|ms|min|h|%|Hz|kHz|kW|W|mm|cm|m|Nm|kN|N|l/min|rpm)"
_VALUE = re.compile(r"[<>≤≥]?\s*-?\d+(?:[.,]\d+)?\s*" + _UNITS + r"(?![\w])")


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", str(text or "").replace("\r", "")).strip()


def _sentence_split(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ù«\"(])|\n+", text) if s.strip()]


def _meaning_from(text: str) -> str:
    t = LEAD_RX.sub("", text.strip(), count=1).strip(" ,;:-–—")
    return t[:1].upper() + t[1:] if t else ""


def classify(text: str, item: dict) -> dict:
    """
    Cataloga una risposta libera. Restituisce {"kind", "value", "extra"}:
      conferma        «sì» alla proposta dell'AI
      conferma+       «sì, …» con un'aggiunta (extra)
      si              «sì» senza dettagli a una domanda che chiede un elenco
      rifiuto         «no» alla proposta (la domanda torna senza proposta)
      no              «no» a una domanda di approfondimento (es. «Ci sono sensori?» → no)
      correzione      «no, …» con la versione giusta (value)
      discorsiva      spiegazione libera (value)
      non_so          la domanda resta in attesa
      ignora_domanda  non chiedere più la domanda
      ignora_termine  il termine non interessa
    """
    t = _clean(text)
    if not t:
        return {"kind": "vuota", "value": "", "extra": ""}
    if IGNORE_Q_RX.match(t):
        return {"kind": "ignora_domanda", "value": "", "extra": ""}
    if IGNORE_TERM_RX.match(t):
        return {"kind": "ignora_termine", "value": "", "extra": ""}
    if DUNNO_RX.match(t):
        return {"kind": "non_so", "value": "", "extra": ""}
    has_prop = bool((item.get("proposal") or "").strip())
    m = YES_RX.match(t)
    if m:
        rest = m.group(2).strip()
        rest = re.sub(r"^(?:e|ed|ma|inoltre|anche|però|pero'?|tuttavia|aggiungo(?:\s+che)?)\b[\s,:]*", "",
                      rest, flags=re.I).strip()
        if has_prop:
            return {"kind": "conferma+" if rest else "conferma", "value": item["proposal"], "extra": rest}
        if rest:
            return {"kind": "discorsiva", "value": rest, "extra": ""}
        return {"kind": "si", "value": "", "extra": ""}
    m = NO_RX.match(t)
    if m:
        rest = m.group(2).strip()
        if rest:
            return {"kind": "correzione", "value": rest, "extra": ""}
        return {"kind": "rifiuto" if has_prop else "no", "value": "", "extra": ""}
    return {"kind": "discorsiva", "value": t, "extra": ""}


def extract(text: str, term: str = "", configs: Iterable[str] = ()) -> dict:
    """
    Struttura una risposta discorsiva: righe «etichetta: valori», note per
    configurazione, valori di taratura con unita' di misura, nuove sigle con
    la definizione («BCU (Brake Control Unit)», «BCU = …») e sigle sconosciute.
    """
    out = {"fields": {}, "configs": {}, "defs": {}, "values": [], "unknown": [], "rest": []}
    cfgs = {c.upper(): c for c in configs}
    for line in (text or "").splitlines():
        m = _LABEL_LINE.match(line)
        if m:
            lab = m.group(1).lower()
            field = next(f for p, f in LABELS if re.fullmatch(p, lab, re.I))
            out["fields"].setdefault(field, []).append(m.group(2).strip())
            continue
        m = _CFG_LINE.match(line)
        if m and (not cfgs or m.group(1).upper() in cfgs):
            out["configs"][cfgs.get(m.group(1).upper(), m.group(1))] = m.group(2).strip()
            continue
        m = _DEF_LINE.match(line)
        if m and K._norm(m.group(1)) != K._norm(term):
            out["defs"][m.group(1)] = _meaning_from(m.group(2))
            continue
        out["rest"].append(line)
    rest = "\n".join(out["rest"])
    for acr, long in K.inline_definitions(rest).items():
        if K._norm(acr) != K._norm(term):
            out["defs"].setdefault(acr, long)
    names = set(cfgs.values()) | {m.group(1) for m in _CFG_NAME.finditer(rest)}
    for c in names:                        # frasi che citano una configurazione
        for s in _sentence_split(rest):
            if re.search(r"(?<![\w\-])" + re.escape(c) + r"(?![\w\-])", s, re.I):
                s = re.sub(r"^\s*" + re.escape(c) + r"\s*[:=]\s*", "", s, flags=re.I)
                out["configs"].setdefault(cfgs.get(c.upper(), c), s)
    out["values"] = list(dict.fromkeys(v.strip() for v in _VALUE.findall(text or "")))
    known = (set(K._alias_map()) | {K._norm(term)} | {K._norm(x) for x in out["defs"]} | set(cfgs)
             | {K._norm(x) for x in names})
    for m in K._ACR.finditer(text or ""):
        w = m.group(1)
        if re.search(r"[A-Z]{2}", w) and w not in K._STOP and K._norm(w) not in known and w not in out["unknown"]:
            out["unknown"].append(w)
    out["rest"] = rest.strip()
    return out


def _ai_structure(item: dict, text: str, timeout: int = 60) -> Optional[dict]:
    """Facoltativo: l'AI locale struttura la risposta discorsiva (None se non disponibile)."""
    try:
        import requests
        prompt = (
            "Sei l'assistente di un esperto di treni ETR1000. L'esperto ha risposto a una tua domanda: "
            "estrai le informazioni SENZA inventare nulla e rispondi SOLO con un JSON.\n"
            f"CONCETTO: {item.get('term', '')}\nDOMANDA: {item.get('question', '')}\n"
            + (f"PROPOSTA ORIGINALE: {item.get('proposal')}\n" if item.get("proposal") else "")
            + f"RISPOSTA DELL'ESPERTO: {text[:3000]}\n"
            "JSON: {\"tipo\": conferma|rifiuto|correzione|spiegazione, \"significato\": \"definizione breve "
            "in italiano se la risposta la contiene, altrimenti vuoto\", \"dettagli\": \"come funziona, "
            "riformulato in modo chiaro\", \"componenti\": [], \"sensori\": [], \"centraline\": [], "
            "\"tarature\": [], \"eventi_tcms\": [], \"correlati\": [], \"nuovi_termini\": "
            "[{\"termine\": \"\", \"significato\": \"\"}], \"domande\": [\"max 2 domande di "
            "approfondimento utili, in italiano\"]}")
        r = requests.post(K._ollama_host() + "/api/chat", timeout=(3, timeout), json={
            "model": cfg.OLLAMA_MODEL, "stream": False, "format": "json",
            "keep_alive": getattr(cfg, "OLLAMA_KEEP_ALIVE", "30m"),
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.1, "num_predict": 700}})
        r.raise_for_status()
        return json.loads((r.json().get("message") or {}).get("content", "") or "{}")
    except Exception as exc:
        log.info("Strutturazione AI della risposta non disponibile: %s", exc)
        return None


def ai_available(timeout: float = 2.0) -> bool:
    try:
        import requests
        return requests.get(K._ollama_host() + "/api/tags", timeout=timeout).ok
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Esportazione
# ---------------------------------------------------------------------------

def default_path() -> Path:
    return Path(getattr(cfg, "QUESTION_SHEET_DIR", "") or Path(__file__).resolve().parent) / f"{SHEET}.xlsx"


def _hash(text: str) -> str:
    return hashlib.sha1(" ".join((text or "").split()).lower().encode()).hexdigest()[:12]


def export_sheet(dest: Optional[Path] = None, limit: Optional[int] = None, term_filter: str = "",
                 items: Optional[list[dict]] = None) -> tuple[Path, int]:
    """Crea il foglio questionAI con le domande in attesa. Restituisce (percorso, n. domande)."""
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    limit = int(limit if limit is not None else getattr(cfg, "QUESTION_SHEET_MAX", 200) or 0)
    items = list(items) if items is not None else K.pending()
    if term_filter:
        items = [x for x in items if term_filter.lower() in x["term"].lower()]
    if limit:
        items = items[:limit]
    dest = Path(dest) if dest else default_path()
    if dest.suffix.lower() != ".xlsx":
        dest = dest / f"{SHEET}.xlsx" if dest.is_dir() or not dest.suffix else dest.with_suffix(".xlsx")
    uid = uuid.uuid4().hex[:12]
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    head_fill = PatternFill("solid", fgColor="1F4E78")
    ans_fill = PatternFill("solid", fgColor="FFF2CC")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for c, (h, w, key) in enumerate(COLUMNS, 1):
        cell = ws.cell(1, c, h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="C00000") if key == "answer" else head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[cell.column_letter].width = w
        if key in HIDDEN:
            ws.column_dimensions[cell.column_letter].hidden = True
    rows = {}
    for i, x in enumerate(items, 1):
        ctx = x.get("context", "")
        if x.get("source"):
            ctx += f"  — {x['source']}" + (f", pag. {x['page']}" if x.get("page") else "")
        vals = {"id": i, "term": x["term"], "kind": KIND_LABEL.get(x.get("kind", ""), K.field_label(x["field"])),
                "question": x["question"], "proposal": x.get("proposal", ""), "context": ctx.strip(),
                "answer": "", "notes": "", "qid": x["id"], "field": x["field"]}
        if x["field"] != "meaning" and x.get("kind") != "followup":
            vals["kind"] = K.field_label(x["field"])
        for c, (_h, _w, key) in enumerate(COLUMNS, 1):
            v = vals[key]
            cell = ws.cell(i + 1, c, ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v, str) else v)
            cell.alignment = Alignment(vertical="top", wrap_text=key not in ("id", "qid", "field"))
            cell.border = border
            if key == "answer":
                cell.fill = ans_fill
        rows[str(i)] = {"qid": x["id"], "key": x["key"], "term": x["term"], "field": x["field"],
                        "question": x["question"], "proposal": x.get("proposal", "")}
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{ws.cell(1, len(COLUMNS)).column_letter}{max(1, len(items) + 1)}"
    info = wb.create_sheet(INFO_SHEET)
    info.column_dimensions["A"].width = 110
    for r, line in enumerate(INSTRUCTIONS, 1):
        info.cell(r, 1, line).font = Font(bold=(r == 1), size=12 if r == 1 else 11)
    meta = wb.create_sheet(META_SHEET)
    meta.append(["uid", uid])
    meta.append(["creato", datetime.now().strftime("%d/%m/%Y %H:%M")])
    meta.append(["domande", len(items)])
    meta.sheet_state = "hidden"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        wb.save(dest)
    except PermissionError as exc:
        raise RuntimeError(f"Impossibile salvare {dest}: il file è aperto in Excel? Chiudilo e riprova.") from exc
    with K._lock:
        reg = K._sheets()
        reg["sheets"][uid] = {"file": str(dest), "created": K._now(), "n": len(items), "rows": rows,
                              "last_id": 0, "status": "da compilare", "resume_from": 0}
        K._write("sheets", reg)
    return dest, len(items)


# ---------------------------------------------------------------------------
# Importazione
# ---------------------------------------------------------------------------

def _norm_head(h) -> str:
    return re.sub(r"[^a-z_]", "", str(h or "").lower().replace("'", "").replace("’", ""))


_HEAD_KEYS = {
    "id": ("id", "nr", "n"),
    "term": ("termineconcetto", "termine", "concetto"),
    "question": ("domandadellai", "domanda"),
    "proposal": ("propostadellaisecce", "propostadellai", "proposta"),
    "answer": ("latuarisposta", "risposta", "rispostaesperto"),
    "notes": ("notefacoltative", "note"),
    "qid": ("_qid", "qid"),
    "field": ("_campo", "campo", "field"),
}


def read_sheet(path: Path) -> tuple[str, list[dict]]:
    """Legge il foglio compilato: (uid, righe con risposta). Tollera colonne spostate."""
    from openpyxl import load_workbook
    path = Path(str(path).strip().strip('"'))
    if not path.is_file():
        raise FileNotFoundError(f"File non trovato: {path}")
    try:
        wb = load_workbook(path, data_only=True)
    except Exception as exc:
        raise RuntimeError(f"Impossibile leggere {path.name}: {exc}") from exc
    uid = ""
    if META_SHEET in wb.sheetnames:
        for r in wb[META_SHEET].iter_rows(values_only=True):
            if r and r[0] == "uid":
                uid = str(r[1] or "")
    ws = wb[SHEET] if SHEET in wb.sheetnames else wb.worksheets[0]
    cols, head_row = {}, 0
    for r in range(1, 6):
        heads = {_norm_head(ws.cell(r, c).value): c for c in range(1, ws.max_column + 1)}
        found = {k: next((heads[a] for a in al if a in heads), 0) for k, al in _HEAD_KEYS.items()}
        if found["answer"] and (found["qid"] or found["question"]):
            cols, head_row = found, r
            break
    if not cols:
        raise RuntimeError(f"{path.name}: non trovo le colonne «LA TUA RISPOSTA» e «Domanda dell'AI» "
                           f"(il foglio deve essere quello generato da AskTrainMind).")
    rows = []
    for r in range(head_row + 1, ws.max_row + 1):
        get = lambda k: ws.cell(r, cols[k]).value if cols.get(k) else None  # noqa: E731
        ans = get("answer")
        q = get("question")
        if q in (None, "") and get("qid") in (None, ""):
            continue
        rid = get("id")
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            rid = r - head_row
        rows.append({"id": rid, "row": r, "term": _clean(get("term")), "question": _clean(q),
                     "proposal": _clean(get("proposal")), "answer": "" if ans is None else str(ans).strip(),
                     "notes": _clean(get("notes")), "qid": _clean(get("qid")), "field": _clean(get("field"))})
    rows.sort(key=lambda x: x["id"])
    return uid, rows


def _item_for(row: dict, reg_rows: dict) -> dict:
    """Domanda collegata alla riga: in coda se c'e' ancora, altrimenti ricostruita dal foglio."""
    pend = {x["id"]: x for x in K._questions()["pending"]}
    if row["qid"] and row["qid"] in pend:
        return pend[row["qid"]]
    meta = reg_rows.get(str(row["id"])) or {}
    term = row["term"] or meta.get("term", "")
    field = row["field"] or meta.get("field") or "meaning"
    return {"id": row["qid"] or meta.get("qid", ""), "key": K.key_of(term) or K._norm(term), "term": term,
            "field": field, "kind": "verify" if row["proposal"] else "meaning",
            "question": row["question"] or meta.get("question", ""),
            "proposal": row["proposal"] or meta.get("proposal", ""), "context": "", "source": "", "page": 0}


def _remove_pending(qid: str) -> None:
    q = K._questions()
    q["pending"] = [x for x in q["pending"] if x["id"] != qid]
    K._write("questions", q)


def _configs() -> list[str]:
    return [t["term"] for t in K.all_terms() if t.get("category") == "configurazione"] or \
        list(getattr(cfg, "CONFIG_NAMES", []) or [])


def _is_list(text: str) -> bool:
    parts = K.split_list(text)
    return bool(parts) and all(len(p.split()) <= 7 for p in parts)


def _apply_structure(term: str, st: dict, src: str, stats: dict) -> None:
    for field, vals in st["fields"].items():
        for v in vals:
            K.set_field(term, field, v, source=src)
    for c, v in st["configs"].items():
        K.set_field(term, f"configs.{c}", v, source=src)
    if st["values"] and not st["fields"].get("relations.tarature"):
        t = K.get(term) or {}
        if "taratur" in (t.get("category", "") + " ".join(st["values"])) or len(st["values"]) <= 6:
            K.set_field(term, "relations.tarature", "; ".join(st["values"]), source=src)
    for acr, long in st["defs"].items():
        if long and not K.get(acr):
            K.upsert(acr, long, K.guess_category(acr, long), source=src, status="confermato")
            stats["new_terms"] += 1
    for w in st["unknown"][:5]:
        if K.ask_meaning(w, context=f"Risposta su «{term}»: {st['rest'][:400]}", source=src, priority=3):
            stats["new_questions"] += 1


def _apply_ai(term: str, data: dict, src: str, stats: dict) -> None:
    for r in K.RELATIONS:
        vals = [str(v).strip() for v in (data.get(r) or []) if str(v).strip()]
        if vals:
            K.set_field(term, f"relations.{r}", "; ".join(vals), source=src)
    for nt in data.get("nuovi_termini") or []:
        if isinstance(nt, dict) and nt.get("termine") and nt.get("significato") and not K.get(nt["termine"]):
            K.upsert(nt["termine"], nt["significato"], K.guess_category(nt["termine"], nt["significato"]),
                     source=src, status="proposto")
            stats["new_terms"] += 1
    for q in (data.get("domande") or [])[:2]:
        if isinstance(q, str) and len(q) > 10:
            _followup(term, q, stats)


def _followup(term: str, question: str, stats: dict, context: str = "") -> bool:
    fid = "followup." + _hash(question)[:8]
    reg = K._sheets()
    key = f"{K.key_of(term) or K._norm(term)}|{fid}"
    if key in reg["asked"]:
        return False
    if K.enqueue(term, fid, question, "followup", context=context[:600], source=SHEET, priority=4):
        reg["asked"].append(key)
        K._write("sheets", reg)
        stats["new_questions"] += 1
        return True
    return False


def apply_answer(item: dict, text: str, notes: str = "", use_ai: bool = False,
                 stats: Optional[dict] = None, source: str = SHEET) -> str:
    """Cataloga e applica una risposta. Restituisce la categoria assegnata."""
    stats = stats if stats is not None else _new_stats()
    c = classify(text, item)
    kind = c["kind"]
    term, field, qid = item["term"], item["field"], item.get("id", "")
    if not term:
        return "vuota"
    stats["kinds"][kind] = stats["kinds"].get(kind, 0) + 1
    if kind == "vuota":
        return kind
    if kind == "non_so":
        if qid:
            K.skip(qid)
        return kind
    if kind in ("ignora_domanda", "ignora_termine"):
        if qid and any(x["id"] == qid for x in K._questions()["pending"]):
            K.drop(qid, whole_term=kind == "ignora_termine")
        elif kind == "ignora_termine":
            K.ignore(term)
        return kind
    configs = _configs()
    value, extra = c["value"], c["extra"]
    structured = None
    if use_ai and kind in ("discorsiva", "correzione", "conferma+") and len(text) > 80:
        structured = _ai_structure(item, text)
    if field == "meaning":
        old = K.get(term)
        if kind == "rifiuto":
            # la proposta era sbagliata: la domanda torna come «cos'è?» senza proposta
            if qid:
                _remove_pending(qid)
            K.enqueue(term, "meaning", f"La mia proposta per «{term}» era sbagliata: cos'è «{term}»? "
                                       f"Spiegami in una o due frasi.", "meaning", "", item.get("context", ""),
                      item.get("source", ""), item.get("page", 0), priority=3)
            if old:
                K.add_answer(term, item["question"], text, field, source)
            stats["applied"] += 1
            return kind
        if kind in ("si", "no"):
            # «sì/no» a «cos'è X?» non spiega nulla: resta in attesa
            if qid:
                K.skip(qid)
            stats["kinds"][kind] -= 1
            stats["kinds"]["non_so"] = stats["kinds"].get("non_so", 0) + 1
            return "non_so"
        if kind in ("conferma", "conferma+"):
            st = extract(extra, term, configs)
            meaning, details = value, st["rest"]
        else:
            st = extract(value, term, configs)
            sents = _sentence_split(st["rest"])
            meaning = _meaning_from(sents[0]) if sents else ""
            details = " ".join(sents[1:])
            if structured and str(structured.get("significato", "")).strip():
                meaning = str(structured["significato"]).strip()
                details = st["rest"] if len(sents) > 1 else details
        if not meaning:
            meaning = _meaning_from(value or text)
        if len(meaning) > 400:
            meaning, details = meaning[:meaning.rfind(" ", 0, 400)] + "…", value or text
        cat = (old or {}).get("category") or K.guess_category(term, item.get("context", "") + " " + text)
        K.upsert(term, meaning, cat, source=source, details=None, status="confermato")
        if details:
            K.set_field(term, "details", details, source=source)
        _apply_structure(term, st, source, stats)
        K.attach_passages(term)
        if qid:
            _remove_pending(qid)
        stats["deepen"] += K.deepen(term)
    else:
        if not K.get(term):
            K.upsert(term, item.get("proposal") or term, "concetto", status="proposto")
        if kind == "rifiuto":
            if qid:
                _remove_pending(qid)
            K.add_answer(term, item["question"], text, field, source)
            stats["applied"] += 1
            return kind
        if kind == "no":
            # «Ci sono sensori in X?» → «no»: informazione utile, non va richiesta di nuovo
            q = K._questions()
            q["ignored"].append(f"{item.get('key') or K._norm(term)}|{field}")
            q["pending"] = [x for x in q["pending"] if x["id"] != qid]
            K._write("questions", q)
        elif kind == "si":
            if qid:
                _remove_pending(qid)
            _followup(term, f"Hai risposto «sì» a: «{item['question']}». Quali, nello specifico?", stats)
        else:
            if kind in ("conferma", "conferma+"):
                K.set_field(term, field, value, source=source)
            st = extract(extra if kind == "conferma+" else ("" if kind == "conferma" else value), term, configs)
            main = st["rest"]
            if main:
                if field.startswith("relations.") and not _is_list(main):
                    K.set_field(term, "details", f"{K.field_label(field)}: {main}", source=source)
                else:
                    K.set_field(term, field, main, source=source)
            _apply_structure(term, st, source, stats)
            if qid:
                _remove_pending(qid)
    if structured:
        _apply_ai(term, structured, source, stats)
    if notes:
        t = K.get(term) or {}
        if notes not in (t.get("notes") or ""):
            K.set_field(term, "notes", ((t.get("notes") or "") + " " + notes).strip(), source=source)
    K.add_answer(term, item["question"], text + (f"\n(Note: {notes})" if notes else ""), field, source)
    stats["applied"] += 1
    return kind


def deepen_from(term: str, question: str, text: str, stats: dict, use_ai: bool = False) -> int:
    """
    Nuove domande di approfondimento su un concetto gia' spiegato dall'esperto
    (usato quando si ricarica un file questionAI gia' caricato).
    """
    n0 = stats["new_questions"]
    t = K.get(term)
    if not t:
        return 0
    stats["deepen"] += K.deepen(term)
    st = extract(text, term, _configs())
    for w in st["unknown"][:5]:
        if K.ask_meaning(w, context=f"Risposta su «{term}»: {text[:400]}", source=SHEET, priority=3):
            stats["new_questions"] += 1
    tt = t["term"]
    cfgs = [c for c in _configs() if c not in (t.get("configs") or {})]
    if cfgs:
        _followup(tt, f"Quello che mi hai spiegato su «{tt}» vale per tutte le configurazioni "
                      f"({', '.join(cfgs[:6])})? Se ci sono differenze, indicale per configurazione "
                      f"(es. «VZ_FR: …»).", stats, text)
    if st["values"]:
        _followup(tt, f"Per «{tt}» hai indicato i valori {', '.join(st['values'][:5])}: sono uguali in tutte "
                      f"le configurazioni e cosa succede quando vengono superati?", stats, text)
    if re.search(r"\b(se|quando|qualora|in caso)\b", text, re.I) and not re.search(r"guast|avari|fault", text, re.I):
        _followup(tt, f"Cosa succede a «{tt}» in caso di guasto o di funzionamento degradato? "
                      f"Ci sono eventi TCMS o messaggi al macchinista?", stats, text)
    if not (t.get("relations") or {}).get("correlati"):
        _followup(tt, f"Con quali altre funzioni o sistemi del treno interagisce «{tt}»?", stats, text)
    if use_ai and len(text) > 60:
        data = _ai_structure({"term": tt, "question": question, "proposal": ""}, text)
        if data:
            for q in (data.get("domande") or [])[:2]:
                if isinstance(q, str) and len(q) > 10:
                    _followup(tt, q, stats, text)
    return stats["new_questions"] - n0


def _new_stats() -> dict:
    return {"rows": 0, "answered": 0, "applied": 0, "already": 0, "deepened_terms": 0, "deepen": 0,
            "new_questions": 0, "new_terms": 0, "kinds": {}, "errors": [], "stopped": False,
            "resume_from": 0, "last_id": 0, "uid": "", "file": ""}


def resume_point(path: Path) -> int:
    """ID da cui riprendere il file (0 = dall'inizio / gia' completato)."""
    try:
        uid, _rows = read_sheet(path)
    except Exception:
        return 0
    s = K._sheets()["sheets"].get(uid) or {}
    return int(s.get("resume_from") or 0) if s.get("status") == "interrotto" else 0


def import_sheet(path, start_id: Optional[int] = None, progress: Callable[[str], None] = print,
                 use_ai: Optional[bool] = None, should_stop: Callable[[], bool] = lambda: False) -> dict:
    """
    Carica le risposte del foglio questionAI compilato.

    start_id: ID da cui partire (None = riprende in automatico dopo un'interruzione,
    altrimenti dall'inizio). Le risposte gia' acquisite (stessa domanda, stesso testo)
    non sono riapplicate ma usate per approfondire i concetti.
    Interrompibile con Ctrl+C: la conoscenza fino all'ultima risposta e' salvata e
    stats["resume_from"] indica l'ID da cui ricaricare il file.
    """
    stats = _new_stats()
    path = Path(str(path).strip().strip('"'))
    uid, rows = read_sheet(path)
    stats["rows"], stats["file"] = len(rows), str(path)
    if not uid:
        uid = "file-" + _hash(str(path.resolve()))
    stats["uid"] = uid
    reg = K._sheets()
    sh = reg["sheets"].setdefault(uid, {"file": str(path), "created": K._now(), "n": len(rows), "rows": {},
                                        "last_id": 0, "status": "da compilare", "resume_from": 0})
    if start_id is None:
        start_id = int(sh.get("resume_from") or 0) if sh.get("status") == "interrotto" else 0
        if start_id:
            progress(f"↻ Il caricamento precedente di questo file si era interrotto: riprendo dall'ID {start_id}.")
    todo = [r for r in rows if r["id"] >= (start_id or 0)]
    if use_ai is None:
        use_ai = bool(getattr(cfg, "QUESTION_SHEET_USE_AI", True)) and ai_available()
    every = max(1, int(getattr(cfg, "QUESTION_SHEET_SAVE_EVERY", 10)))
    answered = [r for r in todo if r["answer"]]
    stats["answered"] = len(answered)
    progress(f"{path.name}: {len(rows)} domande, {len(answered)} con risposta"
             + (f" (dall'ID {start_id})" if start_id else "") + (" · AI locale attiva" if use_ai else ""))
    deepened: set[str] = set()
    current = 0          # ID della riga in elaborazione (0 = nessuna)
    last_done = 0
    K._training = K._batch = True
    try:
        for i, r in enumerate(answered, 1):
            if should_stop():
                raise KeyboardInterrupt
            current = r["id"]
            item = _item_for(r, sh.get("rows", {}))
            dkey = f"{item.get('key') or K._norm(item['term'])}|{item['field']}|{_hash(item['question'])}"
            h = _hash(r["answer"] + "|" + r["notes"])
            try:
                if reg["done"].get(dkey) == h:
                    stats["already"] += 1
                    k = K.key_of(item["term"]) or K._norm(item["term"])
                    if k not in deepened and classify(r["answer"], item)["kind"] not in (
                            "ignora_domanda", "ignora_termine", "non_so"):
                        deepened.add(k)
                        if deepen_from(item["term"], item["question"], r["answer"], stats, use_ai):
                            stats["deepened_terms"] += 1
                else:
                    kind = apply_answer(item, r["answer"], r["notes"], use_ai, stats)
                    if kind != "non_so":
                        reg = K._sheets()
                        reg["done"][dkey] = h
                    progress(f"  [{r['id']}] {item['term']}: {kind}")
            except K.KnowledgeFileError:
                raise
            except Exception as exc:
                log.exception("questionAI: errore sulla riga %s", r["id"])
                stats["errors"].append(f"ID {r['id']}: {exc}")
                progress(f"  ⚠ ID {r['id']} ({item['term']}): {exc} — riga saltata")
            stats["last_id"] = last_done = r["id"]
            current = 0
            reg = K._sheets()
            sh = reg["sheets"][uid]
            sh.update({"last_id": r["id"], "status": "in caricamento", "resume_from": r["id"] + 1,
                       "file": str(path)})
            if i % every == 0:
                K._write("sheets", reg, strict=False)
                K._flush(strict=False)
        reg = K._sheets()
        reg["sheets"][uid].update({"status": "caricato", "resume_from": 0, "imported": K._now()})
        K._write("sheets", reg, strict=False)
    except KeyboardInterrupt:
        stats["stopped"] = True
        nxt = next((x["id"] for x in answered if x["id"] > last_done), last_done + 1)
        stats["resume_from"] = current or nxt
        reg = K._sheets()
        reg["sheets"][uid].update({"status": "interrotto", "resume_from": stats["resume_from"]})
        K._write("sheets", reg, strict=False)
        progress(f"\n⏸ Caricamento interrotto all'ID {stats['resume_from']}. La conoscenza appresa fino a qui "
                 f"è salvata: ricarica il file {path.name} dall'ID {stats['resume_from']} in poi "
                 f"(al prossimo caricamento dello stesso file riparto da lì in automatico).")
    finally:
        K._training = K._batch = False
        K._flush_final(progress)
    try:
        from webapp import qa
        qa.clear_cache()
    except Exception:
        pass
    return stats


def report(stats: dict) -> str:
    lab = {"conferma": "conferme", "conferma+": "conferme con aggiunte", "correzione": "correzioni",
           "rifiuto": "proposte rifiutate", "discorsiva": "spiegazioni", "si": "«sì» senza dettagli",
           "no": "«no»", "non_so": "«non so» (restano in attesa)", "ignora_domanda": "domande ignorate",
           "ignora_termine": "termini ignorati"}
    kinds = ", ".join(f"{n} {lab.get(k, k)}" for k, n in stats["kinds"].items() if n)
    out = [f"{stats['applied']} risposte acquisite" + (f" ({kinds})" if kinds else "")]
    if stats["already"]:
        out.append(f"{stats['already']} già acquisite in precedenza → approfonditi {stats['deepened_terms']} concetti")
    if stats["new_terms"]:
        out.append(f"{stats['new_terms']} nuovi concetti imparati dalle tue spiegazioni")
    if stats["new_questions"] or stats["deepen"]:
        out.append(f"{stats['new_questions'] + stats['deepen']} nuove domande di approfondimento "
                   f"(esportale con un nuovo questionAI)")
    if stats["errors"]:
        out.append(f"{len(stats['errors'])} righe con errori: " + "; ".join(stats["errors"][:5]))
    if stats["stopped"]:
        out.append(f"INTERROTTO: ricarica il file dall'ID {stats['resume_from']}")
    return "\n".join(out)
