"""
req_ai_comparator.py
--------------------
Confronto di UN requisito fra la configurazione di riferimento
(normalmente VZI_Base) e le altre configurazioni del treno.

API pubblica
    dump_fields(req, for_llm=False) -> str
        Campi testuali della tabella del requisito, separati da separatori.
    desc_similarity(a, b)           -> float
        Similarita' 0.0-1.0 delle due Description.
    identical(reqs)                 -> bool
        True se la Description e' la stessa in tutte le versioni.
    compare(req_id, base_req, other_name, other_req) -> (bool, str)
        (True, "")    → MATCHED
        (False, "..") → differenze da scrivere in rosso nella cella

CRITERIO DI CONFRONTO — punto centrale
    Il requisito e' definito dalla sua DESCRIPTION. Gli altri campi della
    tabella (Type / ApplicabilityDetails, Derived to, User Interface, SIL,
    Safety level) descrivono il CONTESTO di applicazione: vengono passati
    al modello come informazione di contorno e non generano mai da soli
    una differenza.

DUE INSIDIE DEI DOCUMENTI ETR1000
    1. La stessa colonna si chiama "Type" nella VZI_Base e
       "ApplicabilityDetails" nelle altre configurazioni. E' la STESSA
       colonna: la differenza di nome non va mai segnalata. Per questo il
       prompt usa etichette neutre e non mostra mai i nomi originali.
    2. Lo stesso requisito puo' essere estratto da una tabella orizzontale
       in un documento e da una verticale in un altro. Il layout non e'
       una differenza di requisito e non viene mai citato nel prompt.

DUE FALSI ROSSI STORICI, ENTRAMBI NEUTRALIZZATI QUI
    a) Il modello riempie il campo 'differenze' elencando cio' che e'
       UGUALE ("Logica operativa identica. SIL 2."). Il post-filtro
       _is_no_diff_text() riconosce queste risposte e le converte in
       MATCHED.
    b) Il modello inventa una differenza di layout. Il confronto
       deterministico sulla Description ha sempre la precedenza sul
       verdetto del modello.
"""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from typing import Optional

import config as cfg
from ai_synthesizer import _call_ollama, _chiudi_frase, _e_errore_ai, _token_budget
from llm_json import parse_json_relaxed

log = logging.getLogger(__name__)

import json as _json
from pathlib import Path as _Path

_cache: dict[tuple, tuple[bool, str]] = {}

_CACHE_FILE = getattr(
    cfg, "HISTORY_DIR", _Path.home() / "AppData" / "Local" / "FunzioniAI"
) / "req_ai_cache.json"


def load_cache() -> None:
    """Rilegge gli esiti salvati nei run precedenti."""
    try:
        if _CACHE_FILE.exists():
            raw = _json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            for k, v in raw.items():
                if "«" in (v[1] or ""):
                    continue      # vecchio formato che citava le parole: si rigenera
                _cache[tuple(k.split("||"))] = (bool(v[0]), v[1])
            log.info(f"  [ReqAI] Cache caricata: {len(_cache)} confronti")
    except Exception as exc:
        log.warning(f"  [ReqAI] Cache non leggibile: {exc}")


def save_cache() -> None:
    """Salva gli esiti per i run successivi."""
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            _json.dumps({"||".join(map(str, k)): [v[0], v[1]]
                         for k, v in _cache.items()}),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning(f"  [ReqAI] Cache non salvabile: {exc}")
    save_concepts()


# ---------------------------------------------------------------------------
# Parametri, con valori di riserva se config.py non e' stato aggiornato
# ---------------------------------------------------------------------------

_PRIMARY = getattr(cfg, "REQ_PRIMARY_FIELD", "description")
_SIM_MATCH = getattr(cfg, "REQ_DESC_SIMILARITY_MATCH", 0.97)
_SIM_DIFF  = getattr(cfg, "REQ_DESC_SIMILARITY_DIFF", 0.55)   
_SCORE_MATCH = getattr(cfg, "REQ_LLM_SCORE_MATCH", 80)
_SEP = getattr(cfg, "REQ_FIELD_SEP", "\n" + "—" * 20 + "\n")
_BASE_DEFAULT = getattr(cfg, "REQ_BASE_CONFIG", "VZI_Base")

_LABELS_H = getattr(cfg, "REQ_FIELD_LABEL", {
    "description":    "Description",
    "req_type":       "Type / Applicability Details",
    "derived_to":     "Derived to",
    "user_interface": "User Interface",
    "sil":            "SIL",
})
_LABELS_V = getattr(cfg, "REQ_FIELD_LABEL_V", {
    "description": "Description",
    "sil":         "Safety level",
})

