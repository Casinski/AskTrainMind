"""
llm_json.py
-----------
Lettura tollerante delle risposte JSON del modello locale.

PERCHE' SERVE
  Ollama interrompe la generazione al raggiungimento di `num_predict`:
  la risposta arriva TRONCATA A META' DI UNA STRINGA e `json.loads()`
  fallisce con "Unterminated string starting at: line 1 column N".
  Era la causa dei WARNING

      [Summary] parsing fallito su <funzione>: Unterminated string ...
      [Summary] <funzione> / <config>: riassunto LLM non disponibile

  che facevano degradare OGNI riassunto a semplice estratto testuale.

STRATEGIA A CASCATA
  1. `json.loads` sul testo ripulito (code fence, prefissi, virgole finali).
  2. Riparazione del troncamento: chiusura della stringa aperta e delle
     parentesi mancanti. Il contenuto gia' generato viene conservato.
  3. Estrazione diretta dei campi richiesti con espressione regolare,
     anche quando la struttura e' irrecuperabile.

Il valore recuperato e' sempre il testo EFFETTIVAMENTE prodotto dal
modello: non viene mai inventato nulla.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger(__name__)

__all__ = ["parse_json_relaxed", "JsonRecovery"]


class JsonRecovery:
    """Esito della lettura: dati + come sono stati ottenuti."""

    __slots__ = ("data", "repaired", "truncated", "method")

    def __init__(self, data: dict, repaired: bool = False,
                 truncated: bool = False, method: str = "strict"):
        self.data = data
        self.repaired = repaired
        self.truncated = truncated
        self.method = method

    def __bool__(self) -> bool:
        return bool(self.data)


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _clean(raw: str) -> str:
    """Toglie code fence, testo prima della prima graffa e virgole finali."""
    testo = _FENCE_RE.sub("", (raw or "").strip())
    i = testo.find("{")
    if i > 0:
        testo = testo[i:]
    return _TRAILING_COMMA_RE.sub(r"\1", testo.strip())


def _close_truncated(testo: str) -> str | None:
    """
    Chiude un JSON interrotto a meta'.

    Scorre i caratteri tenendo conto di stringhe ed escape: alla fine
    chiude l'eventuale stringa aperta, elimina una coppia chiave/valore
    rimasta a meta' e aggiunge le parentesi mancanti.
    """
    if not testo.startswith("{"):
        return None

    stack: list[str] = []
    in_str = False
    esc = False
    for ch in testo:
        if esc:
            esc = False
            continue
        if ch == "\\":
            if in_str:
                esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()

    if not stack and not in_str:
        return None                      # non e' troncato

    fuori = testo
    if esc:                              # troncato su una sequenza di escape
        fuori = fuori[:-1]
    if in_str:
        # Il backslash finale renderebbe l'ultima virgoletta un escape.
        while fuori.endswith("\\"):
            fuori = fuori[:-1]
        fuori += '"'
    else:
        # Troncato subito dopo una virgola o dopo una chiave senza valore
        fuori = fuori.rstrip()
        if fuori.endswith(","):
            fuori = fuori[:-1]
        elif fuori.endswith(":"):
            fuori += '""'

    for ch in reversed(stack):
        fuori += "}" if ch == "{" else "]"
    return fuori


def _regex_fields(testo: str, campi) -> dict:
    """Recupero dei singoli campi quando la struttura non e' riparabile."""
    out: dict = {}
    for campo in campi or ():
        m = re.search(rf'"{re.escape(campo)}"\s*:\s*"(.*)', testo, re.DOTALL)
        if m:
            val = m.group(1)
            # Fine della stringa: la prima virgoletta non preceduta da "\"
            fine = re.search(r'(?<!\\)"', val)
            if fine:
                val = val[: fine.start()]
            try:
                val = json.loads(f'"{val.rstrip(chr(92))}"')
            except Exception:
                val = val.replace('\\n', '\n').replace('\\"', '"')
            if val.strip():
                out[campo] = val.strip()
            continue
        m = re.search(rf'"{re.escape(campo)}"\s*:\s*(-?\d+(?:\.\d+)?)', testo)
        if m:
            out[campo] = m.group(1)
    return out


def parse_json_relaxed(raw: str, campi_testo=()) -> JsonRecovery:
    """
    Legge la risposta del modello restituendo sempre un JsonRecovery.

    Args:
        raw         : risposta grezza del modello
        campi_testo : nomi dei campi da recuperare in extremis via regex
                      (es. ("riassunto",) oppure ("differenze", "score"))

    Returns:
        JsonRecovery con `data` vuoto solo se non c'e' davvero nulla di
        utilizzabile nella risposta.
    """
    testo = _clean(raw)
    if not testo:
        return JsonRecovery({}, method="vuoto")

    try:
        data = json.loads(testo)
        if isinstance(data, dict):
            return JsonRecovery(data, method="strict")
    except Exception:
        pass

    # Prima graffa → ultima graffa (il modello puo' aggiungere commenti)
    m = re.search(r"\{.*\}", testo, re.DOTALL)
    if m:
        try:
            data = json.loads(_TRAILING_COMMA_RE.sub(r"\1", m.group()))
            if isinstance(data, dict):
                return JsonRecovery(data, method="blocco")
        except Exception:
            pass

    riparato = _close_truncated(testo)
    if riparato:
        try:
            data = json.loads(riparato)
            if isinstance(data, dict):
                return JsonRecovery(
                    data, repaired=True, truncated=True, method="riparato"
                )
        except Exception:
            pass

    campi = _regex_fields(testo, campi_testo)
    if campi:
        return JsonRecovery(
            campi, repaired=True, truncated=True, method="regex"
        )

    return JsonRecovery({}, method="fallito")
