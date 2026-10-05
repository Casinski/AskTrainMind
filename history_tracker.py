"""
history_tracker.py
------------------
Tiene traccia nel tempo di cosa è già stato analizzato e di cosa è cambiato.

DUE LIVELLI DI CONTROLLO (per non rianalizzare migliaia di PDF a ogni run)

  LIVELLO 1 — "fast": impronta del FILE
      size + mtime del PDF locale. Costo ~0 (una stat su disco).
      Se invariato rispetto all'ultima esecuzione → la sezione NON può
      essere cambiata → skip totale (nessuna estrazione, nessuna LLM).

  LIVELLO 2 — "deep": impronta del CONTENUTO
      hash SHA-1 del testo normalizzato della sezione + lista ordinata
      degli ID requisito. Costo medio (estrazione PDF, nessuna LLM).
      Eseguito quando il livello 1 segnala un cambiamento, quando non
      esiste ancora uno stato, oppure periodicamente
      (cfg.RECHECK_DEEP_EVERY_DAYS) per intercettare casi limite.

  Solo se il livello 2 rileva una differenza reale si paga la chiamata LLM.

OUTPUT STORICO
  - state.json              stato corrente (impronte)
  - history.jsonl           un evento per riga, machine-readable
  - storico_differenze.log  log leggibile dall'utente
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import config as cfg

log = logging.getLogger(__name__)

_state: dict = {}
_dirty = False


# ---------------------------------------------------------------------------
# Caricamento / salvataggio stato
# ---------------------------------------------------------------------------

def load_state() -> None:
    global _state
    try:
        if cfg.HISTORY_STATE_FILE.exists():
            _state = json.loads(cfg.HISTORY_STATE_FILE.read_text(encoding="utf-8"))
            log.info(f"  [Storico] Stato caricato: {len(_state)} voci")
        else:
            _state = {}
            log.info("  [Storico] Nessuno stato precedente — prima esecuzione")
    except Exception as exc:
        log.warning(f"  [Storico] Stato non leggibile ({exc}) — riparto da zero")
        _state = {}


def save_state() -> None:
    if not _dirty:
        return
    try:
        cfg.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        cfg.HISTORY_STATE_FILE.write_text(
            json.dumps(_state, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        log.info(f"  [Storico] Stato salvato: {cfg.HISTORY_STATE_FILE}")
    except Exception as exc:
        log.error(f"  [Storico] Errore salvataggio stato: {exc}")


def _key(func_id: str, doc_id: str, config_name: str) -> str:
    return f"{func_id}||{doc_id}||{config_name}"


# ---------------------------------------------------------------------------
# LIVELLO 1 — impronta file
# ---------------------------------------------------------------------------

def file_stamp(path) -> str:
    """'size:mtime' del PDF, oppure '' se non disponibile."""
    try:
        p = Path(path)
        st = p.stat()
        return f"{st.st_size}:{int(st.st_mtime)}"
    except Exception:
        return ""


def file_unchanged(func_id, doc_id, config_name, stamp: str) -> bool:
    """True se il file è identico all'ultima analisi registrata."""
    if not stamp:
        return False
    rec = _state.get(_key(func_id, doc_id, config_name))
    if not rec or rec.get("file_stamp") != stamp:
        return False
    if _deep_check_due(rec):
        log.debug("    [Storico] Controllo profondo periodico dovuto")
        return False
    return True


def _deep_check_due(rec: dict) -> bool:
    days = getattr(cfg, "RECHECK_DEEP_EVERY_DAYS", 0)
    if not days:
        return False
    try:
        last = datetime.fromisoformat(rec.get("deep_checked_at", ""))
        return (datetime.now(timezone.utc) - last).days >= days
    except Exception:
        return True


# ---------------------------------------------------------------------------
# LIVELLO 2 — impronta contenuto
# ---------------------------------------------------------------------------

def text_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", (text or "")).strip().lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


