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
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import config as cfg
from ai_synthesizer import _call_ollama, _chiudi_frase, _e_errore_ai, _token_budget
from llm_json import parse_json_relaxed

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


# ---------------------------------------------------------------------------
# Similarita' FUNZIONALE (cella "Funzioni AI" delle configurazioni ≠ base)
# ---------------------------------------------------------------------------
# Due funzioni sono analoghe se il loro SIGNIFICATO e' analogo: la sola
# somiglianza dei caratteri penalizza impaginazione, intestazioni di pagina,
# righe spezzate e tabelle riformattate, che non cambiano il funzionamento.
# La percentuale combina quindi:
#   • sequenza delle parole di contenuto (stesso discorso, stesso ordine)
#   • lessico di contenuto (stessi concetti, anche se riordinati)
#   • requisiti in comune (ID 2F_..., l'ancora funzionale piu' solida)
# e sottrae una PENALITA' per le differenze funzionali o d'impianto grandi:
#   • valori numerici con unita' cambiati (soglie, tempi, tensioni...)
#   • requisiti presenti in una sola configurazione
#   • sezioni con molto contenuto in piu' o in meno
#   • componenti/sigle d'impianto presenti in una sola configurazione
# Le differenze rilevanti vengono anche restituite come elenco leggibile,
# cosi' la cella le "marca" sotto la sigla di similarita'.

_BOILER_RE = re.compile("|".join(f"(?:{p})" for p in (
    r"this document and its contents", r"distribution, utilization",
    r"payment of damages", r"all rights reserved", r"^©",
    r"^document state\s*:?", r"^language\s*:?$", r"^revision\s*:?$",
    r"^page\s*:?$", r"^released$", r"^(?:en|it|_?[a-z])$",
    r"^vsi$", r"^progetto\s*:?$", r"^project\s*:?$",
    r"^titolo documento\s*:?$", r"^document title\s*:?$",
    r"^codice documento\s*:?$", r"^document code\s*:?$", r"^rev\.?\s*:?$",
    r"^pagina$", r"^di$", r"^of$", r"^\d{1,3}$", r"^etr\s?1000 vzi-?\d+$",
    r"^fa\d{6,}$", r"^3[a-z]{2,4}\d{6}-\d{4}$", r"^\[pagina \d+\]$",
    r"^vehicle functional$", r"^specification$",
)), re.I)

_REQ_ID_RE = re.compile(
    r"\b(\d[A-Z]_[\d.]+?)\.?\s*-?\s*Zefiro-?\s*Europe\s*\.\s*([A-Z]+)\s*\.\s*(\d+)",
    re.I)

_UNIT = (r"kv|vac|vdc|v|ka|ma|a|khz|hz|ms|sec|s|min|h|bar|kpa|mpa|°c|%|"
         r"km/h|kmh|m/s|mm|cm|m|kva|kw|w|kn|n|kg|rpm")
_UNIT_LABEL = {"kv": "kV", "vac": "Vac", "vdc": "Vdc", "v": "V", "ka": "kA",
               "ma": "mA", "a": "A", "khz": "kHz", "hz": "Hz", "kpa": "kPa",
               "mpa": "MPa", "°c": "°C", "kva": "kVA", "kw": "kW", "w": "W",
               "kn": "kN", "n": "N"}
_VALUE_RE = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(" + _UNIT + r")(?![\w/])", re.I)

_STOP = frozenset((
    "the a an and or of to in on for by with from at as is are be been shall "
    "should will can may must this that these those it its which when if then "
    "than not all any each other such into via per there their has have had "
    "was were also only both between within without under over during after "
    "before up down out off one two description safety level type derived "
    "requirement requirements interface user sil function design nr id"
).split())
_WORD_RE = re.compile(r"[a-z][a-z0-9_\-]{2,}")
_ACR_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)?\b")
# Sigle che non descrivono l'impianto: rimandi a hazard (HRnn), nomi di
# carrozza (DM1, M3, T2), connettivi logici, marcatori editoriali.
_ACR_NOISE_RE = re.compile(
    r"^(?:HR\d+|[A-Z]{1,2}\d{1,2}|SIL\d?|ID|TRS|CONCEPT|NA|OK|TBD|TBC|AND|OR|"
    r"NOT|XOR|DELETED|IF|THEN|ELSE|[A-Z]{1,3}\d{6,}\w*|FF\d+|VZ\w*|ETR\w*|"
    r"ON|OFF|OPEN|CLOSED|MASTER|SLAVE|KO|TRUE|FALSE|YES|NO|ITALY|FRANCE|"
    r"SPAIN|GERMANY|AUSTRIA|BELGIUM|NETHERLANDS|SWITZERLAND|NOTE|WARNING)$")


