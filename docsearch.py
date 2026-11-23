"""
docsearch.py
------------
«Chiedi» legge i documenti: indice dei TESTI dei requisiti e dei paragrafi delle
sezioni dei PDF collegate alle funzioni, con ricerca in italiano su testi inglesi.

Esempio: «nel documento FRS Air Supply legato al Controllo del compressore
principale nel VZI_New14 a che valore di pressione devono attivarsi i
compressori?» → requisito 2F_06.03.Zefiro-Europe.CONCEPT.46: «All main
compressors shall be ordered to run during start up of the train when MR
pressure is less than 800 kPa, after 3400V AC is available.»

Come funziona (nessuna AI, nessun server: la stessa logica è replicata in
webapp/static/offline.js per la pagina offline dell'utente):

  1. build_index(model, details)   alla creazione della cartella User (e alla
     prima domanda nell'anteprima developer) raccoglie:
       - ogni requisito (ID, Description per gruppo di configurazioni con lo
         stesso testo, funzione, documento e pagina del PDF in cui compare);
       - i paragrafi delle pagine di ogni funzione nei PDF (le righe ripetute
         su molte pagine — intestazioni, piè di pagina — sono scartate).
  2. search(index, domanda, ...)   la domanda è divisa in parole; le parole
     italiane sono tradotte nei termini tecnici inglesi dei documenti (SYN,
     modificabile) e ridotte alla radice (prime 6 lettere); i passaggi sono
     ordinati con BM25 + bonus per funzione/documento/configurazione citati
     e numeri con unità se la domanda chiede un valore. Le parole che
     nominano il documento o la funzione scelgono DOVE cercare, non COSA.
  3. I concetti appresi dall'AI (glossario) aggiungono i loro sinonimi
     (es. MR = main reservoir) alla ricerca.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from typing import Callable, Iterable, Optional

log = logging.getLogger("docsearch")

# Italiano → parole dei documenti (inglese). Chiave = parola o radice italiana
# (prime lettere); i valori sono cercati come radici inglesi.
SYN: dict[str, list[str]] = {
    "compress": ["compressor"], "pression": ["pressure"], "serbato": ["reservoir", "tank"],
    "principal": ["main", "primary"], "ausiliar": ["auxiliary"], "attiv": ["activate", "active", "run", "start", "ordered", "enable", "switch on"],
    "accend": ["start", "switch on", "run"], "avvi": ["start", "run", "startup"], "partenz": ["start"],
    "spegn": ["stop", "switch off"], "ferm": ["stop", "standstill"], "arrest": ["stop"],
    "disattiv": ["deactivate", "disable", "stop"], "abilit": ["enable", "enabled"], "disabilit": ["disable", "inhibit"],
    "soglia": ["threshold", "limit"], "limit": ["limit", "threshold"],
    "tempo": ["time", "delay", "timeout", "seconds"], "ritard": ["delay", "time"], "second": ["seconds", "s"],
    "temperatur": ["temperature"], "velocit": ["speed", "velocity"], "tension": ["voltage"], "corrent": ["current"],
    "potenz": ["power"], "frequenz": ["frequency"], "frenat": ["brake", "braking"], "fren": ["brake", "braking"],
    "emergenz": ["emergency"], "porta": ["door"], "porte": ["doors", "door"], "pantograf": ["pantograph"],
    "interrutt": ["breaker", "switch"], "batteri": ["battery"], "caric": ["charge", "charger", "load"],
    "trazion": ["traction"], "motor": ["motor", "engine"], "convertit": ["converter"], "inverter": ["inverter"],
    "climatizz": ["hvac", "air conditioning"], "condizion": ["condition", "conditioning"], "riscald": ["heating", "heater"],
    "raffredd": ["cooling"], "ventil": ["ventilation", "fan"], "illumin": ["lighting", "light"], "luci": ["lights", "lighting"],
    "fanal": ["headlight", "lamp"], "cabina": ["cab", "cabin"], "banco": ["desk"], "macchinist": ["driver"],
    "conducent": ["driver"], "passegger": ["passenger"], "carrozz": ["car", "coach", "vehicle"], "veicol": ["vehicle"],
    "treno": ["train"], "convogl": ["train", "consist"], "composizion": ["consist", "composition", "multiple"],
    "multipl": ["multiple"], "singol": ["single"], "comando": ["command", "order"], "comand": ["command", "order"],
    "segnal": ["signal"], "allarm": ["alarm", "warning"], "avvis": ["warning", "alarm"], "guast": ["fault", "failure"],
    "anomal": ["fault", "failure", "anomaly"], "diagnost": ["diagnostic", "diagnostics", "event"], "event": ["event"],
    "registr": ["record", "log", "recorder"], "sensor": ["sensor", "transducer"], "pressostat": ["pressure switch"],
    "valvol": ["valve"], "elettrovalv": ["solenoid valve", "magnet valve"], "aria": ["air"], "alimentaz": ["supply", "feed"],
    "aliment": ["supply", "feed", "power"], "fornitur": ["supply"], "controll": ["control", "check", "monitor"],
    "gestion": ["management", "control", "handling"], "monitor": ["monitor", "monitoring"], "verific": ["check", "verify", "test"],
    "prova": ["test"], "test": ["test"], "manutenz": ["maintenance"], "parcheggi": ["parking"], "sosta": ["parking", "standstill"],
    "deposit": ["depot", "parking"], "rotazion": ["rotation", "rotate"], "alternanz": ["rotation", "alternate"],
    "sabbi": ["sand", "sanding"], "pattin": ["slide", "skid", "wsp"], "slittam": ["slip", "slide"], "ruot": ["wheel", "axle"],
    "assi": ["axle"], "carrell": ["bogie"], "boccol": ["axle box", "hotbox"], "sospension": ["suspension"],
    "molla": ["spring"], "molle": ["springs", "spring"], "toilett": ["toilet", "wc"], "acqua": ["water"], "serbatoi": ["tank", "reservoir"],
    "incend": ["fire"], "fumo": ["smoke"], "rilev": ["detection", "detect", "detector"], "estint": ["extinguish", "extinguishing"],
    "uscit": ["output", "exit"], "ingress": ["input", "entry"], "apertur": ["opening", "open"], "chiusur": ["closing", "close"],
    "apri": ["open"], "chiud": ["close"], "blocc": ["lock", "block", "inhibit"], "sblocc": ["unlock", "release"],
    "rilasc": ["release"], "inibiz": ["inhibit", "inhibition"], "consens": ["enable", "permission", "consent"],
    "ridondan": ["redundant", "redundancy"], "radio": ["radio"], "telecamer": ["camera", "cctv"], "annunc": ["announcement", "pa"],
    "informazion": ["information"], "display": ["display", "screen"], "schermo": ["screen", "display"], "pulsant": ["pushbutton", "button"],
    "selettor": ["selector", "switch"], "chiave": ["key"], "linea": ["line", "trainline", "catenary"], "catenari": ["catenary", "line"],
    "neutr": ["neutral section", "neutral"], "fase": ["phase", "section"], "isolament": ["isolation", "insulation"],
    "esclusion": ["isolation", "bypass", "cut out"], "bypass": ["bypass"], "riduzion": ["reduction", "reduced", "derating"],
    "aument": ["increase"], "diminu": ["decrease", "reduce"], "inferior": ["less", "lower", "below"], "minor": ["less", "lower", "below"],
    "superior": ["greater", "higher", "above", "exceed"], "maggior": ["greater", "higher", "above", "more"], "sotto": ["below", "less"],
    "sopra": ["above", "greater"], "massim": ["maximum", "max"], "minim": ["minimum", "min"], "quando": ["when"],
    "dopo": ["after"], "prima": ["before"], "durant": ["during"], "tutti": ["all"], "ciascun": ["each"], "ogni": ["each", "every"],
    "numer": ["number"], "quant": ["number", "value"], "distanz": ["distance"], "lunghezz": ["length"], "peso": ["weight", "load"],
    "accelerazion": ["acceleration"], "deceleraz": ["deceleration"], "livell": ["level"], "stato": ["status", "state"],
    "modalit": ["mode"], "modo": ["mode"], "funzion": ["function"], "ciclo": ["cycle"], "periodo": ["period"], "durata": ["duration", "time"],
    "intervall": ["interval"], "ore": ["hours"], "minut": ["minutes"],
}

STOP = set("""il lo la i gli le un uno una di a da in con su per tra fra e o ma che chi cui non come dove quale quali
del dello della dei degli delle al allo alla ai agli alle dal dallo dalla dai dagli dalle nel nello nella nei negli nelle
sul sullo sulla sui sugli sulle col ed od se ne mi ti ci vi si lo è e' sono sia siano era essere ha hanno ho hai avere
fa fanno fare può possono puo deve devono devo dovrebbe questo questa questi queste quello quella quelli quelle
anche più piu meno molto poco già gia ancora poi però pero quindi cosa cos dimmi spiega spiegami mostra mostrami
vorrei voglio sapere puoi potresti documento documenti doc requisito requisiti legato legata legati legate relativo
relativa relativi relative riguardo riguarda secondo base configurazione configurazioni treno treni pagina pagine
frs trs the of and to in for on by at is are be a an or as with from this that shall which
valore valori quanto quanta quanti quante che""".split())     # «a che valore / quanto»: domanda su un numero (NUMERIC_Q)

NUMERIC_Q = re.compile(r"\b(valor[ei]|quant[oaie]|soglia|soglie|limite|limiti|pression[ei]|temp[oi]|temperatur|velocit|"
                       r"tension[ei]|corrent[ei]|ritard|durat|frequenz|percentual|kpa|bar|km/h|second)", re.I)
UNIT_RX = re.compile(r"\d[\d.,]*\s*(?:kpa|bar|mbar|psi|km/h|kmh|m/s|v\b|kv|vac|vdc|a\b|ka|ma|ms|s\b|sec|seconds?|min|minutes?|h\b|"
                     r"hours?|°c|°|%|hz|khz|kw|w\b|mm|cm|m\b|km|kg|t\b|l\b)", re.I)
ID_RX = re.compile(r"\b\d?[A-Z]{1,3}_\d{2}\.\d{2}\.[\w\-]+\.(?:CONCEPT|TRS|SRS|SYS|REQ|[A-Z]+)\.[\w]+", re.I)
WORD_RX = re.compile(r"[a-zà-ù0-9]+(?:[.,/][0-9]+)*", re.I)


def stem(w: str) -> str:
    w = w.lower()
    if w.isdigit() or len(w) <= 4:
        return w
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    return w[:6]


def tokens(text: str) -> list[str]:
    return [stem(w) for w in WORD_RX.findall((text or "").lower()) if len(w) >= 2]


def _syn_for(w: str) -> list[str]:
    best = ""
    for k in SYN:
        if w.startswith(k) and len(k) > len(best):
            best = k
    return SYN.get(best, [])


def query_terms(q: str, extra: Iterable[tuple[str, list[str]]] = ()) -> tuple[list[str], list[list[str]]]:
    """Radici da cercare: (radici, gruppi) — ogni parola della domanda è un gruppo di alternative
    (la parola stessa + traduzioni), così una parola tradotta in più modi conta una volta sola."""
    groups: list[list[str]] = []
    for w in WORD_RX.findall(q.lower()):
        if len(w) < 2 or w in STOP:
            continue
        alts = {stem(w)}
        for en in _syn_for(w):
            alts.update(stem(x) for x in en.split())
        alts = {a for a in alts if a not in STOP and len(a) >= 2}
        if alts and alts not in [set(g) for g in groups]:
            groups.append(sorted(alts))
    # concetti appresi dall'AI: (termine, [alias]) → gli alias diventano alternative della parola
    # (es. «MR» trova anche «main reservoir»)
    for term, aliases in extra:
        st = stem(term)
        for g in groups:
            if st in g:
                g.extend(a for al in aliases for a in tokens(al) if a not in STOP and a not in g)
                g.sort()
    flat = sorted({a for g in groups for a in g})
    return flat, groups


# ---------------------------------------------------------------------------
# Indice
# ---------------------------------------------------------------------------

def _page_texts(path: str, cache: dict) -> list[str]:
    if path not in cache:
        try:
            import fitz
            with fitz.open(path) as d:
                cache[path] = [p.get_text() for p in d]
        except Exception as exc:
            log.warning("PDF non leggibile %s: %s", path, exc)
            cache[path] = []
    return cache[path]


def _blocks(path: str, page: int, cache: dict) -> list[str]:
    key = (path, page)
    if key not in cache:
        out = []
        try:
            import fitz
            with fitz.open(path) as d:
                if 1 <= page <= len(d):
                    for b in d[page - 1].get_text("blocks"):
                        t = " ".join(str(b[4]).split())
                        if t:
                            out.append(t)
        except Exception as exc:
            log.warning("PDF non leggibile %s: %s", path, exc)
        cache[key] = out
    return cache[key]


def _req_page(rid: str, r: dict, path: str, pages_cache: dict, memo: dict) -> int:
    """Pagina del PDF in cui compare l'ID del requisito (vicino alle pagine della funzione)."""
    page = r.get("first") or r.get("page") or 0
    if not path:
        return page
    key = (path, rid, r.get("first"), r.get("last"))
    if key not in memo:
        pts = _page_texts(path, pages_cache)
        lo, hi = max(1, (r.get("first") or 1) - 1), min(len(pts), (r.get("last") or r.get("first") or 1) + 2)
        needle = rid.split(".")[-1]
        cand = [p for p in range(lo, hi + 1) if rid in pts[p - 1].replace("\n", "")]
        if not cand:
            cand = [p for p in range(1, len(pts) + 1) if rid in pts[p - 1].replace("\n", "")]
        if not cand and needle:
            cand = [p for p in range(lo, hi + 1) if needle in pts[p - 1]]
        memo[key] = cand[0] if cand else page
    return memo[key]