# Frasi tipiche con cui il modello dichiara, di fatto, una NON differenza
_NO_DIFF_MARKERS = getattr(cfg, "REQ_NO_DIFF_MARKERS", [
    "identic", "identich", "nessuna differenza", "non sono differenze",
    "non vi sono differenze", "equivalent", "coincidono", "uguali",
    "stessa logica", "stesso", "stessa", "nessuna variazione",
    "no difference", "same", "corrispond",
])

# Indicatori espliciti di divergenza: se presenti, la risposta e' un DIFF vero
_DIFF_MARKERS_RE = re.compile(
    r"\b(invece|mentre|divers[aeio]|differisce|different[ei]|"
    r"a differenza|non presente|assente|manca|mancante|aggiunt\w*|"
    r"rimoss\w*|solo in|soltanto in|presente solo|soglia divers\w*|"
    r"valore divers\w*|anziche|al posto di|sostituit\w*)\b"
)

# Campi comuni usati dal confronto strutturale: solo il primario
_COMMON_FIELDS = (_PRIMARY,)


# ---------------------------------------------------------------------------
# Normalizzazione
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Normalizzazione leggera: spazi compattati, minuscole."""
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _norm_desc(s: str) -> str:
    """
    Normalizzazione aggressiva per il confronto della Description.

    Si elimina tutto cio' che non e' sostanza tecnica: punteggiatura,
    maiuscole, a-capo e trattini di sillabazione introdotti dal PDF.
    Si conservano cifre, '%', '.', '/' e '-' perche' fanno parte di
    soglie e unita' di misura ("750 kPa", "35 s", "1.5 kV").
    """
    t = _norm(s)
    t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    # sillabazione del PDF: "re- activation", "re -activation" e "re-activation"
    # sono la stessa parola, non una differenza di requisito
    t = re.sub(r"(?<=[^\W\d_])\s*-\s*(?=[^\W\d_])", "", t)
    t = re.sub(r"[^\w\s%./-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def same_text(a: str, b: str) -> bool:
    """True se due Description sono lo stesso testo a meno di sillabazione,
    punteggiatura, maiuscole e spazi."""
    na, nb = _norm_desc(a), _norm_desc(b)
    return bool(na) and na == nb


# ---------------------------------------------------------------------------
# Dump dei campi
# ---------------------------------------------------------------------------

def dump_fields(req, for_llm: bool = False) -> str:
    """
    Campi testuali della tabella del requisito, separati da separatori.

    for_llm=False → testo destinato alla CELLA EXCEL: etichette leggibili,
                    Description sempre per prima.
    for_llm=True  → testo destinato al PROMPT: la Description e' marcata
                    [CAMPO PRINCIPALE], gli altri campi [contesto].
                    Le etichette sono neutre: nei documenti la stessa
                    colonna si chiama "Type" oppure "ApplicabilityDetails",
                    e mostrarne il nome originale induce il modello a
                    segnalare una differenza inesistente.

    Il layout ("V" verticale: ID | Description | Safety level, oppure
    "H"/"T" orizzontale) seleziona solo l'insieme di etichette: non viene
    mai scritto nel prompt.
    """
    labels = _LABELS_V if getattr(req, "layout", "") == "V" else _LABELS_H

    desc = (getattr(req, _PRIMARY, "") or "").strip()
    parts: list[str] = []

    if desc:
        parts.append(
            f"[CAMPO PRINCIPALE] Description: {desc}" if for_llm
            else f"Description: {desc}"
        )

    for attr, label in labels.items():
        if attr == _PRIMARY:
            continue
        val = (getattr(req, attr, "") or "").strip()
        if not val:
            continue
        parts.append(
            f"[contesto] {label}: {val}" if for_llm else f"{label}: {val}"
        )

    if not parts:
        parts.append(f"ID: {getattr(req, 'req_id', '')}")

    return _SEP.join(parts)


# ---------------------------------------------------------------------------
# Confronto deterministico sulla Description
# ---------------------------------------------------------------------------

def _common_sig(req) -> str:
    """Impronta del campo primario, normalizzata."""
    return _norm_desc(getattr(req, _PRIMARY, ""))


def desc_similarity(a, b) -> float:
    """Similarita' 0.0-1.0 fra le Description dei due requisiti."""
    da, db = _common_sig(a), _common_sig(b)
    if not da and not db:
        return 1.0
    if not da or not db:
        return 0.0
    if da == db:
        return 1.0
    return SequenceMatcher(None, da, db).ratio()


def same_core(a, b) -> bool:
    """True se la Description dei due requisiti coincide esattamente."""
    return _common_sig(a) == _common_sig(b)


