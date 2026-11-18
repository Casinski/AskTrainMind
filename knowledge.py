"""
knowledge.py
------------
Conoscenza dell'AI di AskTrainMind: concetti tecnici ferroviari (sigle,
sistemi, loop, sensori, centraline, configurazioni del treno...) appresi
dai documenti e dalle risposte del developer.

Tutto e' salvato in file JSON leggibili e modificabili a mano nella cartella
KNOWLEDGE_DIR (default: ./knowledge, vedi TRAINING_AI.md):

    glossario.json  concetti appresi: significato, dettagli, relazioni
                    (componenti, sensori, centraline, tarature, eventi TCMS,
                    concetti correlati), informazioni, note per configurazione
    domande.json    domande in sospeso dell'AI e domande/termini ignorati
    passaggi.json   frasi dei documenti di addestramento per ogni concetto
    fonti.json      documenti letti (con lo stato: completato / da riprendere)

Flusso di addestramento (menu developer, AVVIA_DEVELOPER.bat)
    1. train(percorsi): legge PDF/DOCX/TXT/MD, trova sigle e definizioni
       (tabelle delle abbreviazioni, "Nome esteso (SIGLA)", frasi "X is a..."),
       conserva le frasi in cui compaiono i concetti e accoda le domande.
       Interrompibile in qualsiasi momento: riprende dal punto in cui si e'
       fermato.
    2. answer(): il developer risponde, conferma o corregge. Dopo aver
       capito un concetto l'AI pone domande di approfondimento in base alla
       categoria (es. per un loop: elementi coinvolti, sensori, centraline e
       tarature, eventi TCMS; per una configurazione: costruttore, anno,
       treni, tratte).
    3. La conoscenza e' usata da: prompt di analisi (augment), Chiedi
       (server e pagina offline User), vista Esplora (glossario sui termini).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

import config as cfg

log = logging.getLogger(__name__)

CATEGORIES = {
    "sottosistema": "Sottosistema / impianto",
    "loop": "Loop / circuito di sicurezza",
    "funzione": "Funzione / logica del treno",
    "sensore": "Sensore / trasduttore",
    "centralina": "Centralina / unità di controllo",
    "rele": "Relè / contattore / interruttore",
    "attuatore": "Attuatore / valvola / motore",
    "componente": "Altro componente",
    "segnale": "Segnale / variabile / evento",
    "configurazione": "Configurazione / flotta del treno",
    "concetto": "Concetto / modalità di funzionamento",
    "sigla": "Sigla / abbreviazione",
}

# Relazioni di un concetto (chiave -> etichetta)
RELATIONS = {
    "componenti": "Elementi del treno coinvolti",
    "sensori": "Sensori",
    "centraline": "Centraline / unità di controllo",
    "tarature": "Valori di taratura / soglie",
    "eventi_tcms": "Eventi / diagnostica TCMS",
    "correlati": "Concetti correlati",
}

# Informazioni libere (fatti) chieste per categoria
FACTS = {
    "costruttore": "Costruttore",
    "anno": "Anno di costruzione / entrata in servizio",
    "treni": "Treni (veicoli)",
    "tratte": "Dove viaggia / tratte",
    "posizione": "Dove si trova sul treno",
    "baseline": "Baseline software",
}

# Domande di approfondimento per categoria: (campo, domanda)
_DEEPEN_SYSTEM = [
    ("details", "Come funziona «{t}» in pratica? (condizioni, sequenza, effetti sul treno)"),
    ("relations.componenti", "Quali elementi del treno sono coinvolti in «{t}»?"),
    ("relations.sensori", "Ci sono sensori che intervengono in «{t}»? Quali?"),
    ("relations.centraline", "Quali centraline / unità di controllo gestiscono «{t}»?"),
    ("relations.tarature", "Ci sono valori di taratura o soglie per «{t}»? (es. sensore X: allarme a 110 °C)"),
    ("relations.eventi_tcms", "Il TCMS ha degli eventi o diagnostiche che riguardano «{t}»? Quali?"),
    ("relations.correlati", "A quali altri concetti, sistemi o funzioni è collegato «{t}»?"),
]
DEEPEN = {
    "sottosistema": _DEEPEN_SYSTEM,
    "loop": _DEEPEN_SYSTEM,
    "funzione": _DEEPEN_SYSTEM,
    "concetto": [_DEEPEN_SYSTEM[0], _DEEPEN_SYSTEM[1], _DEEPEN_SYSTEM[6]],
    "configurazione": [
        ("facts.costruttore", "Chi è il costruttore di «{t}»?"),
        ("facts.anno", "Quando è stata costruita / è entrata in servizio «{t}»?"),
        ("facts.treni", "Quali treni appartengono a «{t}»?"),
        ("facts.tratte", "Dove viaggiano i treni di «{t}» (paesi, tratte)?"),
        ("details", "In cosa differisce «{t}» dalle altre configurazioni dell'ETR1000?"),
    ],
    "sensore": [
        ("details", "Cosa misura «{t}»?"),
        ("facts.posizione", "Dove è installato «{t}» sul treno?"),
        ("relations.centraline", "Quale centralina legge il segnale di «{t}»?"),
        ("relations.tarature", "Quali sono i valori di taratura / soglie di «{t}»?"),
        ("relations.eventi_tcms", "Quali eventi TCMS genera «{t}» in caso di guasto o superamento soglia?"),
    ],
    "centralina": [
        ("details", "Quali funzioni svolge «{t}»?"),
        ("relations.sensori", "Quali sensori / ingressi gestisce «{t}»?"),
        ("relations.tarature", "«{t}» ha parametri di taratura? Quali?"),
        ("relations.eventi_tcms", "Quali eventi TCMS riguardano «{t}»?"),
    ],
    "rele": [
        ("details", "A cosa serve «{t}» e cosa comanda?"),
        ("relations.correlati", "A quale circuito / loop / sistema appartiene «{t}»?"),
    ],
    "attuatore": [
        ("details", "A cosa serve «{t}» e chi lo comanda?"),
        ("relations.centraline", "Quale centralina comanda «{t}»?"),
    ],
    "componente": [
        ("details", "A cosa serve «{t}» e dove si trova sul treno?"),
        ("relations.correlati", "A quale sistema appartiene «{t}»?"),
    ],
    "segnale": [
        ("details", "Chi genera «{t}» e cosa provoca?"),
        ("relations.eventi_tcms", "«{t}» è associato a eventi TCMS? Quali?"),
    ],
    "sigla": [],
}

FILES = {"glossary": "glossario.json", "questions": "domande.json",
         "passages": "passaggi.json", "sources": "fonti.json"}

TEXT_EXT = {".pdf", ".docx", ".txt", ".md"}

_lock = threading.RLock()
_cache: dict[str, tuple[float, object]] = {}
_dirty: set[str] = set()      # file modificati in memoria durante l'addestramento
_version = 0
_rx_cache: tuple[int, Optional[re.Pattern]] = (-1, None)


class KnowledgeFileError(RuntimeError):
    """File della conoscenza modificato a mano e non piu' valido."""


# ---------------------------------------------------------------------------
# File
# ---------------------------------------------------------------------------

def kdir() -> Path:
    return Path(getattr(cfg, "KNOWLEDGE_DIR", Path(__file__).with_name("knowledge")))


def path(name: str = "glossary") -> Path:
    return kdir() / FILES[name]


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip()).upper()


def _now() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _read(name: str, default):
    p = path(name)
    hit = _cache.get(name)
    try:
        mt = p.stat().st_mtime
    except OSError:
        if hit and hit[0] == -1:
            return hit[1]
        data = json.loads(json.dumps(default))
        _cache[name] = (-1, data)
        return data
    if hit and hit[0] == mt:
        return hit[1]
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig") or "null")
    except ValueError as exc:
        line = getattr(exc, "lineno", "?")
        col = getattr(exc, "colno", "?")
        bak = p.with_suffix(".json.bak")
        raise KnowledgeFileError(
            f"Il file {p} non è un JSON valido (riga {line}, colonna {col}): {exc.msg if hasattr(exc, 'msg') else exc}.\n"
            f"Correggerlo con un editor (attenzione a virgole e virgolette)"
            + (f" oppure ripristinare la copia {bak.name}." if bak.is_file() else ".")) from exc
    if data is None:
        data = json.loads(json.dumps(default))
    _cache[name] = (mt, data)
    return data


