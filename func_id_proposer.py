"""
func_id_proposer.py
-------------------
Proposta di FUNC ID e DESCRIZIONE FUNZIONE per le funzioni trovate
dall'opzione "Ricerca Funzioni" (foglio "Index Funzioni").

Le colonne A (FUNC ID) e B (DESCRIZIONE FUNZIONE) del foglio "Funzioni"
seguono una convenzione che viene APPRESA dalle funzioni gia' presenti:

  FUNC ID = <PREFISSO>_<titolo del paragrafo>
      PREFISSO  -> ricavato dal titolo del documento (DOC ID): e' il
                   prefisso piu' usato dalle funzioni gia' presenti con lo
                   stesso DOC ID ("FRS_Air Supply" -> "AIR"). Se il DOC ID
                   non ha ancora funzioni si usa INDEX_FUNC_ID_PREFIX_MAP
                   oppure un prefisso derivato dal titolo del documento.
      titolo    -> titolo del paragrafo nell'indice, spazi e " - " -> "_",
                   punteggiatura conservata ("Provision for Tilt system"
                   -> "Provision_for_Tilt_system").
      paragrafo padre -> per le sotto-funzioni il titolo del padre viene
                   anteposto se le funzioni esistenti lo fanno (modalita'
                   "auto"), se il titolo e' troppo generico ("Activation")
                   o per evitare un FUNC ID gia' usato.

  DESCRIZIONE = frase in italiano nello stile delle descrizioni esistenti
      ("Funzione per gestire ..."), generata da Ollama a partire dal
      titolo del documento, dal paragrafo padre e dal testo del paragrafo
      (INDEX_FUNC_DESC_MODE = "ai"), oppure da un modello di testo
      ("template"), oppure lasciata vuota ("off").

Se la funzione e' gia' presente nel foglio "Funzioni" i due valori
vengono semplicemente ricopiati.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Iterable, Optional

import config as cfg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parametri (con valori di riserva se config.py non e' aggiornato)
# ---------------------------------------------------------------------------

PREFIX_MAP      = getattr(cfg, "INDEX_FUNC_ID_PREFIX_MAP", {})
LEARN_PREFIX    = getattr(cfg, "INDEX_FUNC_ID_LEARN_FROM_SHEET", True)
PARENT_MODE     = getattr(cfg, "INDEX_FUNC_ID_PARENT_MODE", "auto")
SHORT_WORDS     = getattr(cfg, "INDEX_FUNC_ID_SHORT_TITLE_WORDS", 1)
EXISTING_FUZZY  = getattr(cfg, "INDEX_FUNC_ID_EXISTING_FUZZY", 0.9)
DESC_MODE       = getattr(cfg, "INDEX_FUNC_DESC_MODE", "ai")
DESC_TEMPLATE   = getattr(cfg, "INDEX_FUNC_DESC_TEMPLATE",
                          "Funzione per gestire {title} ({doc_title}, §{paragraph})")
DESC_EXAMPLES   = getattr(cfg, "INDEX_FUNC_DESC_EXAMPLES", 6)
DESC_MAX_CHARS  = getattr(cfg, "INDEX_FUNC_DESC_MAX_CHARS", 300)
DESC_INPUT_CHARS = getattr(cfg, "INDEX_FUNC_DESC_INPUT_CHARS", 3000)
DESC_CACHE_FILE = getattr(cfg, "INDEX_FUNC_DESC_CACHE_FILE", None)

_PLACEHOLDER_IDS  = {"funcxxx", "funcid"}
_PLACEHOLDER_DESC = {"", "xxxxx", "tbd", "descrizionefunzione"}


# ---------------------------------------------------------------------------
# Normalizzazione
# ---------------------------------------------------------------------------

def id_key(s: str) -> str:
    """Chiave di confronto: 'AIR_Provision_for_Tilt_system' -> 'airprovisionfortiltsystem'."""
    return re.sub(r"[\W_]+", "", (s or "").lower())


def _norm(s: str) -> str:
    t = re.sub(r"[\W_]+", " ", (s or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", s or "")


def title_to_id_part(title: str) -> str:
    """
    Titolo di paragrafo -> parte del FUNC ID, come nel foglio Funzioni:
      'Service Brake - Direct Electro-Pneumatic Brake'
          -> 'Service_Brake_Direct_Electro-Pneumatic_Brake'
      'Detection of Non-Rotating Axle (DNRA)'
          -> 'Detection_of_Non-Rotating_Axle_(DNRA)'
    """
    t = (title or "").replace("–", "-").replace("—", "-").strip()
    t = re.sub(r"\s+[-/]\s+|\s+", "_", t)
    t = re.sub(r"_+", "_", t)
    return t.strip("_ .")


def split_func_id(func_id: str) -> tuple[str, str]:
    """('AIR', 'Provision_for_Tilt_system') da 'AIR_Provision_for_Tilt_system'."""
    if "_" not in (func_id or ""):
        return "", func_id or ""
    prefix, rest = func_id.split("_", 1)
    return prefix, rest


def doc_title(doc_id: str) -> str:
    """'FRS_Air Supply' -> 'Air Supply' (titolo del documento)."""
    return doc_id.split("_", 1)[1].strip() if "_" in doc_id else doc_id.strip()


# ---------------------------------------------------------------------------
# Funzioni gia' presenti nel foglio "Funzioni"
# ---------------------------------------------------------------------------

@dataclass
class ExistingFunc:
    func_id: str
    description: str
    row: int
    doc_ids: list[str] = field(default_factory=list)

    @property
    def prefix(self) -> str:
        return split_func_id(self.func_id)[0]

    @property
    def key(self) -> str:
        """Chiave del FUNC ID senza prefisso."""
        return id_key(split_func_id(self.func_id)[1])


def read_existing_functions(ws) -> list[ExistingFunc]:
    """
    Funzioni del foglio "Funzioni":
      riga funzione  -> col A = FUNC ID, col B = descrizione
      righe documento -> col C = cartella, col D = DOC ID
    """
    out: list[ExistingFunc] = []
    cur: Optional[ExistingFunc] = None
    for r, row in enumerate(ws.iter_rows(min_row=2, max_col=4, values_only=True),
                            start=2):
        a, b, c, d = (list(row) + [None] * 4)[:4]
        a = "" if a is None else str(a).strip()
        if a:
            cur = None
            if id_key(a) in _PLACEHOLDER_IDS:
                continue
            cur = ExistingFunc(a, "" if b is None else str(b).strip(), r)
            out.append(cur)
        if cur is not None and c and d:
            doc = str(d).strip()
            if doc and doc not in ("\\", "/") and doc not in cur.doc_ids:
                cur.doc_ids.append(doc)
    return out


# ---------------------------------------------------------------------------
# Esito della proposta
# ---------------------------------------------------------------------------

@dataclass
class Proposal:
    func_id: str
    description: str
    existing: bool                 # True = ricopiata dal foglio Funzioni
    row: int = 0                   # riga nel foglio Funzioni (se esistente)
    note: str = ""                 # dettaglio per il commento della cella


# ---------------------------------------------------------------------------
# Proposer
# ---------------------------------------------------------------------------

class FuncIdProposer:
    """
    Apprende la convenzione dalle funzioni esistenti e propone FUNC ID e
    descrizione per le funzioni dell'indice.

    Le voci passate a resolve() devono avere gli attributi
    title, parent, level, index (vedi index_funzioni.FuncEntry).
    """

    def __init__(
        self,
        existing: list[ExistingFunc],
        desc_mode: str = DESC_MODE,
        llm: Optional[Callable[[str], str]] = None,
        cache_only: bool = False,
        parent_mode: str = PARENT_MODE,
        prefix_map: Optional[dict] = None,
        learn: bool = LEARN_PREFIX,
    ):
        self.existing = existing
        self.desc_mode = (desc_mode or "off").lower()
        self.llm = llm
        # True = descrizioni AI solo dalla cache (nessuna chiamata a Ollama)
        self.cache_only = cache_only
        self.parent_mode = (parent_mode or "auto").lower()
        self.prefix_map = {k.lower(): v for k, v in
                           (PREFIX_MAP if prefix_map is None else prefix_map).items()}
        self.learn = learn
        self.used_ids: set[str] = {id_key(e.func_id) for e in existing}
        self.prefix_source: dict[str, str] = {}
        self._prefixes: dict[str, str] = {}
        self.parent_votes = Counter()
        self.include_parent = False
        self._cache: dict[str, str] = {}
        self._cache_dirty = False

    # ── Cache su disco delle descrizioni AI ───────────────────────────────
    # Il foglio viene rigenerato a ogni esecuzione: senza cache il modello
    # verrebbe reinterpellato per tutte le funzioni nuove ogni volta.
    # Per forzare la rigenerazione cancellare INDEX_FUNC_DESC_CACHE_FILE.
    def load_cache(self) -> None:
        if not DESC_CACHE_FILE:
            return
        try:
            with open(DESC_CACHE_FILE, encoding="utf-8") as fh:
                self._cache = dict(json.load(fh))
        except FileNotFoundError:
            self._cache = {}
        except Exception as exc:
            log.warning(f"  [Index] Cache descrizioni non leggibile: {exc}")
            self._cache = {}

    def save_cache(self) -> None:
        if not DESC_CACHE_FILE or not self._cache_dirty:
            return
        try:
            from pathlib import Path
            Path(DESC_CACHE_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(DESC_CACHE_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, ensure_ascii=False, indent=1)
            self._cache_dirty = False
        except Exception as exc:
            log.warning(f"  [Index] Cache descrizioni non salvata: {exc}")

    # ── Funzioni esistenti per DOC ID ─────────────────────────────────────
    def _by_doc(self, doc_id: str) -> list[ExistingFunc]:
        d = doc_id.lower()
        return [e for e in self.existing if any(x.lower() == d for x in e.doc_ids)]

    # ── Prefisso ──────────────────────────────────────────────────────────
    def prefix_for(self, doc_id: str) -> str:
        if doc_id in self._prefixes:
            return self._prefixes[doc_id]
        p, src = "", ""
        if doc_id.lower() in self.prefix_map:
            p, src = self.prefix_map[doc_id.lower()], "config INDEX_FUNC_ID_PREFIX_MAP"
        elif self.learn:
            counts = Counter(e.prefix for e in self._by_doc(doc_id) if e.prefix)
            if counts:
                p = counts.most_common(1)[0][0]
                src = f"appreso da {counts[p]} funzioni del foglio Funzioni"
        if not p:
            p, src = self._derive_prefix(doc_id), "derivato dal titolo del documento"
        self._prefixes[doc_id] = p
        self.prefix_source[doc_id] = src
        return p

    def _taken_prefixes(self, doc_id: str) -> set[str]:
        taken = {e.prefix.upper() for e in self.existing
                 if e.prefix and doc_id.lower() not in (x.lower() for x in e.doc_ids)}
        taken |= {v.upper() for k, v in self._prefixes.items() if k != doc_id}
        taken |= {v.upper() for k, v in self.prefix_map.items() if k != doc_id.lower()}
        return taken

    def _derive_prefix(self, doc_id: str) -> str:
        """
        'Drive Control' -> 'DRI', 'TCMS - Operational' -> 'TCMS';
        se gia' usato da un altro DOC ID si prova con le iniziali.
        """
        words = _words(doc_title(doc_id))
        if not words:
            return "FUNC"
        first = words[0]
        cands = []
        if first.isupper() and len(first) >= 2:
            cands.append(first)
        cands.append(first[:3].upper())
        if len(words) > 1:
            cands.append("".join(w[0] for w in words).upper())
            cands.append((first[:3] + "".join(w[0] for w in words[1:])).upper())
        taken = self._taken_prefixes(doc_id)
        for c in cands:
            if c not in taken:
                return c
        n = 2
        while f"{cands[0]}{n}" in taken:
            n += 1
        return f"{cands[0]}{n}"

    # ── Abbinamento con le funzioni esistenti ─────────────────────────────
    @staticmethod
    def _keys(item) -> tuple[str, str]:
        own = id_key(item.title)
        with_parent = id_key((item.parent or "") + item.title) if item.parent else ""
        return own, with_parent

    def _match_block(self, doc_id: str, items: list) -> dict[int, tuple[ExistingFunc, str]]:
        """{posizione voce: (funzione esistente, 'own'|'parent'|'fuzzy')}"""
        cands = self._by_doc(doc_id)
        found: dict[int, tuple[ExistingFunc, str]] = {}
        used: set[int] = set()
        # 1) chiave esatta (titolo o padre + titolo)
        for i, it in enumerate(items):
            own, wp = self._keys(it)
            for e in cands:
                if e.row in used:
                    continue
                if e.key == own or (wp and e.key == wp):
                    found[i] = (e, "own" if e.key == own else "parent")
                    used.add(e.row)
                    break
        # 2) somiglianza del testo
        for i, it in enumerate(items):
            if i in found:
                continue
            best, best_r = None, 0.0
            t = _norm(it.title)
            for e in cands:
                if e.row in used:
                    continue
                r = SequenceMatcher(None, _norm(split_func_id(e.func_id)[1]), t).ratio()
                if r > best_r:
                    best, best_r = e, r
            if best is not None and best_r >= EXISTING_FUZZY:
                found[i] = (best, "fuzzy")
                used.add(best.row)
        return found

    # ── FUNC ID nuovo ─────────────────────────────────────────────────────
    def _wants_parent(self, item) -> bool:
        if item.level < 2 or not item.parent:
            return False
        if self.parent_mode == "always":
            return True
        if self.parent_mode == "never":
            return False
        if self.include_parent:
            return True
        # Titolo troppo generico ("Activation"): senza il padre sarebbe ambiguo
        return len(_words(item.title)) <= SHORT_WORDS

    def propose_id(self, doc_id: str, item) -> tuple[str, str]:
        prefix = self.prefix_for(doc_id)
        own = title_to_id_part(item.title)
        parent = title_to_id_part(item.parent) if item.parent else ""
        note = ""
        if self._wants_parent(item) and parent and \
                not id_key(own).startswith(id_key(parent)):
            body, note = f"{parent}_{own}", "titolo del paragrafo padre anteposto"
        else:
            body = own
        fid = f"{prefix}_{body}"
        if id_key(fid) in self.used_ids and parent and body == own:
            fid, note = f"{prefix}_{parent}_{own}", \
                "padre anteposto per evitare un FUNC ID gia' usato"
        if id_key(fid) in self.used_ids:
            base, n = fid, 2
            while id_key(f"{base}_{n}") in self.used_ids:
                n += 1
            fid, note = f"{base}_{n}", "suffisso aggiunto per evitare un FUNC ID gia' usato"
        self.used_ids.add(id_key(fid))
        return fid, note

    # ── Descrizione nuova ─────────────────────────────────────────────────
    def _examples(self, doc_id: str) -> list[ExistingFunc]:
        def ok(e: ExistingFunc) -> bool:
            return id_key(e.description) not in _PLACEHOLDER_DESC
        same = [e for e in self._by_doc(doc_id) if ok(e)]
        out = same[:DESC_EXAMPLES]
        if len(out) < DESC_EXAMPLES:
            seen_docs: set[str] = set()
            for e in self.existing:          # un esempio per DOC ID: varieta'
                if len(out) >= DESC_EXAMPLES:
                    break
                d = (e.doc_ids or [""])[0].lower()
                if e in out or not ok(e) or d in seen_docs:
                    continue
                seen_docs.add(d)
                out.append(e)
        return out

    def _template(self, doc_id: str, item) -> str:
        try:
            return DESC_TEMPLATE.format(
                title=item.title, doc_title=doc_title(doc_id), doc_id=doc_id,
                paragraph=item.index or "-", parent=item.parent or "",
            ).strip()
        except (KeyError, IndexError, ValueError) as exc:
            log.warning(f"  [Index] INDEX_FUNC_DESC_TEMPLATE non valido: {exc}")
            return f"Funzione per gestire {item.title} ({doc_title(doc_id)})"

    def build_prompt(self, doc_id: str, item, func_id: str, text: str) -> str:
        examples = "\n".join(
            f"- {e.func_id}: {e.description}" for e in self._examples(doc_id))
        parent = f"Paragrafo padre: {item.parent}\n" if item.parent else ""
        body = (text or "").strip()[:DESC_INPUT_CHARS] or "(testo non disponibile)"
        return (
            "Sei un tecnico ferroviario esperto di sistemi ETR1000.\n"
            "Nel foglio 'Funzioni' ogni funzione ha un FUNC ID e una "
            "DESCRIZIONE FUNZIONE. Esempi gia' presenti:\n"
            f"{examples or '- (nessun esempio disponibile)'}\n\n"
            "Scrivi la DESCRIZIONE FUNZIONE per questa nuova funzione:\n"
            f"Documento: {doc_id} (titolo: {doc_title(doc_id)})\n"
            f"{parent}"
            f"Paragrafo: {item.index} {item.title}\n"
            f"FUNC ID: {func_id}\n\n"
            f"--- TESTO DEL PARAGRAFO ---\n{body}\n\n"
            "REGOLE\n"
            "1. Una sola frase in italiano tecnico, nello stesso stile e con "
            "la stessa struttura degli esempi (es. 'Funzione per ...').\n"
            f"2. Massimo {DESC_MAX_CHARS} caratteri. Niente elenchi.\n"
            "3. Descrivi lo scopo della funzione; non citare codici di "
            "documento, numeri di paragrafo, pagine o ID di requisiti.\n"
            "4. Non inventare dettagli che non compaiono nel testo.\n\n"
            'Rispondi SOLO con questo JSON:\n{"descrizione": "..."}'
        )

    def describe(self, doc_id: str, item, func_id: str,
                 text_for: Optional[Callable] = None) -> tuple[str, str]:
        if self.desc_mode == "off":
            return "", ""
        if self.desc_mode == "ai" and (self.llm is not None or self.cache_only):
            text = ""
            if text_for is not None:
                try:
                    text = text_for(item) or ""
                except Exception as exc:
                    log.debug(f"  [Index] testo di '{item.title}' non estratto: {exc}")
            prompt = self.build_prompt(doc_id, item, func_id, text)
            key = hashlib.sha1(f"{getattr(cfg, 'OLLAMA_MODEL', '')}|{prompt}"
                               .encode("utf-8")).hexdigest()
            if key in self._cache:
                return self._cache[key], "descrizione generata da Ollama (cache)"
            desc = _parse_description(self.llm(prompt)) if self.llm else ""
            if desc:
                desc = _limit(desc, DESC_MAX_CHARS)
                self._cache[key] = desc
                self._cache_dirty = True
                return desc, "descrizione generata da Ollama"
            if self.llm:
                log.info(f"  [Index] {func_id}: descrizione AI non disponibile, uso il modello")
        return _limit(self._template(doc_id, item), DESC_MAX_CHARS), \
            "descrizione dal modello INDEX_FUNC_DESC_TEMPLATE"

    # ── Elaborazione completa ─────────────────────────────────────────────
    def resolve(self, blocks: Iterable[tuple[str, list]],
                text_for: Optional[Callable[[str, object], str]] = None
                ) -> list[list[Proposal]]:
        """
        blocks = [(doc_id, [voci])]. Ritorna, per ogni blocco, una
        Proposal per voce (stesso ordine).

        Primo passaggio: abbina le voci alle funzioni esistenti e conta
        quante sotto-funzioni esistenti includono il titolo del padre.
        Secondo passaggio: propone FUNC ID e descrizione per le nuove.
        """
        blocks = list(blocks)
        if self.desc_mode == "ai" and (self.llm is not None or self.cache_only):
            self.load_cache()
        matches = []
        for doc_id, items in blocks:
            m = self._match_block(doc_id, items)
            matches.append(m)
            for i, (_, how) in m.items():
                it = items[i]
                if it.level >= 2 and it.parent and how in ("own", "parent") and \
                        id_key(it.parent) not in id_key(it.title):
                    self.parent_votes[how] += 1
        self.include_parent = self.parent_votes["parent"] > self.parent_votes["own"]
        if self.parent_mode == "auto":
            log.info(f"  [Index] FUNC ID sotto-funzioni: padre "
                     f"{'incluso' if self.include_parent else 'escluso'} "
                     f"(esistenti con padre: {self.parent_votes['parent']}, "
                     f"senza: {self.parent_votes['own']}); titoli di "
                     f"{SHORT_WORDS} parola/e -> padre anteposto")

        out: list[list[Proposal]] = []
        for (doc_id, items), m in zip(blocks, matches):
            props: list[Proposal] = []
            for i, it in enumerate(items):
                if i in m:
                    e, how = m[i]
                    note = (f"Gia' presente nel foglio Funzioni (riga {e.row}): "
                            f"valori ricopiati"
                            + (" — abbinamento per somiglianza" if how == "fuzzy" else ""))
                    props.append(Proposal(e.func_id, e.description, True, e.row, note))
                    continue
                fid, id_note = self.propose_id(doc_id, it)
                tf = (lambda x, _d=doc_id: text_for(_d, x)) if text_for else None
                desc, d_note = self.describe(doc_id, it, fid, tf)
                parts = [f"Proposta — prefisso '{self.prefix_for(doc_id)}' "
                         f"({self.prefix_source.get(doc_id, '')})"]
                if it.parent:
                    parts.append(f"paragrafo padre: {it.parent}")
                parts += [p for p in (id_note, d_note) if p]
                props.append(Proposal(fid, desc, False, 0, "; ".join(parts)))
                log.info(f"  [Index] Nuova funzione: {fid}")
            out.append(props)
            self.save_cache()        # salvataggio progressivo
        return out


# ---------------------------------------------------------------------------
# Utilita'
# ---------------------------------------------------------------------------

def _parse_description(raw: str) -> str:
    if not raw or raw.lstrip().startswith("[Errore AI"):
        return ""
    try:
        from llm_json import parse_json_relaxed
        rec = parse_json_relaxed(raw, campi_testo=("descrizione",))
        if rec:
            return str(rec.data.get("descrizione") or "").strip()
    except Exception:                                    # pragma: no cover
        pass
    return ""


def _limit(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def ollama_llm() -> Optional[Callable[[str], str]]:
    """Funzione di chiamata a Ollama, o None se il modello non e' disponibile."""
    try:
        import ai_synthesizer
    except Exception as exc:                             # pragma: no cover
        log.warning(f"  [Index] Ollama non utilizzabile: {exc}")
        return None
    if not ai_synthesizer.check_ollama():
        return None
    budget = ai_synthesizer._token_budget(DESC_MAX_CHARS)
    return lambda prompt: ai_synthesizer._call_ollama(prompt, num_predict=budget)
