"""
ai_synthesizer.py
-----------------
Pipeline di valutazione semantica (Fasi 3-6).

VERSIONE AGGIORNATA:
  - Prompt LLM con sintesi funzionale + riepilogo confronto in italiano.
  - final_decision con priorità al LLM: score >= 75 → VERDE.
  - _diff_to_str gestisce tech_diffs come str o dict.
  - _default_uncertain_result: fallback parsing → NERO (non ROSSO).
  - UNA SOLA chiamata Ollama per gruppo (cache riutilizzata per tutte le config).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import config as cfg
from function_parser import ParsedFunction

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strutture dati
# ---------------------------------------------------------------------------

@dataclass
class ConfigText:
    config_name: str
    page_number: int
    text: str
    page_number_end: int = 0


@dataclass
class SynthesisResult:
    """
    has_differences:
        None  → unica config o incerto → NERO
        False → equivalenti            → VERDE
        True  → differenze funzionali  → ROSSO
    """
    text: str
    has_differences: bool | None
    uncertain: bool = False
    checklist: dict | None = None
    score: int | None = None
    technical_differences: list[str] = field(default_factory=list)
    editorial_differences: list[str] = field(default_factory=list)
    det_summary: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prerequisiti Ollama
# ---------------------------------------------------------------------------

def check_ollama() -> bool:
    try:
        import ollama
        models     = ollama.list()
        available  = [m.model for m in models.models]
        model_base = cfg.OLLAMA_MODEL.split(":")[0]
        if not any(model_base in m for m in available):
            log.error(f"Modello '{cfg.OLLAMA_MODEL}' non trovato. Disponibili: {available}")
            return False
        log.info(f"✅ Ollama OK — modello '{cfg.OLLAMA_MODEL}' disponibile.")
        return True
    except Exception as exc:
        log.error(f"Ollama non raggiungibile: {exc}")
        return False


def _call_ollama(prompt: str) -> str:
    try:
        import ollama
        response = ollama.chat(
            model=cfg.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )
        return response["message"]["content"].strip()
    except Exception as exc:
        log.error(f"  Errore Ollama: {exc}")
        return f"[Errore AI: {exc}]"


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_CHECKLIST_KEYS = [
    "functional_purpose",
    "operational_logic",
    "performance",
    "failure_handling",
    "diagnostics",
    "safety",
]

_CHECKLIST_LABELS = {
    "functional_purpose": "Scopo funzionale",
    "operational_logic":  "Logica operativa",
    "performance":        "Prestazioni",
    "failure_handling":   "Comportamento in guasto",
    "diagnostics":        "Diagnostica",
    "safety":             "Sicurezza",
}

_CRITICAL_KEYS: list[str] = _CHECKLIST_KEYS

_SCORE_RED:    int = getattr(cfg, "LLM_SCORE_THRESHOLD_RED",    75)
_SCORE_YELLOW: int = getattr(cfg, "LLM_SCORE_THRESHOLD_YELLOW", 55)


# ---------------------------------------------------------------------------
# Fase 3+4 — singola chiamata Ollama per gruppo
# ---------------------------------------------------------------------------

def _ask_ollama_group(
    func_id: str,
    func_desc: str,
    doc_id: str,
    valid_texts: list[ConfigText],
    det_summary: list[str],
) -> dict:
    """
    UNA SOLA chiamata Ollama per il gruppo.
    Produce per ogni configurazione:
      1. sintesi: descrizione funzionale in italiano (3-5 frasi)
      2. riepilogo_confronto: testo leggibile che spiega se la config
         è uguale o diversa rispetto alle altre e PERCHÉ.
    """
    all_names = [ct.config_name for ct in valid_texts]

    configs_section = ""
    for ct in valid_texts:
        configs_section += (
            f"\n{'─'*40}\n"
            f"[{ct.config_name}]\n"
            f"{ct.text}\n"
        )

    det_note = ""
    if det_summary:
        det_note = (
            "\nDIFFERENZE NUMERICHE/TEMPORALI GIÀ RILEVATE AUTOMATICAMENTE:\n"
            + "\n".join(f"  • {d}" for d in det_summary[:8])
            + "\nVerifica se queste differenze hanno impatto funzionale reale.\n\n"
        )

    sintesi_keys = "\n".join(
        f'    "{ct.config_name}": "descrizione funzionale in italiano (3-5 frasi)"'
        for ct in valid_texts
    )

    riepilogo_keys = "\n".join(
        f'    "{ct.config_name}": "es: VZI_Base è equivalente a VZI_FR. '
        f'oppure: VZI_ES è differente da VZI_Base a causa di..."'
        for ct in valid_texts
    )

    prompt = (
        "Sei un revisore tecnico ferroviario senior, specializzato in sistemi ETR1000.\n\n"
        f"Funzione: {func_id} — {func_desc}\n"
        f"Documento: {doc_id}\n"
        f"Configurazioni da confrontare: {all_names}\n\n"

        "COSA DEVI PRODURRE:\n"
        "  1. sintesi: per ogni config, descrizione funzionale in italiano (3-5 frasi).\n"
        "  2. riepilogo_confronto: per ogni config, testo leggibile in italiano che spiega\n"
        "     se è uguale o diversa rispetto alle altre e PERCHÉ (valori, logica, soglie).\n"
        "     Esempi:\n"
        "       'VZI_Base è equivalente a VZI_FR: stessa logica, stesse soglie (750 kPa, 35 s).'\n"
        "       'VZI_ES è differente da VZI_Base: soglia pressione 800 kPa vs 750 kPa.'\n\n"

        "COSA VALUTARE (ESCLUSIVAMENTE):\n"
        "  1. Scopo funzionale\n  2. Logica operativa\n  3. Prestazioni e soglie\n"
        "  4. Comportamento in guasto\n  5. Diagnostica\n  6. Sicurezza\n\n"

        "COSA NON VALUTARE (ignora):\n"
        "  - Codici documento, ID requisiti, numeri revisione\n"
        "  - Nomi segnali interni, differenze formattazione\n\n"

        "QUANDO dichiarare DIFFERENT:\n"
        "  - Attivazione in condizioni diverse, soglie/tempi significativamente diversi,\n"
        "    comportamento in guasto diverso, diagnostica diversa, safety diversa.\n\n"

        "QUANDO dichiarare IDENTICAL:\n"
        "  - Stesso comportamento anche se espresso diversamente,\n"
        "    stessi valori numerici, stessa logica.\n\n"

        f"{det_note}"
        f"Testi tecnici:\n{configs_section}\n\n"

        "Score: 0 (diverse) → 100 (identiche). Equivalenti se score ≥ 75.\n\n"

        "Rispondi SOLO con questo JSON:\n"
        "{\n"
        '  "equivalenti": true,\n'
        '  "score": 85,\n'
        '  "checklist": {\n'
        '    "functional_purpose": "IDENTICAL",\n'
        '    "operational_logic": "IDENTICAL",\n'
        '    "performance": "IDENTICAL",\n'
        '    "failure_handling": "IDENTICAL",\n'
        '    "diagnostics": "IDENTICAL",\n'
        '    "safety": "IDENTICAL"\n'
        "  },\n"
        '  "technical_differences": [],\n'
        '  "editorial_differences": [],\n'
        '  "sintesi": {\n'
        f"{sintesi_keys}\n"
        "  },\n"
        '  "riepilogo_confronto": {\n'
        f"{riepilogo_keys}\n"
        "  },\n"
        '  "motivazione": "Spiegazione in italiano (max 2 frasi)"\n'
        "}"
    )

    raw = _call_ollama(prompt)

    try:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            checklist = data.get("checklist", {})
            for k in _CHECKLIST_KEYS:
                v = str(checklist.get(k, "NULL")).upper().strip()
                if v not in ("IDENTICAL", "DIFFERENT", "NULL"):
                    v = "NULL"
                checklist[k] = v
            data["checklist"] = checklist

            data.setdefault("equivalenti", False)
            data.setdefault("score", 50)
            data.setdefault("technical_differences", [])
            data.setdefault("editorial_differences", [])
            data.setdefault("sintesi", {})
            data.setdefault("riepilogo_confronto", {})
            data.setdefault("motivazione", "")

            # Fallback riepilogo_confronto mancante
            if not data["riepilogo_confronto"]:
                motivazione = data.get("motivazione", "")
                for name in all_names:
                    data["riepilogo_confronto"][name] = (
                        motivazione or "Confronto non disponibile."
                    )

            # Sanity check score
            score = data.get("score", 50)
            if not isinstance(score, (int, float)) or not (0 <= score <= 100):
                log.warning(f"  Score fuori range ({score}), impostato a 50")
                data["score"] = 50

            return data

    except (json.JSONDecodeError, AttributeError) as exc:
        log.warning(
            f"  Risposta Ollama non parsabile: {exc}\n"
            f"  Risposta: {raw[:300]}\n"
            "  Fallback: INCERTO."
        )

    return _default_uncertain_result(all_names)


# ---------------------------------------------------------------------------
# Risultati di default
# ---------------------------------------------------------------------------

def _default_uncertain_result(names: list[str]) -> dict:
    """Fallback parsing fallito → NERO (non ROSSO)."""
    return {
        "equivalenti": None,
        "score": 50,
        "checklist": {k: "NULL" for k in _CHECKLIST_KEYS},
        "technical_differences": [],
        "editorial_differences": [],
        "sintesi": {n: "Analisi non disponibile." for n in names},
        "riepilogo_confronto": {
            n: "Confronto non disponibile: errore di analisi LLM." for n in names
        },
        "motivazione": "Errore parsing risposta LLM — classificato come incerto.",
    }


def _default_single_result(config_name: str, text: str) -> dict:
    first_lines = " ".join(
        line.strip() for line in text.splitlines()
        if len(line.strip()) > 20
    )[:400]
    return {
        "equivalenti": True,
        "score": 100,
        "checklist": {k: "NULL" for k in _CHECKLIST_KEYS},
        "technical_differences": [],
        "editorial_differences": [],
        "sintesi": {config_name: first_lines or "[Testo disponibile nel documento]"},
        "riepilogo_confronto": {
            config_name: "Unica configurazione — nessun confronto effettuato."
        },
        "motivazione": "Unica configurazione — nessun confronto effettuato.",
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _diff_to_str(d) -> str:
    """
    Normalizza un elemento di technical_differences a stringa.
    Gestisce sia str che dict {'descrizione': '...'} restituiti dal LLM.
    """
    if isinstance(d, dict):
        return " ".join(str(v) for v in d.values()).lower()
    return str(d).lower()


# ---------------------------------------------------------------------------
# Fase 5 — Decisione finale
# ---------------------------------------------------------------------------

def final_decision(
    det_report: dict,
    llm_result: dict,
) -> tuple[bool | None, str]:
    """
    Decisione finale con priorità al LLM.

    GERARCHIA:
      1. Score >= RED (75) → VERDE
         Il LLM ha letto il testo reale. Prevale sul det_report
         che può avere falsi positivi (tensioni nominali, codici paese).
         Eccezione: se ≥ 2 categorie DIFFERENT con score alto → NERO
         (contraddizione interna del LLM).

      2. Score < YELLOW (55) + ≥ 2 tipi di diff. det confermati → ROSSO
         Doppia conferma richiesta.

      3. Score borderline (YELLOW ≤ score < RED) + ≥ 2 categorie DIFFERENT → ROSSO

      4. Tutto il resto → NERO (incerto, revisione manuale)

    NOTA: il det_report conta coppie pairwise (N*(N-1)/2), quindi con
    4 config produce fino a 6 voci per una sola differenza reale.
    Non usare il conteggio grezzo come soglia.
    """
    checklist  = llm_result.get("checklist", {})
    score      = llm_result.get("score", 50)
    tech_diffs = llm_result.get("technical_differences", [])
    det_diffs  = det_report.get("all_differences_summary", [])

    # Sanity
    if not isinstance(score, (int, float)):
        score = 50

    # ── Errore parsing LLM → NERO ─────────────────────────────────────────
    if any("errore" in _diff_to_str(d) or "parsing" in _diff_to_str(d)
           for d in tech_diffs):
        return None, "Errore parsing LLM — classificato come incerto."

    critical_diffs = [k for k in _CRITICAL_KEYS if checklist.get(k) == "DIFFERENT"]

    # ── PRIORITÀ 1: score alto → VERDE ───────────────────────────────────
    if score >= _SCORE_RED:
        if len(critical_diffs) <= 1:
            # 0 o 1 categoria DIFFERENT con score alto → VERDE
            return False, (
                f"LLM: nessuna differenza funzionale rilevante. Score: {score}."
            )
        # ≥ 2 categorie DIFFERENT con score alto → contraddizione → NERO
        return None, (
            f"Score {score} ma {len(critical_diffs)} categorie DIFFERENT "
            f"({', '.join(critical_diffs)}) — contraddizione, revisione manuale."
        )

    # ── PRIORITÀ 2: score molto basso + det conferma → ROSSO ─────────────
    if score < _SCORE_YELLOW:
        unique_det_types = {
            d.split("]")[0].lstrip("[")
            for d in det_diffs
            if "]" in d
        }
        if len(unique_det_types) >= 2:
            return True, (
                f"Score basso ({score}) confermato da differenze "
                f"in: {', '.join(sorted(unique_det_types))}."
            )
        return None, (
            f"Score basso ({score}) ma differenze parametriche insufficienti "
            "— revisione manuale."
        )

    # ── PRIORITÀ 3: score borderline + ≥ 2 categorie DIFFERENT → ROSSO ──
    if len(critical_diffs) >= 2:
        return True, (
            f"Score borderline ({score}) con {len(critical_diffs)} categorie "
            f"DIFFERENT: {', '.join(critical_diffs)}."
        )

    # ── Default → NERO ────────────────────────────────────────────────────
    return None, (
        f"Score {score} — classificazione incerta, revisione manuale."
    )


# ---------------------------------------------------------------------------
# Formattazione testo cella
# ---------------------------------------------------------------------------

def _format_cell_text(
    config_name: str,
    llm_result: dict,
    decision: bool | None,
    decision_reason: str,
    det_summary: list[str],
    all_config_names: list[str] | None = None,
) -> str:
    """
    Struttura della cella in tre sezioni:

    SEZIONE 1 — Descrizione funzionale (sintesi in italiano)
    SEZIONE 2 — Confronto con altre configurazioni (riepilogo leggibile)
    SEZIONE 3 — Dettaglio tecnico (checklist, diff. parametriche, score)
    """
    lines = []
    n_configs = len(all_config_names) if all_config_names else 0

    sintesi_map     = llm_result.get("sintesi", {})
    riepilogo_map   = llm_result.get("riepilogo_confronto", {})
    checklist       = llm_result.get("checklist", {})
    tech_diffs      = llm_result.get("technical_differences", [])
    score           = llm_result.get("score")
    motivazione     = llm_result.get("motivazione", "").strip()

    # ── SEZIONE 1: Descrizione funzionale ────────────────────────────────
    sintesi = sintesi_map.get(config_name, "").strip()
    if sintesi:
        lines.append(sintesi)

    # ── SEZIONE 2: Confronto leggibile ───────────────────────────────────
    riepilogo = riepilogo_map.get(config_name, "").strip()
    if riepilogo and n_configs > 1:
        lines.append("\nCONFRONTO CON ALTRE CONFIGURAZIONI:")
        lines.append(riepilogo)
    elif n_configs <= 1:
        lines.append("\nUnica configurazione — nessun confronto effettuato.")

    # ── SEZIONE 3: Dettaglio tecnico ─────────────────────────────────────

    # Checklist (solo categorie non NULL)
    checklist_lines = [
        f"  • {_CHECKLIST_LABELS.get(k, k)}: {v}"
        for k, v in checklist.items()
        if v != "NULL"
    ]
    if checklist_lines:
        lines.append("\nANALISI FUNZIONALE:")
        lines.extend(checklist_lines)

    # Differenze tecniche (normalizzate a stringa)
    if tech_diffs:
        lines.append("\nDIFFERENZE FUNZIONALI RILEVATE:")
        for d in tech_diffs:
            lines.append(f"  • {_diff_to_str(d)}")

    # Differenze parametriche oggettive
    functional_det = [
        d for d in det_summary
        if any(kw in d.lower() for kw in [
            "parametri numerici", "timer", "stati operativi"
        ])
    ]
    if functional_det:
        lines.append("\nDIFFERENZE PARAMETRICHE (rilevate automaticamente):")
        for d in functional_det[:4]:
            lines.append(f"  • {d}")

    # Motivazione (se diversa dal riepilogo)
    if motivazione and motivazione != riepilogo:
        lines.append(f"\nNota: {motivazione}")

    # Nota incerto
    if decision is None and n_configs > 1:
        lines.append("\n⚪ Caso non classificabile: revisione manuale raccomandata.")

    # Score
    if score is not None and n_configs > 1:
        lines.append(f"Score equivalenza funzionale: {score}/100")

    return "\n".join(lines) if lines else "[Sintesi non disponibile]"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log_decision(
    config_name: str,
    checklist: dict,
    score: int | None,
    decision: bool | None,
    reason: str,
    tech_diffs: list,
    det_summary: list[str],
) -> None:
    sep = "─" * 55
    decision_label = (
        "🔴 NON EQUIVALENTE"   if decision is True  else
        "🟢 EQUIVALENTE"       if decision is False else
        "⚫ NON CLASSIFICABILE"
    )
    log.info(sep)
    log.info(f"  CONFIG      : {config_name}")
    log.info(f"  SCORE       : {score}/100")
    log.info(f"  DECISIONE   : {decision_label}")
    log.info(f"  MOTIVAZIONE : {reason}")
    if checklist:
        log.info("  CHECKLIST   :")
        for k, v in checklist.items():
            if v != "NULL":
                log.info(f"    {_CHECKLIST_LABELS.get(k, k):<30}: {v}")
    if tech_diffs:
        log.info("  DIFF FUNZIONALI:")
        for d in tech_diffs[:3]:
            log.info(f"    • {_diff_to_str(d)}")
    if det_summary:
        log.info("  DIFF PARAMETRICHE:")
        for d in det_summary[:3]:
            log.info(f"    • {d}")
    log.info(sep)


# ---------------------------------------------------------------------------
# Cache e API pubblica
# ---------------------------------------------------------------------------

_group_cache: dict[tuple[str, str], dict] = {}


def synthesize_with_comparison(
    func_id: str,
    func_desc: str,
    doc_id: str,
    config_name: str,
    page_number: int,
    page_text: str,
    all_config_texts: list[ConfigText],
    parsed_list: list[ParsedFunction] | None = None,
    det_report: dict | None = None,
) -> SynthesisResult:
    """
    Punto di ingresso principale.
    Una sola chiamata Ollama per gruppo; risultato in cache per le altre config.
    """
    if not page_text.strip():
        return SynthesisResult(
            text="[Testo non disponibile nel documento per questa pagina]",
            has_differences=None,
        )

    if det_report is None:
        det_report = {"any_objective_differences": False, "all_differences_summary": []}

    det_summary = det_report.get("all_differences_summary", [])
    valid_texts = [ct for ct in all_config_texts if ct.text.strip()]

    # ── Unica configurazione ──────────────────────────────────────────────
    if len(valid_texts) <= 1:
        log.info(f"  [{config_name}] Unica configurazione — sintesi semplice")
        llm_result = _default_single_result(config_name, page_text)
        cell_text  = _format_cell_text(
            config_name, llm_result, None, "", [],
            all_config_names=[config_name],
        )
        return SynthesisResult(text=cell_text, has_differences=None)

    # ── Cache / chiamata Ollama ───────────────────────────────────────────
    cache_key = (func_id, doc_id)
    if cache_key not in _group_cache:
        log.info(
            f"  Ollama: analisi gruppo {func_id} "
            f"({len(valid_texts)} config)..."
        )
        llm_result = _ask_ollama_group(
            func_id, func_desc, doc_id, valid_texts, det_summary
        )
        _group_cache[cache_key] = llm_result
        log.info(
            f"  ✅ Cache — score={llm_result.get('score')}, "
            f"equivalenti={llm_result.get('equivalenti')}"
        )
    else:
        llm_result = _group_cache[cache_key]
        log.info(f"  [{config_name}] Da cache (score={llm_result.get('score')})")

    # ── Decisione finale ──────────────────────────────────────────────────
    decision, reason = final_decision(det_report, llm_result)

    checklist = llm_result.get("checklist", {})
    score     = llm_result.get("score")

    _log_decision(
        config_name, checklist, score, decision, reason,
        llm_result.get("technical_differences", []), det_summary,
    )

    all_names = [ct.config_name for ct in valid_texts]
    cell_text = _format_cell_text(
        config_name, llm_result, decision, reason, det_summary,
        all_config_names=all_names,
    )

    return SynthesisResult(
        text=cell_text,
        has_differences=decision,
        uncertain=(decision is None),
        checklist=checklist,
        score=score,
        technical_differences=llm_result.get("technical_differences", []),
        editorial_differences=llm_result.get("editorial_differences", []),
        det_summary=det_summary,
    )


def synthesize(
    func_id: str,
    func_desc: str,
    doc_id: str,
    config_name: str,
    page_number: int,
    page_text: str,
) -> str:
    """Versione semplificata senza confronto (compatibilità)."""
    first_lines = " ".join(
        line.strip() for line in page_text.splitlines()
        if len(line.strip()) > 20
    )[:400]
    return first_lines or "[Testo disponibile nel documento]"