def _write(name: str, data) -> None:
    global _version
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.is_file():
        try:
            shutil.copy2(p, p.with_suffix(".json.bak"))
        except OSError:
            pass
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    _cache[name] = (p.stat().st_mtime, data)
    _version += 1


def _flush() -> None:
    for name in list(_dirty):
        hit = _cache.get(name)
        if hit:
            _write(name, hit[1])
        _dirty.discard(name)


def _glossary() -> dict:
    _migrate()
    g = _read("glossary", {"terms": {}})
    if not isinstance(g, dict) or not isinstance(g.get("terms"), dict):
        raise KnowledgeFileError(f"{path('glossary')}: atteso un oggetto {{\"terms\": {{...}}}}")
    return g


def _questions() -> dict:
    q = _read("questions", {"pending": [], "ignored": [], "ignored_terms": []})
    q.setdefault("pending", [])
    q.setdefault("ignored", [])
    q.setdefault("ignored_terms", [])
    return q


def _passages() -> dict:
    return _read("passages", {})


def _sources() -> dict:
    return _read("sources", {})


def _migrate() -> None:
    """Importa il vecchio glossario (HISTORY_DIR/knowledge.json) la prima volta."""
    if path("glossary").exists():
        return
    old = Path(getattr(cfg, "KNOWLEDGE_FILE", "") or "")
    terms: dict = {}
    ignored: list = []
    if old and old.is_file():
        try:
            d = json.loads(old.read_text(encoding="utf-8"))
            for k, t in (d.get("terms") or {}).items():
                terms[_norm(k)] = _complete({**t, "status": "confermato"})
            ignored = list(d.get("ignored") or [])
            log.info(f"Conoscenza importata da {old} ({len(terms)} termini)")
        except Exception as exc:
            log.warning(f"Vecchio glossario {old} non importato: {exc}")
    _write("glossary", {"_info": "Conoscenza dell'AI di AskTrainMind: modificabile a mano (vedi TRAINING_AI.md)",
                        "terms": terms})
    if ignored and not path("questions").exists():
        _write("questions", {"pending": [], "ignored": [], "ignored_terms": ignored})


def _complete(t: dict) -> dict:
    """Aggiunge i campi mancanti a un termine (compatibilita' file scritti a mano)."""
    t = dict(t)
    t.setdefault("term", "")
    t.setdefault("aliases", [])
    t.setdefault("category", "sigla")
    t.setdefault("meaning", "")
    t.setdefault("details", "")
    rel = t.get("relations") if isinstance(t.get("relations"), dict) else {}
    t["relations"] = {k: list(rel.get(k) or []) for k in RELATIONS} | {k: v for k, v in rel.items() if k not in RELATIONS}
    t.setdefault("facts", {})
    t.setdefault("configs", {})
    t.setdefault("notes", "")
    t.setdefault("status", "confermato")
    t.setdefault("sources", [])
    t.setdefault("created", _now())
    t.setdefault("updated", t["created"])
    return t


def load(force: bool = False) -> dict:
    """Vista compatibile: {"terms": {KEY: termine}, "ignored": [...], "sources": {...}}."""
    with _lock:
        if force:
            _cache.clear()
        g = _glossary()
        q = _questions()
        return {"terms": {k: _complete(t) for k, t in g["terms"].items()},
                "ignored": q["ignored_terms"], "sources": _sources()}


def validate() -> list[str]:
    """Controlla i file della conoscenza; restituisce l'elenco degli errori."""
    errs = []
    _cache.clear()
    for name in FILES:
        try:
            {"glossary": _glossary, "questions": _questions,
             "passages": _passages, "sources": _sources}[name]()
        except KnowledgeFileError as exc:
            errs.append(str(exc))
    if not errs:
        for k, t in _glossary()["terms"].items():
            if not isinstance(t, dict) or not t.get("term"):
                errs.append(f"glossario.json: il termine «{k}» non ha il campo \"term\"")
            elif t.get("category") and t["category"] not in CATEGORIES:
                errs.append(f"glossario.json: «{k}» ha categoria sconosciuta «{t['category']}» "
                            f"(valide: {', '.join(CATEGORIES)})")
    return errs


# ---------------------------------------------------------------------------
# Termini
# ---------------------------------------------------------------------------

def all_terms(include_proposed: bool = True) -> list[dict]:
    terms = load()["terms"].values()
    if not include_proposed:
        terms = [t for t in terms if t.get("status") != "proposto"]
    return sorted(terms, key=lambda t: t["term"].upper())


def _alias_map() -> dict[str, str]:
    m = {}
    for k, t in load()["terms"].items():
        m[k] = k
        for a in t.get("aliases", []):
            m.setdefault(_norm(a), k)
    return m


def key_of(term: str) -> Optional[str]:
    return _alias_map().get(_norm(term))


def get(term: str) -> Optional[dict]:
    k = key_of(term)
    return load()["terms"].get(k) if k else None


def upsert(term: str, meaning: str, category: str = "", notes: str = "",
           source: str = "", aliases: Iterable[str] = (), details: Optional[str] = None,
           relations: Optional[dict] = None, facts: Optional[dict] = None,
           status: str = "confermato") -> dict:
    term = (term or "").strip()
    if not term or not (meaning or "").strip():
        raise ValueError("Termine e significato sono obbligatori")
    with _lock:
        g = _glossary()
        k = key_of(term) or _norm(term)
        old = _complete(g["terms"].get(k, {"term": term}))
        rec = dict(old)
        rec.update({
            "term": old.get("term") or term, "meaning": meaning.strip(),
            "category": category if category in CATEGORIES else (old.get("category") or "sigla"),
            "notes": (notes or old.get("notes") or "").strip(),
            "aliases": sorted({a.strip() for a in aliases if a and a.strip() and _norm(a) != k}
                              | set(old.get("aliases", []))),
            "sources": sorted(set(old.get("sources", [])) | ({source} if source else set())),
            "status": status, "updated": _now(),
        })
        if details is not None:
            rec["details"] = details.strip()
        for r, vals in (relations or {}).items():
            rec["relations"][r] = _merge_list(rec["relations"].get(r, []), vals)
        rec["facts"].update({k2: v for k2, v in (facts or {}).items() if v})
        g["terms"][k] = rec
        _write("glossary", g)
        q = _questions()
        if k in q["ignored_terms"]:
            q["ignored_terms"].remove(k)
            _write("questions", q)
        return rec


def _merge_list(old: list, new) -> list:
    if isinstance(new, str):
        new = split_list(new)
    out = list(old)
    low = {x.lower() for x in out}
    for x in new or []:
        x = str(x).strip()
        if x and x.lower() not in low:
            out.append(x)
            low.add(x.lower())
    return out


def split_list(text: str) -> list[str]:
    return [x.strip(" -•\t") for x in re.split(r"[;\n]|,(?![^()]*\))", text or "") if x.strip(" -•\t")]


