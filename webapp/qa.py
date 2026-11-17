"""
webapp/qa.py
------------
Sezione "Chiedi": domande in linguaggio naturale (italiano) sui dati del
file Excel e, se richiesto, sui documenti PDF del computer.

Funzionamento (veloce, senza attese):
  1. riconoscimento di FUNC ID (anche scritti in modo impreciso, o
     descritti a parole) e configurazioni (VZI_FR -> VZ_FR, "base");
  2. riconoscimento dell'intento: differenze, funzionamento, componenti,
     documenti/pagine, requisiti uguali/diversi, figure/tabelle;
  3. risposta DETERMINISTICA costruita dal modello dati (millisecondi),
     composta da blocchi (testo, tabelle, documenti, figure);
  4. facoltativa: spiegazione in italiano generata da Ollama, inviata in
     streaming al browser solo se il modello e' disponibile.
Le risposte sono messe in cache per versione del file Excel.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import threading
from collections import Counter, OrderedDict
from typing import Optional

import config as cfg

from . import documents as D

log = logging.getLogger(__name__)

STOP = set("""il lo la i gli le un uno una di a da in con su per tra fra e o ma che chi cui non
come dove quando quale quali quanto quanti del dello della dei degli delle al allo alla ai agli
alle dal dallo dalla dai dagli dalle nel nello nella nei negli nelle sul sullo sulla sui sugli
sulle mi ti ci vi si puoi potresti mostrami dimmi elenca trova tutte tutti tutto varie vari
funzione funzioni configurazione configurazioni relativi relativa relativo sono sia anche
questo questa quello quella modo semplice livello tecnico tecnica eventuali presenti presente
fra per the and of to is are what how which documento documenti pagina pagine base cosa fa
descrivere descrivi spiega spiegami funziona funzionamento differenze differenza""".split())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-zà-ù0-9]+", (s or "").lower())]


# ---------------------------------------------------------------------------
# Entita'
# ---------------------------------------------------------------------------

class Entities:
    def __init__(self, model: dict):
        self.model = model
        self.funcs: dict[str, dict] = model.get("functions", {})
        self.configs: list[str] = model.get("configs", [])
        self.by_norm = {_norm(f): f for f in self.funcs}
        self.word_df: Counter = Counter()
        self.func_words: dict[str, set[str]] = {}
        for fid in self.funcs:
            ws = {w for w in re.split(r"[_\W]+", fid.lower()) if len(w) > 2}
            # parole della descrizione (italiano), troncate per gestire singolare/plurale
            ws |= {w[:6] for w in _words(self.funcs[fid].get("desc", ""))
                   if len(w) > 4 and w not in STOP and w[:6] not in ("funzio", "garant", "gestir")}
            self.func_words[fid] = ws
            self.word_df.update(ws)

    def functions(self, q: str) -> tuple[list[str], list[str], list[str]]:
        """(funzioni trovate, note sulle interpretazioni, candidati ambigui)"""
        found, notes = [], []
        for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.\-/]{3,}", q):
            if "_" not in tok and not re.search(r"[a-z][A-Z]", tok):
                continue
            n = _norm(tok)
            if n in self.by_norm:
                f = self.by_norm[n]
            else:
                m = difflib.get_close_matches(n, list(self.by_norm), n=1, cutoff=0.82)
                if not m:
                    continue
                f = self.by_norm[m[0]]
                notes.append(f"«{tok}» interpretato come {f}")
            if f not in found:
                found.append(f)
        if found:
            return found, notes, []
        # Nessun FUNC ID esplicito: parole della domanda vs parole dei FUNC ID
        qw = {w for w in _words(q) if len(w) > 3 and w not in STOP}
        if not qw:
            return [], [], []
        scores = {}
        for fid, ws in self.func_words.items():
            s = 0.0
            for w in qw:
                for fw in ws:
                    if w == fw or (len(w) > 4 and (fw.startswith(w[:-1]) or w.startswith(fw) or w[:6] == fw)):
                        s += 1.0 / (1 + self.word_df[fw])
                        break
            if s:
                scores[fid] = s
        if not scores:
            return [], [], []
        ranked = sorted(scores, key=scores.get, reverse=True)
        best = scores[ranked[0]]
        top = [f for f in ranked if scores[f] >= best * 0.999][:6]
        if len(top) == 1:
            return top, [f"Funzione individuata dalla descrizione: {top[0]}"], ranked[1:6]
        return [], [], ranked[:8]

    def configs_in(self, q: str) -> tuple[list[str], list[str]]:
        out, notes = [], []
        normc = {_norm(c): c for c in self.configs}
        for tok in re.findall(r"\bV[A-Z]{1,2}[\w\-]*", q, re.I):
            n = _norm(tok)
            if n in normc:
                c = normc[n]
            else:
                m = difflib.get_close_matches(n, list(normc), n=1, cutoff=0.7)
                if not m:
                    continue
                c = normc[m[0]]
                notes.append(f"«{tok}» interpretato come {c}")
            if c not in out:
                out.append(c)
        # Forme abbreviate: «FR» = VZ_FR, «New14» = VZI_New14 … (sigle corte solo in maiuscolo)
        suff: dict[str, list[str]] = {}
        for c in self.configs:
            sx = re.split(r"[_\-]", c, maxsplit=1)[-1]
            if sx != c and sx.lower() != "base":
                suff.setdefault(sx, []).append(c)
        for sx, cs in suff.items():
            if len(cs) != 1 or cs[0] in out:
                continue
            flags = 0 if len(sx) <= 3 else re.I
            if re.search(rf"(?<![\w\-]){re.escape(sx)}(?![\w\-])", q, flags):
                out.append(cs[0])
        if re.search(r"configurazione\s+base|\bbase\b", q, re.I) and base_config(self.configs) not in out:
            if not any("base" in _norm(c) for c in out):
                out.insert(0, base_config(self.configs))
        return [c for c in self.configs if c in out], notes


def base_config(configs: list[str]) -> str:
    b = getattr(cfg, "BASE_CONFIG_NAME", None) or "VZI_Base"
    return b if b in configs else (configs[0] if configs else b)


# ---------------------------------------------------------------------------
# Intento
# ---------------------------------------------------------------------------

INTENTS = [
    ("figures", r"\bfigur|\btabell|\bimmagin|\bschem[ai]\b|\bdiagramm|\bdisegn|\bgrafic"),
    ("documents", r"\bdocument|\bpdf\b|\bpagin[ae]\b|\bapri\b|dove .*(trattat|descritt)"),
    ("components", r"\bcomponent|\bdispositiv|\bapparecchi|\brel[eè]\b|\bsensor|\bhardware|\bhw\b"),
    ("requirements", r"requisit"),
    ("differences", r"differen|differisc|confront|cambia|variazion|rispetto|diverso|diversi|uguali"),
    ("explain", r"come funziona|funzionamento|descriv|spieg|cosa fa|a cosa serve|semplic|tecnic|cos'?\s*[eè]"),
]


def intent_of(q: str) -> str:
    ql = q.lower()
    for name, rx in INTENTS:
        if re.search(rx, ql):
            if name == "documents" and re.search(r"\bfigur|\btabell", ql):
                return "figures"
            return name
    return "overview"


# ---------------------------------------------------------------------------
# Utilita' sui dati
# ---------------------------------------------------------------------------

_SIM_RE = re.compile(r"SIMILARITY\s*=\s*([\d.,]+)\s*%", re.I)


def _details(func: dict, label_rx: str) -> list[tuple[dict, dict]]:
    out = []
    for doc in func.get("docs", []):
        for d in doc.get("details", []):
            if re.search(label_rx, d["label"], re.I):
                out.append((doc, d))
    return out


def ai_cell(func: dict, config_name: str) -> tuple[str, dict]:
    """Testo "Funzioni AI" della configurazione (primo documento che lo ha)."""
    for doc, d in _details(func, r"^funzioni ai"):
        if d["values"].get(config_name):
            return d["values"][config_name], doc
    return "", {}


def is_reference(text: str) -> bool:
    return bool(re.match(r"\s*RIFERIMENTO\s+\S+", text or "", re.I))


def similarity(text: str) -> Optional[float]:
    m = _SIM_RE.search(text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def clean_ai(text: str) -> str:
    return re.sub(r"\n?Pag\. iniziale:.*$", "", text or "", flags=re.S).strip()


def func_configs(func: dict, configs: list[str]) -> list[str]:
    """Configurazioni per cui la funzione ha dati."""
    have = set()
    for doc in func.get("docs", []):
        have.update(doc.get("links", {}))
        for d in doc.get("details", []):
            have.update(d["values"])
    for r in func.get("reqs", []):
        have.update(r["cells"])
    for ix in func.get("index", []):
        have.update(c for c, s in ix["status"].items() if s.upper().startswith("MATCHED"))
    return [c for c in configs if c in have]


def index_status(func: dict, c: str) -> str:
    for ix in func.get("index", []):
        if c in ix["status"]:
            return ix["status"][c]
    return ""


def _req_rows(func: dict):
    import reqs_not_matched as rnm
    rows = []
    for r in func.get("reqs", []):
        listed = {rnm._n(x) for x in r.get("app", "").split(",") if x.strip()}
        rid = re.sub(r"^\s*\d+\)\s*", "", r["id"])
        rows.append(rnm.ReqRow(func["id"], func.get("desc", ""), rid, listed, dict(r["cells"]), r.get("frs", "")))
    return rows


def req_compare(func: dict, configs: list[str], selected: list[str]) -> dict:
    """Requisiti uguali / diversi fra le configurazioni (logica dell'opzione 5)."""
    import reqs_not_matched as rnm
    rows = _req_rows(func)
    if not rows or len(selected) < 2:
        return {"rows": rows, "findings": [], "equal": [], "covered": []}
    findings = rnm.analyse(configs, rows, selected)
    diff_ids = {f.row.req_id for f in findings}
    covered = []
    for c in selected:
        if any(rnm.cell_state(c, r.cells.get(c, ""), r.listed).kind != "absent" for r in rows):
            covered.append(c)
    equal = [r for r in rows if r.req_id not in diff_ids and
             sum(1 for c in covered if rnm.cell_state(c, r.cells.get(c, ""), r.listed).kind != "absent") >= 2]
    return {"rows": rows, "findings": findings, "equal": equal, "covered": covered}


def _short(t: str, n: int = 260) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"


def _desc_of(row, c: str) -> str:
    import reqs_not_matched as rnm
    st = rnm.cell_state(c, row.cells.get(c, ""), row.listed)
    return rnm.description_from_cell(st)


def doc_ref(model: dict, func: dict, c: str, doc: Optional[dict] = None) -> Optional[dict]:
    """Documento principale della funzione per la configurazione."""
    docs = [doc] if doc else func.get("docs", [])
    for d in docs:
        link = (d.get("links") or {}).get(c)
        if link is None:
            continue
        code = D.doc_code(model, d["doc"], c)
        path = D.resolve_doc(model, d["doc"], c)
        ai_txt = next((x["values"].get(c, "") for x in d.get("details", [])
                       if re.match(r"funzioni ai", x["label"], re.I)), "")
        first, last = D.section_range(ai_txt, link.get("page", 0))
        if link.get("page") and first and not (first <= link["page"] <= last):
            first, last = link["page"], link["page"]
        if not first and link.get("page"):
            first, last = link["page"], link["page"]
        return {"config": c, "doc": d["doc"], "code": code, "page": link.get("page", 0),
                "first": first, "last": last, "url": link.get("url", ""),
                "fid": D.FILES.register(path) if path else "", "file": path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if path else "",
                "local": bool(path)}
    return None


# ---------------------------------------------------------------------------
# Risposte
# ---------------------------------------------------------------------------

class Answer:
    def __init__(self, question: str):
        self.question = question
        self.blocks: list[dict] = []
        self.notes: list[str] = []
        self.followups: list[str] = []
        self.ai_context = ""
        self.ai_task = ""
        self.intent = ""
        self.functions: list[str] = []
        self.configs: list[str] = []
        self.all_configs = False

    def text(self, md: str, tone: str = ""):
        self.blocks.append({"type": "text", "md": md, "tone": tone})

    def title(self, text: str, sub: str = ""):
        self.blocks.append({"type": "title", "text": text, "sub": sub})

    def table(self, columns: list[str], rows: list[list], title: str = "", colors: Optional[dict] = None,
              collapsed: bool = False, max_rows: int = 0):
        self.blocks.append({"type": "table", "title": title, "columns": columns, "rows": rows,
                            "colors": colors or {}, "collapsed": collapsed, "maxRows": max_rows})

    def cards(self, items: list[dict], title: str = ""):
        self.blocks.append({"type": "cards", "title": title, "items": items})

    def to_dict(self) -> dict:
        return {"question": self.question, "intent": self.intent, "functions": self.functions,
                "configs": self.configs, "allConfigs": self.all_configs, "notes": self.notes, "blocks": self.blocks,
                "followups": self.followups, "ai": bool(self.ai_task)}


def _color_map(model: dict) -> dict:
    try:
        import config_colors
        return {c: "#" + config_colors.color_for(c)[-6:] for c in model.get("configs", [])}
    except Exception:
        return {}


ALL_RX = re.compile(r"\btutt[ei]\s+(?:l[ea]\s+|i\s+)?(?:configurazion|varianti|flott|treni|veicol)"
                    r"|\bogni\s+(?:configurazion|flotta|treno|variante)|\b(?:per|in|su)\s+tutt[ei]\b"
                    r"|\btutte\s+quante\b|\bciascuna\s+configurazion"
                    r"|\b(?:tra|fra)\s+(?:le\s+)?(?:varie|diverse)\s+configurazion", re.I)


def targets(a: Answer, model: dict, f: dict, sel: list[str]) -> list[str]:
    """Configurazioni da mostrare: quelle chieste, tutte (se richiesto) o la base."""
    configs = model["configs"]
    if sel:
        return sel
    if a.all_configs:
        return func_configs(f, configs) or [base_config(configs)]
    return [base_config(configs)]


def doc_groups(model: dict, f: dict, cs: list[str]) -> list[dict]:
    """
    Documenti della funzione per le configurazioni, raggruppando quelle che
    puntano allo stesso file e alle stesse pagine (un solo pulsante per tutte).
    """
    groups: "OrderedDict[tuple, dict]" = OrderedDict()
    for doc in f.get("docs", []):
        for c in cs:
            ref = doc_ref(model, f, c, doc)
            if not ref:
                continue
            k = (ref["doc"], ref["code"] or ref["url"].split("#")[0], ref["first"], ref["last"])
            if k in groups:
                groups[k]["configs"].append(c)
            else:
                groups[k] = {**ref, "configs": [c]}
    return list(groups.values())


def docs_block(a: Answer, model: dict, f: dict, cs: list[str], title: str = "") -> list[dict]:
    items = doc_groups(model, f, cs)
    if items:
        a.blocks.append({"type": "docs", "title": title, "items": items})
    return items


def cfg_blocks(a: Answer, model: dict, f: dict, cs: list[str]) -> Optional[dict]:
    """Un blocco per configurazione (stato, similarita', documento, treni)."""
    from . import explorer
    det = explorer.function_detail(model, f["id"], cs)
    if not det:
        return None
    items = []
    for k in det["cards"]:
        items.append({**k, "text": _short(k["text"], 700) if not k["reference"] else "",
                      "extra": [{**x, "text": _short(x["text"], 600)} for x in k["extra"][:3]]})
    trains = {(k.get("fleet", ""), t) for k in items for t in k["trains"]}   # stesso numero, flotte diverse
    blk = {"type": "cfgblocks", "fid": f["id"], "base": det["base"], "items": items,
           "states": explorer.STATE_LABELS, "trains": len(trains)}
    a.blocks.append(blk)
    return det


def answer_differences(a: Answer, model: dict, fids: list[str], sel: list[str]):
    configs = model["configs"]
    base = base_config(configs)
    for fid in fids:
        f = model["functions"][fid]
        cs = sel or func_configs(f, configs)
        if base in configs and base not in cs and not sel:
            cs = [base] + cs
        a.title(fid, f.get("desc", ""))
        if len(cs) >= 2 and (a.all_configs or len(fids) == 1):
            cfg_blocks(a, model, f, cs)   # vista a blocchi con i treni impattati
        rows = []
        cmp_ = req_compare(f, configs, cs) if len(cs) >= 2 else {"rows": _req_rows(f), "findings": [], "covered": cs}
        import reqs_not_matched as rnm
        for c in cs:
            ai_txt, _ = ai_cell(f, c)
            sim = similarity(ai_txt)
            n_req = sum(1 for r in cmp_["rows"] if rnm.cell_state(c, r.cells.get(c, ""), r.listed).kind != "absent")
            n_diff = sum(1 for x in cmp_["findings"] if c in x.missing or
                         rnm.cell_state(c, x.row.cells.get(c, ""), x.row.listed).kind in ("diff_base", "diff_nobase", "only"))
            ref = doc_ref(model, f, c)
            rows.append([c, index_status(f, c) or "—",
                         (ref["code"] + (f" · pag. {ref['page']}" if ref and ref["page"] else "")) if ref else "—",
                         "riferimento" if c == base else (f"{sim:.1f} %" if sim is not None else "—"),
                         n_req, n_diff])
        a.table(["Configurazione", "Index Funzioni", "Documento", "Similarità testo vs " + base,
                 "Requisiti", "Requisiti diversi/assenti"], rows, "Panoramica per configurazione",
                colors={"0": "config"})
        # Differenze descritte nelle righe di dettaglio (Approfondimenti, ...)
        for doc, d in _details(f, r"^(approf|differen|note)"):
            vals = [(c, v) for c, v in d["values"].items() if c in cs and v.strip() and v.strip().upper() != "TBD"]
            if vals:
                a.table(["Configurazione", d["label"].replace("\n", " ")],
                        [[c, v] for c, v in vals], f"{d['label'].splitlines()[0]} — {doc['doc']}",
                        colors={"0": "config"})
        diffs_txt = []
        for c in cs:
            if c == base:
                continue
            t, _ = ai_cell(f, c)
            body = clean_ai(t)
            if body and not re.fullmatch(r"RIFERIMENTO\s+\S+,\s*%\s*SIMILARITY.*", body, re.I | re.S):
                diffs_txt.append([c, body])
        if diffs_txt:
            a.table(["Configurazione", f"Differenze testuali rispetto a {base} (Funzioni AI)"], diffs_txt,
                    "Differenze rilevate nei documenti", colors={"0": "config"})
        if cmp_["findings"]:
            rr = []
            for x in cmp_["findings"]:
                rr.append([x.row.req_id, ", ".join(x.present) or "—", ", ".join(x.missing) or "—",
                           _short(x.description, 220), _short("\n".join(x.lines) + ("\n" + x.ai_note if x.ai_note else ""), 400)])
            a.table(["Requisito", "Presente in", "Assente in", "Descrizione", "Differenza"], rr,
                    f"Requisiti non uguali fra {', '.join(cs)}: {len(rr)}", collapsed=len(rr) > 15, max_rows=15)
        elif len(cs) >= 2 and cmp_["rows"]:
            a.text(f"Tutti i requisiti presenti nel foglio Requisiti risultano **uguali** fra {', '.join(cs)}.", "ok")
        if not cmp_["rows"]:
            a.text("La funzione non ha righe nel foglio **Requisiti** (eseguire l'opzione 1 per estrarle).", "warn")
        a.ai_context += _func_context(model, f, cs, with_reqs=True)
    a.ai_task = ("Riassumi in italiano, in modo chiaro e ordinato, le principali differenze funzionali "
                 "fra le configurazioni indicate per ciascuna funzione. Usa elenchi puntati brevi.")
    a.followups += [f"Quali requisiti differiscono e quali sono uguali tra le varie configurazioni per la funzione {fids[0]}",
                    f"Mostrami i documenti relativi alla funzione {fids[0]}"]


def answer_explain(a: Answer, model: dict, fids: list[str], sel: list[str], simple: bool):
    configs = model["configs"]
    base = base_config(configs)
    for fid in fids:
        f = model["functions"][fid]
        cs = targets(a, model, f, sel)
        a.title(fid, f.get("desc", ""))
        if len(cs) > 1:
            # Vista d'insieme: un blocco per configurazione, poi il testo di riferimento
            cfg_blocks(a, model, f, cs)
            shown = set()
            for c in cs:
                body = clean_ai(ai_cell(f, c)[0])
                if body and not is_reference(body) and body not in shown:
                    shown.add(body)
                    a.text(f"**Funzionamento ({c})**\n\n{body}")
            if not shown:
                bt = clean_ai(ai_cell(f, base)[0])
                if bt:
                    a.text(f"**Funzionamento di riferimento ({base})**\n\n{bt}")
        for c in cs:
            t, _doc = ai_cell(f, c)
            ref = doc_ref(model, f, c)
            body = clean_ai(t)
            if len(cs) == 1:
                if is_reference(body):
                    sim = similarity(body)
                    bt, _ = ai_cell(f, base)
                    a.text(f"**{c}** — il testo del documento è considerato una variante di {base}"
                           + (f" (similarità {sim:.1f} %)" if sim is not None else "") +
                           f". Descrizione di riferimento ({base}):\n\n{clean_ai(bt)}")
                elif body:
                    a.text(f"**{c}** — {body}")
                else:
                    a.text(f"**{c}** — nessuna sintesi «Funzioni AI» nel foglio Funzioni per questa configurazione.", "warn")
                for doc, d in _details(f, r"^(approf|descrizione circ|descrizione$)"):
                    v = d["values"].get(c, "").strip()
                    if v and v.upper() != "TBD":
                        a.text(f"**{d['label'].splitlines()[0]}** ({c}, {doc['doc']}):\n\n{v}", "info")
            if ref and ref["local"] and ref["first"] and len(a.ai_context) < 16000:
                a.ai_context += f"\n### Testo del documento {ref['code']} ({c}), pagine {ref['first']}-{ref['last']}\n"
                a.ai_context += D.section_text(D.FILES.path(ref["fid"]), ref["first"], ref["last"],
                                               9000 if len(cs) == 1 else 3500)
        docs_block(a, model, f, cs, "Documenti")
        a.ai_context += _func_context(model, f, cs, with_reqs=False)
        if len(cs) == 1 and not sel and len(func_configs(f, configs)) > 1:
            a.followups.append(f"Come funziona la funzione {fid} per tutte le configurazioni del treno?")
    a.ai_task = ("Spiega in italiano, in modo SEMPLICE e comprensibile anche a chi non e' esperto, come funziona "
                 "a livello tecnico la funzione: scopo, segnali/sensori coinvolti, logica, condizioni di "
                 "allarme o degrado, effetti sul treno. Usa paragrafi brevi ed elenchi puntati."
                 if simple else
                 "Spiega in italiano come funziona la funzione nella configurazione richiesta: scopo, "
                 "componenti coinvolti, logica di funzionamento, condizioni anomale e reazioni del sistema. "
                 "Usa paragrafi brevi ed elenchi puntati.")
    if len(a.configs) > 1 or a.all_configs:
        a.ai_task += (" Per ogni configurazione indica in cosa differisce dalla configurazione di riferimento, "
                      "basandoti sugli approfondimenti e sulla similarità indicata.")
    a.followups += [f"Quali componenti sono trattati all'interno della funzione {fids[0]}?",
                    f"Mostrami se sono presenti le eventuali figure e tabelle presenti nella configurazione base per la funzione {fids[0]}"]


_ACR_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,}(?:[-/][A-Z0-9]+)*)\b")
_CODE_RE = re.compile(r"\b([A-Z]{2}-[A-Z]\d{3}[A-Z0-9]*)\b")
_NOT_ACR = set("ID AND OR NOT IF THE TBD NA FRS TRS PDF IDU OK ON OFF II III IV".split())


