"""
config_db.py
------------
OPZIONE 0 CREA DB CONFIG — memoria "FOGLIO CONFIG CODICE-REV FRS PER
CONFIGURAZIONE".

Legge il foglio CONFIG del DB Flotte e registra, per ogni DOC ID (colonna B)
e per ogni configurazione (riga 1: VZI_Base, VZI_New14, ...), il "File/Codice"
(o "Codice") e la "Rev" indicati in riga 3. Ogni documento porta anche il tipo
ricavato dalla sezione del foglio (FRS, FPD, FS, WT, EPL, ICD, GEN, SW).

La memoria e' salvata in config.CONFIG_DB_FILE (JSON + copia .csv leggibile);
la versione sostituita resta in config.CONFIG_DB_PREV_FILE.
OPZIONE 0 TOTAL (opzione0.py) usa diff() per sapere quali documenti sono
cambiati (Codice o Rev diversi) rispetto alla memoria precedente.

Uso diretto:
    python config_db.py            # crea / aggiorna la memoria
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import config as cfg

log = logging.getLogger(__name__)

SHEET = getattr(cfg, "SHEET_CONFIG", "CONFIG")
INVALID_CODES = {"", "\\", "/", "_", "-", "–", "tbd", "manca", "#n/a", "n/a", "na", "ref", "rev"}

# Titolo di sezione (colonna A) -> tipo di documento
_SECTIONS = [
    (r"sw\s*config", "SW"),
    (r"functional\s+principle", "FPD"),
    (r"requirement\s+spec|\(frs\)", "FRS"),
    (r"functional\s+schem", "FS"),
    (r"wiring", "WT"),
    (r"part\s+list", "EPL"),
    (r"interface\s+control", "ICD"),
    (r"general\s+vehicle", "GEN"),
]
# Prefisso del DOC ID -> tipo (quando la riga precede ogni titolo di sezione)
_PREFIX = {"FRS": "FRS", "FPD": "FPD", "FS": "FS", "WT": "WT", "EPL": "EPL",
           "ICD": "ICD", "GVN": "GEN", "GEN": "GEN", "SW": "SW"}


_ID_PREFIX = {"GEN": "GVN"}


def norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(text or "").strip().lower())


def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def code_is_valid(code: str) -> bool:
    c = (code or "").strip()
    return bool(c) and c.lower() not in INVALID_CODES and len(c) > 2


def code_variants(code: str) -> list[str]:
    """Nomi file possibili per un Codice (la cella puo' contenere piu' righe)."""
    c = (code or "").strip()
    out = [c] if c else []
    for line in c.splitlines():
        line = line.strip()
        if line and line not in out:
            out.append(line)
    return [x for x in out if code_is_valid(x) and "\n" not in x]


def category_of(doc_id: str, section_cat: str = "") -> str:
    p = (doc_id or "").split("_", 1)[0].upper()
    return _PREFIX.get(p) or section_cat or p


def folder_of(category: str) -> str:
    return (getattr(cfg, "CONFIG_DOC_FOLDERS", {}).get(category) or (category, ""))[0]


def label_of(category: str) -> str:
    return (getattr(cfg, "CONFIG_DOC_FOLDERS", {}).get(category) or ("", category))[1] or category


# ---------------------------------------------------------------------------
# Lettura del foglio CONFIG
# ---------------------------------------------------------------------------

def read_sheet(ws) -> dict:
    """
    Tabella del foglio CONFIG (workbook aperto con data_only=True):
        {"configs": [...], "docs": [{doc_id, category, section, description,
         ext, row, codes: {config: {"code", "rev"}}}]}
    """
    max_col = ws.max_column
    starts: list[tuple[int, str]] = []
    for col in range(4, max_col + 1):
        name = _s(ws.cell(1, col).value)
        if name and name.lower() not in ("doc description", "doc id", "doc ext"):
            starts.append((col, name))
    groups: list[tuple[str, int, int]] = []        # (config, col codice, col rev)
    for i, (col, name) in enumerate(starts):
        end = starts[i + 1][0] - 1 if i + 1 < len(starts) else max_col
        code_col = rev_col = 0
        for c in range(col, end + 1):
            h = _s(ws.cell(3, c).value).lower().replace("\n", " ")
            if not code_col and ("codice" in h and "config" not in h):
                code_col = c
            elif not rev_col and h.startswith("rev"):
                rev_col = c
        groups.append((name, code_col or col, rev_col))

    docs: list[dict] = []
    section, section_cat = "", ""
    for row in range(4, ws.max_row + 1):
        a = _s(ws.cell(row, 1).value)
        doc_id = _s(ws.cell(row, 2).value)
        ext = _s(ws.cell(row, 3).value)
        if a and not ext and (not doc_id or doc_id.upper() == "NOTA"):
            section = " ".join(a.split())
            section_cat = next((k for rx, k in _SECTIONS if re.search(rx, section, re.I)), "")
            continue
        has_codes = any(_s(ws.cell(row, c).value) for _, c, _ in groups)
        synthetic = False
        if (not doc_id or doc_id.startswith("=")) and a and has_codes and section_cat == "GEN":
            # DOC ID formula senza valore in cache (es. =CONCATENATE("GVN_",A))
            # o cella vuota: stesso nome che produrrebbe la formula
            doc_id, synthetic = f"{_ID_PREFIX.get(section_cat, section_cat)}_{' '.join(a.split())}", True
        if not doc_id or doc_id.startswith("="):
            continue
        codes = {}
        for name, c_code, c_rev in groups:
            code = _s(ws.cell(row, c_code).value)
            rev = _s(ws.cell(row, c_rev).value) if c_rev else ""
            if code or rev:
                codes[name] = {"code": code, "rev": rev}
        docs.append({"doc_id": doc_id, "category": category_of(doc_id, section_cat),
                     "section": section, "description": " ".join(a.split()),
                     "ext": (ext if ext.isalpha() and len(ext) <= 4 and ext.upper() != "TBD" else "pdf").lstrip(".").lower(),
                     "row": row, "codes": codes, **({"synthetic": True} if synthetic else {})})
    return {"configs": [g[0] for g in groups], "docs": docs}


def build(excel_path: Path | None = None) -> dict:
    from openpyxl import load_workbook
    path = Path(excel_path or cfg.EXCEL_PATH)
    wb = load_workbook(str(path), data_only=True)
    try:
        if SHEET not in wb.sheetnames:
            raise KeyError(f"Foglio '{SHEET}' non trovato in {path.name}")
        table = read_sheet(wb[SHEET])
    finally:
        wb.close()
    table.update({"title": cfg.CONFIG_DB_TITLE, "excel": path.name,
                  "created": datetime.now().isoformat(timespec="seconds")})
    return table


# ---------------------------------------------------------------------------
# Memoria su disco
# ---------------------------------------------------------------------------

def load(path: Path | None = None) -> dict | None:
    p = Path(path or cfg.CONFIG_DB_FILE)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(table: dict, path: Path | None = None) -> Path:
    """Salva la memoria; quella sostituita diventa CONFIG_DB_PREV_FILE."""
    p = Path(path or cfg.CONFIG_DB_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.is_file() and path is None:
        shutil.copy2(p, cfg.CONFIG_DB_PREV_FILE)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    try:
        with open(p.with_suffix(".csv"), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow([table.get("title", ""), table.get("excel", ""), table.get("created", "")])
            w.writerow(["DOC ID", "TIPO", "CONFIGURAZIONE", "CODICE", "REV", "DESCRIZIONE"])
            for d in table["docs"]:
                for c, v in d["codes"].items():
                    w.writerow([d["doc_id"], d["category"], c, v["code"].replace("\n", " | "),
                                v["rev"], d["description"]])
    except OSError as exc:
        log.warning(f"Copia CSV della memoria non scritta: {exc}")
    return p


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

@dataclass
class Change:
    doc_id: str
    config: str
    category: str
    old_code: str
    old_rev: str
    new_code: str
    new_rev: str
    ext: str = "pdf"

    @property
    def kind(self) -> str:
        if not self.old_code and not self.old_rev:
            return "nuovo"
        if not self.new_code and not self.new_rev:
            return "rimosso"
        return "codice" if norm(self.old_code) != norm(self.new_code) else "rev"

    @property
    def is_frs(self) -> bool:
        return self.category == "FRS"

    def describe(self) -> str:
        old = f"{self.old_code or '-'} rev {self.old_rev or '-'}".replace("\n", " | ")
        new = f"{self.new_code or '-'} rev {self.new_rev or '-'}".replace("\n", " | ")
        return f"{self.doc_id} [{self.config}]: {old} → {new}"


def _index(table: dict) -> dict[tuple[str, str], tuple[dict, dict]]:
    out = {}
    for d in table.get("docs", []):
        for c, v in d.get("codes", {}).items():
            out[(norm(d["doc_id"]), norm(c))] = (d, {"config": c, **v})
    return out


def diff(old: dict, new: dict) -> list[Change]:
    """Documenti cambiati: Codice o Rev diversi (anche nuovi o rimossi)."""
    a, b = _index(old or {}), _index(new or {})
    out = []
    for key in list(b) + [k for k in a if k not in b]:
        da, va = a.get(key, (None, {}))
        db, vb = b.get(key, (None, {}))
        oc, orv = va.get("code", ""), va.get("rev", "")
        nc, nrv = vb.get("code", ""), vb.get("rev", "")
        if norm(oc) == norm(nc) and norm(orv) == norm(nrv):
            continue
        d = db or da
        out.append(Change(d["doc_id"], vb.get("config") or va.get("config"), d["category"],
                          oc, orv, nc, nrv, d.get("ext", "pdf")))
    return out


# ---------------------------------------------------------------------------
# File dei documenti
# ---------------------------------------------------------------------------

def relative_path(config_name: str, category: str, code: str, ext: str = "pdf") -> str:
    return f"{config_name}/CONFIG/{folder_of(category)}/{code}.{ext or 'pdf'}"


def find_file(config_name: str, category: str, code: str, ext: str = "pdf",
              roots: list[Path] | None = None) -> Path | None:
    """
    Documento nella cartella <root>/<configurazione>/CONFIG/<tipo>/ (OneDrive
    DOC_FLOTTE e cartella docs/ del progetto). Nessuna ricerca in altre
    cartelle: un file con lo stesso nome in un'altra configurazione non vale.
    """
    if roots is None:
        roots = [Path(cfg.ONEDRIVE_DOCS_ROOT), Path(__file__).with_name("docs")]
    for variant in code_variants(code):
        names = {f"{variant}.{ext or 'pdf'}".lower(), f"{variant}.pdf".lower()}
        for root in roots:
            folder = Path(root) / config_name / "CONFIG" / folder_of(category)
            try:
                if not folder.is_dir():
                    continue
                for p in folder.iterdir():
                    if p.is_file() and p.name.lower() in names:
                        return p
            except OSError:
                continue
    return None


def sharepoint_url(base_url: str, config_name: str, category: str, code: str,
                   ext: str = "pdf", page: int = 0) -> str:
    if not base_url or not code_variants(code):
        return ""
    # come url_builder: percorso accodato alla base SharePoint senza codifica
    url = base_url + relative_path(config_name, category, code_variants(code)[0], ext)
    return url + (f"#page={page}" if page > 0 else "")


# ---------------------------------------------------------------------------

def create(progress=print) -> dict:
    """OPZIONE 0 CREA DB CONFIG: legge il foglio CONFIG e salva la memoria."""
    table = build()
    p = save(table)
    n = sum(len(d["codes"]) for d in table["docs"])
    by_cat: dict[str, int] = {}
    for d in table["docs"]:
        by_cat[d["category"]] = by_cat.get(d["category"], 0) + 1
    progress(f"  ✔ {cfg.CONFIG_DB_TITLE}: {len(table['docs'])} DOC ID, {n} coppie "
             f"Codice/Rev su {len(table['configs'])} configurazioni")
    progress("    " + ", ".join(f"{k} {v}" for k, v in sorted(by_cat.items())))
    progress(f"    Memoria salvata in {p} (copia leggibile: {p.with_suffix('.csv').name})")
    return table


if __name__ == "__main__":
    import sys
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    create()
