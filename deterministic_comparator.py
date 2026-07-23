"""
deterministic_comparator.py
---------------------------
Fase 2 della pipeline: confronto deterministico SENZA LLM.

VERSIONE AGGIORNATA:
  - Rimossi i codici documento (3ECP..., FA0...) dal confronto:
    sono sempre diversi tra configurazioni per definizione.
  - Rimossi i signal names SNAKE_CASE: troppo rumore.
  - Rimangono SOLO token che indicano differenze funzionali reali:
      • Parametri numerici con unità (soglie, tensioni, correnti, tempi)
      • Timer e timeout espliciti
      • Nomi di stato operativo (FAULT, ACTIVE, DEGRADED, ecc.)
  - I requirement IDs vengono loggati ma NON influenzano la decisione:
    codici requisito diversi non implicano comportamento diverso.
"""
from __future__ import annotations

import logging
import re
from itertools import combinations

from function_parser import ParsedFunction

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pattern — solo token funzionalmente rilevanti
# ---------------------------------------------------------------------------

# Parametri numerici con unità di misura (soglie, prestazioni, tempi)
_RE_NUMERIC = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*"
    r"(?:ms|s|min|h|V|kV|A|mA|Hz|kHz|km/h|kmh|bar|kPa|MPa|"
    r"N|kN|W|kW|MW|mm|cm|m|°C|K|%|rpm)\b",
    re.IGNORECASE,
)

# Timer e timeout espliciti (es. "timeout 500ms", "delay 2s")
_RE_TIMER = re.compile(
    r"\b(?:timer|timeout|delay|ritardo|attesa|watchdog)\s*[=:≤≥<>]?\s*\d+\s*(?:ms|s|min)\b",
    re.IGNORECASE,
)

# Stati operativi nominali (solo quelli con significato funzionale chiaro)
_RE_STATE = re.compile(
    r"\b(?:IDLE|ACTIVE|INACTIVE|FAULT|FAIL(?:URE)?|ERROR|NORMAL|"
    r"DEGRADED|EMERGENCY|STANDBY|ARMED|DISARMED|ENABLED|DISABLED|"
    r"RUNNING|STOPPED)\b"
)


# ---------------------------------------------------------------------------
# Estrazione token funzionali da testo
# ---------------------------------------------------------------------------

def _extract_functional_tokens(text: str | None) -> dict[str, set[str]]:
    """
    Estrae solo i token con rilevanza funzionale diretta.
    NON include: codici documento, signal names, requirement IDs.
    """
    if not text:
        return {"numeric": set(), "timers": set(), "states": set()}

    return {
        "numeric": {
            re.sub(r"\s+", "", m.lower())
            for m in _RE_NUMERIC.findall(text)
        },
        "timers": {
            re.sub(r"\s+", " ", m.lower().strip())
            for m in _RE_TIMER.findall(text)
        },
        "states": {
            m.upper()
            for m in _RE_STATE.findall(text.upper())
        },
    }


def _tokens_from_parsed(pf: ParsedFunction) -> dict[str, dict[str, set[str]]]:
    """
    Estrae token funzionali dai campi più rilevanti della ParsedFunction.
    Esclude 'requirements' e 'hardware_components' perché i loro codici
    sono diversi per definizione tra configurazioni.
    """
    field_map = {
        "thresholds":             pf.thresholds,
        "timing_constraints":     pf.timing_constraints,
        "states":                 pf.states,
        "operational_logic":      pf.operational_logic,
        "failure_behaviour":      pf.failure_behaviour,
        "performance_parameters": pf.performance_parameters,
        "inputs":                 pf.inputs,
        "outputs":                pf.outputs,
    }
    return {field: _extract_functional_tokens(text) for field, text in field_map.items()}


# ---------------------------------------------------------------------------
# Confronto pairwise
# ---------------------------------------------------------------------------

_CATEGORY_LABELS = {
    "numeric": "parametri numerici",
    "timers":  "timer/timeout",
    "states":  "stati operativi",
}

