"""
webapp/explorer.py
------------------
Dati della vista «Esplora» (grafica a blocchi):

    Configurazione treno  →  FRS / DOC ID  →  Funzioni  →  Funzioni AI + Requisiti

tree(model)            albero compatto (calcolato una volta per versione del file)
function_detail(...)   dettaglio di una funzione per tutte le configurazioni
"""
from __future__ import annotations

import re
import threading
from collections import Counter
from pathlib import Path
from typing import Optional

from . import documents as D
from . import qa

# Colori di stato usati dal programma nella riga «Funzioni AI»
_COLOR_STATE = {"00AA00": "g", "FFA500": "o", "C00000": "r", "FF0000": "r"}
STATE_LABELS = {
    "b": "Descrizione propria (riferimento)",
    "g": "Simile alla base (verde, ≥ 80 %)",
    "o": "Differenze moderate (arancione, 50–80 %)",
    "r": "Differenze rilevanti (rosso, < 50 %)",
    "l": "Collegata, non ancora analizzata",
    "x": "Documento non disponibile (link da inserire o da verificare)",
}

_cache: dict[str, dict] = {}
_lock = threading.Lock()


def _ai_detail(doc: dict) -> Optional[dict]:
    return next((d for d in doc.get("details", []) if re.match(r"funzioni ai", d["label"], re.I)), None)


def _sim_thresholds() -> tuple[float, float]:
    try:
        import config as cfg
        return (float(getattr(cfg, "FUNC_SIMILARITY_HIGH", 80.0)),
                float(getattr(cfg, "FUNC_SIMILARITY_MEDIUM", 50.0)))
    except Exception:
        return 80.0, 50.0


def state_of(doc: dict, c: str) -> str:
    """Stato della funzione per la configurazione nel documento (vedi STATE_LABELS)."""
    d = _ai_detail(doc)
    if d:
        col = (d.get("colors") or {}).get(c, "").lstrip("#").upper()
        if col in _COLOR_STATE:
            return _COLOR_STATE[col]
        txt = (d["values"].get(c) or "").strip()
        if txt and qa.link_issue_of_text(txt):
            return "x"
        if txt:
            if qa.is_reference(txt):
                sim = qa.similarity(txt)
                g, m = _sim_thresholds()
                return "g" if sim is not None and sim >= g else ("o" if sim is None or sim >= m else "r")
            return "b"
    return "l" if c in (doc.get("links") or {}) else ""


def _worst(states: list[str]) -> str:
    for s in ("r", "o", "g", "b", "l", "x"):
        if s in states:
            return s
    return ""


_STD_LABEL = re.compile(r"^(link|rif\.?\s*pagina|funzioni\s*ai|\(senza etichetta\))", re.I)


def config_documents(model: dict) -> dict[str, list[dict]]:
    """
    Documenti del foglio CONFIG (FPD, FS, WT, EPL, GEN, ICD, FRS) per
    configurazione, consultabili dalla pagina web accanto agli FRS. Se la
    cartella <configurazione>/CONFIG/<tipo> esiste sul computer vengono
    elencati solo i documenti presenti; altrimenti quelli con un codice valido
    (link SharePoint).
    """
    import config as cfg
    import config_db
    folders = getattr(cfg, "CONFIG_DOC_FOLDERS", {})
    base = model.get("sharepoint_base", "")
    roots = [p for p in (getattr(cfg, "ONEDRIVE_DOCS_ROOT", None),) if p]
    out: dict[str, list[dict]] = {}
    for c in model["configs"]:
        items = []
        for d in model.get("confdocs") or []:
            cat = d.get("category", "")
            v = (d.get("codes") or {}).get(c)
            if cat not in folders or not v or not config_db.code_variants(v.get("code", "")):
                continue
            folder_known = any((Path(r) / c / "CONFIG" / config_db.folder_of(cat)).is_dir() for r in roots)
            path = config_db.find_file(c, cat, v["code"], d.get("ext", "pdf"))
            if folder_known and not path:
                continue
            code = config_db.code_variants(v["code"])[0]
            items.append({"cat": cat, "label": config_db.label_of(cat), "doc": d["doc_id"],
                          "desc": d.get("description", ""), "code": code, "rev": v.get("rev", ""),
                          "url": config_db.sharepoint_url(base, c, cat, v["code"], d.get("ext", "pdf")),
                          "fid": D.FILES.register(str(path)) if path else "", "local": bool(path),
                          "pdf": (d.get("ext") or "pdf") == "pdf"})
        if items:
            order = list(folders)
            items.sort(key=lambda x: (order.index(x["cat"]), x["doc"].lower()))
            out[c] = items
    return out


