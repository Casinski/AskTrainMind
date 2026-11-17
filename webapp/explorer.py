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
from typing import Optional

from . import documents as D
from . import qa

# Colori di stato usati dal programma nella riga «Funzioni AI»
_COLOR_STATE = {"00AA00": "g", "FFA500": "o", "C00000": "r", "FF0000": "r"}
STATE_LABELS = {
    "b": "Descrizione propria (riferimento)",
    "g": "Simile alla base (≥ 90 %)",
    "o": "Differenze moderate",
    "r": "Differenze rilevanti",
    "l": "Collegata, non ancora analizzata",
}

_cache: dict[str, dict] = {}
_lock = threading.Lock()


def _ai_detail(doc: dict) -> Optional[dict]:
    return next((d for d in doc.get("details", []) if re.match(r"funzioni ai", d["label"], re.I)), None)


def state_of(doc: dict, c: str) -> str:
    """Stato della funzione per la configurazione nel documento (vedi STATE_LABELS)."""
    d = _ai_detail(doc)
    if d:
        col = (d.get("colors") or {}).get(c, "").lstrip("#").upper()
        if col in _COLOR_STATE:
            return _COLOR_STATE[col]
        txt = (d["values"].get(c) or "").strip()
        if txt:
            if qa.is_reference(txt):
                sim = qa.similarity(txt)
                return "g" if sim is not None and sim >= 90 else ("o" if sim is None or sim >= 50 else "r")
            return "b"
    return "l" if c in (doc.get("links") or {}) else ""


def _worst(states: list[str]) -> str:
    for s in ("r", "o", "g", "b", "l"):
        if s in states:
            return s
    return ""


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
    res = {"configs": cfg_out, "docs": docs_out, "funcs": func_out, "base": base,
           "states": STATE_LABELS}
    with _lock:
        _cache.clear()
        _cache[key] = res
    return res


def _req_kind(kind: str) -> str:
    return {"ref": "ref", "match_base": "eq", "match_nobase": "eq", "diff_base": "diff",
            "diff_nobase": "diff", "only": "only", "unknown": "unk", "absent": ""}.get(kind, "")


def function_detail(model: dict, fid: str, configs: Optional[list[str]] = None) -> Optional[dict]:
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
        extra = []
        for d0, d in qa._details(f, r"^(approf|descrizione|component|note)"):
            v = (d["values"].get(c) or "").strip()
            if v and v.upper() != "TBD":
                extra.append({"label": d["label"].splitlines()[0], "doc": d0["doc"], "text": v})
        fl = fleets.get(c) or {}
        cards.append({
            "config": c, "base": c == base, "state": _worst([s for s in sts if s]),
            "sim": qa.similarity(body), "reference": qa.is_reference(body),
            "text": body, "doc": doc.get("doc", "") if doc else "", "ref": ref, "extra": extra,
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
    for r in f.get("reqs", []):
        listed = {rnm._n(x) for x in r.get("app", "").split(",") if x.strip()}
        cells = {}
        desc = ""
        for c in cs:
            st = rnm.cell_state(c, r["cells"].get(c, ""), listed)
            k = _req_kind(st.kind)
            if k:
                cells[c] = {"k": k, "t": r["cells"].get(c, "")[:1500]}
            desc = desc or rnm.description_from_cell(st)
        if cells:
            reqs.append({"id": re.sub(r"^\s*\d+\)\s*", "", r["id"]), "cells": cells,
                         "desc": " ".join(desc.split())[:400]})
    rnm_rows = [{"id": x["id"], "present": x["present"], "desc": x["desc"][:400], "note": x["note"][:1200]}
                for x in f.get("rnm", [])]
    return {"id": fid, "desc": f.get("desc", ""), "configs": cs, "base": base, "cards": cards,
            "reqs": reqs, "rnm": rnm_rows,
            "index": [{"doc": i["doc"], "par": i["par"], "title": i["title"], "status": i["status"]}
                      for i in f.get("index", [])]}