def _glossary(path: str) -> dict[str, str]:
    """Acronimi -> significato dalle prime pagine del documento."""
    out = {}
    try:
        n = min(D.page_count(path), 12)
        txt = "\n".join(D.page_text(path, p) for p in range(1, n + 1))
    except Exception:
        return out
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    for i, l in enumerate(lines[:-1]):
        m = re.fullmatch(r"([A-Z][A-Z0-9\-/]{1,12})(?:\s+(.{4,90}))?", l)
        if not m:
            continue
        meaning = m.group(2) or lines[i + 1]
        if re.match(r"^[A-Z][a-z]", meaning) and not re.fullmatch(r"[A-Z0-9\-/ ]+", meaning):
            out.setdefault(m.group(1), meaning[:90])
    return out


def answer_components(a: Answer, model: dict, fids: list[str], sel: list[str]):
    configs = model["configs"]
    base = base_config(configs)
    for fid in fids:
        f = model["functions"][fid]
        cs = sel or func_configs(f, configs)
        a.title(fid, f.get("desc", ""))
        comp = _details(f, r"component")
        shown = False
        for doc, d in comp:
            rows = []
            for c in cs:
                for line in (d["values"].get(c) or "").splitlines():
                    if line.strip():
                        k, _, v = line.partition("=")
                        rows.append([c, k.strip(), v.strip()])
            if rows:
                shown = True
                a.table(["Configurazione", "Sigla", "Componente"], rows,
                        f"{d['label'].splitlines()[0]} — {doc['doc']}", colors={"0": "config"})
        # Componenti/sistemi citati nel testo (sintesi + documento della configurazione base)
        c0 = base if base in cs or not cs else cs[0]
        text = clean_ai(ai_cell(f, c0)[0])
        ref = doc_ref(model, f, c0)
        path = D.FILES.path(ref["fid"]) if ref and ref["local"] else None
        sect = D.section_text(path, ref["first"], ref["last"], 20000) if path and ref["first"] else ""
        counts: Counter = Counter()
        for src in (text, sect):
            for m in _ACR_RE.finditer(src):
                w = m.group(1)
                if w in _NOT_ACR or w.isdigit() or len(w) < 2 or re.fullmatch(r"[A-Z]\d*", w):
                    continue
                counts[w] += 1
            for m in _CODE_RE.finditer(src):
                counts[m.group(1)] += 1
        gl = _glossary(path) if path else {}
        gl.update({"TCMS": gl.get("TCMS", "Train Control and Monitoring System")})
        learned = {}
        try:
            import knowledge
            for t in knowledge.all_terms():
                learned[t["term"].upper()] = t
                for al in t.get("aliases", []):
                    learned[al.upper()] = t
        except Exception:
            pass

        def meaning(w):
            t = learned.get(w.upper())
            if t:
                import knowledge
                return f"🧠 {t['meaning']} ({knowledge.CATEGORIES.get(t['category'], '')})"
            return gl.get(w, "")
        items = [[w, meaning(w), n] for w, n in counts.most_common(30)
                 if n >= 2 or w in gl or w.upper() in learned]
        if items:
            shown = True
            a.table(["Sigla / sistema", "Significato (🧠 = insegnato all'AI, altrimenti dal documento)", "Citazioni"], items,
                    f"Componenti e sistemi citati nella trattazione ({c0}"
                    + (f", {ref['code']} pag. {ref['first']}-{ref['last']}" if ref and ref["first"] else "") + ")")
        if not shown:
            a.text("Nessun componente trovato nei dati disponibili per questa funzione.", "warn")
        a.ai_context += _func_context(model, f, cs, with_reqs=False)
        if sect:
            a.ai_context += f"\n### Testo del documento ({c0})\n{sect[:9000]}"
    a.ai_task = ("Elenca in italiano i componenti (sensori, apparecchiature, relè, sottosistemi) trattati "
                 "nella funzione, con una breve spiegazione del ruolo di ciascuno.")