def _clean_lines(text: str) -> str:
    out = []
    for ln in (text or "").splitlines():
        s = re.sub(r"\s+", " ", ln).strip()
        if s and not _BOILER_RE.search(s):
            out.append(s)
    return "\n".join(out)


def _req_ids(text: str) -> set[str]:
    t = re.sub(r"-\s*\n\s*", "-", text or "")
    t = re.sub(r"\.\s*\n\s*", ".", t)
    return {f"{a}.{b.upper()}.{c}" for a, b, c in _REQ_ID_RE.findall(t)}


def _values(text: str) -> set[tuple[str, str]]:
    out = set()
    for num, unit in _VALUE_RE.findall(text or ""):
        u = unit.lower().replace("sec", "s").replace("kmh", "km/h")
        u = _UNIT_LABEL.get(u, u)
        try:
            out.add((f"{float(num.replace(',', '.')):g}", u))
        except ValueError:
            pass
    return out


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _content_tokens(text: str) -> list[str]:
    t = _REQ_ID_RE.sub(" ", text or "")
    return [_stem(w) for w in _WORD_RE.findall(t.lower()) if w not in _STOP]


def _components(text: str) -> set[str]:
    return {a for a in _ACR_RE.findall(text or "")
            if not _ACR_NOISE_RE.match(a)}


def _cosine(a: list[str], b: list[str]) -> float:
    ca, cb = Counter(a), Counter(b)
    num = sum(ca[k] * cb[k] for k in ca.keys() & cb.keys())
    den = (math.sqrt(sum(v * v for v in ca.values()))
           * math.sqrt(sum(v * v for v in cb.values())))
    return num / den if den else 0.0


@dataclass
class SimilarityReport:
    """Esito del confronto funzionale fra la base e un'altra configurazione."""
    pct: float                                   # 0-100, gia' penalizzata
    sequence: float = 0.0                        # 0-100
    content: float = 0.0                         # 0-100
    reqs_common: int = 0
    reqs_only_base: list[str] = field(default_factory=list)
    reqs_only_other: list[str] = field(default_factory=list)
    values_only_base: list[str] = field(default_factory=list)
    values_only_other: list[str] = field(default_factory=list)
    comps_only_base: list[str] = field(default_factory=list)
    comps_only_other: list[str] = field(default_factory=list)
    length_ratio: float = 1.0
    penalty: float = 0.0
    major: list[str] = field(default_factory=list)  # differenze rilevanti

    @property
    def has_major(self) -> bool:
        return bool(self.major)


def _fmt_vals(vals: list[str], n: int = 4) -> str:
    return ", ".join(vals[:n]) + (f" (+{len(vals) - n})" if len(vals) > n else "")