def set_field(term: str, field: str, value: str, source: str = "") -> dict:
    """Imposta un campo: meaning, details, category, notes, relations.<k>, facts.<k>, configs.<cfg>."""
    with _lock:
        g = _glossary()
        k = key_of(term) or _norm(term)
        rec = _complete(g["terms"].get(k) or {"term": term.strip(), "meaning": ""})
        value = (value or "").strip()
        if field == "details" and rec.get("details") and value and value not in rec["details"]:
            rec["details"] = rec["details"].rstrip() + "\n" + value
        elif field in ("meaning", "details", "notes"):
            rec[field] = value
        elif field == "category":
            if value not in CATEGORIES:
                raise ValueError(f"Categoria non valida: {value}")
            rec["category"] = value
        elif field.startswith("relations."):
            r = field.split(".", 1)[1]
            rec["relations"][r] = _merge_list(rec["relations"].get(r, []), value)
        elif field.startswith("facts."):
            rec["facts"][field.split(".", 1)[1]] = value
        elif field.startswith("configs."):
            rec["configs"][field.split(".", 1)[1]] = value
        elif field == "aliases":
            rec["aliases"] = _merge_list(rec["aliases"], value)
        else:
            raise ValueError(f"Campo sconosciuto: {field}")
        if source:
            rec["sources"] = sorted(set(rec["sources"]) | {source})
        rec["updated"] = _now()
        g["terms"][k] = rec
        _write("glossary", g)
        return rec


def confirm(term: str) -> None:
    with _lock:
        g = _glossary()
        k = key_of(term)
        if k and k in g["terms"]:
            g["terms"][k]["status"] = "confermato"
            g["terms"][k]["updated"] = _now()
            _write("glossary", g)


def delete(term: str) -> bool:
    with _lock:
        g = _glossary()
        k = key_of(term)
        if not k or k not in g["terms"]:
            return False
        g["terms"].pop(k)
        _write("glossary", g)
        q = _questions()
        q["pending"] = [x for x in q["pending"] if x.get("key") != k]
        _write("questions", q)
        return True


def ignore(term: str) -> None:
    """Il termine non va piu' proposto (non e' tecnico / non interessa)."""
    with _lock:
        q = _questions()
        k = _norm(term)
        if k not in q["ignored_terms"]:
            q["ignored_terms"].append(k)
        q["pending"] = [x for x in q["pending"] if x.get("key") != k]
        _write("questions", q)


def mark_source(source: str, n_terms: int) -> None:
    with _lock:
        s = _sources()
        s.setdefault(source, {}).update({"date": _now(), "terms": n_terms, "done": True})
        _write("sources", s)


# ---------------------------------------------------------------------------
# Domande dell'AI
# ---------------------------------------------------------------------------

def pending() -> list[dict]:
    q = _questions()["pending"]
    return sorted(q, key=lambda x: (x.get("priority", 5), x.get("created_ts", 0)))


def _qid(key: str, field: str) -> str:
    return hashlib.sha1(f"{key}|{field}".encode()).hexdigest()[:10]


def enqueue(term: str, field: str, question: str, kind: str = "deepen", proposal: str = "",
            context: str = "", source: str = "", page: int = 0, priority: int = 5,
            save: bool = True, q: Optional[dict] = None) -> bool:
    """Accoda una domanda (una sola per termine+campo). False se gia' presente o ignorata."""
    with _lock:
        q = q if q is not None else _questions()
        k = key_of(term) or _norm(term)
        if k in q["ignored_terms"] or f"{k}|{field}" in q["ignored"]:
            return False
        qid = _qid(k, field)
        for x in q["pending"]:
            if x["id"] == qid:
                if proposal and not x.get("proposal"):
                    x["proposal"] = proposal
                if context and not x.get("context"):
                    x["context"], x["source"], x["page"] = context, source, page
                if save:
                    _write("questions", q)
                return False
        q["pending"].append({"id": qid, "key": k, "term": term.strip(), "field": field, "kind": kind,
                             "question": question, "proposal": proposal, "context": context[:600],
                             "source": source, "page": page, "priority": priority,
                             "created": _now(), "created_ts": time.time()})
        if save:
            _write("questions", q)
        return True


def deepen(term: str, save: bool = True) -> int:
    """Accoda le domande di approfondimento per la categoria del concetto."""
    t = get(term)
    if not t:
        return 0
    n = 0
    q = _questions()
    for field, tmpl in DEEPEN.get(t.get("category", ""), []):
        if _field_value(t, field) or (field == "relations.eventi_tcms" and _norm(t["term"]) == "TCMS"):
            continue
        if enqueue(t["term"], field, tmpl.format(t=t["term"]), "deepen", priority=6, save=False, q=q):
            n += 1
    if n and save:
        _write("questions", q)
    return n


def _field_value(t: dict, field: str):
    if "." in field:
        a, b = field.split(".", 1)
        return (t.get(a) or {}).get(b)
    return t.get(field)


def ask_meaning(term: str, context: str = "", source: str = "", page: int = 0,
                proposal: str = "", priority: int = 4) -> bool:
    """Accoda la domanda "cos'e' X?" (o la verifica se c'e' una proposta)."""
    if proposal:
        return enqueue(term, "meaning", f"Ho capito che «{term}» significa: «{proposal}». È corretto?",
                       "verify", proposal, context, source, page, priority=3)
    return enqueue(term, "meaning", f"Cos'è «{term}»? Spiegami in una o due frasi che cosa significa "
                                    f"e che ruolo ha sul treno.", "meaning", "", context, source, page, priority)


YES = {"s", "si", "sì", "y", "yes", "ok", "giusto", "corretto", "esatto", "confermo"}


def answer(qid: str, text: str, category: str = "", aliases: str = "") -> str:
    """
    Applica la risposta del developer a una domanda in sospeso.
    Per le domande di significato: "s" conferma la proposta, altrimenti il
    testo e' il significato corretto. Restituisce un messaggio di esito.
    """
    with _lock:
        q = _questions()
        item = next((x for x in q["pending"] if x["id"] == qid), None)
        if not item:
            raise KeyError("Domanda non trovata (forse già risposta)")
        text = (text or "").strip()
        if not text:
            raise ValueError("Risposta vuota")
        term, field = item["term"], item["field"]
        if field == "meaning":
            meaning = item.get("proposal") if text.lower() in YES and item.get("proposal") else text
            old = get(term)
            cat = category or (old or {}).get("category") or guess_category(term, item.get("context", "") + " " + meaning)
            upsert(term, meaning, cat, source=item.get("source", ""),
                   aliases=split_list(aliases), status="confermato")
            attach_passages(term)
            msg = f"Imparato: {term} = {meaning}"
            q = _questions()
            q["pending"] = [x for x in q["pending"] if x["id"] != qid]
            _write("questions", q)
            n = deepen(term)
            if n:
                msg += f" ({n} domande di approfondimento accodate)"
            return msg
        if field.startswith("relations.") or field.startswith("facts.") or field in ("details", "notes"):
            if text.lower() in YES and item.get("proposal"):
                text = item["proposal"]
            if not get(term):
                upsert(term, item.get("proposal") or term, "concetto", status="proposto")
            set_field(term, field, text, source="risposta del developer")
        elif field == "category":
            set_field(term, "category", text)
        else:
            set_field(term, field, text)
        q = _questions()
        q["pending"] = [x for x in q["pending"] if x["id"] != qid]
        _write("questions", q)
        return f"Salvato: {term} → {field_label(field)}"


def skip(qid: str) -> None:
    """Rimanda la domanda in fondo alla coda."""
    with _lock:
        q = _questions()
        for x in q["pending"]:
            if x["id"] == qid:
                x["created_ts"] = time.time()
                x["priority"] = min(9, x.get("priority", 5) + 1)
        _write("questions", q)


def drop(qid: str, whole_term: bool = False) -> None:
    """Non porre piu' questa domanda (o nessuna domanda sul termine)."""
    with _lock:
        q = _questions()
        item = next((x for x in q["pending"] if x["id"] == qid), None)
        if not item:
            return
        if whole_term:
            if item["key"] not in q["ignored_terms"]:
                q["ignored_terms"].append(item["key"])
            q["pending"] = [x for x in q["pending"] if x["key"] != item["key"]]
        else:
            q["ignored"].append(f"{item['key']}|{item['field']}")
            q["pending"] = [x for x in q["pending"] if x["id"] != qid]
        _write("questions", q)


def field_label(field: str) -> str:
    if field.startswith("relations."):
        return RELATIONS.get(field[10:], field[10:])
    if field.startswith("facts."):
        return FACTS.get(field[6:], field[6:])
    return {"meaning": "Significato", "details": "Come funziona / dettagli", "notes": "Note",
            "category": "Categoria"}.get(field, field)


