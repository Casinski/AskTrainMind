"""
func_ai_comparator.py
---------------------
Confronto del TESTO DI UNA FUNZIONE fra VZI_Base e le altre
configurazioni. Replica la logica di req_ai_comparator.py, dove al posto
del singolo requisito c'e' l'intera sezione del documento.

GERARCHIA REQUISITI → FUNZIONE
  Una funzione contiene il testo discorsivo E le tabelle dei requisiti.
  Se tutti i requisiti sono MATCHED, la funzione non puo' avere
  differenze sostanziali: l'esito dei requisiti, gia' calcolato prima
  nella pipeline, viene riusato come scorciatoia e risparmia la chiamata
  al modello. Viceversa, se i requisiti divergono, la funzione non puo'
  essere dichiarata MATCHED.
"""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher

import config as cfg
from ai_synthesizer import _call_ollama

log = logging.getLogger(__name__)

_cache: dict[tuple, tuple[bool, str]] = {}

_BASE = getattr(cfg, "REQ_BASE_CONFIG", "VZI_Base")
_SIM_MATCH = getattr(cfg, "FUNC_TEXT_SIMILARITY_MATCH", 0.95)
_SCORE_MATCH = getattr(cfg, "FUNC_LLM_SCORE_MATCH", 80)
_MAX_CHARS = getattr(cfg, "FUNC_DIFF_MAX_CHARS", 900)

_NO_DIFF_MARKERS = getattr(cfg, "REQ_NO_DIFF_MARKERS", [
    "identic", "identich", "nessuna differenza", "non sono differenze",
    "equivalent", "coincidono", "uguali", "stessa logica", "no difference",
])

_DIFF_MARKERS_RE = re.compile(
    r"\b(invece|mentre|divers[aeio]|differisce|different[ei]|"
    r"a differenza|non presente|assente|manca|aggiunt\w*|rimoss\w*|"
    r"solo in|presente solo|soglia divers\w*|valore divers\w*|anziche)\b"
)


