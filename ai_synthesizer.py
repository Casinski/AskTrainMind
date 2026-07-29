"""
ai_synthesizer.py
-----------------
Pipeline di valutazione semantica — versione semplificata.

LOGICA:
  1. UNA sola chiamata Ollama per gruppo di configurazioni.
  2. Il LLM produce:
       - descrizione: cosa fa la funzione (2-3 frasi, italiano)
       - differenze:  lista di differenze reali tra configurazioni (vuota se nessuna)
       - score:       0-100 (equivalenza funzionale)
  3. Decisione colore basata solo sullo score:
       score >= 80  → VERDE  (equivalenti)
       score <  60  → ROSSO  (differenze funzionali reali)
       60 <= score < 80 → NERO (incerto, revisione manuale)

TESTO CELLA (diretto e leggibile):
  [Descrizione funzione]
  [Se ci sono differenze: elenco puntato delle differenze]
  [Se nessuna differenza: riga verde di conferma]
  [Pagine di riferimento]
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
    technical_differences: list = field(default_factory=list)
    editorial_differences: list = field(default_factory=list)
    det_summary: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prerequisiti Ollama
# ---------------------------------------------------------------------------

def check_ollama() -> bool:
    try:
        import ollama
        models    = ollama.list()
        available = [m.model for m in models.models]
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
            options={"temperature": 0.0},
        )
        return response["message"]["content"].strip()
    except Exception as exc:
        log.error(f"  Errore Ollama: {exc}")
        return f"[Errore AI: {exc}]"


# ---------------------------------------------------------------------------
# Soglie (modificabili in config.py)
# ---------------------------------------------------------------------------

_SCORE_GREEN:  int = getattr(cfg, "LLM_SCORE_GREEN",  80)   # >= verde
_SCORE_RED:    int = getattr(cfg, "LLM_SCORE_RED",    60)   # <  rosso


# ---------------------------------------------------------------------------
# Prompt unico per gruppo
# ---------------------------------------------------------------------------

def _ask_ollama_group(
    func_id: str,
    func_desc: str,
    valid_texts: list[ConfigText],
    det_hints: list[str],
) -> dict:
    """
    Chiama Ollama UNA SOLA VOLTA per tutto il gruppo.

    Produce:
      - descrizione: cosa fa la funzione (2-3 frasi, valida per tutte le config)
      - differenze:  lista di differenze funzionali/prestazionali reali
                     tra le configurazioni (vuota se equivalenti)
      - score:       0-100
      - config_note: dict {config_name: nota specifica se diversa dalle altre}
    """
    all_names = [ct.config_name for ct in valid_texts]

    # Sezione testi
    testi = ""
    for ct in valid_texts:
        # Tronca il testo a 3000 caratteri per non saturare il context window
        testo = ct.text[:3000]
        testi += f"\n--- [{ct.config_name}] ---\n{testo}\n"

    # Hint deterministici (valori numerici diversi già trovati)
    hint_str = ""
    if det_hints:
        hint_str = (
            "\nVALORI NUMERICI POTENZIALMENTE DIVERSI (verifica se funzionalmente rilevanti):\n"
            + "\n".join(f"  • {h}" for h in det_hints[:6])
            + "\n"
        )

    config_note_template = "\n".join(
        f'    "{n}": "nota specifica su questa config, oppure stringa vuota se identica alle altre"'
        for n in all_names
    )

    prompt = (
        f"Sei un tecnico ferroviario esperto di sistemi ETR1000.\n"
        f"Analizza la funzione '{func_id}' ({func_desc}) nelle seguenti configurazioni di treno.\n\n"
        f"CONFIGURAZIONI: {all_names}\n"
        f"{hint_str}\n"
        f"TESTI TECNICI:\n{testi}\n\n"
        "ISTRUZIONI:\n"
        "1. Scrivi una DESCRIZIONE della funzione in italiano (2-3 frasi), valida per tutte le config.\n"
        "   Spiega cosa fa la funzione a livello di macrofunzione (logica, condizioni, comportamento in guasto).\n"
        "2. Elenca le DIFFERENZE funzionali e prestazionali REALI tra le configurazioni.\n"
        "   Una differenza è reale se cambia soprattutto la logica operativa, ma anche le soglie numeriche,\n"
        "   oppure il comportamento in guasto o eventualmente la diagnostica associata ai segnali.\n"
        "   NON sono differenze reali: codici documento diversi, nomi requisiti diversi,\n"
        "   stessa funzione descritta con parole diverse.\n"
        "3. Assegna uno score 0-100: 100=identiche, 0=completamente diverse.\n"
        "   Usa score >= 80 se le differenze sono solo formali o assenti.\n"
        "   Usa score < 60 solo per differenze funzionali/prestazionali concrete.\n"
        "4. Per ogni config indica una nota specifica se si comporta diversamente dalle altre.\n\n"
        "Rispondi SOLO con questo JSON (nessun testo prima o dopo):\n"
        "{\n"
        '  "descrizione": "Descrizione funzionale valida per tutte le configurazioni...",\n'
        '  "differenze": [\n'
        '    "VZI_Base ha soglia 750 kPa, VZ_FR ha soglia 800 kPa",\n'
        '    "VZI_ES non implementa il timeout di 35s presente nelle altre config"\n'
        "  ],\n"
        '  "score": 85,\n'
        '  "config_note": {\n'
        f"{config_note_template}\n"
        "  }\n"
        "}"
    )

    raw = _call_ollama(prompt)
    log.debug(f"  [LLM raw] {raw[:400]}")

    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            # Sanity
            data.setdefault("descrizione", "")
            data.setdefault("differenze", [])
            data.setdefault("score", 50)
            data.setdefault("config_note", {})

            score = data["score"]
            if not isinstance(score, (int, float)) or not (0 <= score <= 100):
                data["score"] = 50

            # Normalizza config_note
            for n in all_names:
                data["config_note"].setdefault(n, "")

            return data

    except (json.JSONDecodeError, AttributeError) as exc:
        log.warning(f"  Parsing LLM fallito: {exc} — raw: {raw[:200]}")

    # Fallback incerto
    return {
        "descrizione": "Analisi non disponibile.",
        "differenze": [],
        "score": 50,
        "config_note": {n: "" for n in all_names},
    }


# ---------------------------------------------------------------------------
# Decisione colore
# ---------------------------------------------------------------------------

def _decide(score: int, n_configs: int) -> bool | None:
    """
    Regola semplice basata solo sullo score LLM:
      score >= SCORE_GREEN (80) → False  = VERDE
      score <  SCORE_RED   (60) → True   = ROSSO
      altrimenti               → None   = NERO
    Unica configurazione → sempre NERO (nessun confronto possibile).
    """
    if n_configs <= 1:
        return None
    if score >= _SCORE_GREEN:
        return False
    if score < _SCORE_RED:
        return True
    return None


# ---------------------------------------------------------------------------
# Formattazione testo cella
# ---------------------------------------------------------------------------

def _format_cell(
    config_name: str,
    llm: dict,
    decision: bool | None,
    n_configs: int,
    det_hints: list[str],
) -> str:
    """
    Testo cella diretto e leggibile:

      [Descrizione funzionale — 2-3 frasi]

      [Se differenze:]
      Differenze rilevate:
        • ...
        • ...
      Questa configurazione: [nota specifica se presente]

      [Se nessuna differenza:]
      Tutte le configurazioni implementano questa funzione in modo equivalente.

      [Nota parametrica se ci sono hint deterministici rilevanti]

      Score equivalenza: XX/100
    """
    parts = []

    descrizione = llm.get("descrizione", "").strip()
    if descrizione:
        parts.append(descrizione)

    differenze  = llm.get("differenze", [])
    config_note = llm.get("config_note", {})
    nota        = config_note.get(config_name, "").strip()
    score       = llm.get("score", 50)

    if n_configs <= 1:
        parts.append("\nUnica configurazione disponibile.")
    elif differenze:
        parts.append("\nDifferenze tra configurazioni:")
        for d in differenze:
            parts.append(f"  • {d}")
        if nota:
            parts.append(f"\nQuesta configurazione ({config_name}): {nota}")
    else:
        parts.append(
            "\nTutte le configurazioni implementano questa funzione "
            "in modo equivalente."
        )
        if nota:
            parts.append(f"Nota ({config_name}): {nota}")

    # Hint deterministici solo se ci sono differenze reali (non inquinare celle verdi)
    if det_hints and decision is True:
        rilevanti = [h for h in det_hints if any(
            kw in h.lower() for kw in ["kpa", "km/h", "kv", "ms", "timeout", "timer"]
        )]
        if rilevanti:
            parts.append("\nValori parametrici diversi rilevati:")
            for h in rilevanti[:3]:
                parts.append(f"  • {h}")

    if decision is None and n_configs > 1:
        parts.append("\n⚪ Caso borderline — revisione manuale raccomandata.")

    if n_configs > 1:
        parts.append(f"\nScore equivalenza: {score}/100")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log_result(
    config_name: str,
    score: int,
    decision: bool | None,
    differenze: list,
) -> None:
    label = (
        "🟢 VERDE"  if decision is False else
        "🔴 ROSSO"  if decision is True  else
        "⚫ NERO"
    )
    log.info(f"  [{config_name}] {label} | score={score} | diff={len(differenze)}")


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
    Una sola chiamata Ollama per gruppo; cache per le config successive.
    """
    if not page_text.strip():
        return SynthesisResult(
            text="[Testo non disponibile per questa pagina]",
            has_differences=None,
        )

    if det_report is None:
        det_report = {"any_objective_differences": False, "all_differences_summary": []}

    # De-duplica hints deterministici (le coppie pairwise duplicano le voci)
    seen: set[str] = set()
    det_hints: list[str] = []
    for item in det_report.get("all_differences_summary", []):
        if item not in seen:
            seen.add(item)
            det_hints.append(item)

    valid_texts = [ct for ct in all_config_texts if ct.text.strip()]
    n_configs   = len(valid_texts)

    # ── Unica configurazione ──────────────────────────────────────────────
    if n_configs <= 1:
        log.info(f"  [{config_name}] Unica configurazione")
        # Usa il LLM solo per la descrizione, nessun confronto
        llm = _ask_ollama_group(func_id, func_desc, valid_texts, [])
        cell = _format_cell(config_name, llm, None, 1, [])
        return SynthesisResult(text=cell, has_differences=None, score=llm.get("score"))

    # ── Cache / chiamata Ollama ───────────────────────────────────────────
    cache_key = (func_id, doc_id)
    if cache_key not in _group_cache:
        log.info(f"  Ollama: analisi '{func_id}' ({n_configs} config)...")
        llm = _ask_ollama_group(func_id, func_desc, valid_texts, det_hints)
        _group_cache[cache_key] = llm
        log.info(
            f"  ✅ Cache — score={llm.get('score')} "
            f"diff={len(llm.get('differenze', []))}"
        )
    else:
        llm = _group_cache[cache_key]
        log.info(f"  [{config_name}] Da cache (score={llm.get('score')})")

    score    = llm.get("score", 50)
    decision = _decide(score, n_configs)
    cell     = _format_cell(config_name, llm, decision, n_configs, det_hints)

    _log_result(config_name, score, decision, llm.get("differenze", []))

    return SynthesisResult(
        text=cell,
        has_differences=decision,
        uncertain=(decision is None),
        score=score,
        technical_differences=llm.get("differenze", []),
        det_summary=det_hints,
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