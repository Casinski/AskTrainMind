"""
ai_synthesizer.py
-----------------
Pipeline di valutazione semantica (Fasi 3-6).

VERSIONE AGGIORNATA:
  - Prompt LLM focalizzato su comportamento funzionale, prestazionale
    e in caso di guasto — NON sui codici documento o requisiti.
  - Soglie decisionali più permissive: piccole diff. non critiche → incerto (nero).
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

# Tutte le categorie sono critiche — ma solo queste 6 (no HW/SW/req codes)
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
    Focalizzata su: scopo funzionale, logica operativa, prestazioni,
    comportamento in guasto, diagnostica, sicurezza.
    NON valuta: codici documento, codici requisito, nomi segnale.
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
        f'    "{ct.config_name}": "sintesi funzionale in italiano (max 3 frasi)"'
        for ct in valid_texts
    )

    prompt = (
        "Sei un revisore tecnico ferroviario senior, specializzato in sistemi ETR1000.\n\n"
        f"Funzione: {func_id} — {func_desc}\n"
        f"Documento: {doc_id}\n"
        f"Configurazioni da confrontare: {all_names}\n\n"

        "COSA DEVI VALUTARE — concentrati ESCLUSIVAMENTE su:\n"
        "  1. Scopo funzionale: la funzione fa la stessa cosa in tutte le configurazioni?\n"
        "  2. Logica operativa: le condizioni di attivazione/disattivazione sono equivalenti?\n"
        "  3. Prestazioni: soglie, valori numerici, tempi di risposta sono equivalenti?\n"
        "  4. Comportamento in guasto: la funzione reagisce allo stesso modo in caso di errore?\n"
        "  5. Diagnostica: le funzioni di diagnostica e i messaggi di errore sono equivalenti?\n"
        "  6. Sicurezza: i requisiti safety e i fallback sono equivalenti?\n\n"

        "COSA NON DEVI VALUTARE (ignora completamente):\n"
        "  - Codici documento (es. 3ECP413571, FA020023100) — sono sempre diversi per configurazione\n"
        "  - ID requisiti (es. REQ-001, SRS-042) — i codici cambiano, conta il contenuto\n"
        "  - Numeri di revisione o versione del documento\n"
        "  - Nomi di segnali interni o variabili software specifiche\n"
        "  - Differenze di formattazione o stile del testo\n\n"

        "QUANDO dichiarare DIFFERENT (differenza tecnica reale):\n"
        "  - La funzione si attiva in condizioni diverse\n"
        "  - I valori di soglia o i tempi di risposta differiscono in modo significativo\n"
        "  - Il comportamento in guasto porta a stati diversi\n"
        "  - La diagnostica rileva o segnala eventi diversi\n"
        "  - I requisiti di sicurezza impongono vincoli diversi\n\n"

        "QUANDO dichiarare IDENTICAL:\n"
        "  - Il comportamento descritto è lo stesso anche se espresso con parole diverse\n"
        "  - I valori numerici sono gli stessi o equivalenti (es. stessa soglia)\n"
        "  - La logica operativa porta agli stessi stati nelle stesse condizioni\n\n"

        f"{det_note}"
        f"Testi tecnici completi:\n{configs_section}\n\n"

        "Per ciascuna delle 6 categorie:\n"
        "  IDENTICAL → comportamento equivalente in tutte le configurazioni\n"
        "  DIFFERENT → differenza funzionale reale tra almeno due configurazioni\n"
        "  NULL      → categoria non trattata in nessuna configurazione\n\n"

        "Score equivalenza funzionale: 0 (completamente diverse) → 100 (identiche).\n"
        "Considera equivalenti (score ≥ 75) se le differenze sono solo formali.\n"
        "Considera NON equivalenti (score < 75) solo per differenze funzionali reali.\n\n"

        "Rispondi ESCLUSIVAMENTE con questo JSON (nessun testo prima o dopo):\n"
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
        '  "editorial_differences": ["eventuale diff. solo formale"],\n'
        '  "sintesi": {\n'
        f"{sintesi_keys}\n"
        "  },\n"
        '  "motivazione": "Spiegazione in italiano (max 2 frasi) del perché sono equivalenti o diverse"\n'
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
            data.setdefault("motivazione", "")

            return data

    except (json.JSONDecodeError, AttributeError) as exc:
        log.warning(
            f"  Risposta Ollama non parsabile: {exc}\n"
            f"  Risposta: {raw[:300]}\n"
            "  Fallback: NON equivalente."
        )

    return _default_non_equivalent_result(all_names)


def _default_non_equivalent_result(names: list[str]) -> dict:
    return {
        "equivalenti": False,
        "score": 0,
        "checklist": {k: "NULL" for k in _CHECKLIST_KEYS},
        "technical_differences": ["Errore parsing LLM — classificato NON equivalente per sicurezza"],
        "editorial_differences": [],
        "sintesi": {n: "" for n in names},
        "motivazione": "Errore nell'analisi LLM.",
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
        "motivazione": "Unica configurazione — nessun confronto effettuato.",
    }


# ---------------------------------------------------------------------------
# Fase 5 — Decisione finale ibrida
# ---------------------------------------------------------------------------

def final_decision(
    det_report: dict,
    llm_result: dict,
) -> tuple[bool | None, str]:
    """
    Decisione finale basata su:
      1. Differenze funzionali oggettive (parametri numerici, timer, stati)
      2. Checklist LLM sulle 6 categorie funzionali
      3. Score LLM

    NON penalizza differenze su codici documento o requisiti.
    """
    checklist  = llm_result.get("checklist", {})
    score      = llm_result.get("score", 50)
    tech_diffs = llm_result.get("technical_differences", [])
    det_diffs  = det_report.get("all_differences_summary", [])

    # ── Differenze oggettive su parametri funzionali ──────────────────────
    # Solo timer e parametri numerici contano (non codici o signal names)
    functional_det_diffs = [
        d for d in det_diffs
        if any(kw in d.lower() for kw in [
            "parametri numerici", "timer", "timeout", "stati operativi"
        ])
    ]
    if len(functional_det_diffs) >= 3:
        # Almeno 3 differenze funzionali oggettive → ROSSO
        return True, (
            f"Differenze funzionali oggettive ({len(functional_det_diffs)} voci): "
            f"{functional_det_diffs[0]}"
        )

    # ── Categorie critiche DIFFERENT da LLM ──────────────────────────────
    critical_diffs = [k for k in _CRITICAL_KEYS if checklist.get(k) == "DIFFERENT"]

    if len(critical_diffs) >= 2:
        # Due o più categorie funzionali diverse → ROSSO
        return True, (
            f"LLM: differenze funzionali in {', '.join(critical_diffs)}. "
            f"Score: {score}."
        )

    if len(critical_diffs) == 1 and score < _SCORE_RED:
        # Una sola categoria diversa + score non alto → INCERTO (nero)
        return None, (
            f"LLM: differenza in '{critical_diffs[0]}', score {score} — "
            "caso borderline, revisione manuale raccomandata."
        )

    # ── Score basso con differenze tecniche segnalate ─────────────────────
    if score < _SCORE_YELLOW and tech_diffs:
        return True, f"Score basso ({score}) con differenze funzionali segnalate."

    # ── Score borderline senza differenze critiche → incerto ──────────────
    if _SCORE_YELLOW <= score < _SCORE_RED and tech_diffs:
        return None, (
            f"Score {score} con alcune diff. segnalate — "
            "non classificabile con certezza."
        )

    # ── Equivalente ───────────────────────────────────────────────────────
    if score >= _SCORE_RED:
        return False, f"Nessuna differenza funzionale rilevante. Score: {score}."

    return None, f"Caso borderline — score {score}."


# ---------------------------------------------------------------------------
# Formattazione testo cella
# ---------------------------------------------------------------------------

def _format_cell_text(
    config_name: str,
    llm_result: dict,
    decision: bool | None,
    decision_reason: str,
    det_summary: list[str],
) -> str:
    lines = []

    # Sintesi funzionale della configurazione corrente
    sintesi_map = llm_result.get("sintesi", {})
    sintesi = sintesi_map.get(config_name, "").strip()
    if sintesi:
        lines.append(sintesi)

    # Checklist (solo categorie non NULL)
    checklist = llm_result.get("checklist", {})
    checklist_lines = [
        f"  • {_CHECKLIST_LABELS.get(k, k)}: {v}"
        for k, v in checklist.items()
        if v != "NULL"
    ]
    if checklist_lines:
        lines.append("\nCONFRONTO FUNZIONALE:")
        lines.extend(checklist_lines)

    # Differenze tecniche funzionali (solo quelle reali, non codici)
    tech_diffs = llm_result.get("technical_differences", [])
    if tech_diffs:
        lines.append("\nDIFFERENZE FUNZIONALI:")
        for d in tech_diffs:
            lines.append(f"  • {d}")

    # Differenze numeriche/temporali oggettive (se presenti e rilevanti)
    functional_det = [
        d for d in det_summary
        if any(kw in d.lower() for kw in ["parametri numerici", "timer", "stati operativi"])
    ]
    if functional_det:
        lines.append("\nDIFFERENZE PARAMETRICHE (rilevate automaticamente):")
        for d in functional_det[:4]:
            lines.append(f"  • {d}")

    # Motivazione
    motivazione = llm_result.get("motivazione", "").strip()
    if motivazione:
        lines.append(f"\nAnalisi: {motivazione}")

    # Nota incerto
    if decision is None:
        lines.append("\n⚪ Non classificabile: revisione manuale raccomandata.")

    # Score
    score = llm_result.get("score")
    if score is not None:
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
    tech_diffs: list[str],
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
                log.info(f"    {_CHECKLIST_LABELS.get(k,k):<30}: {v}")
    if tech_diffs:
        log.info("  DIFF FUNZIONALI:")
        for d in tech_diffs[:3]:
            log.info(f"    • {d}")
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
        cell_text  = _format_cell_text(config_name, llm_result, None, "", [])
        return SynthesisResult(text=cell_text, has_differences=None)

    # ── Cache / chiamata Ollama ───────────────────────────────────────────
    cache_key = (func_id, doc_id)
    if cache_key not in _group_cache:
        log.info(
            f"  Ollama: analisi funzionale gruppo {func_id} "
            f"({len(valid_texts)} config in un unico prompt)..."
        )
        llm_result = _ask_ollama_group(
            func_id, func_desc, doc_id, valid_texts, det_summary
        )
        _group_cache[cache_key] = llm_result
        log.info(
            f"  ✅ Risultato in cache — "
            f"score={llm_result.get('score')}, "
            f"equivalenti={llm_result.get('equivalenti')}"
        )
    else:
        llm_result = _group_cache[cache_key]
        log.info(f"  [{config_name}] Da cache (score={llm_result.get('score')})")

    # ── Decisione finale ──────────────────────────────────────────────────
    decision, reason = final_decision(det_report, llm_result)

    checklist = llm_result.get("checklist", {})
    score     = llm_result.get("score")

    _log_decision(config_name, checklist, score, decision, reason,
                  llm_result.get("technical_differences", []), det_summary)

    cell_text = _format_cell_text(config_name, llm_result, decision, reason, det_summary)

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