# ---------------------------------------------------------------------------
# Uso della conoscenza
# ---------------------------------------------------------------------------

def _regex() -> Optional[re.Pattern]:
    global _rx_cache
    d = load()
    if _rx_cache[0] == _version:
        return _rx_cache[1]
    keys = []
    for t in d["terms"].values():
        keys.append(t["term"])
        keys.extend(t.get("aliases", []))
    keys = sorted({k for k in keys if len(k) >= 2}, key=len, reverse=True)
    rx = re.compile(r"(?<![\w\-])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w\-])", re.I) if keys else None
    _rx_cache = (_version, rx)
    return rx


def glossary_for(text: str, limit: int = 40) -> list[dict]:
    """Termini appresi presenti nel testo (in ordine di frequenza)."""
    rx = _regex()
    if not rx or not text:
        return []
    d = load()
    alias = _alias_map()
    cnt: Counter = Counter()
    for m in rx.finditer(text):
        k = alias.get(_norm(m.group(1)))
        if k:
            cnt[k] += 1
    return [d["terms"][k] for k, _ in cnt.most_common(limit)]


def glossary_text(terms: list[dict]) -> str:
    out = []
    for t in terms:
        cat = CATEGORIES.get(t.get("category", ""), "")
        line = f"- {t['term']}: {t['meaning']}"
        if cat:
            line += f" [{cat}]"
        if t.get("details"):
            line += f" — {' '.join(t['details'].split())[:300]}"
        rel = "; ".join(f"{RELATIONS[r]}: {', '.join(v)}" for r, v in (t.get("relations") or {}).items()
                        if v and r in RELATIONS)
        if rel:
            line += f" ({rel[:400]})"
        if t.get("notes"):
            line += f" — {t['notes']}"
        out.append(line)
    return "\n".join(out)


def augment(prompt: str) -> str:
    """
    Aggiunge al prompt il glossario dei termini appresi che vi compaiono.
    Usato da ai_synthesizer._call_ollama (analisi) e dalla sezione Chiedi.
    """
    if not getattr(cfg, "KNOWLEDGE_USE_IN_ANALYSIS", True):
        return prompt
    try:
        terms = [t for t in glossary_for(prompt, int(getattr(cfg, "KNOWLEDGE_MAX_TERMS_IN_PROMPT", 25)))
                 if t.get("status") != "proposto"]
    except Exception as exc:
        log.debug(f"Conoscenza non applicata: {exc}")
        return prompt
    if not terms:
        return prompt
    return ("GLOSSARIO TECNICO ETR1000 (definizioni fornite dall'esperto: usale per interpretare "
            "correttamente sigle e componenti, senza citarle se non servono):\n"
            + glossary_text(terms) + "\n\n" + prompt)


def passages(term: str) -> list[dict]:
    k = key_of(term) or _norm(term)
    return list(_passages().get(k, []))


def term_markdown(t: dict, with_passages: bool = True) -> str:
    """Scheda di un concetto in Markdown (Chiedi, terminale)."""
    cat = CATEGORIES.get(t.get("category", ""), "")
    h = f"**{t['term']}**" + (f" — *{cat}*" if cat else "")
    if t.get("aliases"):
        h += f" (anche: {', '.join(t['aliases'])})"
    out = [h, "", t.get("meaning", "")]
    if t.get("status") == "proposto":
        out.append("> ⚠️ Significato proposto dall'AI dai documenti, non ancora confermato dal developer.")
    if t.get("details"):
        out += ["", t["details"]]
    lines = []
    for f, lab in FACTS.items():
        v = (t.get("facts") or {}).get(f)
        if v:
            lines.append(f"- **{lab}:** {v}")
    for r, lab in RELATIONS.items():
        v = (t.get("relations") or {}).get(r)
        if v:
            lines.append(f"- **{lab}:** {', '.join(v)}")
    for c, v in (t.get("configs") or {}).items():
        if v:
            lines.append(f"- **{c}:** {v}")
    if lines:
        out += [""] + lines
    if t.get("notes"):
        out += ["", f"*Note:* {t['notes']}"]
    if with_passages:
        ps = passages(t["term"])[:3]
        if ps:
            out += ["", "Dai documenti di addestramento:"]
            out += [f"> {p['text'][:300]} — *{p['source']}{', pag. ' + str(p['page']) if p.get('page') else ''}*" for p in ps]
    return "\n".join(out).strip()


# Parole italiane comuni (non sono concetti da imparare)
STOP_IT = set("""il lo la i gli le un uno una di a da in con su per tra fra del dello della dei degli delle
al allo alla ai agli alle dal dallo dalla dai dagli dalle nel nello nella nei negli nelle sul sullo sulla
sui sugli sulle col e ed o od ma se che chi cui non come dove quando quanto quanti quante quale quali cosa
cos cose è e' sono sia siano era erano essere ha hanno ho hai avere fa fanno fare può possono puo deve
devono questo questa questi queste quello quella quelli quelle mi ti ci vi si ne lo anche più piu meno
molto poco tutto tutti tutte ogni altro altri altre stesso stessa già gia ancora poi però pero quindi
funziona funzionano funzionamento funzione funzioni spiega spiegami spiegare descrivi descrivere dimmi
mostra mostrami treno treni configurazione configurazioni base differenza differenze differenti diverso
diversi uguale uguali requisito requisiti documento documenti pagina pagine sistema sistemi elemento
elementi coinvolti coinvolto gestisce gestiscono valori valore tipo modo parte sul sulla nelle volte
costruito costruita costruttore viaggiano viaggia quali sapere vorrei voglio puoi potresti dove rispetto
tra loro esempio caso casi eventi evento ci sono hanno""".split())

_ACR = re.compile(r"(?<![\w\-])([A-Z][A-Z0-9]{1,9}(?:[-_/][A-Z0-9]{1,8}){0,2})(?![\w\-])")
_EQUIP = re.compile(r"(?<![\w\-])([A-Z]{1,3}-[A-Z]{1,2}\d{2,4}[A-Z0-9]*)(?![\w\-])")
_ASKED = re.compile(r"(?:cos['’]?\s*[eè]|cosa\s+[eè]|che\s+cos['’]?\s*[eè]|cosa\s+significa|cosa\s+vuol\s+dire|"
                    r"significato\s+di|cosa\s+sono|chi\s+[eè]|definizione\s+di|parlami\s+d[ie]l?l?[oa]?)\s+"
                    r"(?:(?:il|lo|la|i|gli|le|un|uno|una|l['’])\s*)?([\w\-/]+(?:\s+[\w\-/]+)?)", re.I)


def unknown_words(question: str, vocab: Optional[set] = None, exclude: Iterable[str] = ()) -> list[str]:
    """
    Parole della domanda che sembrano concetti tecnici non ancora appresi:
    sigle (DNRA, HABD...), parole dopo «cos'è / cosa significa...», parole
    del lessico tecnico dei documenti (vocab) non presenti nel glossario.
    """
    alias = _alias_map()
    excl = {_norm(x) for x in exclude}
    out: list[str] = []

    def add(w: str):
        w = w.strip(" ?.,;:!'\"«»()")
        if len(w) < 2 or _norm(w) in alias or _norm(w) in excl or w.lower() in STOP_IT:
            return
        if any(_norm(w) == _norm(x) for x in out):
            return
        out.append(w)

    for m in _ASKED.finditer(question):
        phrase = m.group(1)
        first = phrase.split()[0]
        add(first if first.lower() not in STOP_IT else phrase)
    for m in _ACR.finditer(question):
        w = m.group(1)
        if not re.search(r"[A-Z]{2}", w) or w in _STOP:
            continue
        add(w)
    if vocab:
        for w in re.findall(r"[A-Za-zÀ-ù][\w\-]{2,}", question):
            if w.lower() in vocab and w.lower() not in STOP_IT and not re.search(r"[_\d]", w):
                add(w.lower())
    return out