# Soglia minima: ignora differenze su set molto piccoli (< 2 token)
# per evitare falsi positivi da testo sparse
_MIN_TOKENS_FOR_DIFF = 2


def compare_pair(pf_a: ParsedFunction, pf_b: ParsedFunction) -> dict:
    """
    Confronta deterministicamente due ParsedFunction sui token funzionali.
    Ignora codici documento, requisiti e signal names.
    """
    tokens_a = _tokens_from_parsed(pf_a)
    tokens_b = _tokens_from_parsed(pf_b)

    differences = {}
    summary     = []

    for field_name in tokens_a:
        toks_a = tokens_a[field_name]
        toks_b = tokens_b.get(field_name, {})
        field_diffs = {}

        for cat in toks_a:
            set_a = toks_a.get(cat, set())
            set_b = toks_b.get(cat, set())

            # Ignora confronti su set troppo piccoli
            if len(set_a) < _MIN_TOKENS_FOR_DIFF and len(set_b) < _MIN_TOKENS_FOR_DIFF:
                continue

            only_a = set_a - set_b
            only_b = set_b - set_a

            # Soglia: almeno 2 token diversi per segnalare differenza
            if len(only_a) >= _MIN_TOKENS_FOR_DIFF or len(only_b) >= _MIN_TOKENS_FOR_DIFF:
                label = _CATEGORY_LABELS.get(cat, cat)
                field_diffs[cat] = {
                    f"solo_in_{pf_a.config_name}": sorted(only_a),
                    f"solo_in_{pf_b.config_name}": sorted(only_b),
                }
                if only_a:
                    summary.append(
                        f"[{field_name}/{label}] Solo in {pf_a.config_name}: "
                        f"{', '.join(sorted(only_a)[:5])}"
                    )
                if only_b:
                    summary.append(
                        f"[{field_name}/{label}] Solo in {pf_b.config_name}: "
                        f"{', '.join(sorted(only_b)[:5])}"
                    )

        if field_diffs:
            differences[field_name] = field_diffs

    has_diffs = bool(differences)

    if has_diffs:
        log.info(
            f"  [det] {pf_a.config_name} vs {pf_b.config_name}: "
            f"⚡ {len(summary)} diff. funzionali oggettive"
        )
    else:
        log.info(
            f"  [det] {pf_a.config_name} vs {pf_b.config_name}: "
            f"✅ Nessuna diff. funzionale oggettiva"
        )

    return {
        "pair":                      (pf_a.config_name, pf_b.config_name),
        "has_objective_differences": has_diffs,
        "differences":               differences,
        "summary":                   summary,
    }


def compare_all(parsed_list: list[ParsedFunction]) -> dict:
    """
    Confronta tutte le coppie (pairwise) sui token funzionali.
    """
    if len(parsed_list) <= 1:
        return {
            "pairs": {},
            "any_objective_differences": False,
            "all_differences_summary": [],
            "equivalent_groups": [[p.config_name for p in parsed_list]],
        }

    pairs_result = {}
    any_diffs    = False
    all_summary  = []

    for pf_a, pf_b in combinations(parsed_list, 2):
        report = compare_pair(pf_a, pf_b)
        pairs_result[(pf_a.config_name, pf_b.config_name)] = report
        if report["has_objective_differences"]:
            any_diffs = True
        for item in report["summary"]:
            if item not in all_summary:   # de-duplica voci identiche da coppie diverse
                all_summary.append(item)

    equiv_groups = _build_equivalent_groups(parsed_list, pairs_result)

    return {
        "pairs":                     pairs_result,
        "any_objective_differences": any_diffs,
        "all_differences_summary":   all_summary,
        "equivalent_groups":         equiv_groups,
    }


def _build_equivalent_groups(
    parsed_list: list[ParsedFunction],
    pairs_result: dict,
) -> list[list[str]]:
    names  = [p.config_name for p in parsed_list]
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for (a, b), report in pairs_result.items():
        if not report["has_objective_differences"]:
            union(a, b)

    groups: dict[str, list[str]] = {}
    for name in names:
        root = find(name)
        groups.setdefault(root, []).append(name)

    return list(groups.values())