def identical(reqs: list) -> bool:
    """
    True se la Description e' la stessa in tutte le versioni del requisito.

    I campi di contesto sono ignorati di proposito: 'Type' e
    'ApplicabilityDetails' sono la stessa colonna con nome diverso a
    seconda del documento, e confrontarli faceva scattare il ramo
    'MISS VZI_BASE REQ, FOUND DIFF' su requisiti in realta' identici.

    Oltre all'uguaglianza esatta si ammette una tolleranza redazionale:
    tutte le coppie sopra REQ_DESC_SIMILARITY_MATCH valgono identiche.
    """
    if not reqs:
        return True
    if len({_common_sig(r) for r in reqs}) <= 1:
        return True
    for i in range(len(reqs)):
        for j in range(i + 1, len(reqs)):
            if desc_similarity(reqs[i], reqs[j]) < _SIM_MATCH:
                return False
    return True


# ---------------------------------------------------------------------------
# Post-filtro sulle risposte del modello
# ---------------------------------------------------------------------------

def _is_no_diff_text(diff: str) -> bool:
    """
    True se il testo prodotto dal modello, pur non vuoto, NON descrive
    alcuna differenza reale.

    E' il falso rosso piu' frequente: invece di lasciare vuoto il campo
    'differenze', il modello elenca cio' che e' UGUALE, per esempio
        "Logica operativa e comportamento in guasto identici. SIL 2."
        "Logica operativa identica, livello SIL/Safety level identico."
    Oppure ripete le istruzioni del prompt
        "Non sono differenze reali: riformulazioni, codici documento..."

    STRATEGIA
      1. Se compare un indicatore esplicito di divergenza → DIFF vero.
      2. Se il testo cita il layout della tabella → non e' una differenza
         di requisito: il layout dipende dal documento, non dal contenuto.
      3. Altrimenti il testo viene spezzato in proposizioni: se OGNI
         proposizione contiene un marcatore di non-differenza, oppure e'
         un frammento privo di contenuto, si tratta di un MATCHED.
    """
    t = _norm(diff)
    if not t:
        return True

    # 1. Divergenza dichiarata esplicitamente → e' un DIFF reale
    if _DIFF_MARKERS_RE.search(t):
        # ...a meno che la frase parli SOLO di layout o di nomi di colonna
        if re.search(r"\b(layout|tabella (verticale|orizzontale)|"
                     r"verticale|orizzontale|colonna|intestazion\w*|"
                     r"applicabilitydetails|applicability details)\b", t) \
                and not re.search(r"\b(soglia|valore|timeout|timer|"
                                  r"condizione|logica|guasto|sil \d)\b", t):
            return True
        return False

    # 2. Riferimenti al layout: mai una differenza di requisito
    if re.search(r"\b(layout|tabella (verticale|orizzontale))\b", t) \
            and not re.search(r"\b(soglia|valore|condizione|logica)\b", t):
        return True

    # 3. Ogni proposizione dichiara un'uguaglianza o e' priva di contenuto
    frasi = [f.strip() for f in re.split(r"[.;\n]+", t) if f.strip()]
    if not frasi:
        return True
    return all(
        any(mk in f for mk in _NO_DIFF_MARKERS) or len(f) < 12
        for f in frasi
    )