def note_unknown(words: Iterable[str], question: str, source: str = "Chiedi") -> int:
    """Accoda le domande "cos'e' X?" per le parole sconosciute di una domanda."""
    n = 0
    for w in words:
        if ask_meaning(w, context=f"Domanda in Chiedi: {question}", source=source, priority=2):
            n += 1
    return n


def export_snapshot(include_proposed: Optional[bool] = None) -> dict:
    """Conoscenza da incorporare nella pagina offline (solo lettura)."""
    if include_proposed is None:
        include_proposed = bool(getattr(cfg, "USER_EXPORT_PROPOSED", True))
    terms = all_terms(include_proposed)
    ps = _passages()
    keep = {key_of(t["term"]) for t in terms}
    return {"terms": terms, "categories": CATEGORIES, "relations": RELATIONS, "facts": FACTS,
            "passages": {k: v[:4] for k, v in ps.items() if k in keep},
            "pending": len(_questions()["pending"]), "updated": _now()}


def summary() -> dict:
    terms = all_terms()
    src = _sources()
    return {"terms": len(terms), "confirmed": sum(1 for t in terms if t.get("status") != "proposto"),
            "proposed": sum(1 for t in terms if t.get("status") == "proposto"),
            "pending": len(_questions()["pending"]),
            "sources": len(src), "sources_done": sum(1 for s in src.values() if s.get("done")),
            "dir": str(kdir())}


# ---------------------------------------------------------------------------
# Estrazione dai documenti
# ---------------------------------------------------------------------------

_STOP = set("""ID AND OR NOT IF THE TBD NA FRS TRS PDF OK ON OFF II III IV VI VII VIII IX XI XII YES NO
FOR TO OF IN BY AT AS IS BE IT AN ALL ANY SHALL MUST WITH FROM THIS THAT ARE NOTE TABLE FIGURE REV REF
DOC PAGE SIL SIL0 SIL1 SIL2 SIL3 SIL4 MAX MIN NR VZ VZI DE EN IT FR ES DA DI DEL CON PER IL LA LE UN UNA
TYPE DERIVED CONCEPT EUROPE ZEFIRO TCN IDU EVENT EVENTS DELETED WARNING ALARM TRUE FALSE STATUS STATE INFO
ERROR NEW OLD HIGH LOW RESET SET ACTIVE INACTIVE DATE NOTES SYSTEM TEXT NONE ALL SEE ITEM VALUE TIME
DESCRIPTION REQUIREMENT REQUIREMENTS SAFETY LEVEL APPLICABILITY DETAILS CONFIDENTIAL PROPRIETARY
WHEN THEN ELSE CASE ONLY ALSO EACH BOTH ETC SEC REV ISSUE VERSION APPROVED CHECKED PREPARED""".split())
_ABBR_LINE = re.compile(r"^\s*([A-Z][A-Z0-9\-/]{1,12})\s{1,}[-–:=]?\s*([A-Z][A-Za-z].{3,120})$")
_INLINE_LONG_ACR = re.compile(r"((?:[A-Z][a-z]+[\s\-]+){1,6}[A-Z][a-z]+)\s*\(([A-Z][A-Z0-9]{1,9})\)")
_INLINE_ACR_LONG = re.compile(r"(?<![\w\-])([A-Z][A-Z0-9]{1,9})\s*\(((?:[A-Z][a-z]+[\s\-]+){1,6}[A-Z][a-z]+)\)")


def _abbreviations(text: str) -> dict[str, str]:
    """Definizioni dalle tabelle 'Abbreviations / Acronyms' del documento."""
    out: dict[str, str] = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        m = _ABBR_LINE.match(l)
        if m and m.group(1) not in _STOP and not m.group(2).rstrip().endswith(":"):
            out.setdefault(m.group(1), m.group(2).strip())
            continue
        if re.fullmatch(r"[A-Z][A-Z0-9\-/]{1,12}", l) and l not in _STOP and i + 1 < len(lines):
            nxt = lines[i + 1]
            if re.match(r"^[A-Z][a-z]", nxt) and 4 <= len(nxt) <= 120 and not nxt.endswith(":") \
                    and not re.fullmatch(r"[A-Z0-9\-/ ]+", nxt) and nxt.split()[0].lower() not in ("derived", "description", "type"):
                out.setdefault(l, nxt)
    return out


def _initials_ok(acr: str, long: str) -> bool:
    ini = "".join(w[0] for w in re.split(r"[\s\-]+", long) if w).upper()
    letters = re.sub(r"[^A-Z]", "", acr)
    return bool(letters) and (ini.startswith(letters) or letters in ini or
                              sum(1 for c in letters if c in ini) >= max(2, len(letters) - 1))


def inline_definitions(text: str) -> dict[str, str]:
    """«Hot Axle Box Detection (HABD)» e «HABD (Hot Axle Box Detection)»."""
    flat = " ".join(text.split())
    out = {}
    for m in _INLINE_LONG_ACR.finditer(flat):
        long, acr = m.group(1).strip(), m.group(2)
        words = long.split()
        for n in range(len(words), 0, -1):   # prendi le ultime parole coerenti con la sigla
            cand = " ".join(words[-n:])
            if _initials_ok(acr, cand) and len(cand.split()) >= max(1, len(re.sub(r"[^A-Z]", "", acr)) - 1):
                out.setdefault(acr, cand)
                break
    for m in _INLINE_ACR_LONG.finditer(flat):
        acr, long = m.group(1), m.group(2).strip()
        if acr not in _STOP and _initials_ok(acr, long):
            out.setdefault(acr, long)
    return {k: v for k, v in out.items() if k not in _STOP}


def _definition_sentence(term: str, sentence: str) -> bool:
    t = re.escape(term)
    return bool(re.search(rf"(?<![\w\-]){t}(?![\w\-])\s*(?:\([^)]*\)\s*)?(?:is|are|means|refers to|is defined as|"
                          rf"è|e'|sono|indica|significa|si intende|:)\s+\w", sentence, re.I)
                or re.search(rf"(?:the|a|an|il|la|lo|un|una)\s+{t}\s+(?:is|are|è|e')\s", sentence, re.I))


def guess_category(term: str, ctx: str) -> str:
    c = ctx.lower()
    if re.fullmatch(r"V[ZI][\w\-]*", term or ""):
        return "configurazione"
    if _EQUIP.fullmatch(term or ""):
        if re.search(r"\brel[eèa]|relay|contactor|contattor|breaker|interruttor|switch|fuse|fusibil", c):
            return "rele"
        return "componente"
    if re.search(r"\bloop\b|anello|safety (circuit|loop)|circuito di sicurezza", c):
        return "loop"
    if re.search(r"sensor|transducer|probe|sonda|pt100|thermo|pressure switch", c):
        return "sensore"
    if re.search(r"control unit|\becu\b|\bunit\b|centralin|controller|computer|\bplc\b", c):
        return "centralina"
    if re.search(r"valve|valvol|motor|actuator|attuator|cylinder|pump|compress", c):
        return "attuatore"
    if re.search(r"signal|segnal|event|evento|bit\b|variable", c):
        return "segnale"
    if re.search(r"system|sistema|subsystem|impianto", c):
        return "sottosistema"
    if re.search(r"function|funzion|mode|modalit", c):
        return "funzione"
    return "sigla"


def _sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [s for s in re.split(r"(?<=[.;!?])\s+(?=[A-Z0-9«\"(])", flat) if 25 <= len(s) <= 500]


def _prose(s: str) -> bool:
    """Frase di testo vero (non elenco di codici requisito, indici, tabelle di numeri)."""
    words = s.split()
    if len(words) < 5:
        return False
    codes = sum(1 for w in words if w.count(".") >= 2 or w.count("_") >= 1 or sum(ch.isdigit() for ch in w) >= 2)
    return codes / len(words) < 0.3 and sum(ch.isalpha() for ch in s) / len(s) > 0.6