def functional_similarity(base_txt: str, other_txt: str,
                          base_name: str = "base",
                          other_name: str = "altra") -> SimilarityReport:
    """
    Similarita' 0-100 basata sul significato funzionale delle due sezioni
    e sulle differenze rilevanti (valori, requisiti, contenuto, impianto).
    """
    ca, cb = _clean_lines(base_txt), _clean_lines(other_txt)
    ta, tb = _content_tokens(ca), _content_tokens(cb)
    if not ta and not tb:
        return SimilarityReport(pct=100.0, sequence=100.0, content=100.0)
    if not ta or not tb:
        return SimilarityReport(pct=0.0, major=["contenuto assente in una "
                                                "delle due configurazioni"])

    seq = SequenceMatcher(None, ta, tb, autojunk=False).ratio()
    cos = _cosine(ta, tb)
    ra, rb = _req_ids(base_txt), _req_ids(other_txt)
    w = getattr(cfg, "FUNC_SIM_WEIGHTS", (0.45, 0.25, 0.30))
    parts = [(seq, w[0]), (cos, w[1])]
    if ra or rb:
        parts.append((len(ra & rb) / len(ra | rb), w[2]))
    score = 100.0 * sum(x * k for x, k in parts) / sum(k for _, k in parts)

    va, vb = _values(ca), _values(cb)
    only_va = sorted(f"{n} {u}" for n, u in va - vb)
    only_vb = sorted(f"{n} {u}" for n, u in vb - va)
    pa, pb = _components(ca), _components(cb)
    only_pa, only_pb = sorted(pa - pb), sorted(pb - pa)
    lr = min(len(ta), len(tb)) / max(len(ta), len(tb))

    rep = SimilarityReport(
        pct=score, sequence=seq * 100, content=cos * 100,
        reqs_common=len(ra & rb),
        reqs_only_base=sorted(ra - rb), reqs_only_other=sorted(rb - ra),
        values_only_base=only_va, values_only_other=only_vb,
        comps_only_base=only_pa, comps_only_other=only_pb,
        length_ratio=lr,
    )

    # ── Penalita' per differenze funzionali / d'impianto ────────────────
    p_val = getattr(cfg, "FUNC_SIM_PENALTY_VALUE", 3.0)
    p_req = getattr(cfg, "FUNC_SIM_PENALTY_REQ", 1.0)
    p_cmp = getattr(cfg, "FUNC_SIM_PENALTY_COMPONENT", 0.5)
    p_max = getattr(cfg, "FUNC_SIM_PENALTY_MAX", 30.0)
    n_val = len(set(only_va) | set(only_vb))
    n_req = len(rep.reqs_only_base) + len(rep.reqs_only_other)
    n_cmp = len(only_pa) + len(only_pb)
    rep.penalty = min(p_max, p_val * min(n_val, 6) + p_req * min(n_req, 10)
                      + p_cmp * min(n_cmp, 10)
                      + (10.0 if lr < 0.5 else 5.0 if lr < 0.7 else 0.0))

    # ── Differenze rilevanti, scritte in cella ───────────────────────────
    min_req = getattr(cfg, "FUNC_SIM_MAJOR_MIN_REQS", 2)
    min_cmp = getattr(cfg, "FUNC_SIM_MAJOR_MIN_COMPONENTS", 3)
    if only_va or only_vb:
        rep.major.append(
            "Valori/soglie diversi: "
            + (f"{base_name} {_fmt_vals(only_va)}" if only_va else "")
            + (" → " if only_va and only_vb else "")
            + (f"{other_name} {_fmt_vals(only_vb)}" if only_vb else ""))
    if n_req >= min_req:
        seg = []
        if rep.reqs_only_base:
            seg.append(f"{len(rep.reqs_only_base)} solo in {base_name}")
        if rep.reqs_only_other:
            seg.append(f"{len(rep.reqs_only_other)} solo in {other_name}")
        rep.major.append("Requisiti diversi: " + ", ".join(seg))
    if lr < 0.7:
        piu = other_name if len(tb) > len(ta) else base_name
        rep.major.append(f"Contenuto molto diverso: {piu} descrive la "
                         f"funzione con circa {round((1 / lr - 1) * 100)}% "
                         "di testo in piu'")
    if len(only_pa) + len(only_pb) >= min_cmp:
        seg = []
        if only_pa:
            seg.append(f"{base_name} {_fmt_vals(only_pa)}")
        if only_pb:
            seg.append(f"{other_name} {_fmt_vals(only_pb)}")
        rep.major.append("Componenti/sigle d'impianto diversi: "
                         + "; ".join(seg))

    pct = max(0.0, score - rep.penalty)
    # Con differenze rilevanti la funzione non puo' risultare "uguale":
    # resta sotto la soglia del verde grassetto.
    green = getattr(cfg, "FUNC_SIMILARITY_GREEN", 90.0)
    if rep.major and pct >= green:
        pct = green - 0.1
    rep.pct = round(pct, 3)
    return rep


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

    raw = _call_ollama(prompt, num_predict=_token_budget(900))
    score, diff = 50, ""
    rec = parse_json_relaxed(raw, campi_testo=("score", "differenze"))
    if rec:
        data = rec.data
        try:
            score = int(float(data.get("score", 50)))
        except (TypeError, ValueError):
            score = 50
        if not 0 <= score <= 100:
            score = 50
        diff = str(data.get("differenze") or "").strip()
        if rec.truncated and diff:
            diff = _chiudi_frase(diff)
            log.info(
                f"  [FuncAI] {func_id}: risposta troncata dal limite di "
                f"token — contenuto recuperato ({rec.method})"
            )
    elif not _e_errore_ai(raw):
        log.warning(
            f"  [FuncAI] risposta non interpretabile per {func_id}: "
            f"{raw[:200]!r}"
        )

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