"""
ai_synthesizer.py
-----------------
Genera la sintesi tecnica di una funzione ferroviaria usando
Ollama (AI locale, completamente gratuita).

LOGICA DI CONFRONTO TRA CONFIGURAZIONI:
  Per ogni documento (doc_id) vengono raccolti i testi estratti
  da TUTTE le configurazioni disponibili. Il flusso è:

  1. Estrazione testi da tutte le configurazioni del gruppo
  2. Valutazione SEMANTICA dell'equivalenza tramite Ollama:
     - Ollama legge tutti i testi e decide se le funzioni descritte
       sono semanticamente equivalenti (stesso scopo, stessi componenti,
       stessa logica) anche se il testo è formulato diversamente
     - Risponde in JSON strutturato
  3. In base al risultato:
     a. Tutte equivalenti → sintesi + nota di equivalenza (cella VERDE)
     b. Alcune equivalenti → sintesi con differenze marcate (cella ROSSA)
     c. Nessuna equivalente → sintesi con confronto esplicito (cella ROSSA)

COLORAZIONE CELLE:
  - Verde  : tutte le configurazioni del gruppo sono semanticamente equivalenti
  - Rosso  : esistono differenze semantiche tra le configurazioni
  - Nero   : unica configurazione disponibile (nessun confronto possibile)
"""
from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass

import config as cfg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strutture dati
# ---------------------------------------------------------------------------

@dataclass
class ConfigText:
    """
    Testo estratto dalla pagina di riferimento per una specifica configurazione.
    """
    config_name: str
    page_number: int
    text: str


@dataclass
class SynthesisResult:
    """
    Risultato della sintesi per una singola cella.

    Attributi:
        text           : testo da scrivere nella cella Excel
        has_differences: True  → cella da colorare ROSSA (differenze rilevate)
                         False → cella da colorare VERDE (equivalente)
                         None  → cella da lasciare in nero (unica configurazione)
    """
    text: str
    has_differences: bool | None   # None = unica config, nessun confronto


# ---------------------------------------------------------------------------
# Verifica prerequisiti Ollama
# ---------------------------------------------------------------------------

def check_ollama() -> bool:
    """
    Verifica che Ollama sia in esecuzione e il modello configurato
    sia disponibile. Restituisce True se tutto è OK.
    """
    try:
        import ollama
        models     = ollama.list()
        available  = [m.model for m in models.models]
        model_base = cfg.OLLAMA_MODEL.split(":")[0]

        if not any(model_base in m for m in available):
            log.error(
                f"Modello '{cfg.OLLAMA_MODEL}' non trovato in Ollama.\n"
                f"  Modelli disponibili: {available}\n"
                f"  Scarica con: ollama pull {cfg.OLLAMA_MODEL}"
            )
            return False

        log.info(f"✅ Ollama OK — modello '{cfg.OLLAMA_MODEL}' disponibile.")
        return True

    except Exception as exc:
        log.error(
            f"Ollama non raggiungibile: {exc}\n"
            "  Assicurati che Ollama sia avviato (icona nella barra delle applicazioni).\n"
            "  Se non è avviato: aprilo dal menu Start."
        )
        return False


# ---------------------------------------------------------------------------
# Chiamata base a Ollama
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str) -> str:
    """
    Chiama Ollama con il prompt fornito e restituisce la risposta testuale.
    """
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
# Valutazione semantica dell'equivalenza
# ---------------------------------------------------------------------------

