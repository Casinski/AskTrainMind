"""
function_parser.py
------------------
Fase 1 della pipeline: estrae una struttura dati tecnica
da un testo grezzo di funzione ferroviaria ETR1000.

VERSIONE LEGGERA: usa SOLO regex, nessuna chiamata Ollama.
Il parsing LLM è stato rimosso perché troppo lento per uso produttivo.
I campi vengono popolati con pattern euristici sul testo grezzo.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Struttura dati
# ---------------------------------------------------------------------------

@dataclass
class ParsedFunction:
    """
    Rappresentazione strutturata di una funzione ferroviaria.
    Tutti i campi possono essere None se non rilevati nel testo.
    """
    config_name:            str
    function_purpose:       str | None = None
    inputs:                 str | None = None
    outputs:                str | None = None
    trigger_conditions:     str | None = None
    operational_logic:      str | None = None
    states:                 str | None = None
    failure_behaviour:      str | None = None
    safety_behaviour:       str | None = None
    interfaces:             str | None = None
    hardware_components:    str | None = None
    software_components:    str | None = None
    requirements:           str | None = None
    diagnostics:            str | None = None
    performance_parameters: str | None = None
    timing_constraints:     str | None = None
    thresholds:             str | None = None


_FIELDS = [
    "function_purpose", "inputs", "outputs", "trigger_conditions",
    "operational_logic", "states", "failure_behaviour", "safety_behaviour",
    "interfaces", "hardware_components", "software_components",
    "requirements", "diagnostics", "performance_parameters",
    "timing_constraints", "thresholds",
]

# ---------------------------------------------------------------------------
# Pattern di estrazione (euristici, nessuna LLM)
# ---------------------------------------------------------------------------

# Requirement IDs
_RE_REQ = re.compile(
    r"\b(?:[A-Z]{2,10}[-_]){1,3}(?:REQ[-_]?)?\d+\b", re.IGNORECASE
)
# Parametri numerici con unità
_RE_NUMERIC = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*"
    r"(?:ms|s|min|h|V|kV|A|mA|Hz|kHz|km/h|bar|kPa|N|kN|W|kW|mm|cm|m|°C|%|rpm)\b",
    re.IGNORECASE,
)
# Timer/timeout
_RE_TIMER = re.compile(
    r"\b(?:timer|timeout|delay|watchdog)\s*[=:≤≥<>]?\s*\d+\s*(?:ms|s|min)\b",
    re.IGNORECASE,
)
# Codici HW (es. 3ECP413571-0001)
_RE_HW_CODE = re.compile(r"\b[A-Z0-9]{3,}[-][A-Z0-9]{3,}(?:[-][A-Z0-9]+)*\b")
# Stati
_RE_STATE = re.compile(
    r"\b(?:IDLE|ACTIVE|INACTIVE|FAULT|FAIL(?:URE)?|ERROR|NORMAL|"
    r"DEGRADED|EMERGENCY|STANDBY|ARMED|DISARMED|ENABLED|DISABLED|"
    r"RUNNING|STOPPED|OPEN|CLOSED)\b"
)
# Segnali SNAKE_CASE
_RE_SIGNAL = re.compile(r"\b[A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]{2,})+\b")


def parse_function_structure(
    config_name: str,
    text: str,
    func_id: str = "",
    func_desc: str = "",
) -> ParsedFunction:
    """
    Estrae la struttura della funzione con regex — nessuna chiamata Ollama.
    Veloce: < 1ms per funzione.
    """
    if not text.strip():
        log.warning(f"  [parse] [{config_name}] Testo vuoto")
        return ParsedFunction(config_name=config_name)

    pf = ParsedFunction(config_name=config_name)

    # Requirements
    reqs = list(dict.fromkeys(_RE_REQ.findall(text)))  # dedup mantenendo ordine
    if reqs:
        pf.requirements = ", ".join(reqs[:20])

    # Thresholds / parametri numerici
    nums = list(dict.fromkeys(
        re.sub(r"\s+", "", m.lower()) for m in _RE_NUMERIC.findall(text)
    ))
    if nums:
        pf.thresholds = ", ".join(nums[:20])

    # Timing constraints
    timers = list(dict.fromkeys(
        re.sub(r"\s+", " ", m.lower().strip()) for m in _RE_TIMER.findall(text)
    ))
    if timers:
        pf.timing_constraints = ", ".join(timers[:10])

    # Hardware components (codici documento)
    hw_codes = list(dict.fromkeys(_RE_HW_CODE.findall(text)))
    if hw_codes:
        pf.hardware_components = ", ".join(hw_codes[:20])

    # States
    states = list(dict.fromkeys(_RE_STATE.findall(text.upper())))
    if states:
        pf.states = ", ".join(states[:15])

    # Signals / interfaces (SNAKE_CASE)
    signals = list(dict.fromkeys(_RE_SIGNAL.findall(text)))
    if signals:
        pf.interfaces = ", ".join(signals[:20])

    # Function purpose: prima riga non vuota significativa
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 20 and not line.startswith("["):
            pf.function_purpose = line[:200]
            break

    populated = sum(1 for f in _FIELDS if getattr(pf, f) is not None)
    log.info(
        f"  [parse] [{config_name}] ✅ Parsing regex OK — "
        f"campi valorizzati: {populated}/{len(_FIELDS)}"
    )
    return pf