def candidates(pages: list[tuple[int, str]], source: str = "", limit: int = 40) -> list[dict]:
    """
    Termini tecnici da chiarire presenti nelle pagine [(n_pagina, testo)].
    Esclude quelli gia' appresi o ignorati. Ordinati per frequenza.
    """
    d = load()
    known = set(_alias_map()) | set(d["ignored"])
    full = "\n".join(t for _p, t in pages)
    abbr = {**inline_definitions(full), **_abbreviations(full)}
    cnt, first = _count_terms(pages)
    out = []
    for w, n in cnt.most_common():
        if _norm(w) in known:
            continue
        if n < 2 and w not in abbr:
            continue
        pg, ctx = first[w]
        out.append({"term": w, "count": n, "page": pg, "context": ctx, "source": source,
                    "proposal": abbr.get(w, ""),
                    "category": guess_category(w, ctx + " " + abbr.get(w, ""))})
        if len(out) >= limit:
            break
    return out


def _count_terms(pages: list[tuple[int, str]]):
    cnt: Counter = Counter()
    first: dict[str, tuple[int, str]] = {}
    for pg, txt in pages:
        flat = " ".join(txt.split())
        for rx in (_EQUIP, _ACR):
            for m in rx.finditer(flat):
                w = m.group(1).strip("-_/")
                if len(w) < 2 or w in _STOP or w.isdigit() or re.fullmatch(r"[A-Z]\d*", w):
                    continue
                if re.fullmatch(r"\d+[A-Z]+|[A-Z]{1,2}\d{3,}", w):   # codici documento / numeri
                    continue
                cnt[w] += 1
                if w not in first:
                    a, b = max(0, m.start() - 140), min(len(flat), m.end() + 140)
                    first[w] = (pg, ("…" if a else "") + flat[a:b] + ("…" if b < len(flat) else ""))
    return cnt, first


def question_for(c: dict) -> str:
    """Domanda in italiano da porre all'utente per il termine candidato."""
    t = c["term"]
    if _EQUIP.fullmatch(t):
        return (f"Nel documento compare l'apparecchiatura «{t}» ({c['count']} volte). "
                f"Che cos'è (relè, interruttore, sensore…) e a cosa serve?")
    if c.get("proposal"):
        return f"Ho capito che «{t}» significa: «{c['proposal']}». È corretto?"
    return (f"Cosa significa «{t}» (compare {c['count']} volte)? È un sensore, una centralina, "
            f"un segnale, un sottosistema…?")


# ---------------------------------------------------------------------------
# Lettura dei documenti (con cache del testo per la ricerca dei passaggi)
# ---------------------------------------------------------------------------

def _corpus_dir() -> Path:
    base = Path(getattr(cfg, "CACHE_DIR", kdir() / ".cache"))
    return base / "knowledge_corpus"


def _sig(p: Path) -> str:
    st = p.stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def _long(p) -> str:
    """Su Windows usa il prefisso per percorsi lunghi (oltre 260 caratteri)."""
    s = str(p)
    if os.name != "nt" or s.startswith("\\\\?\\"):
        return s
    s = os.path.abspath(s)
    return "\\\\?\\UNC\\" + s[2:] if s.startswith("\\\\") else "\\\\?\\" + s


def _plain(p) -> Path:
    s = str(p)
    if s.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + s[8:])
    return Path(s[4:] if s.startswith("\\\\?\\") else s)


def _src_name(p: Path) -> str:
    p = _plain(p)
    try:
        r = p.resolve()
    except OSError:
        r = Path(os.path.abspath(p))
    try:
        return r.relative_to(Path(__file__).resolve().parent).as_posix()
    except ValueError:
        return str(r)


def iter_files(paths: Iterable, progress=None) -> list[Path]:
    """Elenca i documenti leggibili. Cartelle/file mancanti, irraggiungibili (es. OneDrive non
    sincronizzato) o con percorso troppo lungo vengono saltati senza fermare la scansione."""
    def warn(msg):
        log.info(msg.strip())
        if progress:
            progress(msg)

    def ok(name: str) -> bool:
        return os.path.splitext(name)[1].lower() in TEXT_EXT and not name.startswith("~$")

    out: list[Path] = []
    skipped = 0
    for raw in paths:
        p = Path(str(raw).strip().strip('"'))
        lp = _long(p)
        try:
            if os.path.isdir(lp):
                def onerr(exc):
                    nonlocal skipped
                    skipped += 1
                    warn(f"  ⚠ Cartella saltata: {_plain(getattr(exc, 'filename', '') or '')} ({exc.strerror or exc})")
                found = []
                for root, dirs, names in os.walk(lp, onerror=onerr):
                    dirs.sort()
                    found += [Path(root) / n for n in names if ok(n)]
                out += sorted(found)
            elif os.path.isfile(lp) and ok(p.name):
                out.append(Path(lp))
            else:
                warn(f"  ⚠ Percorso non trovato, saltato: {p}")
        except OSError as exc:
            warn(f"  ⚠ Percorso saltato: {p} ({exc})")
    if skipped:
        warn(f"  ⚠ {skipped} cartelle non accessibili saltate; la lettura prosegue con le altre.")
    seen, res = set(), []
    for p in out:
        try:
            r = os.path.normcase(os.path.realpath(p))
        except OSError:
            r = str(p)
        if r not in seen:
            seen.add(r)
            res.append(p)
    return res


def page_count(p: Path) -> int:
    if p.suffix.lower() == ".pdf":
        import fitz
        with fitz.open(str(p)) as doc:
            return doc.page_count
    return len(_text_pages(p))


def _text_pages(p: Path) -> list[str]:
    if p.suffix.lower() == ".docx":
        try:
            import docx
        except ImportError as exc:
            raise RuntimeError("Per i file .docx installare python-docx (pip install python-docx)") from exc
        d = docx.Document(str(p))
        paras = [x.text for x in d.paragraphs if x.text.strip()]
        for t in d.tables:
            for row in t.rows:
                paras.append("  ".join(c.text.strip() for c in row.cells))
        text = "\n".join(paras)
    else:
        text = p.read_text(encoding="utf-8", errors="replace")
    chunks, buf = [], []
    for line in text.splitlines():
        buf.append(line)
        if sum(len(x) for x in buf) > 3000:
            chunks.append("\n".join(buf))
            buf = []
    if buf:
        chunks.append("\n".join(buf))
    return chunks or [""]


def read_page(p: Path, n: int, _doc=None) -> str:
    if p.suffix.lower() == ".pdf":
        return _doc.load_page(n - 1).get_text() if _doc is not None else ""
    return _text_pages(p)[n - 1]


def _corpus_path(p: Path) -> Path:
    return _corpus_dir() / (hashlib.sha1(str(_plain(p).resolve()).encode()).hexdigest()[:16] + ".json")


def _corpus_save(p: Path, pages: dict) -> None:
    cp = _corpus_path(p)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"source": _src_name(p), "pages": pages}, ensure_ascii=False), encoding="utf-8")


def search_corpus(term: str, limit: int = 6) -> list[dict]:
    """Frasi dei documenti gia' letti che contengono il termine (definizioni prima)."""
    d = _corpus_dir()
    if not d.is_dir() or not term.strip():
        return []
    rx = re.compile(rf"(?<![\w\-]){re.escape(term.strip())}(?![\w\-])", re.I)
    defs, other = [], []
    for f in d.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for pg, txt in c.get("pages", {}).items():
            if not rx.search(txt):
                continue
            for s in _sentences(txt):
                if rx.search(s) and _prose(s):
                    it = {"text": s, "source": Path(c["source"]).name, "page": int(pg)}
                    (defs if _definition_sentence(term, s) else other).append(it)
        if len(defs) >= limit:
            break
    return (defs + other)[:limit]


