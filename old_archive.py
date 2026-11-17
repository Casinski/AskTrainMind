"""
old_archive.py
--------------
Archivio delle versioni precedenti del file Excel (cartella "_OLD").

Ogni volta che un'opzione del menu sta per modificare il file Excel, PRIMA
del primo salvataggio il file viene copiato in

    <cartella del file Excel>/_OLD/<AAAA-MM-GG_hh-mm-ss>_Opzione_<N>/
        <nome file>.xlsx      versione del file su cui e' stata richiesta l'opzione
        RICHIESTA.txt         opzione richiesta, parametri scelti, ambito
                              dell'elaborazione, fogli e CELLE aggiornate,
                              eventuale file RESULTS, esito

Una sola copia per esecuzione: i salvataggi automatici successivi della
stessa opzione non creano altre cartelle. Se l'opzione non modifica il file
(nessun salvataggio) non viene archiviato nulla. RICHIESTA.txt viene
riscritto a fine esecuzione con l'elenco completo delle celle aggiornate.
In modalita' RESULTS (DB non aggiornato) si archivia comunque il file di
partenza e RICHIESTA.txt riporta il percorso del file RESULTS.

Configurazione (config.py): OLD_ARCHIVE_ENABLED, OLD_ARCHIVE_DIR.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import config as cfg

log = logging.getLogger(__name__)

TXT_NAME = "RICHIESTA.txt"

_session: dict | None = None


def enabled() -> bool:
    return bool(getattr(cfg, "OLD_ARCHIVE_ENABLED", True))


def archive_root(excel_path: Path | None = None) -> Path:
    root = getattr(cfg, "OLD_ARCHIVE_DIR", None)
    if root:
        return Path(root)
    return Path(excel_path or cfg.EXCEL_PATH).parent / "_OLD"


def begin(option: str, label: str, details: dict | None = None,
          sheets: list[str] | None = None) -> None:
    """Registra l'opzione richiesta dall'utente (da chiamare all'avvio)."""
    global _session
    _session = {
        "option": option,
        "label": label,
        "details": {},
        "sheets": list(sheets or []),
        "time": datetime.now(),
        "folder": None,
        "scope": [],
        "results": None,
        "update_db": True,
        "outcome": "",
    }
    set_details(details or {})


def set_details(details: dict) -> None:
    """Aggiunge/aggiorna i parametri della richiesta (vuoti ignorati)."""
    if _session is None:
        return
    for k, v in details.items():
        if v in ("", None, []):
            _session["details"].pop(k, None)
        else:
            _session["details"][k] = v


def details() -> dict:
    return dict((_session or {}).get("details", {}))


def session_time() -> datetime:
    return (_session or {}).get("time") or datetime.now()


def option() -> str:
    return (_session or {}).get("option", "")


def sheets() -> list[str]:
    return list((_session or {}).get("sheets", []))


def set_sheets(sheets: list[str]) -> None:
    if _session is not None:
        _session["sheets"] = list(sheets)


def add_scope(line: str) -> None:
    """Riga descrittiva su cosa viene elaborato (funzioni, FRS, ...)."""
    if _session is not None and line not in _session["scope"]:
        _session["scope"].append(line)


def set_update_db(value: bool) -> None:
    if _session is not None:
        _session["update_db"] = bool(value)


def set_results(path: Path | None) -> None:
    if _session is not None and path:
        _session["results"] = Path(path)


def archive_before_save(target: Path | None = None) -> Path | None:
    """
    Copia il file Excel nella cartella _OLD (solo la prima volta per
    esecuzione). Ritorna la cartella creata, None se non archiviato.
    """
    if not enabled() or _session is None or _session["folder"] is not None:
        return None
    src = Path(target or cfg.EXCEL_PATH)
    if not src.exists():
        return None
    stamp = _session["time"].strftime("%Y-%m-%d_%H-%M-%S")
    folder = archive_root(src) / f"{stamp}_Opzione_{_session['option']}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, folder / src.name)
        (folder / TXT_NAME).write_text(_describe(src), encoding="utf-8")
    except Exception as exc:
        log.warning(f"  [_OLD] Archiviazione non riuscita in {folder}: {exc}")
        _session["folder"] = False
        return None
    _session["folder"] = folder
    log.info(f"  [_OLD] Versione precedente del file archiviata in: {folder}")
    return folder


def finish(outcome: str) -> None:
    """Riscrive il file di testo dell'archivio con esito e celle aggiornate."""
    if not _session:
        return
    _session["outcome"] = f"{outcome} ({datetime.now():%d/%m/%Y %H:%M:%S})"
    if not _session.get("folder"):
        return
    try:
        src = Path(_session.get("src") or cfg.EXCEL_PATH)
        (_session["folder"] / TXT_NAME).write_text(_describe(src), encoding="utf-8")
    except Exception as exc:
        log.warning(f"  [_OLD] Esito non scritto: {exc}")


def _describe(src: Path) -> str:
    import run_options
    s = _session or {}
    s["src"] = src
    lines = [
        "AskTrainMind - archivio della versione precedente del file Excel",
        "=" * 64,
        f"Data richiesta    : {s['time']:%d/%m/%Y %H:%M:%S}",
        f"Opzione richiesta : {s['option']}) {s['label']}",
        f"File originale    : {src}",
        "",
        "PARAMETRI SCELTI DALL'UTENTE",
        "-" * 64,
    ]
    for k, v in s.get("details", {}).items():
        if isinstance(v, (list, tuple)):
            v = ", ".join(map(str, v))
        lines.append(f"  {k:<22}: {v}")
    if not s.get("details"):
        lines.append("  (nessun parametro: valori predefiniti)")
    lines += ["", "AMBITO DELL'ELABORAZIONE", "-" * 64]
    lines += [f"  {ln}" for ln in s.get("scope", [])] or ["  intero foglio/file"]
    if s.get("sheets"):
        lines.append(f"  Fogli ricreati/aggiornati: {', '.join(s['sheets'])}")
    lines += ["", "AGGIORNAMENTO DEL FILE", "-" * 64]
    if s.get("update_db", True):
        lines.append("  Il file DB Flotte e' stato aggiornato direttamente: i fogli")
        lines.append("  elencati sono stati rielaborati (nessun testo vecchio residuo).")
    else:
        lines.append("  L'utente ha chiesto di NON aggiornare il file DB Flotte.")
        lines.append(f"  Risultati scritti nel file RESULTS: {s.get('results') or '(non creato)'}")
        lines.append("  Le celle elencate sotto vanno copiate manualmente nel DB Flotte.")
    lines += ["", "CELLE AGGIORNATE", "-" * 64]
    cell_lines = run_options.tracker.lines(
        limit=getattr(cfg, "OLD_ARCHIVE_MAX_CELL_LINES", 400))
    lines += cell_lines or ["  nessuna cella modificata (finora)"]
    lines += [
        "",
        f"Il file '{src.name}' in questa cartella e' la versione del file Excel",
        "su cui l'utente ha richiesto l'opzione indicata, salvata PRIMA che",
        "l'opzione lo modificasse.",
    ]
    if s.get("outcome"):
        lines += ["", f"Esito: {s['outcome']}"]
    return "\n".join(lines) + "\n"