def answer_documents(a: Answer, model: dict, fids: list[str], sel: list[str]):
    configs = model["configs"]
    for fid in fids:
        f = model["functions"][fid]
        cs = sel or func_configs(f, configs)
        a.title(fid, f.get("desc", ""))
        items = docs_block(a, model, f, cs, "Documenti (si aprono alla pagina in cui è trattata la funzione)")
        have = {c for x in items for c in x["configs"]}
        missing = [c for c in cs if c not in have]
        if missing:
            a.text(f"Nessun documento collegato nel foglio Funzioni per: {', '.join(missing)}.", "warn")
        if any(not x["local"] for x in items):
            a.text("Alcuni PDF non sono stati trovati nelle cartelle locali: è disponibile il link SharePoint. "
                   "Le cartelle cercate sono indicate nella Guida (ONEDRIVE_DOCS_ROOT, cartella *docs*, "
                   "WEB_EXTRA_DOC_DIRS).", "info")


def answer_figures(a: Answer, model: dict, fids: list[str], sel: list[str]):
    for fid in fids:
        f = model["functions"][fid]
        cs = targets(a, model, f, sel)
        a.title(fid, f.get("desc", ""))
        done: dict[tuple, str] = {}
        for c in cs:
            ref = doc_ref(model, f, c)
            k = (ref["code"], ref["first"], ref["last"]) if ref else None
            if k and k in done:
                a.text(f"**{c}**: stesso documento e stesse pagine di **{done[k]}** (figure e tabelle identiche).", "info")
                continue
            if k:
                done[k] = c
            if not ref:
                a.text(f"**{c}**: nessun documento collegato alla funzione.", "warn")
                continue
            if not ref["local"]:
                a.text(f"**{c}**: il PDF {ref['code']} non è presente sul computer; impossibile analizzarlo.", "warn")
                a.blocks.append({"type": "docs", "items": [{**ref, "configs": [c]}]})
                continue
            path = D.FILES.path(ref["fid"])
            ft = D.figures_tables(path, ref["first"], ref["last"])
            head = (f"**{c}** — {ref['code']} ({ref['doc']}), pagine {ft['first']}–{ft['last']}: "
                    f"**{len(ft['figures'])}** figure, **{len(ft['tables'])}** tabelle"
                    + (f" (oltre a {ft['requirement_tables']} tabelle di requisiti)" if ft["requirement_tables"] else "")
                    + ".")
            if not ft["figures"] and not ft["tables"]:
                head += (" Le pagine della funzione contengono solo tabelle di requisiti: le trovi nel foglio "
                         "Requisiti oppure con «Pagine della funzione» qui sotto." if ft["requirement_tables"]
                         else " Usa «Pagine della funzione» qui sotto per sfogliare le pagine.")
            a.text(head, "ok" if ft["figures"] or ft["tables"] else "info")
            items = []
            for x in ft["figures"]:
                items.append({"kind": "figure", "fid": ref["fid"], "page": x["page"], "bbox": x["bbox"],
                              "caption": x["caption"] or f"Figura a pag. {x['page']}", "config": c})
            for x in ft["tables"]:
                items.append({"kind": "table", "fid": ref["fid"], "page": x["page"], "bbox": x["bbox"],
                              "caption": x["caption"] or f"Tabella a pag. {x['page']} ({x['n_rows']}×{x['n_cols']})",
                              "rows": x["rows"], "config": c})
            if items:
                a.blocks.append({"type": "figures", "items": items})
            a.blocks.append({"type": "docs", "items": [{**ref, "configs": [c]}]})


