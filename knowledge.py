"""
knowledge.py
------------
Conoscenza appresa dall'AI: glossario tecnico (sigle, sensori, centraline,
relè, sottosistemi del treno...) insegnato dall'utente.

Flusso
    1. L'utente sceglie i documenti da cui "imparare" (pagina web, scheda
       Conoscenza).
    2. candidates() estrae dal testo i termini tecnici non ancora noti
       (sigle, codici di apparecchiatura, parole ricorrenti) con un esempio
       di frase in cui compaiono e, se il documento la contiene, la
       definizione presa dalla tabella delle abbreviazioni.
    3. Per ogni termine l'AI pone una domanda ("Cosa significa HABD?
       E' un sensore, una centralina...?"); l'utente risponde, corregge o
       salta. suggest() chiede al modello locale una proposta di risposta.
    4. Le risposte confermate sono salvate in KNOWLEDGE_FILE (JSON) e
       vengono usate:
         - dall'analisi del programma (opzioni 1, 2, 5): augment() aggiunge
           ai prompt di Ollama il significato dei termini presenti nel testo;
         - dalle risposte della sezione "Chiedi" e dalla spiegazione AI.

API
    load() / all_terms() / get(term) / upsert(term, ...) / delete(term)
    glossary_for(text, limit) -> list[dict]
    augment(prompt) -> str
    candidates(pages_text, source, limit) -> list[dict]
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import config as cfg

log = logging.getLogger(__name__)

CATEGORIES = {
    "sensore": "Sensore / trasduttore",
    "centralina": "Centralina / unità di controllo",
    "rele": "Relè / contattore / interruttore",
    "attuatore": "Attuatore / valvola / motore",
    "sottosistema": "Sottosistema / impianto",
    "segnale": "Segnale / variabile / evento",
    "componente": "Altro componente",
    "sigla": "Sigla / abbreviazione",
    "concetto": "Concetto / modalità di funzionamento",
}

_lock = threading.RLock()
_data: Optional[dict] = None
_mtime: float = -1.0
_rx_cache: tuple[int, Optional[re.Pattern]] = (-1, None)
_version = 0


def path() -> Path:
    p = getattr(cfg, "KNOWLEDGE_FILE", None)
    if p:
        return Path(p)
    return Path(getattr(cfg, "HISTORY_DIR", Path(__file__).parent)) / "knowledge.json"


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip()).upper()


def load(force: bool = False) -> dict:
    """{"terms": {KEY: {...}}, "ignored": [KEY...], "sources": {...}}"""
    global _data, _mtime, _version
    with _lock:
        p = path()
        try:
            mt = p.stat().st_mtime
        except OSError:
            mt = 0.0
        if _data is None or force or mt != _mtime:
            data = {"terms": {}, "ignored": [], "sources": {}}
            if mt:
                try:
                    data.update(json.loads(p.read_text(encoding="utf-8")))
                except Exception as exc:
                    log.warning(f"Conoscenza: file {p} non leggibile: {exc}")
            _data, _mtime = data, mt
            _version += 1
        return _data


def _save() -> None:
    global _mtime, _version
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(_data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    _mtime = p.stat().st_mtime
    _version += 1


def all_terms() -> list[dict]:
    d = load()
    return sorted(d["terms"].values(), key=lambda t: t["term"].upper())


def get(term: str) -> Optional[dict]:
    return load()["terms"].get(_norm(term))


def upsert(term: str, meaning: str, category: str = "", notes: str = "",
           source: str = "", aliases: Iterable[str] = ()) -> dict:
    term = (term or "").strip()
    if not term or not (meaning or "").strip():
        raise ValueError("Termine e significato sono obbligatori")
    with _lock:
        d = load()
        k = _norm(term)
        old = d["terms"].get(k, {})
        rec = {
            "term": term, "meaning": meaning.strip(),
            "category": category if category in CATEGORIES else (old.get("category") or "componente"),
            "notes": (notes or "").strip(),
            "aliases": sorted({a.strip() for a in aliases if a and a.strip()} | set(old.get("aliases", []))),
            "sources": sorted(set(old.get("sources", [])) | ({source} if source else set())),
            "created": old.get("created") or datetime.now().strftime("%d/%m/%Y %H:%M"),
            "updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        d["terms"][k] = rec
        if k in d["ignored"]:
            d["ignored"].remove(k)
        _save()
        return rec


def delete(term: str) -> bool:
    with _lock:
        d = load()
        ok = d["terms"].pop(_norm(term), None) is not None
        if ok:
            _save()
        return ok


def ignore(term: str) -> None:
    """Il termine non va piu' proposto (non e' tecnico / non interessa)."""
    with _lock:
        d = load()
        k = _norm(term)
        if k not in d["ignored"]:
            d["ignored"].append(k)
            _save()


def mark_source(source: str, n_terms: int) -> None:
    with _lock:
        d = load()
        d["sources"][source] = {"date": datetime.now().strftime("%d/%m/%Y %H:%M"), "terms": n_terms}
        _save()


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
    alias = {}
    for k, t in d["terms"].items():
        alias[k] = k
        for a in t.get("aliases", []):
            alias[_norm(a)] = k
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
        terms = glossary_for(prompt, int(getattr(cfg, "KNOWLEDGE_MAX_TERMS_IN_PROMPT", 25)))
    except Exception as exc:
        log.debug(f"Conoscenza non applicata: {exc}")
        return prompt
    if not terms:
        return prompt
    return ("GLOSSARIO TECNICO ETR1000 (definizioni fornite dall'esperto: usale per interpretare "
            "correttamente sigle e componenti, senza citarle se non servono):\n"
            + glossary_text(terms) + "\n\n" + prompt)


# ---------------------------------------------------------------------------
# Estrazione dei termini da imparare
# ---------------------------------------------------------------------------

_ACR = re.compile(r"(?<![\w\-])([A-Z][A-Z0-9]{1,9}(?:[-_/][A-Z0-9]{1,8}){0,2})(?![\w\-])")
_EQUIP = re.compile(r"(?<![\w\-])([A-Z]{1,3}-[A-Z]{1,2}\d{2,4}[A-Z0-9]*)(?![\w\-])")
_STOP = set("""ID AND OR NOT IF THE TBD NA FRS TRS PDF OK ON OFF II III IV VI VII VIII IX XI XII YES NO
FOR TO OF IN BY AT AS IS BE IT AN ALL ANY SHALL MUST WITH FROM THIS THAT ARE NOTE TABLE FIGURE REV REF
DOC PAGE SIL SIL0 SIL1 SIL2 SIL3 SIL4 MAX MIN NR VZ VZI DE EN IT FR ES DA DI DEL CON PER IL LA LE UN UNA
TYPE DERIVED CONCEPT EUROPE ZEFIRO TCN IDU EVENT EVENTS DELETED WARNING ALARM TRUE FALSE STATUS STATE INFO
ERROR NEW OLD HIGH LOW RESET SET ACTIVE INACTIVE DATE NOTES SYSTEM TEXT NONE ALL SEE ITEM VALUE TIME
DESCRIPTION REQUIREMENT REQUIREMENTS SAFETY LEVEL APPLICABILITY DETAILS CONFIDENTIAL PROPRIETARY""".split())
_ABBR_LINE = re.compile(r"^\s*([A-Z][A-Z0-9\-/]{1,12})\s{1,}[-–:=]?\s*([A-Z][A-Za-z].{3,120})$")


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


def _guess_category(term: str, ctx: str) -> str:
    c = ctx.lower()
    if _EQUIP.fullmatch(term):
        if re.search(r"\brel[eèa]|relay|contactor|contattor", c):
            return "rele"
        if re.search(r"breaker|interruttor|switch|fuse|fusibil", c):
            return "rele"
        return "componente"
    if re.search(r"sensor|transducer|probe|sonda|pt100|thermo|pressure switch", c):
        return "sensore"
    if re.search(r"control unit|ecu|\bunit\b|centralin|controller|computer|\bplc\b", c):
        return "centralina"
    if re.search(r"valve|valvol|motor|actuator|attuator|cylinder|pump|compress", c):
        return "attuatore"
    if re.search(r"signal|segnal|event|evento|bit\b|variable|loop", c):
        return "segnale"
    if re.search(r"system|sistema|subsystem|impianto", c):
        return "sottosistema"
    return "sigla"


def candidates(pages: list[tuple[int, str]], source: str = "", limit: int = 40) -> list[dict]:
    """
    Termini tecnici da chiarire presenti nelle pagine [(n_pagina, testo)].
    Esclude quelli gia' appresi o ignorati. Ordinati per frequenza.
    """
    d = load()
    known = set(d["terms"]) | set(d["ignored"])
    for t in d["terms"].values():
        known |= {_norm(a) for a in t.get("aliases", [])}
    full = "\n".join(t for _p, t in pages)
    abbr = _abbreviations(full)
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
                    a, b = max(0, m.start() - 110), min(len(flat), m.end() + 110)
                    first[w] = (pg, ("…" if a else "") + flat[a:b] + ("…" if b < len(flat) else ""))
    out = []
    for w, n in cnt.most_common():
        if _norm(w) in known:
            continue
        if n < 2 and w not in abbr:
            continue
        pg, ctx = first[w]
        out.append({"term": w, "count": n, "page": pg, "context": ctx, "source": source,
                    "proposal": abbr.get(w, ""),
                    "category": _guess_category(w, ctx + " " + abbr.get(w, ""))})
        if len(out) >= limit:
            break
    return out


def question_for(c: dict) -> str:
    """Domanda in italiano da porre all'utente per il termine candidato."""
    t = c["term"]
    if _EQUIP.fullmatch(t):
        return (f"Nel documento compare l'apparecchiatura «{t}» ({c['count']} volte). "
                f"Che cos'è (relè, interruttore, sensore…) e a cosa serve?")
    if c.get("proposal"):
        return (f"Il documento definisce «{t}» come «{c['proposal']}». È corretto? "
                f"Spiegami che tipo di elemento è e che ruolo ha sul treno.")
    return (f"Cosa significa «{t}» (compare {c['count']} volte)? È un sensore, una centralina, "
            f"un segnale, un sottosistema…?")