def tree(model: dict, key: str) -> dict:
    with _lock:
        if key in _cache:
            return _cache[key]
    configs = model["configs"]
    fleets = model.get("fleets", {})
    funcs = model["functions"]
    by_cfg: dict[str, dict[str, list[str]]] = {c: {} for c in configs}
    fstate: dict[str, dict[str, str]] = {}
    fsim: dict[str, dict[str, float]] = {}
    for fid, f in funcs.items():
        st: dict[str, list[str]] = {}
        for doc in f.get("docs", []):
            for c in configs:
                s = state_of(doc, c)
                if not s:
                    continue
                st.setdefault(c, []).append(s)
                lst = by_cfg[c].setdefault(doc["doc"], [])
                if fid not in lst:
                    lst.append(fid)
            d = _ai_detail(doc)
            if d:
                for c, v in d["values"].items():
                    sim = qa.similarity(v)
                    if sim is not None:
                        fsim.setdefault(fid, {})[c] = sim
        fstate[fid] = {c: _worst(v) for c, v in st.items()}
    base = qa.base_config(configs)
    cfg_out = []
    for c in configs:
        docs = by_cfg[c]
        cnt = Counter(fstate[f].get(c, "") for fs in docs.values() for f in set(fs))
        fl = fleets.get(c) or {}
        cfg_out.append({"name": c, "base": c == base, "docs": len(docs),
                        "funcs": len({f for fs in docs.values() for f in fs}),
                        "states": dict(cnt), "fleet": fl.get("name", ""), "trains": fl.get("trains", []),
                        "native": fl.get("native", ""), "bl": fl.get("bl", "")})
    docs_out = {}
    for c in configs:
        items = []
        for doc, fs in sorted(by_cfg[c].items(), key=lambda kv: kv[0].lower()):
            cnt = Counter(fstate[f].get(c, "") for f in fs)
            items.append({"doc": doc, "code": D.doc_code(model, doc, c), "funcs": sorted(fs),
                          "states": dict(cnt)})
        docs_out[c] = items
    func_out = {}
    for fid, f in funcs.items():
        func_out[fid] = {"desc": f.get("desc", ""), "st": fstate.get(fid, {}), "sim": fsim.get(fid, {}),
                         "req": len(f.get("reqs", [])), "rnm": len(f.get("rnm", [])),
                         "docs": [d["doc"] for d in f.get("docs", [])]}
    try:
        confdocs = config_documents(model)
    except Exception:
        confdocs = {}
    res = {"configs": cfg_out, "docs": docs_out, "funcs": func_out, "base": base,
           "states": STATE_LABELS, "confdocs": confdocs}
    with _lock:
        _cache.clear()
        _cache[key] = res
    return res


def _req_kind(kind: str) -> str:
    return {"ref": "ref", "match_base": "eq", "match_nobase": "eq", "diff_base": "diff",
            "diff_nobase": "diff", "only": "only", "unknown": "unk", "absent": ""}.get(kind, "")


_gdesc_cache: dict = {"id": None, "data": {}}


def _global_descs(model: dict) -> dict:
    """Description per ID di requisito lette da tutto il foglio (calcolate una volta per modello)."""
    import reqs_not_matched as rnm
    with _lock:
        if _gdesc_cache["id"] != id(model):
            rows = [r for f in model.get("functions", {}).values() for r in qa._req_rows(f)]
            _gdesc_cache.update(id=id(model), data=rnm.global_descriptions(model["configs"], rows))
        return _gdesc_cache["data"]


_LABEL_RE = re.compile(r"^(MATCHED|MISS VZI_BASE REQ(, MATCHED|, FOUND DIFF)?)\s*$", re.I)