@dataclass
class ChangeReport:
    changed: bool
    is_new: bool
    text_changed: bool = False
    reqs_added: list = None
    reqs_removed: list = None
    reqs_modified: list = None

    def summary(self) -> str:
        if self.is_new:
            return "prima analisi"
        bits = []
        if self.text_changed:
            bits.append("testo sezione modificato")
        if self.reqs_added:
            bits.append(f"+{len(self.reqs_added)} requisiti")
        if self.reqs_removed:
            bits.append(f"-{len(self.reqs_removed)} requisiti")
        if self.reqs_modified:
            bits.append(f"~{len(self.reqs_modified)} requisiti modificati")
        return ", ".join(bits) or "nessuna differenza"


def check_content(
    func_id: str,
    doc_id: str,
    config_name: str,
    section_text: str,
    requirements: list,
) -> ChangeReport:
    """Confronta testo e requisiti con l'ultimo stato registrato."""
    rec = _state.get(_key(func_id, doc_id, config_name))
    new_txt  = text_hash(section_text)
    new_reqs = {r.req_id: r.fingerprint() for r in requirements}

    if not rec:
        return ChangeReport(changed=True, is_new=True,
                            reqs_added=list(new_reqs), reqs_removed=[], reqs_modified=[])

    old_txt  = rec.get("text_hash", "")
    old_reqs = rec.get("reqs", {})

    added    = [r for r in new_reqs if r not in old_reqs]
    removed  = [r for r in old_reqs if r not in new_reqs]
    modified = [r for r in new_reqs if r in old_reqs and new_reqs[r] != old_reqs[r]]
    txt_changed = (old_txt != new_txt)

    return ChangeReport(
        changed=bool(txt_changed or added or removed or modified),
        is_new=False,
        text_changed=txt_changed,
        reqs_added=added, reqs_removed=removed, reqs_modified=modified,
    )


# ---------------------------------------------------------------------------
# Registrazione
# ---------------------------------------------------------------------------

def record(
    func_id: str,
    doc_id: str,
    config_name: str,
    file_stamp_value: str,
    section_text: str,
    requirements: list,
    report: ChangeReport | None = None,
    score: int | None = None,
) -> None:
    """Aggiorna lo stato e, se c'è stata una differenza, scrive lo storico."""
    global _dirty
    now = datetime.now(timezone.utc).isoformat()

    _state[_key(func_id, doc_id, config_name)] = {
        "file_stamp": file_stamp_value,
        "text_hash": text_hash(section_text),
        "reqs": {r.req_id: r.fingerprint() for r in requirements},
        "score": score,
        "deep_checked_at": now,
        "updated_at": now,
    }
    _dirty = True

    if report and report.changed and not report.is_new:
        _write_history(func_id, doc_id, config_name, report, now)


def touch(func_id: str, doc_id: str, config_name: str) -> None:
    """Segna la voce come verificata senza modificarne le impronte."""
    global _dirty
    rec = _state.get(_key(func_id, doc_id, config_name))
    if rec:
        rec["checked_at"] = datetime.now(timezone.utc).isoformat()
        _dirty = True


def _write_history(func_id, doc_id, config_name, report, now) -> None:
    event = {
        "ts": now, "func_id": func_id, "doc_id": doc_id, "config": config_name,
        "text_changed": report.text_changed,
        "reqs_added": report.reqs_added or [],
        "reqs_removed": report.reqs_removed or [],
        "reqs_modified": report.reqs_modified or [],
    }
    try:
        cfg.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        with cfg.HISTORY_LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.error(f"  [Storico] Errore scrittura history.jsonl: {exc}")

    righe = [
        f"[{now}] {func_id} / {doc_id} / {config_name}",
        f"    {report.summary()}",
    ]
    for rid in (report.reqs_added or []):
        righe.append(f"    + NUOVO     {rid}")
    for rid in (report.reqs_removed or []):
        righe.append(f"    - RIMOSSO   {rid}")
    for rid in (report.reqs_modified or []):
        righe.append(f"    ~ MODIFICATO {rid}")
    blocco = "\n".join(righe)

    log.warning("  �óÄ STORICO — differenza rilevata:\n" + blocco)
    try:
        with Path(cfg.HISTORY_READABLE_LOG).open("a", encoding="utf-8") as fh:
            fh.write(blocco + "\n\n")
    except Exception:
        pass