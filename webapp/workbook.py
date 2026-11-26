"""
webapp/workbook.py
------------------
Converte i fogli "Index Funzioni", "Funzioni", "Requisiti" e "Reqs not
matched" in JSON per la griglia web e costruisce il modello dati usato
dalla sezione "Chiedi".

Ottimizzazioni:
  - il file Excel viene letto UNA sola volta per versione: il risultato
    (JSON gzip per foglio + modello) e' salvato in WEB_CACHE_DIR con chiave
    percorso + data di modifica + dimensione; le aperture successive
    leggono solo la cache (millisecondi);
  - il server invia al browser i byte gia' compressi (nessuna
    ricompressione per richiesta);
  - la modifica del file Excel (es. al termine di un'opzione) viene
    rilevata e la conversione rifatta in background.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import config as cfg

log = logging.getLogger(__name__)

PROGRAM_DIR = Path(__file__).resolve().parent.parent
CACHE_VERSION = 6

SHEET_INDEX = getattr(cfg, "SHEET_INDEX_FUNZIONI", "Index Funzioni")
SHEET_FUNZ = getattr(cfg, "SHEET_FUNZIONI", "Funzioni")
SHEET_REQ = getattr(cfg, "SHEET_REQUISITI", "Requisiti")
SHEET_RNM = getattr(cfg, "SHEET_REQS_NOT_MATCHED", "Reqs not matched")
SHEETS = [SHEET_INDEX, SHEET_FUNZ, SHEET_REQ, SHEET_RNM]


# ---------------------------------------------------------------------------
# Percorsi
# ---------------------------------------------------------------------------

def excel_path() -> Optional[Path]:
    """EXCEL_PATH di config.py; in mancanza un file con lo stesso nome (o
    "DB Flotte*.xlsx") nella cartella del programma."""
    p = Path(cfg.EXCEL_PATH)
    if p.is_file():
        return p
    local = PROGRAM_DIR / p.name
    if local.is_file():
        return local
    found = sorted(PROGRAM_DIR.glob("DB Flotte*.xlsx"))
    return found[0] if found else None


def cache_dir() -> Path:
    d = getattr(cfg, "WEB_CACHE_DIR", None)
    d = Path(d) if d else Path(cfg.HISTORY_DIR) / "web_cache"
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        d = PROGRAM_DIR / ".web_cache"
        d.mkdir(parents=True, exist_ok=True)
        return d


# ---------------------------------------------------------------------------
# Conversione celle
# ---------------------------------------------------------------------------

def _rgb(color) -> str:
    """'#RRGGBB' da un colore openpyxl (solo colori RGB espliciti)."""
    try:
        if color is None or color.type != "rgb":
            return ""
        v = color.rgb
        if not isinstance(v, str) or len(v) < 6:
            return ""
        v = v[-6:].upper()
        return "" if v == "000000" else "#" + v
    except Exception:
        return ""


def _fill(cell) -> str:
    try:
        if cell.fill is None or cell.fill.fill_type != "solid":
            return ""
        v = _rgb(cell.fill.fgColor)
        return "" if v in ("#FFFFFF",) else v
    except Exception:
        return ""


def _text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:g}"
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M") if (v.hour or v.minute) else v.strftime("%d/%m/%Y")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return str(v)


def _is_formula(v: Any) -> bool:
    return (isinstance(v, str) and v.startswith("=")) or type(v).__name__ in (
        "ArrayFormula", "DataTableFormula")


def parse_page(value: str) -> int:
    """Come excel_scanner._parse_page: '32 utente - 34 dinamico' -> 34."""
    if not value:
        return 0
    m = re.search(r"(\d+)\s*dinamico", str(value), re.IGNORECASE)
    if m:
        return int(m.group(1))
    nums = re.findall(r"\d+", str(value))
    return int(nums[0]) if nums else 0


class _Styles:
    def __init__(self):
        self.items: list[dict] = []
        self._idx: dict[tuple, int] = {}

    def get(self, cell) -> int:
        f = cell.font
        key = (_rgb(f.color) if f is not None else "", _fill(cell),
               bool(f is not None and f.b), bool(f is not None and f.i),
               bool(f is not None and f.strike))
        if key == ("", "", False, False, False):
            return -1
        if key not in self._idx:
            d = {}
            if key[0]:
                d["c"] = key[0]
            if key[1]:
                d["bg"] = key[1]
            if key[2]:
                d["b"] = 1
            if key[3]:
                d["i"] = 1
            if key[4]:
                d["s"] = 1
            self._idx[key] = len(self.items)
            self.items.append(d)
        return self._idx[key]


def _col_width(ws, col: int) -> int:
    from openpyxl.utils import get_column_letter
    dim = ws.column_dimensions.get(get_column_letter(col))
    w = dim.width if dim is not None and dim.width else 12
    return int(max(60, min(560, w * 7.5)))


# ---------------------------------------------------------------------------
# Lettura di un foglio
# ---------------------------------------------------------------------------

def _last_row(ws, max_col: int) -> int:
    r = ws.max_row
    while r > 1 and all(ws.cell(r, c).value in (None, "") for c in range(1, max_col + 1)):
        r -= 1
    return r


def _last_col(ws) -> int:
    c = ws.max_column
    while c > 1 and ws.cell(1, c).value in (None, ""):
        c -= 1
    return c


def read_sheet(ws, ws_data, sd=None, configs_all: Optional[list[str]] = None) -> dict:
    """Foglio -> dict JSON: colonne, righe (valori, stili, commenti, link)."""
    name = ws.title
    ncol = _last_col(ws)
    nrow = _last_row(ws, ncol)
    styles = _Styles()
    headers = [_text(ws.cell(1, c).value).strip() for c in range(1, ncol + 1)]
    known = set(configs_all or [])
    cols = []
    for c in range(1, ncol + 1):
        h = headers[c - 1]
        cell = ws.cell(1, c)
        cols.append({"t": h or f"Col {c}", "w": _col_width(ws, c),
                     "cfg": h in known, "bg": _fill(cell) or "", "fc": _rgb(cell.font.color) if cell.font else ""})

    is_funz = name == SHEET_FUNZ
    rows = []
    cur_func, cur_doc, cur_cart = "", "", ""
    doc_row_idx = -1
    for r in range(2, nrow + 1):
        vals, st, cm, ln = [], {}, {}, {}
        for c in range(1, ncol + 1):
            cell = ws.cell(r, c)
            v = cell.value
            if _is_formula(v):
                dv = ws_data.cell(r, c).value if ws_data is not None else None
                v = dv if dv is not None else ""
            vals.append(_text(v))
            s = styles.get(cell)
            if s >= 0:
                st[c - 1] = s
            if cell.comment is not None and cell.comment.text:
                cm[c - 1] = cell.comment.text.strip()
            if cell.hyperlink is not None and cell.hyperlink.target:
                ln[c - 1] = {"url": cell.hyperlink.target}
        row: dict[str, Any] = {"v": vals}
        a = vals[0].strip() if vals else ""
        if is_funz:
            label = vals[4].strip() if ncol >= 5 else ""
            if a:
                cur_func, cur_doc = a, ""
                row["k"] = "func"
            elif label.lower() == "link":
                cur_doc, cur_cart = vals[3].strip(), vals[2].strip()
                row["k"] = "doc"
                doc_row_idx = len(rows)
                vals[4] = "Link"
                for c in range(5, ncol):
                    cfg_name = headers[c]
                    if cfg_name not in known:
                        continue
                    raw = ws.cell(r, c + 1).value
                    if raw in (None, "") and not ln.get(c):
                        continue
                    vals[c] = f"#Sharepoint//{cur_doc}"
                    ln[c] = {"doc": cur_doc, "cfg": cfg_name, "cart": cur_cart}
            else:
                row["k"] = "detail"
                if label.lower().startswith("rif. pagina") and 0 <= doc_row_idx == len(rows) - 1:
                    prev = rows[doc_row_idx]
                    for c, info in (prev.get("l") or {}).items():
                        info["page"] = parse_page(vals[int(c)])
                        info["rif"] = vals[int(c)].strip()
            row["g"] = cur_func
            if cur_doc and row["k"] != "func":
                row["d"] = cur_doc
        elif name == SHEET_INDEX:
            is_title = bool(a) and "_" not in vals[2] and _fill(ws.cell(r, 1)) != ""
            if is_title:
                cur_doc = a
                row["k"] = "doc"
            else:
                row["k"] = "func"
            row["g"] = cur_doc
        elif name == SHEET_REQ:
            if a:
                cur_func = a
                row["k"] = "func"
            else:
                row["k"] = "req"
            row["g"] = cur_func
        else:
            row["g"] = a
        if st:
            row["s"] = st
        if cm:
            row["n"] = cm
        if ln:
            row["l"] = ln
        rows.append(row)

    if sd is not None and is_funz:
        _resolve_links(rows, sd)

    freeze = ws.freeze_panes or ""
    fc = 0
    m = re.match(r"([A-Z]+)(\d+)", freeze or "")
    if m:
        from openpyxl.utils import column_index_from_string
        fc = column_index_from_string(m.group(1)) - 1
    # Colonne bloccate oltre la meta' dello schermo non sono utili sul web
    fc = min(fc, 4)
    carry = {SHEET_FUNZ: [0, 1], SHEET_REQ: [0, 1], SHEET_INDEX: []}.get(name, [])
    configs = [h for h in headers if h in known]
    note = ws.cell(1, 1).comment.text if ws.cell(1, 1).comment is not None else ""
    return {"name": name, "cols": cols, "rows": rows, "styles": styles.items,
            "freezeCols": fc, "carry": carry, "configs": configs,
            "hierarchical": name in (SHEET_FUNZ, SHEET_REQ, SHEET_INDEX),
            "note": note}


def _resolve_links(rows: list[dict], sd) -> None:
    """URL SharePoint (come la formula HYPERLINK del foglio)."""
    import url_builder
    for row in rows:
        for info in (row.get("l") or {}).values():
            if "doc" not in info:
                continue
            try:
                info["url"] = url_builder.build(sd, info["doc"], info["cfg"],
                                                int(info.get("page") or 0),
                                                info.get("cart", "")) or ""
            except Exception:
                info["url"] = ""


# ---------------------------------------------------------------------------
# Modello dati per la sezione "Chiedi"
# ---------------------------------------------------------------------------

def build_model(sheets: dict[str, dict], configs: list[str]) -> dict:
    """{functions: {FUNC_ID: {...}}, configs: [...]} dai fogli convertiti."""
    funcs: dict[str, dict] = {}

    def F(fid: str, desc: str = "") -> dict:
        f = funcs.setdefault(fid, {"id": fid, "desc": "", "docs": [], "reqs": [],
                                   "rnm": [], "index": [], "frs": []})
        if desc and not f["desc"]:
            f["desc"] = desc
        return f

    sh = sheets.get(SHEET_FUNZ)
    if sh:
        heads = [c["t"] for c in sh["cols"]]
        cur = None
        doc = None
        for row in sh["rows"]:
            v = row["v"]
            if row.get("k") == "func":
                cur = F(v[0].strip(), v[1].strip())
                doc = None
            elif row.get("k") == "doc" and cur is not None:
                doc = {"doc": v[3].strip(), "cart": v[2].strip(), "links": {}, "details": []}
                for c, info in (row.get("l") or {}).items():
                    if "cfg" in info:
                        rif = info.get("rif", "")
                        doc["links"][info["cfg"]] = {
                            "page": info.get("page", 0), "url": info.get("url", ""), "rif": rif,
                            # "X" = documento aggiornato nel foglio CONFIG, pagina da
                            # reinserire (OPZIONE 0 TOTAL): PDF non mostrato
                            "invalid": rif.upper() == str(getattr(cfg, "RIF_PAGINA_INVALID_TXT", "X")).upper()}
                cur["docs"].append(doc)
            elif row.get("k") == "detail" and doc is not None:
                label = v[4].strip()
                values = {heads[c]: v[c] for c in range(5, len(v))
                          if heads[c] in configs and v[c].strip()}
                colors = {heads[int(c)]: sh["styles"][s].get("c", "")
                          for c, s in (row.get("s") or {}).items()
                          if int(c) >= 5 and heads[int(c)] in configs}
                notes = {heads[int(c)]: t for c, t in (row.get("n") or {}).items()
                         if int(c) >= 5 and heads[int(c)] in configs}
                if label or values:
                    doc["details"].append({"label": label or "(senza etichetta)",
                                           "values": values, "colors": colors,
                                           "notes": notes})
    sh = sheets.get(SHEET_REQ)
    if sh:
        heads = [c["t"] for c in sh["cols"]]
        cfg_cols = [i for i, h in enumerate(heads) if h in configs]
        frs_i = next((i for i, h in enumerate(heads) if h.upper() == "FRS"), None)
        req_i = next((i for i, h in enumerate(heads) if h.upper().startswith("REQUISITO")), 2)
        app_i = next((i for i, h in enumerate(heads) if "APPARTENENZA" in h.upper()), None)
        cur = None
        for row in sh["rows"]:
            v = row["v"]
            if row.get("k") == "func":
                cur = F(v[0].strip(), v[1].strip())
            if cur is None or not v[req_i].strip():
                continue
            cells = {heads[i]: v[i] for i in cfg_cols if v[i].strip()}
            cur["reqs"].append({"id": v[req_i].strip(),
                                "frs": v[frs_i].strip() if frs_i is not None else "",
                                "app": v[app_i].strip() if app_i is not None else "",
                                "cells": cells})
    sh = sheets.get(SHEET_RNM)
    if sh:
        heads = [c["t"] for c in sh["cols"]]
        cfg_cols = [i for i, h in enumerate(heads) if h in configs]
        req_i = next((i for i, h in enumerate(heads) if h.upper().startswith("REQUISITO")), 2)
        d_i = next((i for i, h in enumerate(heads) if h.lower() == "descrizione"), None)
        n_i = next((i for i, h in enumerate(heads) if h.lower().startswith("note")), None)
        for row in sh["rows"]:
            v = row["v"]
            fid = v[0].strip()
            if not fid:
                continue
            F(fid, v[1].strip())["rnm"].append({
                "id": v[req_i].strip(),
                "present": [heads[i] for i in cfg_cols if v[i].strip()],
                "desc": v[d_i] if d_i is not None else "",
                "note": v[n_i] if n_i is not None else ""})
        compared = [heads[i] for i in cfg_cols]
    else:
        compared = []
    sh = sheets.get(SHEET_INDEX)
    if sh:
        heads = [c["t"] for c in sh["cols"]]
        cfg_cols = [i for i, h in enumerate(heads) if h in configs]
        doc = ""
        for row in sh["rows"]:
            v = row["v"]
            if row.get("k") == "doc":
                doc = v[0].strip()
                continue
            fid = v[2].strip() if len(v) > 2 else ""
            if not fid:
                continue
            F(fid, v[3].strip() if len(v) > 3 else "")["index"].append({
                "doc": doc, "par": v[1].strip(), "title": v[0].strip(),
                "status": {heads[i]: v[i] for i in cfg_cols if v[i].strip()},
                "notes": {heads[int(c)]: t for c, t in (row.get("n") or {}).items()
                          if int(c) < len(heads) and heads[int(c)] in configs}})
    return {"functions": funcs, "configs": configs, "rnm_configs": compared}


def read_fleets(wb_data, configs: list[str]) -> dict:
    """
    Foglio «Flotte»: per ogni configurazione il nome della flotta, la configurazione
    "nativa" e i numeri dei treni (veicoli) che la adottano.
    """
    name = getattr(cfg, "SHEET_FLOTTE", "Flotte")
    if name not in wb_data.sheetnames:
        return {}
    import difflib
    ws = wb_data[name]
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[1]:
            continue
        trains = [int(x) if isinstance(x, float) and x.is_integer() else x
                  for x in r[6:] if x not in (None, "") and not (isinstance(x, str) and x.startswith("="))]
        rows.append({"name": " ".join(_text(r[0]).split()), "id": _text(r[1]).strip(),
                     "native": _text(r[2]).strip(), "bl": " ".join(_text(r[3]).split()),
                     "trains": list(dict.fromkeys(str(t) for t in trains))})
    out: dict[str, dict] = {}
    free = list(rows)
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    for c in configs:
        hit = next((x for x in free if norm(x["id"]) == norm(c)), None)
        if hit:
            out[c] = hit
            free.remove(hit)
    for c in configs:
        if c in out or not free:
            continue
        m = difflib.get_close_matches(norm(c), [norm(x["id"]) for x in free], n=1, cutoff=0.6)
        if m:
            hit = next(x for x in free if norm(x["id"]) == m[0])
            out[c] = hit
            free.remove(hit)
    return out


# ---------------------------------------------------------------------------
# Conversione completa con cache
# ---------------------------------------------------------------------------

def _key(path: Path) -> str:
    st = path.stat()
    raw = f"{CACHE_VERSION}|{path.resolve()}|{st.st_mtime_ns}|{st.st_size}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name)


def convert(path: Path) -> dict:
    """Legge il file Excel (lento: ~2-5 s) e produce fogli + modello."""
    import openpyxl
    t0 = time.time()
    wb = openpyxl.load_workbook(path)
    wb_data = openpyxl.load_workbook(path, data_only=True)
    sd = None
    try:
        import support_loader
        sd = support_loader.load(wb_data)
    except Exception as exc:
        log.warning(f"Dati di supporto (link documenti) non letti: {exc}")
    configs: list[str] = []
    if SHEET_FUNZ in wb.sheetnames:
        ws = wb[SHEET_FUNZ]
        for c in range(6, ws.max_column + 1):
            h = _text(ws.cell(1, c).value).strip()
            if h:
                configs.append(h)
    for name in (SHEET_REQ, SHEET_INDEX):
        if name in wb.sheetnames:
            ws = wb[name]
            for c in range(1, ws.max_column + 1):
                h = _text(ws.cell(1, c).value).strip()
                if re.match(r"^VZ", h) and h not in configs:
                    configs.append(h)
    sheets = {}
    for name in SHEETS:
        if name in wb.sheetnames:
            sheets[name] = read_sheet(wb[name], wb_data[name], sd, configs)
    model = build_model(sheets, configs)
    model["sharepoint_base"] = getattr(sd, "base_url", "") if sd else ""
    model["config_map"] = getattr(sd, "config_map", {}) if sd else {}
    model["man_cpr_map"] = getattr(sd, "man_cpr_map", {}) if sd else {}
    model["fleets"] = read_fleets(wb_data, configs)
    model["confdocs"] = []
    try:
        import config_db
        if config_db.SHEET in wb_data.sheetnames:
            model["confdocs"] = config_db.read_sheet(wb_data[config_db.SHEET])["docs"]
    except Exception as exc:
        log.warning(f"Documenti del foglio CONFIG non letti: {exc}")
    try:
        import config_colors
        config_colors.register_configs(configs)
        colors = {c: "#" + config_colors.color_for(c)[-6:] for c in configs}
    except Exception:
        colors = {}
    meta = {"file": str(path), "name": path.name,
            "mtime": datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
            "sheets": [{"name": n, "rows": len(sheets[n]["rows"])} for n in SHEETS if n in sheets],
            "configs": configs, "colors": colors,
            "missing": [n for n in SHEETS if n not in sheets],
            "parse_seconds": round(time.time() - t0, 2)}
    log.info(f"Excel convertito in {meta['parse_seconds']} s")
    return {"meta": meta, "sheets": sheets, "model": model}


class Snapshot:
    def __init__(self, key: str, meta: dict, sheet_gz: dict[str, bytes], model: dict):
        self.key = key
        self.meta = meta
        self.sheet_gz = sheet_gz
        self.model = model


def _gz(obj: Any) -> bytes:
    return gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 6)


def load_snapshot(path: Path) -> Snapshot:
    key = _key(path)
    d = cache_dir() / f"wb_{key}"
    meta_f = d / "meta.json"
    if meta_f.is_file():
        try:
            meta = json.loads(meta_f.read_text(encoding="utf-8"))
            gz = {s["name"]: (d / f"{_safe(s['name'])}.json.gz").read_bytes() for s in meta["sheets"]}
            model = json.loads(gzip.decompress((d / "model.json.gz").read_bytes()))
            return Snapshot(key, meta, gz, model)
        except Exception as exc:
            log.warning(f"Cache web non leggibile, riconversione: {exc}")
    data = convert(path)
    gz = {n: _gz(s) for n, s in data["sheets"].items()}
    tmp = d.with_name(d.name + ".tmp")
    try:
        tmp.mkdir(parents=True, exist_ok=True)
        for n, b in gz.items():
            (tmp / f"{_safe(n)}.json.gz").write_bytes(b)
        (tmp / "model.json.gz").write_bytes(_gz(data["model"]))
        (tmp / "meta.json").write_text(json.dumps(data["meta"], ensure_ascii=False), encoding="utf-8")
        if d.exists():
            import shutil
            shutil.rmtree(d, ignore_errors=True)
        tmp.rename(d)
        _cleanup(keep=d)
    except OSError as exc:
        log.warning(f"Cache web non salvata: {exc}")
    return Snapshot(key, data["meta"], gz, data["model"])


def _cleanup(keep: Path, max_keep: int = 3) -> None:
    import shutil
    olds = sorted((p for p in cache_dir().glob("wb_*") if p != keep and p.is_dir()),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    for p in olds[max_keep - 1:]:
        shutil.rmtree(p, ignore_errors=True)


class WorkbookStore:
    """Snapshot corrente; rileva le modifiche al file e ricarica in background."""

    def __init__(self):
        self._snap: Optional[Snapshot] = None
        self._lock = threading.Lock()
        self._loading = threading.Event()
        self._ready = threading.Event()
        self._last_check = 0.0
        self.error = ""
        self.listeners: list = []

    def start(self) -> None:
        self._reload_async()

    def _reload_async(self) -> None:
        if self._loading.is_set():
            return
        self._loading.set()
        threading.Thread(target=self._reload, daemon=True).start()

    def _reload(self) -> None:
        try:
            p = excel_path()
            if p is None:
                self.error = (f"File Excel non trovato: {cfg.EXCEL_PATH}. Impostare "
                              "EXCEL_PATH nel terminale developer (voce CONFIG) o in config.py.")
                return
            snap = load_snapshot(p)
            with self._lock:
                self._snap = snap
            self.error = ""
            for fn in list(self.listeners):
                try:
                    fn(snap)
                except Exception:
                    pass
        except Exception as exc:
            log.exception("Conversione Excel fallita")
            self.error = f"Errore nella lettura del file Excel: {exc}"
        finally:
            self._loading.clear()
            self._ready.set()

    @property
    def loading(self) -> bool:
        return self._loading.is_set()

    def get(self, wait: float = 0) -> Optional[Snapshot]:
        if wait:
            self._ready.wait(wait)
        self.check()
        return self._snap

    def check(self, every: float = 2.0) -> None:
        """Ricarica se il file Excel e' cambiato (al massimo ogni `every` s)."""
        now = time.time()
        if now - self._last_check < every or self.loading:
            return
        self._last_check = now
        p = excel_path()
        try:
            if p is not None and (self._snap is None or _key(p) != self._snap.key):
                self._reload_async()
        except OSError:
            pass

    def force_reload(self) -> None:
        self._last_check = 0
        self._reload_async()