def answer_requirements(a: Answer, model: dict, fids: list[str], sel: list[str]):
    configs = model["configs"]
    base = base_config(configs)
    for fid in fids:
        f = model["functions"][fid]
        cs = sel or func_configs(f, configs)
        a.title(fid, f.get("desc", ""))
        cmp_ = req_compare(f, configs, cs)
        if not sel and len(cmp_["covered"]) >= 2 and len(cmp_["covered"]) < len(cs):
            cs = cmp_["covered"]
            cmp_ = req_compare(f, configs, cs)
        if not cmp_["rows"]:
            a.text("La funzione non ha requisiti nel foglio **Requisiti**.", "warn")
            continue
        covered = cmp_["covered"]
        not_cov = [c for c in cs if c not in covered]
        a.blocks.append({"type": "stats", "items": [
            {"label": "Requisiti della funzione", "value": len(cmp_["rows"])},
            {"label": "Uguali", "value": len(cmp_["equal"]), "tone": "ok"},
            {"label": "Diversi / assenti", "value": len(cmp_["findings"]), "tone": "bad"},
            {"label": "Configurazioni confrontate", "value": ", ".join(covered) or "—"}]})
        if base in covered and len(covered) > 1:
            import reqs_not_matched as rnm
            mat = []
            for c in covered:
                if c == base:
                    continue
                k = Counter()
                for r in cmp_["rows"]:
                    sb = rnm.cell_state(base, r.cells.get(base, ""), r.listed).kind
                    sc = rnm.cell_state(c, r.cells.get(c, ""), r.listed).kind
                    if sb == "absent" and sc == "absent":
                        continue
                    if sc == "match_base":
                        k["eq"] += 1
                    elif sc == "diff_base":
                        k["diff"] += 1
                    elif sc in ("absent", "unknown") and sb != "absent":
                        k["miss"] += 1
                    elif sc in ("only", "diff_nobase", "match_nobase"):
                        k["only"] += 1
                mat.append([c, k["eq"], k["diff"], k["miss"], k["only"]])
            a.table(["Configurazione", f"Uguali a {base}", "Con differenze", f"Presenti solo in {base}",
                     f"Assenti in {base}"], mat, f"Confronto con la configurazione {base}",
                    colors={"0": "config"})
        if not_cov:
            a.text(f"Configurazioni senza requisiti per questa funzione (non trattata o non estratta): "
                   f"{', '.join(not_cov)}.", "info")
        if cmp_["findings"]:
            rr = [[x.row.req_id, ", ".join(x.present) or "—", ", ".join(x.missing) or "—",
                   _short(x.description, 300), _short("\n".join(x.lines), 400)] for x in cmp_["findings"]]
            a.table(["Requisito", "Presente in", "Assente in", "Descrizione", "Differenza"], rr,
                    f"❌ Requisiti DIVERSI o non presenti in tutte le configurazioni ({len(rr)})",
                    collapsed=len(rr) > 20, max_rows=20)
        if cmp_["equal"]:
            rr = [[r.req_id, ", ".join(c for c in covered if r.cells.get(c, "").strip()),
                   _short(_desc_of(r, base) or next((_desc_of(r, c) for c in covered if _desc_of(r, c)), ""), 300)]
                  for r in cmp_["equal"]]
            a.table(["Requisito", "Configurazioni", "Descrizione"], rr,
                    f"✅ Requisiti UGUALI ({len(rr)})", collapsed=len(rr) > 20, max_rows=20)
        a.ai_context += _func_context(model, f, cs, with_reqs=True)
    a.ai_task = ("Riassumi in italiano quali requisiti sono uguali e quali differiscono fra le configurazioni, "
                 "spiegando il significato pratico delle differenze principali.")