def build_index(model: dict, details: dict, file_of: Callable[[dict], tuple[str, str]],
                progress: Callable[[str], None] = lambda m: None, prose: bool = True) -> dict:
    """
    details:  {fid: explorer.function_detail(model, fid, None)}
    file_of:  ref (qa.doc_ref) → (percorso PDF locale o "", id file per i link)
    Ritorna {"docs": [[nome, codice, idfile]], "items": [[tipo, fid, rid, [config], doc, pagina, testo, alt?]],
             (alt = [[config, doc, pagina]] per le configurazioni con un altro PDF/pagina)
             "funcs": {fid: desc}, "syn": SYN, "stop": [...]}
    """
    docs: list[list] = []
    doc_ix: dict[tuple, int] = {}
    items: list[list] = []
    pages_cache: dict = {}
    blocks_cache: dict = {}
    seen_par: set = set()
    page_memo: dict = {}
    configs = model["configs"]

    def dix(ref: dict, fileid: str) -> int:
        k = (ref.get("doc", ""), ref.get("code", ""), fileid)
        if k not in doc_ix:
            doc_ix[k] = len(docs)
            docs.append([ref.get("doc", ""), ref.get("code", ""), fileid])
        return doc_ix[k]

    from webapp import qa
    n = 0
    for fid, det in sorted(details.items()):
        f = model["functions"].get(fid)
        if not f:
            continue
        n += 1
        if n % 100 == 0:
            progress(f"    indice dei documenti: {n}/{len(details)} funzioni, {len(items)} passaggi")
        refs = {}
        for c in configs:
            r = qa.doc_ref(model, f, c)
            if r:
                path, fileid = file_of(r)
                refs[c] = (r, path, fileid)
        # requisiti: un passaggio per testo distinto (configurazioni con lo stesso testo insieme)
        for rq in det.get("reqs", []):
            groups = rq.get("groups") or [rq.get("desc", "")]
            by_g: dict[int, list[str]] = defaultdict(list)
            for c, cell in rq["cells"].items():
                by_g[cell.get("g", 0)].append(c)
            for g, cs in by_g.items():
                text = groups[g] if 0 <= g < len(groups) else next((rq["cells"][c].get("d", "") for c in cs), "")
                text = " ".join((text or "").split())
                if not text:
                    continue
                # documento e pagina del requisito per ogni configurazione (il PDF della configurazione chiesta)
                where = []
                for c in sorted(cs, key=configs.index):
                    if c in refs:
                        r, path, fileid = refs[c]
                        where.append((0 if path else 1, c, dix(r, fileid), _req_page(rq["id"], r, path, pages_cache, page_memo)))
                where.sort(key=lambda w: w[0])
                d, page = (where[0][2], where[0][3]) if where else (-1, 0)
                alt = [[c, wd, wp] for _o, c, wd, wp in where if (wd, wp) != (d, page)]
                items.append(["r", fid, rq["id"], sorted(cs, key=configs.index), d, page, text] + ([alt] if alt else []))
        if not prose:
            continue
        # paragraphs of the function pages
        done_pages: dict[tuple, list[str]] = {}
        for c, (r, path, fileid) in refs.items():
            if not path or not r.get("first"):
                continue
            for p in range(r["first"], (r.get("last") or r["first"]) + 1):
                done_pages.setdefault((path, p, fileid, r.get("doc", ""), r.get("code", "")), []).append(c)
        for (path, p, fileid, docname, code), cs in done_pages.items():
            for t in _blocks(path, p, blocks_cache):
                if len(t) < 40 or len(t.split()) < 7 or ID_RX.search(t) or t.lower().startswith(("description", "derived", "type ", "sil")):
                    continue
                key = (path, t[:120])
                if key in seen_par:
                    continue
                seen_par.add(key)
                d = dix({"doc": docname, "code": code}, fileid)
                items.append(["p", fid, "", sorted(set(cs), key=configs.index), d, p, t[:1200]])
    # righe ripetute su molte pagine (intestazioni / piè di pagina): scartate
    cnt = Counter(it[6] for it in items if it[0] == "p")
    items = [it for it in items if it[0] != "p" or cnt[it[6]] <= 3]
    progress(f"    indice dei documenti: {sum(1 for i in items if i[0] == 'r')} requisiti, "
             f"{sum(1 for i in items if i[0] == 'p')} paragrafi, {len(docs)} documenti")
    return {"docs": docs, "items": items, "syn": SYN, "stop": sorted(STOP),
            "funcs": {fid: model["functions"][fid].get("desc", "") for fid in details if fid in model["functions"]}}


