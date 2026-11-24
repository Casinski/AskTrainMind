"""
understand.py
-------------
Comprensione della domanda di «Chiedi» e «🎓 Risposta AI» (server / anteprima developer).
Stessa logica di webapp/static/offline.js (oggetto U) usata dalla pagina offline.

La domanda è letta come la leggerebbe un ingegnere ferroviario:
  * COSA chiede   (valori, definizione, funzionamento, condizioni, differenze…)
  * QUALE grandezza (pressione, tempo, temperatura…)
  * DOVE cercare  (documento FRS nominato, funzione, configurazione)
  * di COSA parla (compressori, porte, freno di emergenza…)
Le parole del «dove» e della forma della domanda non sono usate come parole da
cercare né segnalate come «parole sconosciute». Poi il testo dei documenti viene
letto nel perimetro capito, i valori sono estratti con la loro condizione
(es. «MR ≥ 1000 kPa») e spiegati in italiano (es. «Arresto compressori principali»).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

NUM = r"\d+(?:[.,]\d+)?"


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn").lower()


QTY = [
    {"key": "pressione", "label": "pressione", "q": re.compile(r"pression|pressur|\bkpa\b|\bbar\b|\bpsi\b"), "units": r"kpa|mbar|bar|psi"},
    {"key": "temperatura", "label": "temperatura", "q": re.compile(r"temperatur|°\s*c\b|\bgradi\b"), "units": r"°\s*c|°|deg(?:rees?)?\s*c?"},
    {"key": "velocita", "label": "velocità", "q": re.compile(r"velocit|km/h|\bkmh\b"), "units": r"km/h|kmh|m/s"},
    {"key": "tensione", "label": "tensione", "q": re.compile(r"tension|voltag|\bvolt\b|\bkv\b|\bvdc\b|\bvac\b"), "units": r"kv|vdc|vac|v"},
    {"key": "corrente", "label": "corrente", "q": re.compile(r"corrent|amper"), "units": r"ka|ma|a"},
    {"key": "tempo", "label": "tempo", "q": re.compile(r"\btemp[oi]\b|ritard|durat|timeout|\bsecond|\bminut|dopo quanto|entro quanto|\bore\b"),
     "units": r"ms|sec(?:onds?)?|s|min(?:utes?)?|hours?|h"},
    {"key": "frequenza", "label": "frequenza", "q": re.compile(r"frequenz|\bhz\b"), "units": r"khz|hz"},
    {"key": "potenza", "label": "potenza", "q": re.compile(r"potenz|\bkw\b"), "units": r"mw|kw|w"},
    {"key": "percentuale", "label": "percentuale", "q": re.compile(r"percentual|%"), "units": r"%"},
]
ANY = {"key": "valori", "label": "valori numerici", "q": None, "units": "|".join(x["units"] for x in QTY)}


def unit_rx(qt: dict) -> re.Pattern:
    return re.compile(rf"(?<![\w.])({NUM})\s*({qt['units']})(/(?:min|s|h))?(?![a-z0-9])", re.I)


VALUES_Q = re.compile(r"\bvalor[ei]\b|\bquant[oaie]\b|\bsogli[ae]\b|\blimit[ei]\b|\brange\b|\bintervall[oi] di\b|"
                      r"\ba che (?:pression|temperatur|velocit|tension|corrent|valor|frequenz|potenz)|"
                      r"\b(?:qual[ei]?|che) (?:e |sono )?(?:il |la |i |le )?(?:pression|temperatur|velocit|tension|corrent|frequenz|potenz|tarat)")
WHEN_Q = re.compile(r"\bquando\b|in (?:quali|che) (?:condizion|cas)|\bperch[eé]\b|cosa succede")
DEFINE_Q = re.compile(r"(?:cos['’]?\s*[eè]|cosa\s+[eè]|che\s+cos['’]?\s*[eè]|cosa\s+significa|cosa\s+vuol\s+dire|significato\s+di|"
                      r"cosa\s+sono|definizione\s+di|cosa\s+indica|per\s+cosa\s+sta)(?=[\s?.,!]|$)", re.I)
LIST_ALL = re.compile(r"\b(tutt[ie]|elenc\w*|lista|ci sono|presenti|quali (?:sono i |)valori|che valori)\b", re.I)
# parole che indicano DOVE cercare o la forma della domanda (non il contenuto)
FRAME_STOP = set("""interno interna interni interne dentro presente presenti contenuto contenuti contenute riportato riportati
  riportate indicato indicati indicate specificato specificati specificate definito definiti definite previsto previsti previste
  ci sono trovano trova trovare elenco elenca elencami lista tutti tutte tutto ogni vari varie diversi diverse sistema frs trs doc
  documento documenti valore valori quale quali quanto quanta quanti quante che cosa come dove sogli soglia soglie limite limiti
  parametro parametri numero numeri dato dati presenti esistono esiste riguardo riguardano riguarda relativi relative
  vengono viene sono e è hanno ha nel nella nei nelle per il lo la i gli le di da in con su tra fra del della dei delle al alla
  ai alle dal dalla un una uno all dall dell nell sull configurazione configurazioni treno treni base a si dopo entro
  quanto quanta quanti quante succede avviene accade massimo massima massimi massime minimo minima minimi minime
  raggiungere raggiunge raggiungono possono puo può deve devono essere avere""".split())
ASK_LABEL = {"values": "Valori", "define": "Definizione", "when": "Condizioni", "explain": "Funzionamento",
             "differences": "Differenze", "requirements": "Requisiti", "documents": "Documenti",
             "components": "Componenti", "overview": "Panoramica", "generic": "Domanda"}


def _stop_it() -> set:
    try:
        import knowledge
        return knowledge.STOP_IT
    except Exception:
        return set()


def doc_functions(docs: list[str], S) -> set:
    D = docs_index(S)
    return {f for d in docs for f in D[d]["fids"]}


def is_frame_word(w: str) -> bool:
    f = fold(w)
    return f in FRAME_STOP or any(x["q"].search(f) for x in QTY)


# ---------------------------------------------------------------------------
# documenti nominati nella domanda
# ---------------------------------------------------------------------------

def docs_index(S) -> dict:
    if getattr(S, "_udocs", None) is not None:
        return S._udocs
    D: dict = {}
    by_idx = {}
    for j, d in enumerate(S.ix["docs"]):
        if d[0] not in D:
            core = re.sub(r"^(?:frs|trs|srs|sss)[\s_\-]+", "", fold(d[0]))
            core = re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", core)).strip()
            D[d[0]] = {"name": d[0], "core": core, "idx": set(), "codes": set(), "fids": set()}
        D[d[0]]["idx"].add(j)
        if d[1]:
            D[d[0]]["codes"].add(d[1])
        by_idx[j] = D[d[0]]
    for it in S.ix["items"]:
        for j in [it[4]] + [a[1] for a in (it[7] if len(it) > 7 else [])]:
            if j in by_idx:
                by_idx[j]["fids"].add(it[1])
    S._udocs = D
    return D


def docs_in(q: str, S) -> list[str]:
    D, out = docs_index(S), []
    qn = " " + re.sub(r"\s+", " ", re.sub(r"[_\-'’/]+", " ", fold(q))) + " "
    for v in D.values():
        if len(v["core"]) >= 3 and re.search(r"[^a-z0-9]" + re.escape(v["core"]).replace(r"\ ", r"\s+") + r"[^a-z0-9]", qn):
            out.append(v["name"])
        elif any(c.upper() in q.upper() for c in v["codes"]):
            out.append(v["name"])
    if not out and re.search(r"\b(frs|documento|doc)\b", q, re.I):
        qs = {a for g in S.terms(q) for a in g}
        import docsearch
        for v in D.values():
            need = {t for t in docsearch.tokens(v["core"]) if len(t) >= 3 and t not in ("and", "the", "of")}
            if need and need <= qs:
                out.append(v["name"])
    return out


# ---------------------------------------------------------------------------
# cornice della domanda
# ---------------------------------------------------------------------------

def ask_type(ql: str, intent: str, qty: Optional[dict], defined: bool) -> str:
    if defined:
        return "define"
    if VALUES_Q.search(ql) or (qty and re.search(r"\b(che|qual[ei]?|quant[oaie]|a che)\b", ql)):
        return "values"
    if WHEN_Q.search(ql) and "come funziona" not in ql:
        return "when"
    if intent and intent not in ("overview", "concept"):
        return intent
    return "overview" if intent == "overview" else "generic"


def topic_text(q: str, fr: dict, S) -> str:
    t = " " + re.sub(r"['’]", " ", q) + " "
    D = docs_index(S)

    def cut(s: str):
        nonlocal t
        if s:
            pat = re.escape(s)
            pat = re.sub(r"(\\ |_|\\-)+", r"[\\s_\\-]+", pat)
            t = re.sub(r"(?<![\w\-])" + pat + r"(?![\w\-])", " ", t, flags=re.I)

    for d in fr["docs"]:
        cut(d)
        cut(D[d]["core"])
        for c in D[d]["codes"]:
            cut(c)
    for f in fr["functions"]:
        cut(f)
    for c in fr["configs"]:
        cut(c)
    stop_it = _stop_it()
    out = []
    for w in t.split():
        f = re.sub(r"[^a-z0-9]", "", fold(w))
        if not w or f in FRAME_STOP or re.sub(r"[?!.,;:]", "", w.lower()) in stop_it:
            continue
        if fr["qty"] and fr["qty"]["q"] is not None and fr["qty"]["q"].search(fold(w)):
            continue
        out.append(w)
    return " ".join(out)


def frame(q: str, S, intent: str, functions: list[str], configs: list[str], terms: list[dict]) -> dict:
    ql = fold(q)
    qty = next((x for x in QTY if x["q"].search(ql)), None)
    docs = docs_in(q, S) if S else []
    fr = {"q": q, "qty": qty, "docs": docs, "intent": intent, "functions": functions, "configs": configs, "terms": terms}
    fr["ask"] = ask_type(ql, intent, qty, bool(DEFINE_Q.search(q)))
    if fr["ask"] == "values" and not fr["qty"]:
        fr["qty"] = ANY
    m = re.search(r"\b(massim|minim|piu alt|piu bass|mass\b|min\b)", ql)
    fr["extreme"] = (None if not m else "min" if m.group(1).startswith(("minim", "piu bass", "min")) else "max")
    fr["topic"] = topic_text(q, fr, S) if S else q
    fr["groups"] = S.terms(fr["topic"]) if S else []
    return fr


# ---------------------------------------------------------------------------
# valori con condizione e significato in italiano
# ---------------------------------------------------------------------------

CMP = [
    (r"(>=|>\s*=|≥|=>)$", "≥"), (r"(<=|<\s*=|≤|=<)$", "≤"), (r">$", ">"), (r"<$", "<"), (r"(\+/-|±|\+-)$", "±"),
    (r"(at least|minimum|min\.?|not less than)$", "≥"), (r"(at most|maximum|max\.?|not more than|not exceed(?:ing)?)$", "≤"),
    (r"(less than|lower than|below|under|decrease[sd]?(?: down)?(?: to| below)?|falls?(?: down)? (?:below|under|to)|drops? (?:below|to))$", "<"),
    (r"(more than|greater than|higher than|above|exceed(?:s|ed|ing)?|over|rises? above)$", ">"),
    (r"(after|delay of|delayed by)$", "dopo"), (r"(within|in less than)$", "entro"), (r"(for(?: more than| at least)?|during)$", "per"),
    (r"(reach(?:ed|es)?|achieve[sd]?|increased?(?: up)? to|up to|at|of|=|equal to|is|set to)$", "="),
]
CMP = [(re.compile(a), b) for a, b in CMP]
OBJ = [(re.compile(a), b) for a, b in [
    (r"\b(main reservoir pipe|mrp)\b", "condotta serbatoio principale (MRP)"), (r"\b(main reservoir|mr)\b", "serbatoio principale (MR)"),
    (r"\bmain pipe\b", "condotta principale"), (r"\bbrake pipe\b", "condotta generale del freno"), (r"\bbrake cylinder\b", "cilindro freno"),
    (r"\bpantograph\b", "circuito pantografo"), (r"\b(suspension|air bellows?|sensor ts)\b", "sospensione pneumatica"),
    (r"\bpressure decrease\b", "calo di pressione"), (r"\b(train speed|speed (?:is|>|<|above|below|exceeds?|higher|lower))\b", "velocità del treno"),
    (r"\b(line voltage|catenary)\b", "tensione di linea"), (r"\btemperature\b", "temperatura"), (r"\brun(?:ning)? time\b", "tempo di funzionamento"),
]]
SUBJ = [(re.compile(a), b) for a, b in [
    (r"primary (?:main )?compressor", "compressore principale primario"), (r"secondary (?:main )?compressor", "compressore principale secondario"),
    (r"first compressor", "primo compressore"), (r"second(?:ary)? compressor", "secondo compressore"), (r"auxiliary compressor", "compressori ausiliari"),
    (r"main compressor", "compressori principali"), (r"compressor", "compressori"), (r"emergency brake", "freno di emergenza"),
    (r"brake test", "prova freno"), (r"parking brake", "freno di stazionamento"), (r"pressure switch|\bps[pc]\b|\bpcp\b", "pressostato"),
    (r"transducer|pressure sensor", "trasduttori di pressione"), (r"leakage", "perdita d'aria"), (r"tilt", "sistema di assetto (tilt)"),
    (r"suspension", "sospensione"), (r"pantograph", "pantografo"), (r"air dryer", "essiccatore"), (r"\bdoors?\b", "porte"),
    (r"heater|heating", "riscaldamento"), (r"hvac|air condition", "climatizzazione"), (r"traction", "trazione"), (r"battery", "batteria"),
    (r"\bbrake", "freno"), (r"sensor", "sensori"), (r"\bevent\b|fault message|alarm|warning", "messaggio diagnostico"), (r"driver", "macchinista"),
]]
ACT = [(re.compile(a), b) for a, b in [
    (r"normal (?:operation|condition)|works? between|management", "funzionamento normale"),
    (r"\bblocked\b|inhibit", "inibizione"), (r"\bstop(?:s|ped)?\b|switch(?:ed)? off", "arresto"),
    (r"\bstart(?:s|ed)?\b|\brun(?:s|ning)?\b|switch(?:ed)? on|ordered to run", "avvio"), (r"disabled?|deactivat", "disabilitazione"),
    (r"enabled?|activat", "abilitazione"), (r"released?", "rilascio"), (r"applied|appl(?:y|ies)|request", "intervento"),
    (r"close[sd]? (?:its )?contacts?|\bclose[sd]?\b", "chiusura"), (r"\bopen(?:s|ed)?\b", "apertura"), (r"leakage", "rilevamento perdita"),
    (r"\bevent\b|alarm|warning|fault|message", "segnalazione"), (r"indicated|displayed|shown", "visualizzazione"),
    (r"toleran|deviat|differ", "tolleranza"),
]]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _first(table, s: str):
    return next((x for x in table if x[0].search(s)), None)


def sentence_at(text: str, at: int) -> str:
    pos = 0
    for p in re.split(r"(?<=[.;:])\s+(?=[A-Z])|\s+•\s+", text):
        i = text.find(p, pos)
        if i <= at < i + len(p) + 1:
            return p
        pos = i + len(p)
    return text


def gloss(sent: str) -> str:
    """Significato in italiano: azione = verbo retto da «shall», soggetto = ciò che lo precede."""
    s = sent.lower()
    m = re.search(r"\bshall\s+(?:not\s+)?(?:be\s+)?([a-z]+(?:\s+[a-z]+){0,3})", s)
    a = b = None
    if m:
        head = re.split(r"\bthen\b|,|\bkpa\b|\bif\b|\bwhen\b", s[:m.start()])[-1]
        verb = re.sub(r"^(?:start|begin)s?\s+to\s+", "", m.group(1))
        a = _first(ACT, verb) or _first(ACT, head)
        b = _first(SUBJ, head) or _first(SUBJ, verb)
        if a and re.search(r"\bnot\b", s[m.start():m.start() + 10]):
            a = (a[0], "nessun " + a[1])
    a = a or _first(ACT, s)
    b = b or _first(SUBJ, s)
    quoted = re.search(r"[\"“«]([^\"”»]{4,60})[\"”»]", sent)
    if a and a[1] == "segnalazione" and quoted:
        return f"Segnalazione «{quoted.group(1).strip()}»"
    if a and b:
        return _cap(f"{a[1]} {'diagnostica' if b[1] == 'messaggio diagnostico' and a[1] == 'segnalazione' else b[1]}")
    return _cap(a[1]) if a else _cap(b[1]) if b else ""


def _unit(u: str) -> str:
    u = re.sub(r"\s+", "", u)
    for rx, rep in ((r"^kpa$", "kPa"), (r"^°c$", "°C"), (r"^km/h$", "km/h"), (r"^(?:s|sec|seconds?)$", "s"),
                    (r"^(?:min|minutes?)$", "min"), (r"^(?:h|hours?)$", "h")):
        if re.match(rx, u, re.I):
            return rep
    return u


def _n(s: str) -> str:
    return s.replace(",", ".")


def values_in(text: str, qt: dict) -> list[dict]:
    out: list[dict] = []
    for m in unit_rx(qt).finditer(text):
        start, lo = m.start(), None
        unit, rate = _unit(m.group(2)), m.group(3) or ""
        if rate and qt is not ANY and qt["key"] != "tempo":
            continue        # gradiente (°C/s, kPa/min…): non è un valore della grandezza chiesta
        pre = text[max(0, start - 70):start]
        r = re.search(rf"(?:between\s+)?({NUM})\s*(?:{qt['units']})?\s*(-|–|\.{{2,3}}|/|and|to)\s*$", pre, re.I)
        if r and not (r.group(2) == "to" and re.search(r"increase|decrease|up to", pre[:len(pre) - len(r.group(0))], re.I)):
            lo = r.group(1)
            pre = pre[:len(pre) - len(r.group(0))]
            if out and out[-1]["n"] == float(_n(lo)) and out[-1]["end"] >= start - len(r.group(0)) - 12:
                out.pop()
        p = re.sub(r"\(\s*$", "", pre.lower())
        p = re.sub(r"\s*(?:pressure\s+)?limit\s*\d+\s*(?:is\s*)?$", " ", p)
        p = re.sub(r"\s*(?:value|pressure)\s*$", " ", p).rstrip()
        sym = ("/" if r.group(2) == "/" else "–") if lo else next((b for a, b in CMP if a.search(p)), "")
        win = text[max(0, start - 70):start].lower()
        obj, best = "", -1
        for orx, lab in OBJ:
            ms = list(orx.finditer(win))
            if ms and ms[-1].start() > best:
                best, obj = ms[-1].start(), lab
        if rate:
            obj = obj or "variazione"
        n = float(_n(m.group(1)))
        neg = "-" if qt["key"] == "temperatura" and start and text[start - 1] == "-" else ""
        v = (f"{_n(lo)}{'/' if sym == '/' else '–'}{_n(m.group(1))} {unit}{rate}" if lo else f"{neg}{_n(m.group(1))} {unit}{rate}")
        out.append({"v": v, "n": -n if neg else n, "unit": unit + rate, "sym": "" if lo else sym, "obj": obj,
                    "start": start, "end": m.end(), "sent": sentence_at(text, start)})
    return out


# ---------------------------------------------------------------------------
# lettura dei documenti nel perimetro capito
# ---------------------------------------------------------------------------

def scope_hits(fr: dict, S, limit: int = 400) -> list[dict]:
    """Tutti i passaggi del perimetro (documento/funzione/configurazione) che contengono la grandezza."""
    D = docs_index(S)
    dset = {j for d in fr["docs"] for j in D[d]["idx"]}
    fset, cset = set(fr["functions"]), set(fr["configs"])
    rx = unit_rx(fr["qty"]) if fr["qty"] else None
    raw = []
    for i, it in enumerate(S.ix["items"]):
        if dset and not (it[4] in dset or any(a[1] in dset for a in (it[7] if len(it) > 7 else []))):
            continue
        if fset and it[1] not in fset:
            continue
        if cset and not cset & set(it[3]):
            continue
        if rx and not rx.search(it[6]):
            continue
        tk = S.toks[i]
        hit = sum(1 for g in fr["groups"] if any(a in tk for a in g))
        raw.append((hit, 1 if it[0] == "r" else 0, i))
    best = max([x[0] for x in raw] or [0])
    keep = [x for x in raw if not fr["groups"] or not best or x[0] >= max(1, -(-best // 2))]
    keep.sort(key=lambda x: (-x[0], -x[1], x[2]))
    seen, out = set(), []
    for _h, _r, i in keep:
        key = re.sub(r"[^a-z0-9]", "", fold(S.ix["items"][i][6]))[:200]
        if key in seen:
            continue
        seen.add(key)
        h = S.hit(i, cset)
        h["terms"] = [a for g in fr["groups"] for a in g]
        h["cover"] = 1
        out.append(h)
        if len(out) >= limit:
            break
    return out


def facts(hits: list[dict], qt: dict) -> list[dict]:
    F, by = [], {}
    for h in hits:
        for x in values_in(h["text"], qt):
            g = gloss(x["sent"])
            key = (h["fid"], x["v"], x["sym"], x["obj"], g)
            ref = {k: h.get(k) for k in ("id", "page", "doc", "code", "file", "kind")}
            if key in by:
                f = by[key]
                if h.get("id") and not any(r["id"] == h["id"] for r in f["refs"]):
                    f["refs"].append(ref)
                continue
            f = {**x, "fid": h["fid"], "gloss": g, "refs": [ref], "text": h["text"], "configs": h["configs"]}
            by[key] = f
            F.append(f)
    return F


def short_id(i: str) -> str:
    return ".".join(i.split(".")[-2:]) if i else ""


def ref_txt(f: dict) -> str:
    ids = [short_id(r["id"]) for r in f["refs"] if r.get("id")]
    pg = list(dict.fromkeys(str(r["page"]) for r in f["refs"] if r.get("page")))
    return " · ".join(x for x in [", ".join(ids) if ids else "paragrafo", f"pag. {', '.join(pg)}" if pg else ""] if x)


def cond(f: dict) -> str:
    if re.match(r"^[a-z]", f["sym"] or ""):
        return f"{f['obj'] + ' ' if f['obj'] else ''}{f['sym']} {f['v']}".strip()
    if f["sym"] == "=":
        return f"{f['obj'] or 'valore'} = {f['v']}"
    if f["sym"] == "±":
        return f"tolleranza ± {f['v']}"
    return f"{f['obj'] + ' ' if f['obj'] else ''}{f['sym'] + ' ' if f['sym'] else ''}{f['v']}".strip()


def _desc(t: str) -> str:
    t = re.split(r"\n?—{5,}\n?", str(t or "").replace("\r", ""))[0]
    return re.sub(r"^Description:\s*", "", t, flags=re.I).strip()


def short_desc(d: str) -> str:
    d = re.sub(r"^Funzione per\s+", "", _desc(d), flags=re.I)
    m = re.search(r",\s*(garantendo|assicurando|evitando|in modo)", d)
    return (d[:m.start()] if m and m.start() > 30 else d).rstrip(".")


def quote(t: str, n: int = 170) -> str:
    t = " ".join(str(t).split())
    return t if len(t) <= n else re.sub(r"\s\S*$", "", t[:n - 3]) + "…"


def acronyms(texts: Iterable[str], skip: Iterable[str]) -> list[dict]:
    try:
        import knowledge
        terms = list(knowledge.load()["terms"].values())
    except Exception:
        return []
    allt = " ".join(texts)
    seen = {re.sub(r"[^a-z0-9]", "", s.lower()) for s in skip}
    out = []
    for t in terms:
        k = re.sub(r"[^a-z0-9]", "", t["term"].lower())
        if t.get("category") == "configurazione" or k in seen or not re.match(r"^[A-Z][A-Z0-9\-]{1,7}$", t["term"]):
            continue
        if re.search(r"(?<![\w\-])" + re.escape(t["term"]) + r"(?![\w\-])", allt):
            out.append(t)
            seen.add(k)
        if len(out) >= 8:
            break
    return out


def understood(fr: dict) -> str:
    qt = fr.get("qty")
    p = [{"values": f"i valori e le soglie di **{qt['label']}**" if qt and qt is not ANY else "i **valori numerici**",
          "define": "il **significato**", "when": "**quando / in quali condizioni** avviene", "explain": "il **funzionamento**",
          "differences": "le **differenze fra configurazioni**", "requirements": "i **requisiti**", "documents": "i **documenti**",
          "components": "i **componenti**"}.get(fr["ask"], "una **risposta tecnica**")]
    topic = " ".join(re.sub(r"[?!.]", " ", fr.get("topic", "")).split())
    if topic and fr["ask"] != "define":
        p.append(f"argomento: *{topic}*")
    if fr.get("terms"):
        p.append("concetti: " + ", ".join(f"**{t['term']}**" for t in fr["terms"]))
    if fr["docs"]:
        p.append("documento " + ", ".join(f"**{d}**" for d in fr["docs"]))
    if fr["functions"]:
        p.append("funzione " + ", ".join(f"**{f}**" for f in fr["functions"]))
    p.append("configurazione " + ", ".join(f"**{c}**" for c in fr["configs"]) if fr["configs"] else "tutte le configurazioni")
    return "🔍 *Ho capito che chiedi:* " + " · ".join(p) + "."


FOOT = ("\n\n*Risposta composta dall'AI di AskTrainMind incrociando la conoscenza ferroviaria appresa con il testo dei "
        "documenti: i valori sono citati dai requisiti — verifica sempre nella Sezione documentale e nel PDF.*")


def _sigle(texts, skip) -> str:
    sig = acronyms(texts, skip)
    return ("\n\n**Sigle:** " + " · ".join(f"**{t['term']}** = {t['meaning']}" for t in sig)) if sig else ""


# limiti di validità dei sensori: non sono valori di esercizio
PLAUS = re.compile(r"out of (?:the )?range|invalid|not valid|plausib|declared? (?:as )?(?:faulty|excluded)|sensor (?:fault|failure)", re.I)


def values_answer(fr: dict, hits: list[dict], enumerate_all: bool, funcs: dict) -> Optional[list[dict]]:
    qt = fr["qty"] or ANY
    F = facts(hits, qt)
    if not F:
        return None
    md = [understood(fr), ""]
    codes = list(dict.fromkeys(h["code"] for h in hits if h.get("code")))
    where = (f" nel documento **{', '.join(fr['docs'])}**" + (f" ({', '.join(codes)})" if codes else "")) if fr["docs"] else ""
    cfg = f" per la configurazione **{', '.join(fr['configs'])}**" if fr["configs"] else ""
    byf: dict = {}
    for f in F:
        byf.setdefault(f["fid"], []).append(f)
    if enumerate_all:
        byf = dict(sorted(byf.items(), key=lambda kv: -len(kv[1])))
        lead = _cap((where + cfg).strip()) or "Nei documenti"
        md.append(f"{lead} ho trovato **{len(F)} {'valore' if len(F) == 1 else 'valori'} di {qt['label']}** in "
                  f"**{len(byf)} {'funzione' if len(byf) == 1 else 'funzioni'}**. Ecco cosa significano, funzione per funzione:")
    else:
        f0 = F[0]
        if fr.get("extreme"):
            same = [f for f in F if f["fid"] == f0["fid"]] or F
            same = [f for f in same if not PLAUS.search(f["sent"] or "")] or same
            f0 = (max if fr["extreme"] == "max" else min)(same, key=lambda f: f["n"])
        g = f0["gloss"].lower() + " " if f0["gloss"] else ""
        md += [f"**Risposta: {f0['v']}** — {g}{'' if re.match(r'^[a-z]', f0['sym'] or '') else 'quando '}{cond(f0)}"
               f"{where or ' nel documento **' + (f0['refs'][0]['doc'] or '') + '**'}{cfg} (funzione *{f0['fid']}*, {ref_txt(f0)}).",
               "", f"> {quote(f0['text'])}", "",
               "Valori collegati che un ingegnere considererebbe insieme:" if len(byf) > 1 or len(F) > 1 else ""]
    for shown, (fid, lst) in enumerate(byf.items()):
        if shown >= 8:
            break
        md += ["", f"**{fid}** — {short_desc((funcs.get(fid) or {}).get('desc', ''))}"]
        rows = sorted(lst, key=lambda f: -f["n"])[:10]
        md += [f"- **{f['v']}** — {f['gloss'] or 'valore citato'} ({cond(f)}) · *{ref_txt(f)}*" for f in rows]
        if len(lst) > len(rows):
            md.append(f"- … altri {len(lst) - len(rows)} valori nella tabella qui sotto")
    B = [{"type": "text", "tone": "ai", "md": "\n".join(md) + _sigle([h["text"] for h in hits], fr["configs"]) + FOOT}]
    if len(F) > 6:
        B.append({"type": "table", "title": f"Riepilogo dei valori di {qt['label']} (ordinabile: clic sull'intestazione)",
                  "collapsed": len(F) > 25, "maxRows": 40,
                  "columns": ["Valore", "Condizione", "Cosa avviene", "Funzione", "Riferimento"],
                  "rows": [[f["v"], cond(f), f["gloss"] or "–", f["fid"], ref_txt(f)] for f in F]})
    return B


def passage_answer(fr: dict, hits: list[dict], funcs: dict) -> Optional[list[dict]]:
    if not hits:
        return None
    h = hits[0]
    g = gloss(h["text"])
    who = f"il requisito **{h['id']}**" if h["kind"] == "r" else "il testo"
    md = [understood(fr), "",
          f"Secondo {who} del documento **{h['doc']}**{' (' + h['code'] + ')' if h.get('code') else ''}"
          f"{', pag. ' + str(h['page']) if h.get('page') else ''} — funzione *{h['fid']}* "
          f"({short_desc((funcs.get(h['fid']) or {}).get('desc', ''))}):", "", f"> {quote(h['text'])}"]
    if g:
        v = values_in(h["text"], ANY)
        md += ["", f"*In sintesi:* {g.lower()}{' (' + cond(v[0]) + ')' if v else ''}."]
    more = [x for x in hits[1:4] if x["fid"] != h["fid"] or x["id"] != h["id"]]
    if more:
        md += ["", "Altri passaggi collegati:"] + [
            f"- {'**' + short_id(x['id']) + '**' if x['id'] else 'paragrafo'} ({x['fid']}, pag. {x['page']}): {quote(x['text'])}" for x in more]
    return [{"type": "text", "tone": "ai", "md": "\n".join(md) + _sigle([x["text"] for x in hits[:4]], fr["configs"]) + FOOT}]


def concept_answer(fr: dict, t: dict, hits: list[dict]) -> list[dict]:
    md = [understood(fr), "", f"**{t['term']}** significa **{t.get('meaning', '')}**."]
    det = " ".join(str(t.get("details") or "").split())
    if det:
        md += ["", det if len(det) <= 600 else re.sub(r"\s\S*$", "", det[:597]) + "…"]
    ans = [a for a in (t.get("answers") or []) if a.get("a")]
    if ans and ans[-1]["a"][:60] not in det:
        md += ["", "💬 *L'esperto ha spiegato:* " + " ".join(ans[-1]["a"].split())[:400]]
    fs = (t.get("funcs") or [])[:6]
    if fs:
        md += ["", "Sul treno compare nelle funzioni: " + ", ".join(f"*{f}*" for f in fs) + "."]
    k = t["term"]
    flags = 0 if (k == k.upper() and len(k) <= 3) else re.I
    h = next((x for x in hits if re.search(r"(?<![\w\-])" + re.escape(k) + r"(?![\w\-])", x["text"], flags)), None)
    if h:
        md += ["", f"Nei documenti ({h['doc']}{' ' + h['code'] if h.get('code') else ''}, pag. {h['page']}): «{quote(h['text'])}»"]
    if t.get("status") == "proposto":
        md += ["", "⚠️ Significato ricavato dai documenti, non ancora confermato dal developer."]
    return [{"type": "text", "tone": "ai", "md": "\n".join(md) + FOOT}]