def _ask_ollama_equivalence(
    func_id: str,
    func_desc: str,
    doc_id: str,
    texts: list[ConfigText],
) -> tuple[bool, list[str]]:
    """
    Chiede a Ollama di valutare se le funzioni descritte nei testi
    sono semanticamente equivalenti tra le configurazioni.

    Returns:
        (is_equivalent, equivalent_group_names)
        - is_equivalent        : True se TUTTE le configurazioni sono equivalenti
        - equivalent_group_names: nomi delle configurazioni equivalenti tra loro
    """
    if len(texts) <= 1:
        return True, [t.config_name for t in texts]

    configs_section = ""
    for ct in texts:
        snippet = ct.text[:600].strip()
        if snippet:
            configs_section += (
                f"\n[{ct.config_name} — pagina {ct.page_number}]\n"
                f"{snippet}\n"
            )

    all_names = [t.config_name for t in texts]

    prompt = (
        "Sei un esperto di sistemi ferroviari ETR1000.\n\n"
        f"Funzione: {func_id} — {func_desc}\n"
        f"Documento: {doc_id}\n\n"
        "Ti fornisco estratti tecnici della stessa funzione ferroviaria "
        "da documenti di diverse configurazioni del treno ETR1000.\n"
        "Devi valutare se la funzione descritta è SEMANTICAMENTE EQUIVALENTE "
        "tra le configurazioni.\n\n"
        "Due funzioni sono semanticamente equivalenti se hanno:\n"
        "  - Lo stesso scopo e lo stesso nome funzionale\n"
        "  - Gli stessi componenti principali (anche con codici diversi)\n"
        "  - La stessa logica operativa e le stesse condizioni e valori di attivazione\n"
        "  - Gli stessi interfacciamenti con altri sistemi \n\n"
        "Due funzioni NON sono equivalenti se differiscono in almeno uno di:\n"
        "  - Componenti elettrici, meccanici o software diversi\n"
        "  - Logica di funzionamento o condizioni operative diverse\n"
        "  - Requisiti o parametri tecnici diversi\n"
        "  - Sistemi o sottosistemi coinvolti diversi\n\n"
        "Estratti per configurazione:\n"
        f"{configs_section}\n\n"
        "Rispondi ESCLUSIVAMENTE con un oggetto JSON valido, "
        "senza altro testo prima o dopo:\n"
        "{\n"
        '  "equivalenti": true,\n'
        '  "configurazioni_equivalenti": ["nome1", "nome2"],\n'
        '  "motivazione": "breve spiegazione in italiano (max 1 frase)"\n'
        "}\n\n"
        "Regole:\n"
        f"  - Se TUTTE le {len(texts)} configurazioni sono equivalenti: "
        '"equivalenti": true e lista con TUTTI i nomi\n'
        "  - Se NESSUNA è equivalente alle altre: "
        '"equivalenti": false e lista VUOTA\n'
        "  - Se ALCUNE sono equivalenti tra loro: "
        '"equivalenti": false e lista con solo i nomi equivalenti\n'
        f"  - I nomi disponibili sono: {all_names}"
    )

    raw = _call_ollama(prompt)

    try:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            data        = json.loads(json_match.group())
            is_equiv    = bool(data.get("equivalenti", False))
            equiv_names = [
                n for n in data.get("configurazioni_equivalenti", [])
                if n in all_names
            ]
            motivazione = data.get("motivazione", "")
            log.info(
                f"  Valutazione semantica: "
                f"{'✅ EQUIVALENTI' if is_equiv else '⚡ DIVERSE'} — "
                f"{motivazione}"
            )
            if equiv_names:
                log.info(f"  Configurazioni equivalenti: {equiv_names}")
            return is_equiv, equiv_names

    except (json.JSONDecodeError, AttributeError, KeyError) as exc:
        log.warning(
            f"  Risposta Ollama non parsabile come JSON.\n"
            f"  Risposta: {raw[:300]}\n"
            f"  Errore: {exc}\n"
            "  Fallback: assumo configurazioni NON equivalenti."
        )

    return False, []


# ---------------------------------------------------------------------------
# Generatori di sintesi
# ---------------------------------------------------------------------------

