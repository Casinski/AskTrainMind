"""
old_archive.py
--------------
Archivio delle versioni precedenti del file Excel (cartella "_OLD").

Ogni volta che un'opzione del menu sta per modificare il file Excel, PRIMA
del primo salvataggio il file viene copiato in

    <cartella del file Excel>/_OLD/<AAAA-MM-GG_hh-mm-ss>_Opzione_<N>/
        <nome file>.xlsx      versione del file su cui e' stata richiesta l'opzione
        RICHIESTA.txt         opzione richiesta, parametri, fogli coinvolti, esito

Una sola copia per esecuzione: i salvataggi automatici successivi della
stessa opzione non creano altre cartelle. Se l'opzione non modifica il file
(nessun salvataggio) non viene archiviato nulla.

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
        "details": {k: v for k, v in (details or {}).items() if v not in ("", None, [])},
        "sheets": list(sheets or []),
        "time": datetime.now(),
        "folder": None,
    }


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
    """Aggiunge l'esito dell'opzione al file di testo dell'archivio."""
    if not _session or not _session.get("folder"):
        return
    try:
        with open(_session["folder"] / TXT_NAME, "a", encoding="utf-8") as fh:
            fh.write(f"\nEsito ({datetime.now():%d/%m/%Y %H:%M:%S}): {outcome}\n")
    except Exception as exc:
        log.warning(f"  [_OLD] Esito non scritto: {exc}")


def _describe(src: Path) -> str:
    s = _session or {}
    lines = [
        "AskTrainMind - archivio della versione precedente del file Excel",
        "=" * 64,
        f"Data richiesta    : {s['time']:%d/%m/%Y %H:%M:%S}",
        f"Opzione richiesta : {s['option']}) {s['label']}",
    ]
    for k, v in s.get("details", {}).items():
        if isinstance(v, (list, tuple)):
            v = ", ".join(map(str, v))
        lines.append(f"{k:<18}: {v}")
    if s.get("sheets"):
        lines.append(f"Fogli modificati  : {', '.join(s['sheets'])}")
    lines += [
        f"File originale    : {src}",
        "",
        f"Il file '{src.name}' in questa cartella e' la versione del file Excel",
        "su cui l'utente ha richiesto l'opzione indicata, salvata PRIMA che",
        "l'opzione lo modificasse. La versione aggiornata dall'opzione e' il",
        "file originale indicato sopra.",
    ]
    return "\n".join(lines) + "\n"