def answer_overview(a: Answer, model: dict, fids: list[str], sel: list[str]):
    configs = model["configs"]
    for fid in fids:
        f = model["functions"][fid]
        cs = func_configs(f, configs)
        a.title(fid, f.get("desc", ""))
        a.blocks.append({"type": "stats", "items": [
            {"label": "Configurazioni", "value": ", ".join(cs) or "—"},
            {"label": "Documenti", "value": ", ".join(d["doc"] for d in f.get("docs", [])) or "—"},
            {"label": "Requisiti", "value": len(f.get("reqs", []))},
            {"label": "Righe in Reqs not matched", "value": len(f.get("rnm", []))}]})
        t = clean_ai(ai_cell(f, base_config(configs))[0])
        if t:
            a.text(t)
        a.ai_context += _func_context(model, f, sel or cs, with_reqs=False)
    a.followups += [f"Come funziona la funzione {fids[0]}?",
                    f"Puoi trovare tutte le differenze tra le varie configurazioni per la funzione {fids[0]}",
                    f"Quali componenti sono trattati all'interno della funzione {fids[0]}?",
                    f"Mostrami i documenti relativi alla funzione {fids[0]}"]
    a.ai_task = "Rispondi in italiano alla domanda usando solo le informazioni fornite."


def _func_context(model: dict, f: dict, cs: list[str], with_reqs: bool) -> str:
    out = [f"\n## Funzione {f['id']}: {f.get('desc', '')}"]
    for c in cs:
        t = clean_ai(ai_cell(f, c)[0])
        if t:
            out.append(f"- Sintesi {c}: {t[:1500]}")
    for doc, d in _details(f, r"^(approf|component|descrizione)"):
        for c, v in d["values"].items():
            if c in cs and v.strip():
                out.append(f"- {d['label'].splitlines()[0]} {c}: {v[:1200]}")
    if with_reqs:
        for r in f.get("rnm", [])[:40]:
            out.append(f"- Requisito {r['id']} presente in {', '.join(r['present'])}: {_short(r['desc'], 200)} "
                       f"| {_short(r['note'], 300)}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Ricerca nei documenti del computer
# ---------------------------------------------------------------------------

def _search_terms(q: str) -> tuple[list[str], str]:
    """Parole significative della domanda e frase esatta (FUNC ID o testo fra virgolette)."""
    phrase = ""
    m = re.search(r"[\"«“]([^\"»”]{3,80})[\"»”]", q)
    if m:
        phrase = m.group(1)
    fm = re.search(r"\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b", q)
    if fm and not phrase:
        phrase = fm.group(0).replace("_", " ")
    rest = q.replace(m.group(0), " ") if m else q
    if fm:
        rest = rest.replace(fm.group(0), " ")
    noise = {"cerca", "trova", "mostra", "mostrami", "documenti", "documento", "computer", "dove", "parla",
             "parlano", "pagina", "pagine", "nei", "negli", "file", "pdf", "funzione", "funzioni", "relativi",
             "relativo", "presente", "presenti", "anche", "tutti", "tutte", "quali", "quale", "sono"}
    terms = [w for w in re.findall(r"[A-Za-z0-9][\w\-]{1,}", rest)
             if w.lower() not in STOP and w.lower() not in noise and (len(w) > 2 or w.isupper())]
    return list(dict.fromkeys(terms))[:10], phrase


def quick_search(q: str, limit: int = 40, extra_terms: Optional[list[str]] = None) -> dict:
    """
    Ricerca veloce (indice full-text SQLite) nei PDF del computer, con risultati
    raggruppati per documento: prima le pagine che contengono TUTTE le parole,
    poi (se servono) quelle che ne contengono almeno una.
    """
    idx = D.text_index()
    st = idx.stats()
    if not st["indexed_files"] and not st["running"]:
        idx.update_async()
    terms, phrase = _search_terms(q)
    terms += [t for t in (extra_terms or []) if t not in terms]
    hits: list[dict] = []
    seen: set = set()
    queries = []
    if phrase and terms:
        queries.append((terms, phrase, "and"))
    if phrase:
        queries.append(([], phrase, "and"))
    if terms and len(terms) > 1 or (terms and not phrase):
        queries.append((terms, "", "and"))
    if len(terms) + bool(phrase) > 1:
        queries.append((terms, phrase, "or"))
    for t, p, m in queries:
        if len(hits) >= limit or (m == "or" and len(hits) >= 5):
            break
        for h in idx.search(t, limit, p, m, 30):
            if (h["path"], h["page"]) not in seen:
                seen.add((h["path"], h["page"]))
                h["partial"] = m == "or"
                hits.append(h)
    groups: "OrderedDict[str, dict]" = OrderedDict()
    for h in hits[:limit]:
        g = groups.get(h["path"])
        if g is None:
            p = h["path"].replace("\\", "/")
            g = groups[h["path"]] = {"file": h["file"], "fid": h["fid"], "folder": p.rsplit("/", 1)[0][-80:],
                                     "pages": [], "partial": bool(h.get("partial"))}
        if len(g["pages"]) < 6:
            g["pages"].append({"page": h["page"], "snippet": h["snippet"]})
    return {"groups": list(groups.values()), "terms": terms, "phrase": phrase, "stats": st,
            "hits": len(hits)}


def doc_search(a: Answer, q: str, fids: list[str], model: dict):
    if fids:
        # i documenti sono in inglese: si cerca il nome della funzione (senza prefisso)
        words = [w for w in fids[0].split("_")[1:] if len(w) > 2] or fids[0].split("_")
        res = quick_search(f'"{" ".join(words)}"', 40)
    else:
        res = quick_search(q, 40)
    st = res["stats"]
    if st["running"] or not st["indexed_files"]:
        a.text(f"Indicizzazione dei PDF del computer in corso ({st.get('done', 0)}/{st.get('total', 0)}): "
               "i risultati saranno più completi tra poco.", "info")
    if res["groups"]:
        a.blocks.append({"type": "search", "title": "Risultati nei documenti del computer",
                         "groups": res["groups"], "terms": res["terms"], "phrase": res["phrase"]})
        a.ai_context += "\n### Estratti dai documenti\n" + "\n".join(
            f"- {g['file']} pag. {p['page']}: {p['snippet']}" for g in res["groups"][:6] for p in g["pages"][:2])
    else:
        a.text("Nessun risultato nei documenti indicizzati.", "info")


# ---------------------------------------------------------------------------
# Punto di ingresso
# ---------------------------------------------------------------------------

_cache: "OrderedDict[str, dict]" = OrderedDict()
_contexts: "OrderedDict[str, dict]" = OrderedDict()
_lock = threading.Lock()


def ask(question: str, model: dict, snap_key: str, search_docs: bool = False) -> dict:
    q = (question or "").strip()
    ck = hashlib.sha1(f"{snap_key}|{search_docs}|{q.lower()}".encode()).hexdigest()
    with _lock:
        if ck in _cache:
            _cache.move_to_end(ck)
            return {**_cache[ck], "cached": True}
    ent = Entities(model)
    fids, fnotes, ambiguous = ent.functions(q)
    sel, cnotes = ent.configs_in(q)
    a = Answer(q)
    a.intent = intent_of(q)
    a.functions, a.configs = fids, sel
    a.all_configs = bool(ALL_RX.search(q)) and not sel
    a.notes = fnotes + cnotes
    try:
        if fids:
            handlers = {"differences": answer_differences, "requirements": answer_requirements,
                        "components": answer_components, "documents": answer_documents,
                        "figures": answer_figures, "overview": answer_overview}
            if a.intent == "explain":
                answer_explain(a, model, fids, sel, simple=bool(re.search(r"semplic|facile|parole", q, re.I)))
            else:
                handlers[a.intent](a, model, fids, sel)
        else:
            if ambiguous:
                a.text("Non ho individuato con certezza la funzione. Forse intendevi una di queste?", "info")
                a.blocks.append({"type": "chips", "items": [
                    {"label": f, "desc": model["functions"][f].get("desc", ""), "fid": f} for f in ambiguous]})
            else:
                a.text("Non ho trovato una funzione nella domanda. Indica il FUNC ID (es. "
                       "*BOG_Hotbox_Detection*) oppure alcune parole del nome della funzione.", "warn")
            a.ai_task = "Rispondi in italiano alla domanda usando le informazioni fornite, se pertinenti."
            a.ai_context = "\n".join(_func_context(model, model["functions"][f], model["configs"][:2], False)
                                     for f in ambiguous[:3])
        if search_docs:
            doc_search(a, q, fids, model)
    except Exception as exc:
        log.exception("Errore nella risposta")
        a.text(f"Errore durante l'elaborazione della domanda: {exc}", "bad")
    res = a.to_dict()
    res["id"] = ck
    with _lock:
        _cache[ck] = res
        _contexts[ck] = {"question": q, "task": a.ai_task, "context": a.ai_context[:24000]}
        while len(_cache) > 200:
            _cache.popitem(last=False)
        while len(_contexts) > 200:
            _contexts.popitem(last=False)
    return res


def clear_cache() -> None:
    """Svuota la cache delle risposte (es. dopo aver insegnato nuovi termini all'AI)."""
    with _lock:
        _cache.clear()


def ai_context(answer_id: str) -> Optional[dict]:
    with _lock:
        return _contexts.get(answer_id)


def suggestions(model: dict) -> list[str]:
    funcs = list(model.get("functions", {}))
    f1 = "BOG_Hotbox_Detection" if "BOG_Hotbox_Detection" in funcs else (funcs[0] if funcs else "FUNC_ID")
    f2 = "AIR_Control_of_Main_Compressor" if "AIR_Control_of_Main_Compressor" in funcs else (funcs[1] if len(funcs) > 1 else f1)
    cs = model.get("configs", [])
    c2 = cs[1] if len(cs) > 1 else "VZI_New14"
    return [
        f"Puoi trovare tutte le differenze tra le varie configurazioni per le funzioni {f2}, {f1}",
        f"Come funziona la funzione {f1} nella configurazione {base_config(cs)}?",
        f"Quali componenti sono trattati all'interno della funzione {f1}?",
        f"Mostrami i documenti relativi alla funzione {f1} per le configurazioni {base_config(cs)} e {c2}",
        f"Quali requisiti differiscono e quali sono uguali tra le varie configurazioni per la funzione {f1}",
        f"Potresti descrivere in modo semplice come funziona a livello tecnico la funzione {f1}",
        f"Mostrami se sono presenti le eventuali figure e tabelle presenti nella configurazione base per la funzione {f1}",
    ]


# ---------------------------------------------------------------------------
# Ollama (streaming HTTP, nessuna dipendenza obbligatoria)
# ---------------------------------------------------------------------------

def ollama_host() -> str:
    import os
    h = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    return h if h.startswith("http") else "http://" + h


_ai_status = {"t": 0.0, "ok": False, "msg": ""}


def ollama_probe() -> dict:
    """Stato reale di Ollama e del modello configurato (ignora WEB_QA_USE_AI)."""
    try:
        import requests
        r = requests.get(ollama_host() + "/api/tags", timeout=1.5)
        names = [m.get("name") or m.get("model") or "" for m in r.json().get("models", [])]
        target = cfg.OLLAMA_MODEL
        ok = target in names or f"{target}:latest" in names
        msg = f"Ollama attivo, modello {target}" if ok else f"Modello {target} non installato (ollama pull {target})"
        return {"ok": ok, "reachable": True, "msg": msg}
    except Exception:
        return {"ok": False, "reachable": False, "msg": "Ollama non raggiungibile"}


def ai_status(force: bool = False) -> dict:
    import time
    if not getattr(cfg, "WEB_QA_USE_AI", True):
        return {"ok": False, "msg": "Disattivata (WEB_QA_USE_AI = False)"}
    if not force and time.time() - _ai_status["t"] < 30:
        return {"ok": _ai_status["ok"], "msg": _ai_status["msg"]}
    st = ollama_probe()
    _ai_status.update(t=time.time(), ok=st["ok"], msg=st["msg"])
    return {"ok": st["ok"], "msg": st["msg"]}


def ai_stream(answer_id: str):
    """Generatore di frammenti di testo (streaming da Ollama)."""
    ctx = ai_context(answer_id)
    if not ctx:
        yield "Contesto della domanda non disponibile: ripeti la domanda."
        return
    if not ai_status()["ok"]:
        yield "L'AI locale non è disponibile: " + ai_status()["msg"]
        return
    prompt = (
        "Sei un tecnico ferroviario esperto dei treni ETR1000 (Frecciarossa 1000). Rispondi SEMPRE in "
        "ITALIANO, con un tono chiaro e professionale, usando il formato Markdown (titoletti brevi, "
        "elenchi puntati, **grassetto** per i termini chiave). Basati SOLO sulle informazioni fornite: "
        "se un'informazione non c'e', dillo. Non inventare valori numerici.\n\n"
        f"COMPITO: {ctx['task']}\n\nDOMANDA DELL'UTENTE: {ctx['question']}\n\n"
        f"INFORMAZIONI DISPONIBILI:\n{ctx['context']}\n")
    try:
        import knowledge
        prompt = knowledge.augment(prompt)
    except Exception as exc:
        log.debug(f"Glossario non applicato: {exc}")
    ck = hashlib.sha1((cfg.OLLAMA_MODEL + prompt).encode()).hexdigest()
    cf = D.cache_dir() / "ai_answers" / f"{ck}.txt"
    if cf.is_file():
        yield cf.read_text(encoding="utf-8")
        return
    import requests
    out = []
    try:
        with requests.post(ollama_host() + "/api/chat", stream=True, timeout=(3, int(getattr(cfg, "OLLAMA_TIMEOUT", 300))),
                           json={"model": cfg.OLLAMA_MODEL, "stream": True,
                                 "keep_alive": getattr(cfg, "OLLAMA_KEEP_ALIVE", "30m"),
                                 "messages": [{"role": "user", "content": prompt}],
                                 "options": {"temperature": 0.2, "num_ctx": max(8192, int(getattr(cfg, "OLLAMA_NUM_CTX", 8192))),
                                             "num_predict": 900}}) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                piece = (data.get("message") or {}).get("content", "")
                if piece:
                    out.append(piece)
                    yield piece
                if data.get("done"):
                    break
    except Exception as exc:
        yield f"\n\n[Errore AI: {exc}]"
        return
    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text("".join(out), encoding="utf-8")
    except OSError:
        pass