def _synthesize_single(
    func_id: str,
    func_desc: str,
    doc_id: str,
    config_name: str,
    page_number: int,
    page_text: str,
) -> str:
    """Sintesi semplice per una singola configurazione, senza confronto."""
    prompt = (
        "Sei un esperto di sistemi ferroviari ETR1000 "
        "(treno ad alta velocità italiano di Trenitalia).\n"
        "Ti fornisco un estratto tecnico da un documento di riferimento. "
        "Il tuo compito è sintetizzare la funzione ferroviaria descritta.\n\n"
        f"Funzione: {func_id} — {func_desc}\n"
        f"Documento: {doc_id} | Configurazione: {config_name} | "
        f"Pagina di riferimento: {page_number}\n\n"
        "Estratto del documento:\n"
        "───────────────────────\n"
        f"{page_text[:2200]}\n"
        "───────────────────────\n\n"
        "Scrivi una sintesi tecnica in italiano (massimo 4 frasi) che includa:\n"
        "• Nome e scopo della funzione ferroviaria\n"
        "• Componenti elettrici/meccanici/software principali coinvolti\n"
        "• Logica di funzionamento (condizioni di attivazione/disattivazione)\n"
        "• Eventuali ridondanze o requisiti di sicurezza\n\n"
        "Rispondi SOLO con la sintesi tecnica, senza preamboli o commenti."
    )
    return _call_ollama(prompt)


def _synthesize_all_equivalent(
    func_id: str,
    func_desc: str,
    doc_id: str,
    config_name: str,
    page_number: int,
    page_text: str,
    all_config_texts: list[ConfigText],
) -> str:
    """
    Sintesi quando TUTTE le configurazioni sono semanticamente equivalenti.
    Aggiunge la nota di equivalenza alla fine.
    La cella verrà colorata VERDE dal chiamante.
    """
    base = _synthesize_single(
        func_id, func_desc, doc_id, config_name, page_number, page_text
    )
    equiv_names = [t.config_name for t in all_config_texts]
    nota = (
        f"\nAnalisi — Funzione equivalente tra le seguenti "
        f"configurazioni: {', '.join(equiv_names)}."
    )
    return base + nota


