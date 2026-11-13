"""
app_logging.py
--------------
Log unico per tutto AskTrainMind (script principale, storico differenze e
script di debug): un solo file, LOG_FILE in config.py.

Il file non cresce all'infinito: quando supera LOG_MAX_LINES righe viene
riscritto conservando solo le ultime LOG_KEEP_LINES (le piu' recenti).

Uso:
    import app_logging
    app_logging.setup()                 # una volta, all'avvio
    log = logging.getLogger(__name__)   # nei moduli, come sempre

    app_logging.write_file(testo)       # testo solo nel file (niente console)
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

import config as cfg

FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

_FILE_HANDLER: "TrimmingFileHandler | None" = None
_FILE_LOGGER_NAME = "asktrainmind.file"


class TrimmingFileHandler(logging.Handler):
    """
    FileHandler che, superate max_lines righe, tronca il file alle ultime
    keep_lines. Il conteggio e' tenuto in memoria: il file viene riletto
    solo al momento del taglio.
    """

    def __init__(self, path: Path, max_lines: int, keep_lines: int):
        super().__init__()
        self.path = Path(path)
        self.max_lines = max(100, int(max_lines))
        self.keep_lines = min(max(0, int(keep_lines)), self.max_lines)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lines = self._count_lines()
        self._trim_if_needed()

    def _count_lines(self) -> int:
        try:
            with self.path.open("rb") as fh:
                return sum(1 for _ in fh)
        except FileNotFoundError:
            return 0

    def _trim_if_needed(self) -> None:
        if self._lines <= self.max_lines:
            return
        try:
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
            kept = lines[-self.keep_lines:] if self.keep_lines else []
            header = (f"--- log troncato: conservate le ultime "
                      f"{len(kept)} righe (limite {self.max_lines}) ---")
            self.path.write_text("\n".join([header, *kept]) + "\n", encoding="utf-8")
            self._lines = len(kept) + 1
        except OSError:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            self.handleError(record)
            return
        with self._lock:
            try:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(msg + "\n")
                self._lines += msg.count("\n") + 1
                self._trim_if_needed()
            except OSError:
                self.handleError(record)


def log_path() -> Path:
    return Path(getattr(cfg, "LOG_FILE", Path(__file__).parent / "asktrainmind.log"))


def _file_handler() -> TrimmingFileHandler:
    global _FILE_HANDLER
    if _FILE_HANDLER is None:
        _FILE_HANDLER = TrimmingFileHandler(
            log_path(),
            getattr(cfg, "LOG_MAX_LINES", 20000),
            getattr(cfg, "LOG_KEEP_LINES", 10000),
        )
        _FILE_HANDLER.setFormatter(logging.Formatter(FILE_FORMAT))
    return _FILE_HANDLER


def setup(level: int = logging.INFO, console: bool = True,
          console_level: int | None = None,
          console_format: str = CONSOLE_FORMAT) -> logging.Logger:
    """
    Configura il logger radice: file unico (con taglio automatico) e,
    opzionalmente, console. Chiamate ripetute non duplicano gli handler.
    """
    root = logging.getLogger()
    root.setLevel(min(level, console_level or level))
    fh = _file_handler()
    fh.setLevel(level)
    if fh not in root.handlers:
        root.addHandler(fh)
    if console and not any(getattr(h, "_atm_console", False) for h in root.handlers):
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(console_format))
        ch.setLevel(console_level or level)
        ch._atm_console = True
        root.addHandler(ch)
    return root


def file_logger() -> logging.Logger:
    """Logger che scrive solo nel file unico (non in console)."""
    lg = logging.getLogger(_FILE_LOGGER_NAME)
    if _file_handler() not in lg.handlers:
        lg.addHandler(_file_handler())
    lg.setLevel(logging.INFO)
    lg.propagate = False
    return lg


def write_file(text: str, source: str = "") -> None:
    """Scrive un blocco di testo (es. un report di debug) nel log unico."""
    prefix = f"[{source}] " if source else ""
    file_logger().info(prefix + str(text))
