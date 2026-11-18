"""
webapp/tools.py
---------------
Servizi del menu developer (asktrainmind_dev.py): verifica dei
prerequisiti, parametri CONFIG (variabili di config.py con descrizione e
valori forzati in config_overrides.json) e descrizione delle opzioni 1-5
di funzioni_ai_filter.py.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import config as cfg

from .workbook import PROGRAM_DIR

log = logging.getLogger(__name__)

CONFIG_FILE = PROGRAM_DIR / "config.py"
OVERRIDES_FILE = Path(getattr(cfg, "CONFIG_OVERRIDES_FILE", PROGRAM_DIR / "config_overrides.json"))

# Pacchetti Python usati dal programma: (modulo, pacchetto pip, obbligatorio)
PACKAGES = [
    ("openpyxl", "openpyxl", True),
    ("fitz", "pymupdf", True),
    ("ollama", "ollama", True),
    ("requests", "requests", True),
    ("docx", "python-docx", False),
    ("flask", "flask", True),
]


# ---------------------------------------------------------------------------
# Prerequisiti
# ---------------------------------------------------------------------------

def _pkg_ok(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


# Variabili essenziali per la prima configurazione
SETUP_VARS = ("EXCEL_PATH", "ONEDRIVE_DOCS_ROOT", "OLLAMA_MODEL", "WEB_EXTRA_DOC_DIRS")


def prerequisites() -> dict:
    from . import qa
    checks = []
    py_ok = sys.version_info >= (3, 10)
    checks.append({"id": "python", "label": "Python 3.10 o successivo", "ok": py_ok,
                   "detail": sys.version.split()[0],
                   "fix": "Installare Python 3.10+ da https://www.python.org/downloads/ "
                          "(spuntare «Add python.exe to PATH»)."})
    missing = [pip for mod, pip, req in PACKAGES if req and not _pkg_ok(mod)]
    checks.append({"id": "packages", "label": "Pacchetti Python del programma",
                   "ok": not missing,
                   "detail": "tutti installati" if not missing else "mancano: " + ", ".join(missing),
                   "fix": f'"{sys.executable}" -m pip install -r requirements.txt'})
    st = qa.ollama_probe()
    qa.ai_status(force=True)
    reach = st["reachable"]
    checks.append({"id": "ollama", "label": "Ollama installato e in esecuzione", "ok": reach,
                   "detail": qa.ollama_host() if reach else "non raggiungibile su " + qa.ollama_host(),
                   "fix": "Scaricare Ollama da https://ollama.com/download, installarlo e avviarlo "
                          "(icona nella barra di sistema, oppure comando «ollama serve»)."})
    checks.append({"id": "model", "label": f"Modello AI «{cfg.OLLAMA_MODEL}»", "ok": st["ok"] or False,
                   "detail": st["msg"],
                   "fix": f"ollama pull {cfg.OLLAMA_MODEL}"})
    xp = Path(cfg.EXCEL_PATH)
    checks.append({"id": "excel", "label": "File Excel (EXCEL_PATH)", "ok": xp.is_file(),
                   "detail": str(xp),
                   "fix": "Impostare EXCEL_PATH (terminale developer → CONFIG, o config.py) sul percorso del file DB Flotte."})
    dr = Path(cfg.ONEDRIVE_DOCS_ROOT)
    checks.append({"id": "docs", "label": "Cartella documenti (ONEDRIVE_DOCS_ROOT)", "ok": dr.is_dir(),
                   "detail": str(dr),
                   "fix": "Sincronizzare la libreria SharePoint DOC_FLOTTE con OneDrive e impostare "
                          "ONEDRIVE_DOCS_ROOT sulla cartella locale."})
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "python": sys.executable, "program_dir": str(PROGRAM_DIR)}


# ---------------------------------------------------------------------------
# CONFIG: variabili di config.py con descrizione
# ---------------------------------------------------------------------------

_SECTION_BAR = re.compile(r"^#\s*[═=]{5,}")
_SECTION_DASH = re.compile(r"^#\s*──\s*(.+?)\s*─*\s*$")


def _comment_block(lines: list[str], lineno: int) -> str:
    """Commenti immediatamente sopra la riga (1-based) di assegnazione; se
    la variabile fa parte di un gruppo di assegnazioni consecutive, il
    commento sopra il gruppo."""
    out = []
    i = lineno - 2
    while i >= 0 and lines[i].strip() and not lines[i].strip().startswith("#") \
            and re.match(r"^[A-Z_]+\s*(:.*)?=|^\s+|^\)", lines[i]):
        i -= 1
    while i >= 0:
        s = lines[i].strip()
        if not s.startswith("#") or _SECTION_BAR.match(s) or _SECTION_DASH.match(s):
            break
        out.append(re.sub(r"^#\s?", "", s))
        i -= 1
    return "\n".join(reversed(out)).strip()


EXTRA_DESCRIPTIONS = {
    "EXCEL_PATH": "Percorso completo del file Excel DB Flotte letto e aggiornato dal programma "
                  "e mostrato nella pagina web.",
    "ONEDRIVE_DOCS_ROOT": "Cartella locale (sincronizzata con OneDrive/SharePoint) che contiene i documenti "
                          "DOC_FLOTTE: <configurazione>/CONFIG/<FRS|FS|...>/<codice>.pdf.",
    "MAX_CELLS_PER_RUN": "Opzione 1: numero massimo di celle «Funzioni AI» elaborate in una esecuzione.",
    "AI_CALL_DELAY_SECONDS": "Pausa (secondi) fra una chiamata AI e la successiva.",
    "START_FROM_FUNC_ID": "FUNC ID da cui iniziare l'elaborazione (vuoto = dall'inizio del foglio).",
    "CACHE_DIR": "Cartella della cache dei documenti scaricati/estratti.",
    "SHEET_FUNZIONI": "Nome del foglio Funzioni.",
    "SHEET_CARTELLE": "Nome del foglio Cartelle (contiene l'URL base SharePoint).",
    "SHEET_CONFIG": "Nome del foglio CONFIG (codici documento per configurazione).",
    "SHEET_MAN_CPR": "Nome del foglio MAN_CPR.",
}


def _inline_comment(line: str) -> str:
    m = re.search(r"#\s*(.+)$", line)
    if not m:
        return ""
    before = line[:m.start()]
    if before.count('"') % 2 or before.count("'") % 2:
        return ""
    return m.group(1).strip()


def _kind(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, Path):
        return "path"
    if isinstance(v, str):
        return "str"
    if v is None:
        return "none"
    if isinstance(v, (list, tuple, dict, set)):
        return "json"
    return "other"


def _jsonable(v: Any) -> Any:
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, (set, frozenset, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return repr(v)


def read_overrides() -> dict:
    try:
        return json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def _file_values() -> dict:
    """Valori del file config.py (senza override), eseguendolo isolato."""
    src = CONFIG_FILE.read_text(encoding="utf-8")
    src = src.replace("\n_apply_overrides()", "\n# _apply_overrides()")
    g: dict = {"__file__": str(CONFIG_FILE), "__name__": "config_file_values"}
    exec(compile(src, str(CONFIG_FILE), "exec"), g)
    return {k: v for k, v in g.items() if k.isupper()}


def _is_literal(node) -> bool:
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Path":
        return all(_is_literal(a) for a in node.args)
    try:
        ast.literal_eval(node)
        return True
    except (ValueError, TypeError, SyntaxError):
        return False


def config_items() -> list[dict]:
    src = CONFIG_FILE.read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src)
    defaults = _file_values()
    ov = read_overrides()
    section, subsection = "Generale", ""
    sec_at: dict[int, tuple[str, str]] = {}
    for i, l in enumerate(lines):
        s = l.strip()
        if _SECTION_BAR.match(s) and i + 2 < len(lines) and _SECTION_BAR.match(lines[i + 2].strip()):
            t = lines[i + 1].strip()
            if t.startswith("#") and not _SECTION_BAR.match(t):
                section, subsection = re.sub(r"^#\s*", "", t).strip(), ""
        m = _SECTION_DASH.match(s)
        if m:
            subsection = m.group(1)
        sec_at[i + 1] = (section, subsection)
    items, seen = [], set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        for name in names:
            if not name.isupper() or name in seen or name == "CONFIG_OVERRIDES_FILE":
                continue
            seen.add(name)
            default = defaults.get(name)
            kind = _kind(default)
            if kind == "other":
                continue
            desc = _comment_block(lines, node.lineno)
            inline = _inline_comment(lines[node.lineno - 1])
            if inline:
                desc = (desc + "\n" + inline).strip()
            if not desc:
                desc = EXTRA_DESCRIPTIONS.get(name, "")
            sec, sub = sec_at.get(node.lineno, ("Generale", ""))
            if not desc and sub:
                desc = sub
            seg = ast.get_source_segment(src, node.value) or ""
            items.append({"name": name, "section": sec, "subsection": sub, "line": node.lineno,
                          "kind": kind, "default": _jsonable(default),
                          "source": seg if len(seg) < 400 else seg[:400] + " …",
                          "computed": not _is_literal(node.value),
                          "overridden": name in ov, "value": _jsonable(ov[name]) if name in ov else _jsonable(default),
                          "description": desc or "(nessuna descrizione in config.py)"})
    return items


def _coerce(kind: str, raw: Any) -> Any:
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        s = str(raw).strip().lower()
        if s in ("true", "1", "si", "sì", "yes", "vero"):
            return True
        if s in ("false", "0", "no", "falso"):
            return False
        raise ValueError("valore booleano atteso (true/false)")
    if kind == "int":
        return int(str(raw).strip())
    if kind == "float":
        return float(str(raw).strip().replace(",", "."))
    if kind in ("str", "path"):
        return str(raw)
    if kind in ("json", "none"):
        if isinstance(raw, str):
            s = raw.strip()
            if kind == "none" and s.lower() in ("", "none", "null"):
                return None
            try:
                return json.loads(s)
            except ValueError:
                if kind == "none":
                    return s
                raise ValueError("JSON non valido (es. [\"VZI_Base\", \"VZ_FR\"])")
        return raw
    raise ValueError("tipo non modificabile")


def set_override(name: str, raw: Any) -> dict:
    items = {i["name"]: i for i in config_items()}
    if name not in items:
        raise KeyError(f"Variabile sconosciuta: {name}")
    kind = items[name]["kind"]
    try:
        value = _coerce(kind, raw)
    except (ValueError, TypeError, SyntaxError) as exc:
        hint = {"int": "un numero intero", "float": "un numero", "bool": "vero/falso",
                "list": "una lista Python, es. [\"a\", \"b\"]", "dict": "un dizionario Python, es. {\"k\": 1}",
                "tuple": "una tupla Python, es. (1, 2)"}.get(kind, "un valore valido")
        raise ValueError(f"Valore non valido per {name}: serve {hint} ({exc}).") from exc
    ov = read_overrides()
    ov[name] = value
    _write_overrides(ov)
    _apply_live(name, value, items[name]["kind"])
    return {"name": name, "value": _jsonable(value)}


def reset_override(name: Optional[str] = None) -> None:
    ov = read_overrides()
    defaults = _file_values()
    names = [name] if name else list(ov)
    for n in names:
        ov.pop(n, None)
        if n in defaults:
            setattr(cfg, n, defaults[n])
    _write_overrides(ov)


def _write_overrides(ov: dict) -> None:
    if not ov:
        try:
            OVERRIDES_FILE.unlink()
        except OSError:
            pass
        return
    tmp = OVERRIDES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(ov, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, OVERRIDES_FILE)


def _apply_live(name: str, value: Any, kind: str) -> None:
    """Applica il valore anche al server web in esecuzione."""
    if kind == "path" and isinstance(value, str):
        value = Path(value)
    setattr(cfg, name, value)


# ---------------------------------------------------------------------------
# Lancio delle opzioni
# ---------------------------------------------------------------------------

OPTIONS = [
    {"mode": "1",
     "title": "Analisi completa FRS: sintesi AI delle funzioni + estrazione e confronto requisiti",
     "sheets": "Funzioni, Requisiti, Reqs not matched",
     "desc": "Legge i PDF FRS di ogni configurazione, scrive la sintesi AI di ogni funzione e confronta i "
             "requisiti fra configurazioni. È l'opzione più lunga: per esecuzioni parziali indicare FRS, "
             "funzioni, configurazioni, FUNC ID di partenza o numero massimo di celle.",
     "params": ["frs", "funcs", "configs", "start", "max_cells", "overwrite", "no_rnm", "results_only"]},
    {"mode": "2",
     "title": "Ricostruisci l'indice delle funzioni dai PDF FRS",
     "sheets": "Index Funzioni",
     "desc": "Legge l'indice (sommario) dei PDF FRS delle configurazioni scelte e ricrea l'elenco "
             "delle funzioni (solo FRS/funzioni/configurazioni scelti, se indicati).",
     "params": ["frs", "funcs", "configs", "results_only"]},
    {"mode": "3",
     "title": "Ricalcola il riferimento di pagina di ogni funzione nei PDF",
     "sheets": "Funzioni (colonna Rif. Pagina)",
     "desc": "Aggiorna la pagina del PDF in cui inizia ogni funzione (usata dai link e dai PDF affiancati), "
             "per gli FRS, le funzioni e le configurazioni scelti.",
     "params": ["frs", "funcs", "configs", "start", "results_only"]},
    {"mode": "4",
     "title": "Confronto mirato dei requisiti per uno o più DOC ID",
     "sheets": "Confronto Reqs",
     "desc": "Confronta requisito per requisito i documenti degli FRS scelti fra le configurazioni "
             "scelte, eventualmente solo per i requisiti delle funzioni scelte.",
     "params": ["frs", "funcs", "configs", "results_only"]},
    {"mode": "5",
     "title": "Elenca i requisiti diversi fra configurazioni, con note AI",
     "sheets": "Reqs not matched",
     "desc": "Ricrea l'elenco dei requisiti non uguali fra le configurazioni scelte, con le Note AI "
             "(solo FRS e funzioni scelti, se indicati).",
     "params": ["frs", "funcs", "configs", "results_only"]},
]


def build_args(p: dict) -> list[str]:
    """Argomenti di riga di comando di funzioni_ai_filter.py per i parametri scelti."""
    mode = str(p.get("mode", ""))
    if mode not in {o["mode"] for o in OPTIONS}:
        raise ValueError("Opzione non valida")
    args = ["--mode", mode]
    if p.get("start"):
        args += ["--start", str(p["start"]).strip()]
    if p.get("doc"):
        args += ["--doc", str(p["doc"]).strip()]
    if p.get("configs"):
        args += ["--configs", ", ".join(p["configs"]) if isinstance(p["configs"], list) else str(p["configs"])]
    if p.get("max_cells") not in (None, "", 0, "0"):
        args += ["--max-cells", str(int(p["max_cells"]))]
    if p.get("overwrite") in ("A", "S", "N"):
        args += ["--overwrite", p["overwrite"]]
    if p.get("frs"):
        args += ["--frs", ", ".join(p["frs"]) if isinstance(p["frs"], list) else str(p["frs"])]
    if p.get("funcs"):
        args += ["--funcs", ", ".join(p["funcs"]) if isinstance(p["funcs"], list) else str(p["funcs"])]
    if p.get("no_rnm"):
        args.append("--no-reqs-not-matched")
    if p.get("results_only"):
        args.append("--results-only")
    return args


def frs_choices() -> list[str]:
    try:
        import run_options
        return run_options.frs_choices()
    except Exception:
        return []