def _cell_note(text: str, kind: str) -> str:
    """Testo della cella che non e' il requisito: spiegazione delle differenze (AI) o avvisi."""
    if kind in ("ref", "match_base", "absent"):
        return ""
    t = (text or "").replace("\r", "").strip()
    lines = t.split("\n", 1)
    if _LABEL_RE.match(lines[0].strip()):
        t = lines[1] if len(lines) > 1 else ""
    i = t.rfind("Description:")
    if i >= 0:
        t = t[:i]
    t = re.sub(r"[—\-]{5,}", " ", t).strip(" \n[]")
    if kind == "only" and i < 0 and not t.startswith("Description non estratta"):
        return ""          # MISS VZI_BASE REQ + Description senza etichetta: e' il testo stesso
    return t[:3000]


def _req_entry(row, view: dict, ai: bool = False) -> dict:
    """
    Requisito per Esplora: stato per configurazione ("g" = numero del testo),
    testi distinti ("groups") e, per ogni coppia di testi diversi, la
    spiegazione discorsiva delle differenze di concetto ("gd", chiave "i-j").
    """
    import req_ai_comparator as reqai
    groups: list[str] = []
    for v in view.values():
        g = v["group"]
        if g >= 0:
            while len(groups) <= g:
                groups.append("")
            groups[g] = groups[g] or v["desc"]
    # testi uguali a meno di sillabazione/punteggiatura ("re- activation" =
    # "re-activation"): stesso requisito, un solo gruppo
    remap = list(range(len(groups)))
    for j in range(len(groups)):
        for i in range(j):
            if remap[i] == i and groups[i] and groups[j] and reqai.same_text(groups[i], groups[j]):
                remap[j] = i
                break
    keep = sorted(set(remap))
    renum = {old: new for new, old in enumerate(keep)}
    groups = [groups[i] for i in keep]
    names: dict[int, list[str]] = {}
    cells = {}
    for c, v in view.items():
        g = renum[remap[v["group"]]] if v["group"] >= 0 else -1
        if g >= 0:
            names.setdefault(g, []).append(c)
        cell = {"k": _req_kind(v["kind"]), "g": g}
        note = _cell_note(row.cells.get(c, ""), v["kind"])
        # la spiegazione del foglio (riferita a VZI_Base, con le parole citate) o
        # l'avviso «Description assente» superato dal testo recuperato sono
        # sostituiti dalla spiegazione concettuale calcolata qui sotto
        if note and g >= 0 and groups[g] and v["kind"] in ("diff_base", "diff_nobase", "unknown"):
            note = ""
        if note:
            cell["t"] = note
        if g < 0 and v["desc"]:
            cell["d"] = v["desc"]
        cells[c] = cell
    # requisito ritrovato dopo un confronto non riuscito, con lo stesso testo
    # del riferimento: è un MATCHED
    for c, cell in cells.items():
        if cell["g"] == 0 and groups and groups[0] and view[c]["kind"] == "unknown":
            cell["k"] = "eq"
    desc = next((x for x in groups if x), "") or next((v["desc"] for v in view.values() if v["desc"]), "")
    rq = {"id": row.req_id, "cells": cells, "desc": " ".join(desc.split())}
    if len(groups) > 1:      # testi diversi fra le configurazioni (indice = cella "g")
        rq["groups"] = [x.strip() for x in groups]
        gd = {}
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if groups[i] and groups[j]:
                    t = reqai.concept_diff(groups[i], ", ".join(names.get(i, [])) or f"testo {i + 1}",
                                           groups[j], ", ".join(names.get(j, [])) or f"testo {j + 1}",
                                           use_ai=ai)
                    if t:
                        gd[f"{i}-{j}"] = t
        if gd:
            rq["gd"] = gd
            # nomi usati nella spiegazione: la pagina li sostituisce con le sole
            # configurazioni mostrate
            rq["gn"] = [", ".join(names.get(i, [])) or f"testo {i + 1}" for i in range(len(groups))]
    return rq