def describe_desc_diff(base_req, base_name: str,
                       other_req, other_name: str) -> str:
    """
    Dettaglio leggibile delle differenze fra le due Description.

    Integra il responso del modello, che a volte resta generico, con il
    contenuto testuale realmente divergente. Il risultato e' un periodo
    discorsivo, non un elenco di frecce: l'utente deve poter leggere la
    cella e capire la differenza senza aprire i due PDF.
    """
    a_txt = _norm_desc(getattr(base_req, _PRIMARY, ""))
    b_txt = _norm_desc(getattr(other_req, _PRIMARY, ""))
    if not a_txt or not b_txt:
        return ""

    a, b = a_txt.split(), b_txt.split()
    max_n = getattr(cfg, "REQ_DIFF_DETAIL_MAX", 3)
    max_len = getattr(cfg, "REQ_DIFF_SNIPPET_LEN", 160)
    stile = getattr(cfg, "REQ_DIFF_STYLE", "narrativo")

    sostituzioni, solo_base, solo_altra = [], [], []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        sa = " ".join(a[i1:i2]).strip()
        sb = " ".join(b[j1:j2]).strip()
        if len(sa) < 4 and len(sb) < 4:
            continue                      # micro-divergenza redazionale
        if tag == "replace":
            sostituzioni.append((sa[:max_len], sb[:max_len]))
        elif tag == "delete":
            solo_base.append(sa[:max_len])
        elif tag == "insert":
            solo_altra.append(sb[:max_len])

    sostituzioni = sostituzioni[:max_n]
    solo_base = solo_base[:max_n]
    solo_altra = solo_altra[:max_n]
    if not (sostituzioni or solo_base or solo_altra):
        return ""

    # ── Forma puntuale (compatibilita' con il comportamento precedente) ──
    if stile == "puntuale":
        righe = [f"  • {base_name}: «{x}» → {other_name}: «{y}»"
                 for x, y in sostituzioni]
        righe += [f"  • presente solo in {base_name}: «{x}»" for x in solo_base]
        righe += [f"  • presente solo in {other_name}: «{x}»" for x in solo_altra]
        return "Dettaglio differenze nella Description:\n" + "\n".join(righe)

    # ── Forma narrativa ──────────────────────────────────────────────────
    frasi = []
    for sa, sb in sostituzioni:
        frasi.append(
            f"dove {base_name} prescrive «{sa}», {other_name} prescrive "
            f"invece «{sb}»"
        )
    for sa in solo_base:
        frasi.append(
            f"la prescrizione «{sa}», presente in {base_name}, non compare "
            f"in {other_name}"
        )
    for sb in solo_altra:
        frasi.append(
            f"{other_name} aggiunge la prescrizione «{sb}», assente in "
            f"{base_name}"
        )

    if len(frasi) == 1:
        corpo = frasi[0]
    else:
        corpo = "; ".join(frasi[:-1]) + f"; infine {frasi[-1]}"

    testo = (
        f"Confrontando il testo dei due documenti si osserva che {corpo}. "
        f"Verificare quale delle due formulazioni si applica alla "
        f"configurazione {other_name}."
    )
    return "Differenze nel testo del requisito: " + testo


# ---------------------------------------------------------------------------
# Differenze CONCETTUALI fra due Description (discorsive, senza citare parole)
# ---------------------------------------------------------------------------

CONCEPT_HEADER = "Differenze nel testo del requisito"
SAME_MEANING_TXT = ("Nessuna differenza di contenuto: i due testi esprimono la stessa "
                    "prescrizione e differiscono solo nella forma (ortografia, "
                    "sillabazione, punteggiatura o riformulazione).")

_concept_cache: dict[str, str] = {}
_concept_loaded = False
_ai_down = False
_CONCEPT_FILE = _CACHE_FILE.with_name("req_concept_cache.json")

# Aspetti tecnici riconoscibili nel testo inglese dei requisiti: servono alla
# spiegazione di riserva (senza AI) per dire COSA cambia senza citare parole.
_ASPECTS = (
    ("la segnalazione diagnostica (eventi, guasti o allarmi)",
     r"\b(events?|faults?|alarms?|diagnos\w*|errors?|warnings?|report\w*)\b"),
    ("la registrazione o memorizzazione di dati",
     r"\b(stor(e|ed|ing|age)|record\w*|logg\w*|saved?|memor\w*)\b"),
    ("le grandezze misurate e i sensori impiegati",
     r"\b(sensors?|temperatures?|pressures?|measur\w*|signals?|pt100|speed|voltage)\b"),
    ("i comandi di attivazione o disattivazione",
     r"\b(activat\w*|reactivat\w*|deactivat\w*|enabl\w*|disabl\w*|switch\w*|start\w*|stop\w*|command\w*)\b"),
    ("le temporizzazioni",
     r"\b(time|times|delay\w*|sec|seconds?|ms|minutes?|timer\w*|timeout\w*)\b"),
    ("le indicazioni al personale di condotta (display e messaggi)",
     r"\b(display\w*|idu|hmi|driver|messages?|screen\w*|lamps?)\b"),
    ("gli aspetti di sicurezza",
     r"\b(safety|safe|sil|emergency|protect\w*|isolat\w*)\b"),
    ("il sottosistema a cui è affidato il compito",
     r"\b(tcms|bcu|pcu|ccu|mvb|wtb|mio|dcu|plc)\b"),
    ("l'ambito di applicazione (vetture, carrelli o veicoli interessati)",
     r"\b(cars?|bogies?|vehicles?|trailers?|axles?|cabs?)\b"),
)
_COND_RE = re.compile(r"\b(if|when|whenever|in case|unless|as soon as|provided|only|until|while)\b")
_NEG_RE = re.compile(r"\b(not|no|never|without|none)\b")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _load_concepts() -> None:
    global _concept_loaded
    if _concept_loaded:
        return
    _concept_loaded = True
    try:
        if _CONCEPT_FILE.exists():
            _concept_cache.update(_json.loads(_CONCEPT_FILE.read_text(encoding="utf-8")))
    except Exception as exc:
        log.warning(f"  [ReqAI] Cache differenze concettuali non leggibile: {exc}")