def attach_passages(term: str, items: Optional[list[dict]] = None) -> int:
    """Associa al concetto le frasi dei documenti (dal corpus se non indicate)."""
    k = key_of(term) or _norm(term)
    items = items if items is not None else search_corpus(term, int(getattr(cfg, "KNOWLEDGE_MAX_PASSAGES", 8)))
    if not items:
        return 0
    with _lock:
        ps = _passages()
        cur = ps.setdefault(k, [])
        have = {x["text"] for x in cur}
        n = 0
        for it in items:
            if it["text"] not in have and len(cur) < int(getattr(cfg, "KNOWLEDGE_MAX_PASSAGES", 8)):
                cur.append(it)
                have.add(it["text"])
                n += 1
        if n:
            _write("passages", ps)
        return n


# ---------------------------------------------------------------------------
# Addestramento
# ---------------------------------------------------------------------------

def train(paths: Iterable, progress: Callable[[str], None] = print,
          should_stop: Callable[[], bool] = lambda: False, use_ai: Optional[bool] = None) -> dict:
    """
    Legge i documenti e impara: definizioni (tabelle delle abbreviazioni,
    definizioni nel testo), frasi sui concetti noti o in attesa di risposta,
    sigle ricorrenti da chiarire (accodate come domande).

    Interrompibile: should_stop() viene controllato dopo ogni pagina; con
    Ctrl+C (KeyboardInterrupt) lo stato viene salvato e l'addestramento
    riprende dalla pagina successiva al prossimo avvio.
    """
    use_ai = bool(getattr(cfg, "KNOWLEDGE_USE_OLLAMA", False)) if use_ai is None else use_ai
    files = iter_files(paths, progress)
    stats = {"files": len(files), "read": 0, "skipped": 0, "pages": 0, "definitions": 0,
             "questions": 0, "passages": 0, "errors": 0, "stopped": False}
    if not files:
        progress("Nessun documento PDF/DOCX/TXT/MD trovato nei percorsi indicati.")
        return stats
    max_pages = int(getattr(cfg, "KNOWLEDGE_MAX_PAGES", 0) or 0)
    max_q = int(getattr(cfg, "KNOWLEDGE_MAX_QUESTIONS", 40))
    try:
        for i, p in enumerate(files, 1):
            name = _src_name(p)
            src = _sources()
            st = src.get(name, {})
            try:
                sig = _sig(p)
            except OSError as exc:
                stats["errors"] += 1
                progress(f"  ⚠ {p.name}: file non accessibile, saltato ({exc})")
                continue
            if st.get("sig") == sig and st.get("done"):
                stats["skipped"] += 1
                continue
            if st.get("sig") != sig:
                st = {"sig": sig, "page": 0, "done": False, "cnt": {}, "first": {}, "defs": {}}
            try:
                n = page_count(p)
            except Exception as exc:
                stats["errors"] += 1
                progress(f"  ⚠ {p.name}: non leggibile, saltato ({exc})")
                continue
            last = min(n, max_pages) if max_pages else n
            start = int(st.get("page", 0)) + 1
            progress(f"[{i}/{len(files)}] {p.name} — pagine {start}-{last} di {n}"
                     + (" (ripresa)" if start > 1 else ""))
            try:
                stopped, corpus = _train_file(p, name, st, start, last, stats, progress, should_stop)
            except Exception as exc:
                stats["errors"] += 1
                log.exception("Addestramento: errore su %s", p)
                progress(f"  ⚠ {p.name}: errore durante la lettura, saltato ({exc})")
                continue
            st["pages"] = n
            st["date"] = _now()
            if stopped:
                _save_source(name, st)
                stats["stopped"] = True
                progress(f"  ⏸ Interrotto a pag. {st['page']}: riprenderà da qui al prossimo addestramento.")
                break
            try:
                nq, nd = _finish_file(p, name, st, corpus, max_q, use_ai, progress)
            except Exception as exc:
                stats["errors"] += 1
                log.exception("Addestramento: errore finale su %s", p)
                progress(f"  ⚠ {p.name}: errore nell'elaborazione finale, saltato ({exc})")
                continue
            stats["questions"] += nq
            stats["definitions"] += nd
            st["done"] = True
            for x in ("cnt", "first", "defs"):
                st.pop(x, None)
            _save_source(name, st)
            stats["read"] += 1
    except KeyboardInterrupt:
        _flush()
        stats["stopped"] = True
        progress("\n  ⏸ Addestramento interrotto (Ctrl+C): stato salvato, si riprende dal punto raggiunto.")
    _flush()
    return stats


def _save_source(name: str, st: dict) -> None:
    with _lock:
        _flush()
        s = _sources()
        if "cnt" in st:   # conserva solo i candidati piu' frequenti
            st["cnt"] = dict(Counter(st["cnt"]).most_common(400))
            st["first"] = {k: v for k, v in st.get("first", {}).items() if k in st["cnt"]}
        s[name] = st
        _write("sources", s)


def _train_file(p: Path, name: str, st: dict, start: int, last: int, stats: dict,
                progress, should_stop) -> tuple[bool, dict]:
    doc = None
    if p.suffix.lower() == ".pdf":
        import fitz
        doc = fitz.open(str(p))
    corpus_file = _corpus_path(p)
    try:
        corpus = json.loads(corpus_file.read_text(encoding="utf-8"))["pages"] if corpus_file.is_file() and start > 1 else {}
    except (ValueError, KeyError):
        corpus = {}
    try:
        targets = _target_regex()
        for pg in range(start, last + 1):
            try:
                txt = read_page(p, pg, doc)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                log.debug(f"{p.name} pag. {pg}: {exc}")
                txt = ""
            corpus[str(pg)] = txt
            stats["pages"] += 1
            # definizioni
            defs = {**inline_definitions(txt), **_abbreviations(txt)}
            for k, v in defs.items():
                st.setdefault("defs", {}).setdefault(k, [v, pg])
            # sigle candidate
            cnt, first = _count_terms([(pg, txt)])
            c = st.setdefault("cnt", {})
            for w, n in cnt.items():
                c[w] = c.get(w, 0) + n
                st.setdefault("first", {}).setdefault(w, list(first[w]))
            # frasi sui concetti noti / in attesa
            if targets:
                stats["passages"] += _collect_passages(targets, txt, p.name, pg)
            st["page"] = pg
            if pg % 10 == 0:
                _save_source(name, st)
                _corpus_save(p, corpus)
                progress(f"    … pag. {pg}/{last}")
            if should_stop():
                _corpus_save(p, corpus)
                return True, corpus
        _corpus_save(p, corpus)
        return False, corpus
    except KeyboardInterrupt:
        _save_source(name, st)
        _corpus_save(p, corpus)
        raise
    finally:
        if doc is not None:
            doc.close()


def _target_regex() -> Optional[tuple[re.Pattern, dict]]:
    keys = {}
    for k, t in load()["terms"].items():
        for w in [t["term"], *t.get("aliases", [])]:
            if len(w) >= 2:
                keys[w.upper()] = k
    for x in _questions()["pending"]:
        if x["field"] == "meaning" and len(x["term"]) >= 2:
            keys.setdefault(x["term"].upper(), x["key"])
    if not keys:
        return None
    rx = re.compile(r"(?<![\w\-])(" + "|".join(re.escape(w) for w in sorted(keys, key=len, reverse=True))
                    + r")(?![\w\-])", re.I)
    return rx, keys


def _collect_passages(targets, txt: str, source: str, pg: int) -> int:
    rx, keys = targets
    if not rx.search(txt):
        return 0
    mx = int(getattr(cfg, "KNOWLEDGE_MAX_PASSAGES", 8))
    n = 0
    with _lock:
        ps = _passages()
        q = _questions()
        changed_q = False
        for s in _sentences(txt):
            if not _prose(s):
                continue
            for m in rx.finditer(s):
                k = keys.get(m.group(1).upper())
                if not k:
                    continue
                cur = ps.setdefault(k, [])
                isdef = _definition_sentence(m.group(1), s)
                if any(x["text"] == s for x in cur):
                    continue
                if len(cur) < mx or isdef:
                    it = {"text": s, "source": source, "page": pg}
                    if isdef:
                        cur.insert(0, it)
                        del cur[mx:]
                    else:
                        cur.append(it)
                    n += 1
                # domanda in attesa senza proposta: usa la frase di definizione
                if isdef:
                    for x in q["pending"]:
                        if x["key"] == k and x["field"] == "meaning" and not x.get("proposal"):
                            x["context"] = s[:600]
                            x["source"], x["page"] = source, pg
                            changed_q = True
                break
        if n:
            _dirty.add("passages")
        if changed_q:
            _dirty.add("questions")
    return n