def function_detail(model: dict, fid: str, configs: Optional[list[str]] = None,
                    ai: bool = False) -> Optional[dict]:
    import reqs_not_matched as rnm
    f = model["functions"].get(fid)
    if not f:
        return None
    all_cfg = model["configs"]
    cs = [c for c in (configs or qa.func_configs(f, all_cfg)) if c in all_cfg] or qa.func_configs(f, all_cfg)
    base = qa.base_config(all_cfg)
    fleets = model.get("fleets", {})
    cards = []
    for c in cs:
        txt, doc = qa.ai_cell(f, c)
        body = qa.clean_ai(txt)
        ref = qa.doc_ref(model, f, c)
        sts = [state_of(d, c) for d in f.get("docs", [])]
        # Altri documenti collegati alla funzione per la configurazione (es. FS
        # sotto l'FRS) e documenti con Rif. Pagina "X" (aggiornati nel foglio
        # CONFIG, pagina da reinserire): questi ultimi non vengono mostrati
        links, invalid = [], []
        for d0 in f.get("docs", []):
            lk = (d0.get("links") or {}).get(c)
            if lk is None:
                continue
            if lk.get("invalid"):
                invalid.append(d0["doc"])
            elif not (ref and d0["doc"] == ref["doc"]):
                r2 = qa.doc_ref(model, f, c, doc=d0)
                if r2:
                    links.append(r2)
        main_invalid = bool(ref and ref["doc"] in invalid)
        # Righe aggiunte dall'utente sotto Link / Rif. Pagina / Funzioni AI
        # (es. «Approfondimenti (data 01/07/2026)», «Descrizione circuitale»)
        extra = []
        for d0, d in qa._details(f, r"."):
            if _STD_LABEL.match(d["label"].strip()) or d0["doc"] in invalid:
                continue
            v = (d["values"].get(c) or "").strip()
            if v and v.upper() != "TBD":
                extra.append({"label": " ".join(d["label"].split()), "doc": d0["doc"], "text": v})
        fl = fleets.get(c) or {}
        # Senza documento la configurazione non si confronta: solo il messaggio
        issue = qa.link_issue(f, c)
        if not issue and not body:
            if ref is None:
                issue = "missing"
            elif not ref.get("url") and not ref.get("local"):
                issue = "broken"
        if issue:
            body = ""
        cards.append({
            "config": c, "base": c == base,
            "state": "x" if issue else _worst([s for s in sts if s]),
            "sim": None if issue else qa.similarity(body),
            "reference": False if issue else qa.is_reference(body),
            "diffs": [] if issue else qa.major_diffs(body),
            "linkIssue": issue,
            "linkMsg": {"missing": qa.LINK_MISSING_TXT, "broken": qa.DOC_NOT_FOUND_TXT}.get(issue, ""),
            "text": body, "doc": doc.get("doc", "") if doc else "",
            "ref": None if main_invalid else ref, "extra": extra, "links": links, "invalid": invalid,
            # ordine dei blocchi documento (Link / Rif. Pagina / Funzioni AI / righe extra) nel foglio Funzioni
            "order": [d0["doc"] for d0 in f.get("docs", [])],
            "trains": fl.get("trains", []), "fleet": fl.get("name", ""),
            "index": qa.index_status(f, c),
        })
    # Configurazioni che condividono lo stesso documento (stesso trattamento)
    same: dict[str, list[str]] = {}
    for k in cards:
        if k["ref"] and k["ref"].get("code"):
            same.setdefault(f"{k['ref']['code']}|{k['ref'].get('page', 0)}", []).append(k["config"])
    for k in cards:
        if k["ref"] and k["ref"].get("code"):
            k["sameDoc"] = [x for x in same[f"{k['ref']['code']}|{k['ref'].get('page', 0)}"] if x != k["config"]]
    reqs = []
    gdesc = _global_descs(model)
    for row in qa._req_rows(f):
        view = rnm.row_view(row, cs, gdesc)
        if not view:
            continue
        rq = _req_entry(row, view, ai)
        reqs.append(rq)
    rnm_rows = [{"id": x["id"], "present": x["present"], "desc": x["desc"][:400], "note": x["note"][:1200]}
                for x in f.get("rnm", [])]
    return {"id": fid, "desc": f.get("desc", ""), "configs": cs, "base": base, "cards": cards,
            "reqs": reqs, "rnm": rnm_rows,
            "index": [{"doc": i["doc"], "par": i["par"], "title": i["title"], "status": i["status"]}
                      for i in f.get("index", [])]}