# ---------------------------------------------------------------------------
# Proposta dell'AI locale (facoltativa)
# ---------------------------------------------------------------------------

def _ollama_host() -> str:
    import os
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
    prompt = (
        "Sei un esperto di treni ad alta velocita' ETR1000 (Frecciarossa 1000) e di sistemi TCMS. "
        "Un collega ti chiede cosa significa un termine trovato in un documento tecnico (FRS).\n"
        f"TERMINE: {term}\n"
        + (f"DEFINIZIONE NEL DOCUMENTO: {proposal}\n" if proposal else "")
        + f"FRASE IN CUI COMPARE: {context[:900]}\n"
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


def learn_from_pdf(path: str, first: int = 1, last: int = 0, source: str = "",
                   limit: int = 0) -> dict:
    """Termini da imparare dalle pagine [first, last] del PDF (last=0: fino al limite)."""
    from webapp import documents as D
    n = D.page_count(path)
    max_pages = int(getattr(cfg, "KNOWLEDGE_MAX_PAGES", 80))
    first = max(1, first or 1)
    last = min(n, last or n, first + max_pages - 1)
    pages = [(p, D.page_text(path, p)) for p in range(first, last + 1)]
    # le tabelle delle abbreviazioni sono di solito nelle prime pagine
    head = [(p, D.page_text(path, p)) for p in range(1, min(n, 12) + 1) if p < first]
    limit = limit or int(getattr(cfg, "KNOWLEDGE_MAX_QUESTIONS", 40))
    abbr = _abbreviations("\n".join(t for _p, t in head))
    items = candidates(pages, source or Path(path).name, limit)
    for it in items:
        if not it["proposal"] and it["term"] in abbr:
            it["proposal"] = abbr[it["term"]]
        it["question"] = question_for(it)
    return {"source": source or Path(path).name, "pages": [first, last], "total_pages": n,
            "items": items}