# ---------------------------------------------------------------------------
# Normalizzazione del testo di sezione
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def norm_section(s: str) -> str:
    """
    Normalizzazione del testo di una sezione.

    Si rimuove tutto cio' che varia fra documenti senza essere una
    differenza funzionale: marcatori di pagina inseriti dal lettore,
    codici documento, numeri di revisione, intestazioni ripetute.
    Senza questa pulizia due sezioni identiche risultano sempre diverse,
    perche' ogni PDF porta il proprio codice e la propria revisione.
    """
    t = s or ""
    t = re.sub(r"\[Pagina\s+\d+\]", " ", t)
    t = re.sub(r"\b3[A-Z]{2,4}\d{6}-\d{4}\b", " ", t)      # codice documento
    t = re.sub(r"\bRevision\s*:?\s*[A-Z0-9]\b", " ", t, flags=re.I)
    t = re.sub(r"\bPage\s*:?\s*\d+\b", " ", t, flags=re.I)
    t = re.sub(r"\bDocument state\s*:?\s*\w+\b", " ", t, flags=re.I)
    t = _norm(t)
    t = re.sub(r"[^\w\s%./-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def text_similarity(a: str, b: str) -> float:
    """Similarita' 0.0-1.0 fra i testi di due sezioni."""
    na, nb = norm_section(a), norm_section(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def identical(texts: list[str]) -> bool:
    """True se tutte le sezioni sono equivalenti a due a due."""
    if len(texts) <= 1:
        return True
    if len({norm_section(t) for t in texts}) <= 1:
        return True
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if text_similarity(texts[i], texts[j]) < _SIM_MATCH:
                return False
    return True


def _is_no_diff_text(diff: str) -> bool:
    """True se il testo del modello non descrive differenze reali."""
    t = _norm(diff)
    if not t:
        return True
    if _DIFF_MARKERS_RE.search(t):
        return False
    frasi = [f.strip() for f in re.split(r"[.;\n]+", t) if f.strip()]
    if not frasi:
        return True
    return all(
        any(mk in f for mk in _NO_DIFF_MARKERS) or len(f) < 12 for f in frasi
    )


# ---------------------------------------------------------------------------
# Differenze testuali leggibili
# ---------------------------------------------------------------------------

def describe_text_diff(base_txt: str, base_name: str,
                       other_txt: str, other_name: str) -> str:
    """
    Paragrafo discorsivo sui frammenti realmente divergenti.
    Integra il responso del modello quando resta generico.
    """
    a = norm_section(base_txt).split()
    b = norm_section(other_txt).split()
    if not a or not b:
        return ""

    frasi = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        sa = " ".join(a[i1:i2]).strip()[:180]
        sb = " ".join(b[j1:j2]).strip()[:180]
        if len(sa) < 8 and len(sb) < 8:
            continue
        if tag == "replace":
            frasi.append(f"dove {base_name} riporta «{sa}», "
                         f"{other_name} riporta «{sb}»")
        elif tag == "delete":
            frasi.append(f"il passaggio «{sa}», presente in {base_name}, "
                         f"non compare in {other_name}")
        elif tag == "insert":
            frasi.append(f"{other_name} aggiunge «{sb}», "
                         f"assente in {base_name}")
        if len(frasi) >= 3:
            break

    if not frasi:
        return ""
    corpo = frasi[0] if len(frasi) == 1 else \
        "; ".join(frasi[:-1]) + f"; infine {frasi[-1]}"
    return ("Differenze nel testo della sezione: confrontando i due "
            f"documenti si osserva che {corpo}.")


# ---------------------------------------------------------------------------
# API principale
# ---------------------------------------------------------------------------

def compare(func_id: str, func_desc: str,
            base_name: str, base_txt: str,
            other_name: str, other_txt: str,
            req_verdict: dict | None = None) -> tuple[bool, str]:
    """
    Confronta il testo della funzione fra due configurazioni.

    req_verdict: esito del foglio Requisiti per questa funzione,
    prodotto da RequisitiWriter.last_verdict. Se tutti i requisiti sono
    MATCHED, la funzione e' MATCHED senza chiamare il modello.
    """
    # ── Scorciatoia gerarchica: l'esito dei requisiti comanda ────────────
    if req_verdict and getattr(cfg, "FUNC_USE_REQ_VERDICT", True):
        if req_verdict.get("all_matched"):
            log.info(
                f"  [FuncAI] {func_id} | {other_name}: tutti i "
                f"{req_verdict.get('n_req')} requisiti MATCHED → "
                f"funzione MATCHED senza LLM"
            )
            return True, ""

    d_base, d_other = norm_section(base_txt), norm_section(other_txt)

    if d_base and d_base == d_other:
        return True, ""

    if not d_base or not d_other:
        if not d_base and not d_other:
            return True, ""
        mancante = base_name if not d_base else other_name
        return False, (f"Testo della sezione non estratto per {mancante}: "
                       f"confronto non possibile, verifica manuale.")

    sim = text_similarity(base_txt, other_txt)
    if sim >= _SIM_MATCH:
        # Se pero' i requisiti divergono, la funzione non puo' essere
        # MATCHED: la differenza sta dentro le tabelle.
        if (req_verdict and getattr(cfg, "FUNC_REQ_DIFF_FORCES_DIFF", True)
                and other_name in (req_verdict.get("configs_diff") or [])):
            return False, (
                f"Il testo discorsivo coincide con {base_name} "
                f"(corrispondenza {sim:.0%}), ma nel foglio Requisiti "
                f"{other_name} presenta requisiti divergenti: la differenza "
                f"e' interna alle tabelle, non al testo della sezione."
            )
        return True, ""

    key = (func_id.lower(), base_name, other_name)
    if key in _cache:
        return _cache[key]

    prompt = (
        "Sei un tecnico ferroviario esperto di sistemi ETR1000.\n"
        f"Confronta la STESSA funzione '{func_id}' ({func_desc}) come e' "
        "descritta in due configurazioni di treno.\n\n"
        f"--- [{base_name}] ---\n{base_txt[:3500]}\n\n"
        f"--- [{other_name}] ---\n{other_txt[:3500]}\n\n"
        "REGOLE DI CONFRONTO\n"
        "1. Confronta la PRESCRIZIONE TECNICA: logica operativa, "
        "condizioni di attivazione, soglie e tempi, comportamento in "
        "guasto, diagnostica, livello di sicurezza.\n"
        "2. NON sono differenze: riformulazioni della stessa prescrizione, "
        "codici di documento, numeri di revisione, numerazione delle "
        "sezioni, identificativi dei requisiti diversi, nomi delle colonne "
        "delle tabelle, impaginazione.\n"
        "3. Se NON trovi differenze secondo la regola 1, il campo "
        "'differenze' deve essere ESATTAMENTE la stringa vuota \"\". "
        "NON elencare cio' che e' uguale.\n"
        "4. Se trovi differenze, scrivi un BREVE PARAGRAFO DISCORSIVO in "
        "italiano (3-5 frasi) che dica: cosa prescrive la funzione in "
        f"{base_name}, in che cosa se ne discosta {other_name}, e quale "
        "conseguenza pratica ha la differenza sul comportamento del treno.\n"
        "5. score 0-100: 100 = stessa funzione, 0 = funzioni diverse.\n\n"
        'Rispondi SOLO con questo JSON:\n{"score": 95, "differenze": ""}'
    )

    raw = _call_ollama(prompt)
    score, diff = 50, ""
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            try:
                score = int(float(data.get("score", 50)))
            except (TypeError, ValueError):
                score = 50
            if not 0 <= score <= 100:
                score = 50
            diff = (data.get("differenze") or "").strip()
    except Exception as exc:
        log.warning(f"  [FuncAI] parsing fallito su {func_id}: {exc}")

    if diff and _is_no_diff_text(diff):
        log.info(f"  [FuncAI] {func_id} | {other_name}: nessuna differenza "
                 f"reale nel testo del modello → MATCHED")
        diff = ""

    is_match = (not diff) and score >= _SCORE_MATCH

    # I requisiti divergenti hanno la precedenza sul verdetto del modello
    if (is_match and req_verdict
            and getattr(cfg, "FUNC_REQ_DIFF_FORCES_DIFF", True)
            and other_name in (req_verdict.get("configs_diff") or [])):
        is_match = False
        diff = (f"Il testo della sezione risulta equivalente a {base_name}, "
                f"ma nel foglio Requisiti {other_name} presenta requisiti "
                f"divergenti: vedere le righe di dettaglio.")

    if not is_match:
        dettaglio = describe_text_diff(base_txt, base_name,
                                       other_txt, other_name)
        if not diff:
            diff = (f"Il testo della funzione in {other_name} non coincide "
                    f"con quello di {base_name} "
                    f"(corrispondenza {sim:.0%}, score {score}/100).")
        if dettaglio:
            diff = f"{diff}\n\n{dettaglio}"
        if len(diff) > _MAX_CHARS:
            diff = diff[:_MAX_CHARS].rsplit(" ", 1)[0] + " […]"

    log.info(
        f"  [FuncAI] {func_id} | {base_name} vs {other_name} | "
        f"sim={sim:.2f} score={score} | {'MATCHED' if is_match else 'DIFF'}"
    )

    out = (is_match, "" if is_match else diff)
    _cache[key] = out
    return out


def clear_cache() -> None:
    _cache.clear()