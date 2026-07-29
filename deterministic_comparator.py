"""
deterministic_comparator.py
---------------------------
Fase 2 — confronto deterministico SENZA LLM.

RUOLO SEMPLIFICATO:
  Produce una lista di "hint" leggibili sui valori numerici/timer
  che differiscono tra configurazioni. Questi hint vengono passati
  al prompt LLM come contesto aggiuntivo, ma NON decidono il colore.

  La decisione finale spetta sempre al LLM (ai_synthesizer.py).
"""
from __future__ import annotations

import logging
import re
from itertools import combinations

from function_parser import ParsedFunction

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pattern
# ---------------------------------------------------------------------------

_RE_NUMERIC = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*"
    r"(?:ms|s|min|h|V|kV|A|mA|Hz|kHz|km/h|bar|kPa|MPa|N|kN|W|kW|mm|cm|m|°C|%|rpm)\b",
    re.IGNORECASE,
)

_RE_TIMER = re.compile(
    r"\b(?:timer|timeout|delay|watchdog)\s*[=:≤≥<>]?\s*\d+\s*(?:ms|s|min)\b",
    re.IGNORECASE,
)


def _extract_values(text: str | None) -> set[str]:
    """Estrae tutti i valori numerici con unità dal testo."""
    if not text:
        return set()
    numeric = {re.sub(r"\s+", "", m.lower()) for m in _RE_NUMERIC.findall(text)}
    timers  = {re.sub(r"\s+", " ", m.lower().strip()) for m in _RE_TIMER.findall(text)}
    return numeric | timers


def _values_from_parsed(pf: ParsedFunction) -> set[str]:
    """Aggrega tutti i valori numerici rilevanti della ParsedFunction."""
    fields = [
        pf.thresholds,
        pf.timing_constraints,
        pf.performance_parameters,
        pf.failure_behaviour,
        pf.operational_logic,
    ]
    result: set[str] = set()
    for f in fields:
        result |= _extract_values(f)
    return result


# ---------------------------------------------------------------------------
# Confronto pairwise → hint leggibili
# ---------------------------------------------------------------------------

def compare_pair(pf_a: ParsedFunction, pf_b: ParsedFunction) -> dict:
    """
    Confronta due ParsedFunction e produce hint leggibili sulle differenze
    nei valori numerici/timer. Non decide nulla — solo fornisce contesto al LLM.
    """
    vals_a = _values_from_parsed(pf_a)
    vals_b = _values_from_parsed(pf_b)

    only_a = vals_a - vals_b
    only_b = vals_b - vals_a

    hints: list[str] = []

    # Filtra i valori "rumorosi" (tensioni nominali di sistema sempre diverse)
    # Questi valori sono attesi diversi per definizione tra configurazioni:
    _NOISE_VALUES = {"1.5kv", "3kv", "15kv", "25kv", "0.85kv", "1.8kv"}

    only_a_clean = {v for v in only_a if v not in _NOISE_VALUES}
    only_b_clean = {v for v in only_b if v not in _NOISE_VALUES}

    if only_a_clean:
        hints.append(
            f"{pf_a.config_name} ha: {', '.join(sorted(only_a_clean)[:5])}"
        )
    if only_b_clean:
        hints.append(
            f"{pf_b.config_name} ha: {', '.join(sorted(only_b_clean)[:5])}"
        )

    has_diffs = bool(only_a_clean or only_b_clean)

    if has_diffs:
        log.info(
            f"  [det] {pf_a.config_name} vs {pf_b.config_name}: "
            f"valori diversi trovati ({len(hints)} hint)"
        )
    else:
        log.info(
            f"  [det] {pf_a.config_name} vs {pf_b.config_name}: "
            f"nessun valore numerico diverso"
        )

    return {
        "pair": (pf_a.config_name, pf_b.config_name),
        "has_objective_differences": has_diffs,
        "hints": hints,
    }


def compare_all(parsed_list: list[ParsedFunction]) -> dict:
    """
    Confronta tutte le coppie e aggrega gli hint (de-duplicati).
    """
    if len(parsed_list) <= 1:
        return {
            "any_objective_differences": False,
            "all_differences_summary": [],
        }

    any_diffs  = False
    seen:  set[str]  = set()
    hints: list[str] = []

    for pf_a, pf_b in combinations(parsed_list, 2):
        report = compare_pair(pf_a, pf_b)
        if report["has_objective_differences"]:
            any_diffs = True
        for h in report["hints"]:
            if h not in seen:
                seen.add(h)
                hints.append(h)

    if any_diffs:
        log.info(f"  ⚡ Hint parametrici: {len(hints)} voci uniche")
    else:
        log.info("  ✅ Nessun hint parametrico")

    return {
        "any_objective_differences": any_diffs,
        "all_differences_summary": hints,
    }