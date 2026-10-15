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

import config as cfg
from ai_synthesizer import _call_ollama

log = logging.getLogger(__name__)

# Cache degli esiti: {(req_id, config_base, config_altra): (is_match, diff)}
_cache: dict[tuple, tuple[bool, str]] = {}


# ---------------------------------------------------------------------------
# Parametri, con valori di riserva se config.py non e' stato aggiornato
# ---------------------------------------------------------------------------

_PRIMARY = getattr(cfg, "REQ_PRIMARY_FIELD", "description")
_SIM_MATCH = getattr(cfg, "REQ_DESC_SIMILARITY_MATCH", 0.97)
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
    t = re.sub(r"[^\w\s%./-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


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
        "italiano (3-5 frasi, niente elenchi puntati, niente sigle "
        "criptiche) rivolto a un ingegnere che non ha davanti i due "
        "documenti. Il paragrafo deve dire, nell'ordine:\n"
        "   a) che cosa prescrive il requisito nella configurazione di "
        f"riferimento {base_name};\n"
        f"   b) in che cosa se ne discosta la configurazione {other_name};\n"
        "   c) quale conseguenza pratica ha questa differenza sul "
        "comportamento del treno.\n"
        "   Cita i valori, le condizioni e i componenti concreti che "
        "cambiano. Non usare la parola 'requisito' come soggetto di ogni "
        "frase e non ripetere l'identificativo.\n"
        "6. score 0-100: 100 = stessa prescrizione tecnica, "
        "0 = prescrizioni completamente diverse.\n\n"
        "ESEMPIO DI RISPOSTA SENZA DIFFERENZE:\n"
        '{"score": 96, "differenze": ""}\n'
        "ESEMPIO DI RISPOSTA CON DIFFERENZE:\n"
        '{"score": 35, "differenze": "Nella configurazione di riferimento '
        "l'abbassamento del pantografo e' comandato quando la pressione in "
        "condotta scende sotto 750 kPa, con un ritardo di 2 secondi. Nella "
        "configurazione in esame la stessa soglia e' fissata a 800 kPa e il "
        "ritardo non e' previsto: l'intervento avviene quindi prima e senza "
        "temporizzazione. In pratica il pantografo si abbassa piu' "
        'precocemente durante le fasi di ricarica della condotta."}\n\n'
        "Rispondi SOLO con il JSON, nessun testo prima o dopo.\n"
        "6. score 0-100: 100 = stessa prescrizione tecnica, "
        "0 = prescrizioni completamente diverse.\n\n"
        "ESEMPIO DI RISPOSTA SENZA DIFFERENZE:\n"
        '{"score": 96, "differenze": ""}\n'
        "ESEMPIO DI RISPOSTA CON DIFFERENZE:\n"
        '{"score": 40, "differenze": "In VZ_ES la soglia di intervento e\' '
        '800 kPa contro i 750 kPa della VZI_Base."}\n\n'
        "Rispondi SOLO con il JSON, nessun testo prima o dopo."
    )

    raw = _call_ollama(prompt)
    log.debug(f"  [ReqAI raw] {req_id}: {raw[:300]}")

    score, diff = 50, ""
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            raw_score = data.get("score", 50)
            try:
                score = int(float(raw_score))
            except (TypeError, ValueError):
                score = 50
            if not 0 <= score <= 100:
                score = 50
            diff = (data.get("differenze") or "").strip()
        else:
            log.warning(f"  [ReqAI] nessun JSON nella risposta per {req_id}")
    except Exception as exc:
        log.warning(f"  [ReqAI] parsing fallito su {req_id}: {exc}")

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
        dettaglio = describe_desc_diff(base_req, base_name,
                                       other_req, other_name)
        if not diff:
            diff = (
                f"Il testo del requisito in {other_name} non coincide con "
                f"quello di {base_name} (corrispondenza {sim:.0%}). "
                f"La differenza non e' stata sintetizzata dal modello: "
                f"di seguito il confronto testuale."
            )
        if dettaglio:
            diff = f"{diff}\n\n{dettaglio}"

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