def _finish_file(p: Path, name: str, st: dict, corpus: dict, max_q: int, use_ai: bool,
                 progress) -> tuple[int, int]:
    """Fine documento: definizioni -> proposte da verificare; sigle ricorrenti -> domande."""
    known = set(_alias_map())
    q = _questions()
    ignored = set(q["ignored_terms"])
    defs = st.get("defs", {})
    first = st.get("first", {})
    cnt = Counter(st.get("cnt", {}))
    n = 0
    proposals = 0
    g = _glossary()
    new_keys: dict[str, str] = {}
    for acr, (meaning, pg) in list(defs.items()):
        k = _norm(acr)
        if k in known or k in ignored or cnt.get(acr, 0) < 2 or not _initials_ok(acr, meaning):
            continue
        ctx = (first.get(acr) or [pg, ""])[1]
        g["terms"][k] = _complete({"term": acr, "meaning": meaning, "status": "proposto",
                                   "category": guess_category(acr, ctx + " " + meaning),
                                   "sources": [p.name]})
        known.add(k)
        new_keys[acr.upper()] = k
        proposals += 1
        if enqueue(acr, "meaning", f"Ho capito che «{acr}» significa: «{meaning}». È corretto?", "verify",
                   meaning, ctx, p.name, pg, priority=3, save=False, q=q):
            n += 1
        if proposals >= max_q * 2:
            break
    if proposals:
        _write("glossary", g)
    for w, c in cnt.most_common():
        if n >= max_q:
            break
        k = _norm(w)
        if k in known or k in ignored or c < 3:
            continue
        pg, ctx = first.get(w, [0, ""])
        proposal = ""
        if use_ai:
            try:
                proposal = suggest(w, ctx).get("meaning", "")
            except RuntimeError:
                use_ai = False
        if proposal:
            ok = enqueue(w, "meaning", f"Ho capito che «{w}» significa: «{proposal}» (proposta AI). È corretto?",
                         "verify", proposal, ctx, p.name, pg, priority=4, save=False, q=q)
        else:
            ok = enqueue(w, "meaning", question_for({"term": w, "count": c}), "meaning", "",
                         ctx, p.name, pg, priority=5, save=False, q=q)
        n += ok
    _write("questions", q)
    # frasi del documento per le nuove proposte (dal testo appena letto)
    if new_keys:
        rx = re.compile(r"(?<![\w\-])(" + "|".join(re.escape(w) for w in sorted(new_keys, key=len, reverse=True))
                        + r")(?![\w\-])", re.I)
        for pg, txt in corpus.items():
            _collect_passages((rx, new_keys), txt, p.name, int(pg))
        _flush()
    progress(f"    ✓ {proposals} definizioni trovate, {n} nuove domande per te")
    return n, proposals


# ---------------------------------------------------------------------------
# Proposta dell'AI locale (facoltativa)
# ---------------------------------------------------------------------------

def seed_configs(model: dict) -> int:
    """
    Concetti di base ricavati dal DB Flotte: una scheda per ogni configurazione
    del treno (nome, baseline, treni) e la scheda «ETR1000». I campi gia'
    compilati (anche a mano) non vengono toccati; per quelli mancanti sono
    accodate le domande di approfondimento (costruttore, anno, tratte…).
    Restituisce il numero di schede create.
    """
    fleets = model.get("fleets", {}) or {}
    configs = list(model.get("configs", []))
    base = configs[0] if configs else ""
    new = 0
    for c in configs:
        f = fleets.get(c, {})
        trains = [str(x) for x in f.get("trains", []) if str(x).strip()]
        old = get(c)
        if not old or not old.get("meaning"):
            meaning = (f"Configurazione del treno ETR1000 «{f.get('name') or c}»"
                       + (f", baseline software {f['bl']}" if f.get("bl") else "")
                       + (f"; {len(trains)} treni nel DB Flotte" if trains else "")
                       + (". È la configurazione di riferimento (base) per i confronti." if c == base else "."))
            upsert(c, meaning, "configurazione", source="DB Flotte",
                   aliases=[f["name"]] if f.get("name") and _norm(f["name"]) != _norm(c) else [],
                   facts={"treni": ", ".join(trains), "baseline": f.get("bl", "")})
            new += 1
        else:
            t = _complete(dict(old))
            if trains and not t["facts"].get("treni"):
                set_field(c, "facts.treni", ", ".join(trains), "DB Flotte")
        deepen(c)
    if configs and not get("ETR1000"):
        upsert("ETR1000", "Treno ad alta velocità descritto dal DB Flotte; esiste in più configurazioni ("
               + ", ".join(configs) + ") che differiscono per funzioni, requisiti e documenti FRS.",
               "componente", source="DB Flotte", aliases=["ETR 1000"], status="proposto")
        enqueue("ETR1000", "facts.costruttore", "Chi è il costruttore dell'ETR1000?", "deepen", priority=6)
        enqueue("ETR1000", "details", "Cos'è una configurazione dell'ETR1000 e perché ne esistono diverse?",
                "deepen", priority=6)
        new += 1
    return new


def _ollama_host() -> str:
    h = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    return h if h.startswith("http") else "http://" + h


def suggest(term: str, context: str = "", proposal: str = "", timeout: int = 90) -> dict:
    """
    Chiede al modello locale una proposta di significato per il termine.
    Restituisce {"meaning", "category", "question"}; solleva RuntimeError se
    Ollama non e' disponibile. La proposta va SEMPRE confermata dall'utente.
    """
    import requests
    known = glossary_text(glossary_for(context, 10))
    ps = "\n".join(f"- {x['text'][:300]}" for x in passages(term)[:4])
    prompt = (
        "Sei un esperto di treni ad alta velocita' ETR1000 (Frecciarossa 1000) e di sistemi TCMS. "
        "Un collega ti chiede cosa significa un termine trovato in un documento tecnico (FRS).\n"
        f"TERMINE: {term}\n"
        + (f"DEFINIZIONE NEL DOCUMENTO: {proposal}\n" if proposal else "")
        + f"FRASE IN CUI COMPARE: {context[:900]}\n"
        + (f"ALTRE FRASI DEI DOCUMENTI:\n{ps}\n" if ps else "")
        + (f"TERMINI GIA' NOTI:\n{known}\n" if known else "")
        + "Rispondi SOLO con un JSON: {\"meaning\": \"significato in italiano, max 2 frasi, specificando "
          "a cosa serve sul treno\", \"category\": una tra " + ", ".join(CATEGORIES) + ", "
          "\"question\": \"una domanda breve in italiano da fare all'esperto per confermare o "
          "approfondire\"}. Se non sei sicuro dillo nel significato.")
    try:
        r = requests.post(_ollama_host() + "/api/chat", timeout=(3, timeout), json={
            "model": cfg.OLLAMA_MODEL, "stream": False, "format": "json",
            "keep_alive": getattr(cfg, "OLLAMA_KEEP_ALIVE", "30m"),
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.1, "num_predict": 300}})
        r.raise_for_status()
        txt = (r.json().get("message") or {}).get("content", "")
    except Exception as exc:
        raise RuntimeError(f"AI locale non disponibile: {exc}") from exc
    try:
        data = json.loads(txt)
    except ValueError:
        m = re.search(r"\{.*\}", txt, re.S)
        data = json.loads(m.group(0)) if m else {"meaning": txt.strip()}
    cat = str(data.get("category", "")).lower().replace("è", "e")
    return {"meaning": str(data.get("meaning", "")).strip(),
            "category": cat if cat in CATEGORIES else "",
            "question": str(data.get("question", "")).strip()}
