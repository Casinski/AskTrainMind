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
    """
    Campi testuali della tabella, separati da separatori.
    Layout "V" (ID | Description | Safety level) usa etichette proprie;
    "H"/"T" usano le etichette della tabella orizzontale.
    """
    labels = (cfg.REQ_FIELD_LABEL_V
              if getattr(req, "layout", "") == "V"
              else cfg.REQ_FIELD_LABEL)
    parts = []
    for attr, label in labels.items():
        val = (getattr(req, attr, "") or "").strip()
        if val:
            parts.append(f"{label}: {val}")
    if not parts:                       # nessun campo: almeno l'ID
        parts.append(f"ID: {getattr(req, 'req_id', '')}")
    return cfg.REQ_FIELD_SEP.join(parts)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def identical(reqs: list) -> bool:
    """True se i campi testuali sono identici in tutte le versioni."""
    firme = {_norm(dump_fields(r)) for r in reqs}
    return len(firme) <= 1

def compare(req_id: str, base_req, other_name: str, other_req) -> tuple[bool, str]:
    """
    Confronta il requisito di riferimento con quello di un'altra configurazione.

    Ritorna (is_match, differenze):
      (True,  "")      → testi funzionalmente equivalenti → MATCHED
      (False, "...")   → differenze da scrivere in rosso nella cella

    SHORTCUT DETERMINISTICI (nessuna chiamata al LLM)
      1. Dump dei campi identico dopo normalizzazione.
      2. Layout diverso (V vs H): le tabelle verticali hanno solo
         ID / Description / Safety level, quindi 'Derived to',
         'User Interface' e 'Type / Applicability Details' sono assenti
         per costruzione. Confrontare il dump completo produrrebbe un
         falso "diverso": si confrontano i soli campi comuni.
    """
    base_name = getattr(base_req, "config_name", "") or cfg.REQ_BASE_CONFIG

    # ── Shortcut 1: testi identici ───────────────────────────────────────
    if _norm(dump_fields(base_req)) == _norm(dump_fields(other_req)):
        return True, ""

    # ── Shortcut 2: layout diversi, campi comuni coincidenti ─────────────
    if (getattr(base_req, "layout", "") != getattr(other_req, "layout", "")
            and same_core(base_req, other_req)):
        log.debug(
            f"  [ReqAI] {req_id}: layout diversi "
            f"({base_req.layout}/{other_req.layout}) ma campi comuni "
            f"identici → MATCHED senza LLM"
        )
        return True, ""

    # ── Cache: la chiave deve includere ENTRAMBE le configurazioni ───────
    # Senza base_name lo stesso ID confrontato con basi diverse (caso 1 vs
    # caso 3, dove la base e' una config qualsiasi) riuserebbe un esito
    # sbagliato.
    key = (req_id.lower(), base_name, other_name)
    if key in _cache:
        return _cache[key]

    prompt = (
        "Sei un tecnico ferroviario esperto di sistemi ETR1000.\n"
        f"Confronta lo STESSO requisito '{req_id}' in due configurazioni.\n\n"
        f"--- [{base_name}] ---\n{dump_fields(base_req)[:2500]}\n\n"
        f"--- [{other_name}] ---\n{dump_fields(other_req)[:2500]}\n\n"
        "ISTRUZIONI:\n"
        "1. Sono differenze REALI: logica operativa, soglie numeriche, "
        "comportamento in guasto, livello SIL / Safety level, interfaccia "
        "utente, tipo di requisito (Type / Applicability Details).\n"
        "2. NON sono differenze reali: riformulazioni, codici documento, "
        "punteggiatura, maiuscole, campi presenti in una sola tabella "
        "perche' il layout e' diverso (tabella verticale vs orizzontale).\n"
        "3. score 0-100 (100 = funzionalmente identici).\n"
        "4. 'differenze': testo in italiano, max 3 frasi, concreto e "
        "immediatamente utile a chi legge il foglio Excel. "
        "Stringa vuota se non ci sono differenze reali.\n\n"
        'Rispondi SOLO con questo JSON, nessun testo prima o dopo:\n'
        '{"score": 90, "differenze": "..."}'
    )

    raw = _call_ollama(prompt)
    score, diff = 50, ""
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data  = json.loads(m.group())
            raw_score = data.get("score", 50)
            score = int(raw_score) if isinstance(raw_score, (int, float, str)) \
                and str(raw_score).strip().lstrip("-").isdigit() else 50
            if not 0 <= score <= 100:
                score = 50
            diff = (data.get("differenze") or "").strip()
        else:
            log.warning(f"  [ReqAI] nessun JSON nella risposta per {req_id}")
    except Exception as exc:
        log.warning(f"  [ReqAI] parsing fallito su {req_id}: {exc}")

    is_match = score >= cfg.REQ_LLM_SCORE_MATCH and not diff
    if not is_match and not diff:
        diff = (f"Differenze rilevate tra {base_name} e {other_name} "
                f"(score {score}/100) non descrivibili dal modello: "
                f"verifica manuale consigliata.")

    log.info(
        f"  [ReqAI] {req_id} | {base_name} vs {other_name} | "
        f"score={score} | {'MATCHED' if is_match else 'DIFF'}"
    )

    out = (is_match, "" if is_match else diff)
    _cache[key] = out
    return out


_COMMON_FIELDS = ("description", "sil")


def _common_sig(req) -> str:
    return "|".join(_norm(getattr(req, a, "")) for a in _COMMON_FIELDS)


def same_core(a, b) -> bool:
    """True se i campi comuni ai due layout coincidono."""
    return _common_sig(a) == _common_sig(b)