"""
interrupt_guard.py — salvataggio dei progressi e ripresa dopo un'interruzione.

Se SAVE_PROGRESS = True (config.py):

  - Ctrl+C, Ctrl+Break e la richiesta di chiusura (SIGTERM) non buttano via
    il lavoro: l'opzione in corso smette di analizzare, scrive nel file Excel
    cio' che ha gia' trovato (fogli "Funzioni", "Requisiti", "Index Funzioni",
    senza colonne aggiuntive), salva cache e storico e termina;
  - durante la scrittura del file Excel un secondo Ctrl+C viene rimandato a
    salvataggio concluso, cosi' il file non resta mai scritto a meta';
  - l'opzione 1 salva il file ogni AUTOSAVE_EVERY_N_GROUPS gruppi, utile se
    il processo viene chiuso in modo brusco (finestra chiusa, PC spento);
  - la funzione in lavorazione al momento dell'interruzione viene annotata in
    PROGRESS_STATE_FILE: alla ripartenza l'opzione riprende da li'
    (RESUME_FROM_CHECKPOINT).

Con SAVE_PROGRESS = False il comportamento e' quello originale: Ctrl+C
termina subito e cio' che non e' stato salvato va perso.
"""

from __future__ import annotations

import contextlib
import json
import logging
import signal
import threading
from datetime import datetime
from pathlib import Path

import config as cfg

log = logging.getLogger(__name__)

ENABLED: bool = bool(getattr(cfg, "SAVE_PROGRESS", True))
AUTOSAVE_EVERY: int = int(getattr(cfg, "AUTOSAVE_EVERY_N_GROUPS", 5) or 0)
RESUME: bool = bool(getattr(cfg, "RESUME_FROM_CHECKPOINT", True))
STATE_FILE: Path | None = getattr(
    cfg, "PROGRESS_STATE_FILE",
    Path.home() / "AppData" / "Local" / "FunzioniAI" / "progress_state.json",
)

# True dopo che un'opzione si e' fermata per interruzione (dati salvati)
interrupted: bool = False


def _raise_interrupt(signum, _frame):
    raise KeyboardInterrupt(f"segnale {signum}")


def install_handlers() -> None:
    """Tratta SIGTERM e Ctrl+Break (Windows) come Ctrl+C."""
    if not ENABLED or threading.current_thread() is not threading.main_thread():
        return
    for name in ("SIGTERM", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, _raise_interrupt)
            except (ValueError, OSError):
                pass


@contextlib.contextmanager
def protected():
    """
    Esegue il blocco rimandando Ctrl+C alla sua conclusione: serve per la
    scrittura del file Excel e per le modifiche strutturali dei fogli.
    """
    if not ENABLED or threading.current_thread() is not threading.main_thread():
        yield
        return
    pending: list = []

    def _defer(signum, _frame):
        pending.append(signum)
        log.warning("  ⏸ Interruzione ricevuta: attendo la fine del salvataggio...")

    previous = signal.signal(signal.SIGINT, _defer)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
    if pending:
        raise KeyboardInterrupt()


def handle(exc: BaseException, where: str) -> None:
    """
    Da chiamare in un 'except KeyboardInterrupt': se il salvataggio dei
    progressi e' disattivato rilancia l'eccezione, altrimenti la registra.
    """
    global interrupted
    if not ENABLED:
        raise exc
    interrupted = True
    log.warning(
        f"\n{'!' * 60}\n"
        f"  ⏹ Esecuzione interrotta ({where}).\n"
        f"  Salvo i dati elaborati finora...\n"
        f"{'!' * 60}"
    )


class Autosaver:
    """Chiama 'save' ogni AUTOSAVE_EVERY unita' completate."""

    def __init__(self, save, every: int | None = None):
        self.save = save
        self.every = AUTOSAVE_EVERY if every is None else every
        self.count = 0

    def tick(self, dirty: bool = True) -> None:
        if not ENABLED or self.every <= 0:
            return
        self.count += 1
        if dirty and self.count % self.every == 0:
            log.info(f"  💾 Salvataggio automatico ({self.count} funzioni elaborate)")
            self.save()


# ---------------------------------------------------------------------------
# Punto di ripresa (una voce per opzione del menu)
# ---------------------------------------------------------------------------

def _read() -> dict:
    if not STATE_FILE:
        return {}
    try:
        return json.loads(Path(STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    if not STATE_FILE:
        return
    try:
        path = Path(STATE_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.error(f"  Punto di ripresa non salvato: {exc}")


def save_checkpoint(mode: str, func_id: str = "", note: str = "") -> None:
    if not ENABLED:
        return
    data = _read()
    data[str(mode)] = {
        "func_id": func_id,
        "note": note,
        "time": datetime.now().isoformat(timespec="seconds"),
    }
    _write(data)
    if func_id:
        log.warning(f"  Punto di ripresa salvato: funzione '{func_id}'")


def load_checkpoint(mode: str) -> dict:
    if not (ENABLED and RESUME):
        return {}
    return _read().get(str(mode)) or {}


def clear_checkpoint(mode: str) -> None:
    if not ENABLED:
        return
    data = _read()
    if data.pop(str(mode), None) is not None:
        _write(data)
