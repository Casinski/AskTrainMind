"""
req_ai_comparator.py
--------------------
Confronto di UN requisito fra VZI_Base e le altre configurazioni.
Ritorna (is_match: bool, differenze: str).
"""
from __future__ import annotations
import json, logging, re

import config as cfg
from ai_synthesizer import _call_ollama

log = logging.getLogger(__name__)

_cache: dict[tuple, tuple[bool, str]] = {}


def dump_fields(req) -> str:
    """Tutti i campi testuali della tabella, separati da separatori."""
    parts = []
    for attr, label in cfg.REQ_FIELD_LABEL.items():
        val = (getattr(req, attr, "") or "").strip()
        if val:
            parts.append(f"{label}: {val}")
    return cfg.REQ_FIELD_SEP.join(parts)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def identical(reqs: list) -> bool:
    """True se i campi testuali sono identici in tutte le versioni."""
    firme = {_norm(dump_fields(r)) for r in reqs}
    return len(firme) <= 1


def compare(req_id: str, base_req, other_name: str, other_req) -> tuple[bool, str]:
    """
    Confronta il requisito base con quello di un'altra configurazione.
    Shortcut deterministico: testi identici → MATCHED senza chiamare il LLM.
    """
    if _norm(dump_fields(base_req)) == _norm(dump_fields(other_req)):
        return True, ""

    key = (req_id.lower(), other_name)
    if key in _cache:
        return _cache[key]

    prompt = (
        "Sei un tecnico ferroviario esperto di sistemi ETR1000.\n"
        f"Confronta lo STESSO requisito '{req_id}' in due configurazioni.\n\n"
        f"--- [{cfg.REQ_BASE_CONFIG}] ---\n{dump_fields(base_req)[:2500]}\n\n"
        f"--- [{other_name}] ---\n{dump_fields(other_req)[:2500]}\n\n"
        "ISTRUZIONI:\n"
        "1. Sono differenze REALI: logica operativa, soglie numeriche, "
        "comportamento in guasto, SIL, interfaccia utente, tipo di requisito.\n"
        "2. NON sono differenze reali: riformulazioni, codici documento, "
        "punteggiatura, maiuscole.\n"
        "3. score 0-100 (100 = funzionalmente identici).\n"
        "4. 'differenze': testo in italiano, max 3 frasi, concreto.\n\n"
        'Rispondi SOLO con JSON: {"score": 90, "differenze": "..."}'
    )

    raw = _call_ollama(prompt)
    score, diff = 50, ""
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data  = json.loads(m.group())
            score = int(data.get("score", 50))
            diff  = (data.get("differenze") or "").strip()
    except Exception as exc:
        log.warning(f"  [ReqAI] parsing fallito su {req_id}: {exc}")

    is_match = score >= cfg.REQ_LLM_SCORE_MATCH and not diff
    if not is_match and not diff:
        diff = "Differenze rilevate ma non descrivibili dal modello."

    out = (is_match, "" if is_match else diff)
    _cache[key] = out
    return out