def _synthesize_with_diff(
    func_id: str,
    func_desc: str,
    doc_id: str,
    config_name: str,
    page_number: int,
    page_text: str,
    all_config_texts: list[ConfigText],
    equiv_names: list[str],
) -> str:
    """
    Sintesi con analisi comparativa quando esistono differenze semantiche.
    La cella verrà colorata ROSSA dal chiamante.
    """
    other_configs = [t for t in all_config_texts if t.config_name != config_name]
    all_names     = [t.config_name for t in all_config_texts]

    comparison_section = ""
    if other_configs:
        comparison_section = "\n\nEstratti delle ALTRE configurazioni:\n"
        for other in other_configs:
            snippet = other.text[:700].strip()
            if snippet:
                comparison_section += (
                    f"\n[{other.config_name} — pagina {other.page_number}]\n"
                    f"{snippet}\n"
                )

    if equiv_names and config_name in equiv_names:
        other_equiv   = [n for n in equiv_names if n != config_name]
        non_equiv     = [n for n in all_names if n not in equiv_names]
        diff_instruction = (
            f"La valutazione semantica ha stabilito che '{config_name}' è "
            f"semanticamente equivalente a: {', '.join(other_equiv)}.\n"
            f"Esistono invece differenze rispetto a: {', '.join(non_equiv)}.\n\n"
            "Struttura la risposta in due parti:\n"
            "PARTE 1 (2-3 frasi): descrivi la funzione per questa configurazione "
            "(scopo, componenti, logica operativa).\n"
            "PARTE 2 (1-2 frasi): descrivi le differenze specifiche rispetto a "
            f"{', '.join(non_equiv)} "
            "(componenti diversi, logica diversa, requisiti diversi, ecc.).\n"
            f"Concludi con: \"Analisi — Funzione equivalente tra le seguenti "
            f"configurazioni: {', '.join(equiv_names)}.\""
        )
    else:
        diff_instruction = (
            f"La valutazione semantica ha rilevato differenze significative "
            f"tra tutte le configurazioni: {', '.join(all_names)}.\n\n"
            "Struttura la risposta in due parti:\n"
            f"PARTE 1 (2-3 frasi): descrivi la funzione per '{config_name}' "
            "(scopo, componenti principali, logica operativa).\n"
            "PARTE 2 (1-3 frasi): marca esplicitamente le differenze rispetto "
            "alle altre configurazioni, specificando SOLO gli aspetti "
            "effettivamente diversi tra:\n"
            "  - Componenti elettrici/meccanici/software\n"
            "  - Logica di funzionamento o condizioni operative\n"
            "  - Requisiti o parametri tecnici\n"
            "  - Sistemi o sottosistemi coinvolti"
        )

    prompt = (
        "Sei un esperto di sistemi ferroviari ETR1000 "
        "(treno ad alta velocità italiano di Trenitalia).\n\n"
        f"Funzione: {func_id} — {func_desc}\n"
        f"Documento: {doc_id}\n\n"
        f"CONFIGURAZIONE CORRENTE: {config_name} (pagina {page_number})\n"
        "───────────────────────\n"
        f"{page_text[:1400]}\n"
        "───────────────────────"
        f"{comparison_section}\n\n"
        f"{diff_instruction}\n\n"
        "Scrivi in italiano (massimo 5 frasi totali), "
        "senza preamboli, titoli o intestazioni aggiuntive."
    )
    return _call_ollama(prompt)


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def synthesize_with_comparison(
    func_id: str,
    func_desc: str,
    doc_id: str,
    config_name: str,
    page_number: int,
    page_text: str,
    all_config_texts: list[ConfigText],
) -> SynthesisResult:
    """
    Punto di ingresso principale per la generazione della sintesi.

    Restituisce un SynthesisResult con:
      - text           : testo da scrivere nella cella
      - has_differences: None  → unica configurazione → cella nera
                         False → equivalenti         → cella VERDE
                         True  → differenze rilevate → cella ROSSA

    Flusso:
      1. Unica configurazione → sintesi semplice, has_differences=None
      2. Valutazione semantica Ollama
         a. Tutte equivalenti  → sintesi + nota equivalenza, has_differences=False
         b. Differenze rilevate→ sintesi comparativa,        has_differences=True
    """
    if not page_text.strip():
        return SynthesisResult(
            text="[Testo non disponibile nel documento per questa pagina]",
            has_differences=None,
        )

    # Caso 1: unica configurazione disponibile
    if len(all_config_texts) <= 1:
        log.info(f"  [{config_name}] Unica configurazione — sintesi semplice")
        return SynthesisResult(
            text=_synthesize_single(
                func_id, func_desc, doc_id, config_name, page_number, page_text
            ),
            has_differences=None,
        )

    # Caso 2: valutazione semantica
    log.info(
        f"  [{config_name}] Valutazione semantica equivalenza "
        f"({len(all_config_texts)} configurazioni)..."
    )
    is_equiv, equiv_names = _ask_ollama_equivalence(
        func_id, func_desc, doc_id, all_config_texts
    )

    # Caso 2a: tutte equivalenti → verde
    if is_equiv and len(equiv_names) == len(all_config_texts):
        log.info(f"  [{config_name}] ✅ Tutte equivalenti → cella VERDE")
        return SynthesisResult(
            text=_synthesize_all_equivalent(
                func_id, func_desc, doc_id, config_name,
                page_number, page_text, all_config_texts
            ),
            has_differences=False,
        )

    # Caso 2b/2c: differenze → rosso
    log.info(
        f"  [{config_name}] ⚡ Differenze rilevate → cella ROSSA "
        f"(equivalenti: {equiv_names or 'nessuna'})"
    )
    return SynthesisResult(
        text=_synthesize_with_diff(
            func_id, func_desc, doc_id, config_name, page_number,
            page_text, all_config_texts, equiv_names
        ),
        has_differences=True,
    )


def synthesize(
    func_id: str,
    func_desc: str,
    doc_id: str,
    config_name: str,
    page_number: int,
    page_text: str,
) -> str:
    """
    Versione semplificata senza confronto (compatibilità con codice esistente).
    """
    return _synthesize_single(
        func_id, func_desc, doc_id, config_name, page_number, page_text
    )