def save_concepts() -> None:
    """Salva le spiegazioni concettuali generate (riusate da Excel ed export)."""
    if not _concept_cache:
        return
    try:
        _CONCEPT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CONCEPT_FILE.write_text(_json.dumps(_concept_cache, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.warning(f"  [ReqAI] Cache differenze concettuali non salvabile: {exc}")


def _join_it(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


def concept_fallback(a_txt: str, a_name: str, b_txt: str, b_name: str) -> str:
    """
    Spiegazione di riserva, senza AI: descrive in italiano QUALI ASPETTI del
    requisito cambiano fra i due testi (valori, condizioni, diagnostica,
    ambito...) senza citare le parole che differiscono.
    """
    a, b = _norm_desc(a_txt), _norm_desc(b_txt)
    if not a or not b:
        return ""
    if a == b:
        return SAME_MEANING_TXT
    sim = SequenceMatcher(None, a, b, autojunk=False).ratio()
    if sim >= _SIM_MATCH:
        return SAME_MEANING_TXT

    frasi: list[str] = []
    if sim < 0.35:
        frasi.append(f"I due testi descrivono di fatto prescrizioni diverse: {b_name} "
                     f"tratta la funzione da un punto di vista differente rispetto a {a_name}.")
    elif sim < 0.8:
        frasi.append(f"I due testi trattano lo stesso argomento, ma {b_name} formula la "
                     f"prescrizione con contenuti diversi rispetto a {a_name}.")
    else:
        frasi.append(f"La prescrizione di {b_name} è nella sostanza quella di {a_name}, "
                     f"con alcune differenze di dettaglio.")

    only_a, only_b, changed = [], [], []
    for label, rx in _ASPECTS:
        na, nb = len(re.findall(rx, a)), len(re.findall(rx, b))
        if na and not nb:
            only_a.append(label)
        elif nb and not na:
            only_b.append(label)
        elif na and nb and sim < 0.8 and max(na, nb) >= 2 * min(na, nb):
            changed.append(label)
    if only_a:
        frasi.append(f"In {a_name} il requisito riguarda anche {_join_it(only_a)}, "
                     f"aspetto che in {b_name} non viene trattato.")
    if only_b:
        frasi.append(f"{b_name} introduce invece {_join_it(only_b)}, "
                     f"non previsto nel testo di {a_name}.")
    if changed:
        frasi.append(f"Cambia inoltre il modo in cui sono descritti {_join_it(changed)}.")

    nums_a, nums_b = set(_NUM_RE.findall(a)), set(_NUM_RE.findall(b))
    if nums_a and nums_b and nums_a != nums_b:
        frasi.append("I valori numerici indicati (soglie, tempi o quantità) non coincidono.")
    elif nums_a and not nums_b:
        frasi.append(f"Solo {a_name} specifica valori numerici (soglie, tempi o quantità).")
    elif nums_b and not nums_a:
        frasi.append(f"Solo {b_name} specifica valori numerici (soglie, tempi o quantità).")

    ca, cb = len(_COND_RE.findall(a)), len(_COND_RE.findall(b))
    if ca != cb:
        piu, meno = (b_name, a_name) if cb > ca else (a_name, b_name)
        frasi.append(f"Le condizioni che rendono applicabile la prescrizione sono diverse: "
                     f"{piu} pone vincoli o casi particolari che {meno} non prevede.")
    if bool(_NEG_RE.search(a)) != bool(_NEG_RE.search(b)):
        frasi.append("In uno dei due testi compare un'esclusione o un divieto assente nell'altro, "
                     "che può cambiare il senso della prescrizione.")
    la, lb = len(a.split()), len(b.split())
    if max(la, lb) >= 1.5 * min(la, lb):
        lungo, corto = (b_name, a_name) if lb > la else (a_name, b_name)
        frasi.append(f"Il testo di {lungo} è sensibilmente più dettagliato di quello di {corto}.")
    if len(frasi) == 1:
        frasi.append("Si consiglia di leggere i due testi affiancati per valutarne l'impatto.")
    return " ".join(frasi)


def _concept_ai(a_txt: str, a_name: str, b_txt: str, b_name: str) -> Optional[str]:
    """Spiegazione del modello locale; None se l'AI non è disponibile o la
    risposta non rispetta le regole (in quel caso si usa la riserva)."""
    global _ai_down
    if _ai_down or not getattr(cfg, "REQ_CONCEPT_DIFF_AI", True):
        return None
    prompt = (
        "Sei un ingegnere ferroviario esperto dei treni ETR1000.\n"
        "Lo stesso requisito tecnico compare con due testi diversi in due "
        "configurazioni del treno.\n\n"
        f"--- Testo di {a_name} (riferimento) ---\n{a_txt.strip()[:2500]}\n\n"
        f"--- Testo di {b_name} ---\n{b_txt.strip()[:2500]}\n\n"
        f"COMPITO: spiega in italiano, in modo discorsivo (2-4 frasi), quali sono "
        f"le differenze A LIVELLO DI CONCETTO fra il testo di {b_name} e quello di "
        f"{a_name}: che cosa cambia nella prescrizione, nel comportamento richiesto "
        f"al treno, nei sottosistemi coinvolti o nell'ambito di applicazione.\n"
        "REGOLE\n"
        "1. NON citare e NON virgolettare parole o frasi dei due testi; NON elencare "
        "le parole cambiate; NON tradurre i testi parola per parola.\n"
        "2. Ignora errori di battitura, sillabazione (es. una parola spezzata da un "
        "trattino), punteggiatura, maiuscole e riformulazioni che non cambiano il "
        "significato.\n"
        "3. Se il significato e' lo stesso, il campo 'differenze' deve essere la "
        "stringa vuota \"\".\n"
        "4. Niente elenchi puntati: un breve paragrafo rivolto a un ingegnere.\n\n"
        "ESEMPIO: {\"differenze\": \"Nel riferimento il requisito prescrive la "
        "generazione di un evento diagnostico e la memorizzazione delle misure; "
        "nell'altra configurazione descrive invece come avviene il rilevamento e a "
        "quale sottosistema e' affidato, senza imporre la segnalazione. Anche "
        "l'ambito dei sensori considerati e' definito in modo diverso.\"}\n\n"
        "Rispondi SOLO con il JSON {\"differenze\": \"...\"}."
    )
    raw = _call_ollama(prompt, num_predict=_token_budget(700))
    if _e_errore_ai(raw):
        _ai_down = True          # Ollama non raggiungibile: niente attese per i successivi
        log.info("  [ReqAI] AI non disponibile: differenze concettuali con la spiegazione di riserva")
        return None
    rec = parse_json_relaxed(raw, campi_testo=("differenze",))
    if not rec or not isinstance(rec.data, dict):
        return None
    diff = str(rec.data.get("differenze") or "").strip()
    if rec.truncated and diff:
        diff = _chiudi_frase(diff)
    if not diff or _is_no_diff_text(diff):
        return SAME_MEANING_TXT
    if re.search(r"[«»“”\"]", diff):
        return None              # il modello ha citato parole del testo: si usa la riserva
    return diff


def concept_diff(a_txt: str, a_name: str, b_txt: str, b_name: str, use_ai: bool = True) -> str:
    """
    Differenze CONCETTUALI fra la Description di riferimento (a) e quella di
    un'altra configurazione (b): paragrafo discorsivo in italiano che non
    cita le parole differenti. "" se uno dei due testi manca.

    use_ai=False → solo cache e spiegazione di riserva (nessuna attesa).
    """
    if not _norm_desc(a_txt) or not _norm_desc(b_txt):
        return ""
    if same_text(a_txt, b_txt):
        return SAME_MEANING_TXT
    _load_concepts()
    import hashlib
    key = hashlib.sha1("\x1f".join((_norm_desc(a_txt), a_name, _norm_desc(b_txt), b_name))
                       .encode("utf-8")).hexdigest()
    if key in _concept_cache:
        return _concept_cache[key]
    out = _concept_ai(a_txt, a_name, b_txt, b_name) if use_ai else None
    if out is None:
        return concept_fallback(a_txt, a_name, b_txt, b_name)
    _concept_cache[key] = out
    return out


# ---------------------------------------------------------------------------
# API principale
# ---------------------------------------------------------------------------

def compare(req_id: str, base_req, other_name: str, other_req) -> tuple[bool, str]:
    """
    Confronta il requisito della configurazione di riferimento con quello
    di un'altra configurazione.

    Ritorna
        (True,  "")       → MATCHED, la cella va scritta in verde grassetto
        (False, "testo")  → differenze, la cella va scritta in rosso

    SHORTCUT DETERMINISTICI — nessuna chiamata al modello
        1. Description identica dopo normalizzazione.
        2. Similarita' della Description >= REQ_DESC_SIMILARITY_MATCH:
           le differenze sono solo redazionali.
        3. Entrambe le Description assenti: nulla da confrontare.
        4. Una sola Description assente: non confrontabile, si segnala il
           dato mancante senza interpellare il modello, che altrimenti
           inventerebbe una differenza.

    Il verdetto deterministico ha SEMPRE la precedenza su quello del
    modello: se la Description e' sostanzialmente la stessa, un eventuale
    testo di differenze prodotto dal LLM viene scartato.
    """
    base_name = getattr(base_req, "config_name", "") or _BASE_DEFAULT

    d_base = _common_sig(base_req)
    d_other = _common_sig(other_req)

    # ── Shortcut 1: Description identica ─────────────────────────────────
    if d_base and d_base == d_other:
        return True, ""

    # ── Shortcut 3 e 4: Description mancante ─────────────────────────────
    if not d_base or not d_other:
        if not d_base and not d_other:
            return True, ""
        mancante = base_name if not d_base else other_name
        return False, (
            f"Description assente in {mancante}: confronto non possibile, "
            f"verifica manuale del documento."
        )

    # ── Shortcut 2: differenze solo redazionali ──────────────────────────
    sim = desc_similarity(base_req, other_req)
    if sim >= _SIM_MATCH:
        log.debug(
            f"  [ReqAI] {req_id}: Description simile al {sim:.1%} "
            f"→ MATCHED senza LLM"
        )
        return True, ""

    # ── Shortcut 5: divergenza evidente, nessun verdetto del modello ─────
    # Sotto REQ_DESC_SIMILARITY_DIFF le due Description non sono la stessa
    # prescrizione riformulata: sono testi diversi. Il modello serve solo a
    # spiegare a parole le differenze di concetto (concept_diff), senza
    # citare i frammenti di testo.
    if sim < _SIM_DIFF:
        testo = (
            f"Il testo del requisito in {other_name} differisce in modo "
            f"sostanziale da quello di {base_name} "
            f"(corrispondenza {sim:.0%})."
        )
        concetto = concept_diff(getattr(base_req, _PRIMARY, ""), base_name,
                                getattr(other_req, _PRIMARY, ""), other_name)
        if concetto:
            testo = f"{testo}\n\n{CONCEPT_HEADER}: {concetto}"
        limite = getattr(cfg, "REQ_DIFF_MAX_CHARS", 700)
        if len(testo) > limite:
            testo = testo[:limite].rsplit(" ", 1)[0] + " […]"
        log.info(f"  [ReqAI] {req_id}: sim={sim:.2f} → DIFF")
        out = (False, testo)
        _cache[(req_id.lower(), base_name, other_name)] = out
        return out

    # ── Cache ────────────────────────────────────────────────────────────
    # La chiave include ENTRAMBE le configurazioni: lo stesso ID puo'
    # essere confrontato con basi diverse (caso 1 con VZI_Base, caso 3 con
    # una configurazione qualsiasi) e gli esiti non sono intercambiabili.
    key = (req_id.lower(), base_name, other_name)
    if key in _cache:
        return _cache[key]

    prompt = (
        "Sei un tecnico ferroviario esperto di sistemi ETR1000.\n"
        f"Confronta lo STESSO requisito '{req_id}' in due configurazioni "
        "di treno.\n\n"
        f"--- [{base_name}] ---\n"
        f"{dump_fields(base_req, for_llm=True)[:2500]}\n\n"
        f"--- [{other_name}] ---\n"
        f"{dump_fields(other_req, for_llm=True)[:2500]}\n\n"
        "REGOLE DI CONFRONTO\n"
        "1. Confronta SOLO il [CAMPO PRINCIPALE] Description: e' la "
        "formulazione tecnica del requisito. I campi marcati [contesto] "
        "descrivono l'ambiente di applicazione e NON vanno mai riportati "
        "come differenze.\n"
        "2. NON sono differenze: riformulazioni della stessa prescrizione, "
        "sinonimi, ordine delle frasi, punteggiatura, maiuscole, codici di "
        "documento, nomi delle colonne della tabella di origine, struttura "
        "o impaginazione della tabella.\n"
        "3. SONO differenze: prescrizione tecnica diversa, logica operativa "
        "diversa, soglie o tempi con valori numerici diversi, condizione "
        "presente in una configurazione e assente nell'altra, "
        "comportamento in guasto diverso.\n"
        "4. Se NON trovi differenze secondo la regola 3, il campo "
        "'differenze' deve essere ESATTAMENTE la stringa vuota \"\".\n"
        "   - NON elencare cio' che e' uguale.\n"
        "   - NON scrivere frasi come \"logica identica\", \"SIL identico\", "
        "\"interfaccia utente identica\".\n"
        "   - NON ripetere queste istruzioni nella risposta.\n"
        "   - NON menzionare il layout o la struttura delle tabelle.\n"
        "5. Se trovi differenze, scrivi un BREVE PARAGRAFO DISCORSIVO in "
        "italiano (2-4 frasi, niente elenchi puntati, niente sigle "
        "criptiche) rivolto a un ingegnere che non ha davanti i due "
        "documenti. Spiega le differenze A LIVELLO DI CONCETTO: che cosa "
        f"cambia nella prescrizione di {other_name} rispetto a {base_name} "
        "e quale conseguenza pratica ha sul comportamento del treno.\n"
        "   NON citare e NON virgolettare parole o frasi dei due testi, NON "
        "elencare le parole cambiate e non ripetere l'identificativo.\n"
        "6. score 0-100: 100 = stessa prescrizione tecnica, "
        "0 = prescrizioni completamente diverse.\n\n"
        "ESEMPIO DI RISPOSTA SENZA DIFFERENZE:\n"
        '{"score": 96, "differenze": ""}\n'
        "ESEMPIO DI RISPOSTA CON DIFFERENZE:\n"
        '{"score": 35, "differenze": "Nella configurazione di riferimento '
        "l'abbassamento del pantografo e' comandato da una soglia di pressione "
        "con un ritardo prefissato. Nella configurazione in esame la soglia e' "
        "piu' alta e la temporizzazione non e' prevista: l'intervento avviene "
        "quindi prima e senza attesa, con il pantografo che si abbassa piu' "
        'precocemente durante le fasi di ricarica della condotta."}\n\n'
        "Rispondi SOLO con il JSON, nessun testo prima o dopo."
    )

    raw = _call_ollama(prompt, num_predict=_token_budget(900))
    log.debug(f"  [ReqAI raw] {req_id}: {raw[:300]}")

    score, diff = 50, ""
    rec = parse_json_relaxed(raw, campi_testo=("score", "differenze"))
    if rec:
        data = rec.data
        raw_score = data.get("score", 50)
        try:
            score = int(float(raw_score))
        except (TypeError, ValueError):
            score = 50
        if not 0 <= score <= 100:
            score = 50
        diff = str(data.get("differenze") or "").strip()
        if rec.truncated and diff:
            diff = _chiudi_frase(diff)
            log.info(
                f"  [ReqAI] {req_id}: risposta troncata dal limite di "
                f"token — contenuto recuperato ({rec.method})"
            )
    elif not _e_errore_ai(raw):
        log.warning(
            f"  [ReqAI] risposta non interpretabile per {req_id}: "
            f"{raw[:200]!r}"
        )

    # ── Post-filtro A: 'differenze' che in realta' elenca le uguaglianze ─
    if diff and _is_no_diff_text(diff):
        log.info(
            f"  [ReqAI] {req_id} | {base_name} vs {other_name}: nessuna "
            f"differenza reale nel testo del modello → MATCHED "
            f"(scartato: {diff[:90]!r})"
        )
        diff = ""

    # ── Post-filtro B: il deterministico prevale sul modello ─────────────
    if diff and sim >= _SIM_MATCH:
        log.debug(
            f"  [ReqAI] {req_id}: differenze del modello scartate, "
            f"Description simile al {sim:.1%}"
        )
        diff = ""

    is_match = (not diff) and score >= _SCORE_MATCH

    if not is_match:
        if not diff or re.search(r"[«»“”]", diff):
            # il modello non ha sintetizzato (o ha citato parole): spiegazione concettuale
            diff = concept_diff(getattr(base_req, _PRIMARY, ""), base_name,
                                getattr(other_req, _PRIMARY, ""), other_name)
        if diff == SAME_MEANING_TXT:
            is_match = True        # stessa prescrizione: solo differenze formali

    if not is_match:
        diff = (
            f"Il testo del requisito in {other_name} non coincide con quello di "
            f"{base_name} (corrispondenza {sim:.0%}).\n\n{CONCEPT_HEADER}: {diff}"
        )
        limite = getattr(cfg, "REQ_DIFF_MAX_CHARS", 700)
        if len(diff) > limite:
            diff = diff[:limite].rsplit(" ", 1)[0] + " […]"

    log.info(
        f"  [ReqAI] {req_id} | {base_name} vs {other_name} | "
        f"sim={sim:.2f} score={score} | {'MATCHED' if is_match else 'DIFF'}"
    )

    out = (is_match, "" if is_match else diff)
    _cache[key] = out
    return out


def clear_cache() -> None:
    """Svuota la cache degli esiti. Da chiamare all'avvio di ogni run."""
    _cache.clear()