# ---------------------------------------------------------------------------
# Ricerca
# ---------------------------------------------------------------------------

class Searcher:
    def __init__(self, index: dict):
        self.ix = index
        self.toks = [Counter(tokens(it[6] + " " + it[2])) for it in index["items"]]
        self.len = [sum(t.values()) for t in self.toks]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 1
        df = Counter()
        for t in self.toks:
            df.update(t.keys())
        self.df = df
        self.N = len(self.toks)
        self.fdesc = {fid: set(tokens(fid.replace("_", " ") + " " + d)) for fid, d in index.get("funcs", {}).items()}
        self.ddesc = [set(tokens(d[0].replace("_", " ") + " " + d[1])) for d in index["docs"]]

    def idf(self, t: str) -> float:
        n = self.df.get(t, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def search(self, q: str, configs: Iterable[str] = (), fids: Iterable[str] = (), extra: Iterable[tuple[str, list[str]]] = (),
               limit: int = 6) -> list[dict]:
        for c in sorted(self.ix_configs(), key=len, reverse=True):     # le configurazioni filtrano, non si cercano
            q = re.sub(r"(?<![\w\-])" + re.escape(c) + r"(?![\w\-])", " ", q, flags=re.I)
        for fid in fids:
            q = re.sub(re.escape(fid), " ", q, flags=re.I)
        flat, groups = query_terms(q, extra)
        if not groups:
            return []
        configs, fids = list(configs), list(fids)
        qset = {a for g in groups for a in g}
        # funzioni e documenti citati dalle parole della domanda
        fscore = {fid: len(qset & ws) for fid, ws in self.fdesc.items()}
        fbest = max(fscore.values() or [0])
        dscore = [len(qset & ws) for ws in self.ddesc]
        # Le parole che nominano il documento («FRS Air Supply») o la funzione indicata
        # servono a scegliere DOVE cercare, non COSA: escluse dal punteggio del testo
        # (se ne restano almeno due).
        ctx: set = set()
        dbest = max(dscore or [0])
        if dbest >= 2:
            for j, n in enumerate(dscore):
                if n == dbest:
                    ctx |= self.ddesc[j]
        for fid in fids:
            ctx |= set(tokens(fid.replace("_", " "))) & qset
        if fbest >= 2:      # solo le parole del NOME della funzione («Control of Main Compressor»)
            for fid, n in fscore.items():
                if n == fbest:
                    ctx |= set(tokens(fid.replace("_", " "))) & qset
        content = [g for g in groups if not set(g) & ctx]
        weak = []
        if len(content) >= 2:
            weak = [g for g in groups if set(g) & ctx]     # contano poco e non per la copertura
            groups = content
        numeric = bool(NUMERIC_Q.search(q))
        k1, b = 1.2, 0.75
        out = []
        for i, tf in enumerate(self.toks):
            hit_groups = 0
            s = 0.0
            norm = k1 * (1 - b + b * self.len[i] / self.avg)
            for g in groups:
                # più sinonimi della stessa parola nel passaggio (run + start + ordered) rafforzano il legame
                vals = sorted((self.idf(a) * tf[a] * (k1 + 1) / (tf[a] + norm) for a in g if tf.get(a)), reverse=True)
                if vals:
                    hit_groups += 1
                    s += vals[0] + 0.5 * sum(vals[1:])
            for g in weak:
                vals = [self.idf(a) * tf[a] * (k1 + 1) / (tf[a] + norm) for a in g if tf.get(a)]
                s += 0.3 * max(vals, default=0.0)
            if hit_groups < min(2, len(groups)):
                continue
            it = self.ix["items"][i]
            cover = hit_groups / len(groups)
            s *= 0.5 + cover
            if it[1] in fids:
                s *= 1.8
            elif fbest >= 2 and fscore.get(it[1], 0) >= fbest:
                s *= 1.5
            if it[4] >= 0 and dscore[it[4]] >= 2:
                s *= 1.3
            if configs:
                s *= 1.25 if set(configs) & set(it[3]) else 0.35
            if numeric and UNIT_RX.search(it[6]):
                s *= 1.35
            if it[0] == "r":
                s *= 1.15
            out.append((s, cover, i))
        out.sort(reverse=True)
        res, seen = [], set()
        for s, cover, i in out:
            it = self.ix["items"][i]
            key = it[6][:160]
            if key in seen:
                continue
            seen.add(key)
            di, page = it[4], it[5]
            for c, ad, ap in (it[7] if len(it) > 7 else []):      # il PDF della configurazione chiesta
                if c in configs:
                    di, page = ad, ap
                    break
            d = self.ix["docs"][di] if di >= 0 else ["", "", ""]
            res.append({"kind": it[0], "fid": it[1], "id": it[2], "configs": it[3], "doc": d[0], "code": d[1],
                        "file": d[2], "page": page, "text": it[6], "score": round(s, 2), "cover": round(cover, 2), "terms": [a for g in groups for a in g]})
            if len(res) >= limit:
                break
        return res

    def ix_configs(self) -> set:
        if not hasattr(self, "_cfgs"):
            self._cfgs = {c for it in self.ix["items"] for c in it[3]}
        return self._cfgs


QUESTION_RX = re.compile(r"\?|\b(che|quale|quali|quanto|quanti|quando|come|perch[eé]|dopo|entro|a che|se)\b", re.I)


def answer_blocks(hits: list[dict], configs: Iterable[str] = ()) -> list[dict]:
    """Blocchi della risposta «📄 Dai documenti» (stesso formato di offline.js → docBlocks)."""
    if not hits:
        return []
    h, configs = hits[0], list(configs)
    where = f"nel documento **{h['doc']}**" + (f" ({h['code']})" if h["code"] else "") + (f", pag. {h['page']}" if h["page"] else "")
    where = where[0].upper() + where[1:]
    cf = "configurazioni " + ", ".join(h["configs"])
    if h["kind"] == "r":
        lead = f"### 📄 Dai documenti\n\n{where} — funzione *{h['fid']}*, {cf} — il requisito **{h['id']}** stabilisce che:\n\n> {h['text']}"
    else:
        lead = f"### 📄 Dai documenti\n\n{where} — funzione *{h['fid']}*, {cf} — si legge:\n\n> {h['text']}"
    if configs and not set(configs) & set(h["configs"]):
        lead += f"\n\n⚠️ Il passaggio non risulta nelle configurazioni chieste ({', '.join(configs)}): verifica nel documento."
    lead += "\n\n*Risposta ricavata dalla lettura del testo dei documenti: verifica sempre nel PDF (clic sui passaggi qui sotto).*"
    terms = sorted({t for t in h.get("terms", []) if len(t) >= 3})
    rx = re.compile(r"\b(" + "|".join(map(re.escape, terms)) + r")[a-zà-ù]*", re.I) if terms else None

    def mark(t: str) -> str:
        t = t if len(t) <= 420 else t[:420] + "…"
        return rx.sub(lambda m: f"[[{m.group(0)}]]", t) if rx else t

    items = [{"fid": x["file"], "page": x["page"] or 1, "snippet": mark(x["text"]),
              "file": f"{x['doc']} {x['code'] or ''} — {x['fid']}{' · ' + x['id'] if x['id'] else ''} — {', '.join(x['configs'])}"}
             for x in hits if x["file"]]
    return [{"type": "text", "tone": "know", "md": lead},
            {"type": "hits", "title": "Passaggi dei documenti più pertinenti (clic = apri il PDF alla pagina)", "items": items}]


def quote_answer(hits: list[dict]) -> str:
    """Prima risposta testuale (markdown) a partire dal passaggio migliore."""
    if not hits:
        return ""
    h = hits[0]
    where = f"nel documento **{h['doc']}**" + (f" ({h['code']})" if h["code"] else "") + (f", pag. {h['page']}" if h["page"] else "")
    cfgs = ", ".join(h["configs"])
    if h["kind"] == "r":
        return (f"📄 {where[0].upper() + where[1:]} — funzione *{h['fid']}*, configurazioni {cfgs} — il requisito "
                f"**{h['id']}** stabilisce che:\n\n> {h['text']}")
    return f"📄 {where[0].upper() + where[1:]} — funzione *{h['fid']}*, configurazioni {cfgs} — si legge:\n\n> {h['text']}"
