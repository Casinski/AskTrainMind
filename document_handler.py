

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

import config as cfg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ricerca file locale da URL SharePoint
# ---------------------------------------------------------------------------

def _extract_relative_path(url: str) -> Optional[str]:
    """
    Estrae il percorso relativo dall'URL SharePoint costruito da url_builder.

    Esempio:
        URL input:
            https://gruppofsitaliane.sharepoint.com/:f:/r/sites/.../
            DOC_FLOTTE/VZI_Base/CONFIG/FRS/3EST000225-7907.pdf#page=7

        Percorso relativo estratto:
            VZI_Base/CONFIG/FRS/3EST000225-7907.pdf

    Lo script cerca "DOC_FLOTTE/" nell'URL e prende tutto quello che viene dopo,
    rimuovendo il frammento #page=N finale.
    """
    if not url:
        return None

    # Rimuovi #page=N
    url_clean = re.sub(r"#page=\d+$", "", url.strip())

    # Decodifica caratteri URL (%20 → spazio, ecc.)
    url_decoded = unquote(url_clean)

    # Cerca il punto di ancoraggio "DOC_FLOTTE/" nell'URL
    # Tutto quello che viene dopo è il percorso relativo del file
    anchor = "DOC_FLOTTE/"
    idx = url_decoded.find(anchor)
    if idx == -1:
        # Fallback: prova con "DOC_FLOTTE" senza slash finale
        anchor = "DOC_FLOTTE"
        idx = url_decoded.find(anchor)
        if idx == -1:
            log.warning(f"  'DOC_FLOTTE' non trovato nell'URL: {url_decoded[:100]}")
            return None

    relative = url_decoded[idx + len(anchor):]
    # Rimuovi eventuale slash iniziale
    relative = relative.lstrip("/")
    return relative


def _find_local_file(relative_path: str) -> Optional[Path]:
    """
    Cerca il file nel percorso OneDrive locale.

    Strategia a cascata:
      1. Percorso esatto: ONEDRIVE_DOCS_ROOT / relative_path
      2. Ricerca ricorsiva per nome file (per differenze nei separatori o sottocartelle)
      3. Ricerca case-insensitive (Windows è case-insensitive ma Path non sempre)
    """
    if not relative_path:
        return None

    # Normalizza i separatori (/ → \\ su Windows)
    rel = Path(relative_path.replace("/", "\\"))
    file_name = rel.name   # solo il nome file, es. "3EST000225-7907.pdf"

    # ── Strategia 1: percorso esatto ──────────────────────────────────────
    candidate = cfg.ONEDRIVE_DOCS_ROOT / rel
    if candidate.exists():
        log.info(f"  📁 File trovato (percorso esatto): {candidate}")
        return candidate

    # ── Strategia 2: ricerca ricorsiva per nome file ──────────────────────
    # Utile se la struttura di cartelle locale differisce leggermente dall'URL
    log.debug(
        f"  Percorso esatto non trovato: {candidate}\n"
        f"  Ricerca ricorsiva per '{file_name}'..."
    )
    matches = list(cfg.ONEDRIVE_DOCS_ROOT.rglob(file_name))
    if matches:
        # Se ci sono più risultati, preferisci quello il cui percorso
        # contiene le stesse sottocartelle dell'URL
        rel_parts = set(rel.parts[:-1])  # cartelle senza il nome file
        best = None
        best_score = -1
        for m in matches:
            score = sum(1 for part in m.parts if part in rel_parts)
            if score > best_score:
                best_score = score
                best = m
        log.info(f"  📁 File trovato (ricerca ricorsiva): {best}")
        return best

    # ── Strategia 3: ricerca case-insensitive ─────────────────────────────
    file_name_lower = file_name.lower()
    matches_ci = [
        p for p in cfg.ONEDRIVE_DOCS_ROOT.rglob("*")
        if p.name.lower() == file_name_lower
    ]
    if matches_ci:
        log.info(f"  📁 File trovato (case-insensitive): {matches_ci[0]}")
        return matches_ci[0]

    log.warning(
        f"  ⚠ File non trovato sul disco locale:\n"
        f"    Cercato : {candidate}\n"
        f"    Root    : {cfg.ONEDRIVE_DOCS_ROOT}\n"
        f"    File    : {file_name}\n"
        f"    Verifica che OneDrive sia sincronizzato e che il file esista."
    )
    return None


def download(url: str) -> Optional[Path]:
    """
    Punto di ingresso principale: dato un URL SharePoint,
    trova il file corrispondente nella cartella OneDrive locale.

    Nessuna autenticazione, nessuna rete — tutto locale.

    Args:
        url: URL SharePoint completo con #page=N
             es. "https://.../DOC_FLOTTE/VZI_Base/CONFIG/FRS/file.pdf#page=7"

    Returns:
        Path del file locale, o None se non trovato.
    """
    if not url:
        return None

    log.info(f"  🔍 Ricerca locale per: {url[:80]}...")

    # Verifica che la cartella OneDrive esista
    if not cfg.ONEDRIVE_DOCS_ROOT.exists():
        log.error(
            f"  ❌ Cartella OneDrive non trovata: {cfg.ONEDRIVE_DOCS_ROOT}\n"
            f"  Verifica il percorso ONEDRIVE_DOCS_ROOT in config.py\n"
            f"  e che OneDrive sia sincronizzato."
        )
        return None

    relative = _extract_relative_path(url)
    if not relative:
        log.warning(f"  ⚠ Impossibile estrarre percorso relativo da: {url[:80]}")
        return None

    log.debug(f"  Percorso relativo estratto: {relative}")
    return _find_local_file(relative)


# ---------------------------------------------------------------------------
# Estrazione testo dalla pagina
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Estrazione testo dalla pagina
# ---------------------------------------------------------------------------

def extract_page_text(
    doc_path: Path,
    page_number: int,
    func_desc: str = "",
    func_id: str = "",
    max_extra_pages: int = 15,
) -> tuple[str, int, bool, bool]:
    """
    Estrae il testo a partire dalla pagina indicata (Rif. Pagina) fino alla
    fine della sezione/funzione corrente.

    Parametri:
        doc_path        : percorso del file PDF o DOCX
        page_number     : pagina iniziale 1-based (da Rif. Pagina)
        func_desc       : descrizione funzione (può essere in italiano)
        func_id         : ID funzione es. "LV_Pantograph_Lifting" (in inglese)
                          usato in combinazione con func_desc per trovare
                          l'indice corretto nella pagina
        max_extra_pages : numero massimo di pagine aggiuntive da leggere

    Restituisce:
        (testo_estratto, pagina_finale, start_is_partial, end_is_partial)
    """
    suffix = doc_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(doc_path, page_number, func_desc, func_id, max_extra_pages)
    elif suffix in (".docx", ".doc"):
        text = _extract_docx(doc_path)
        return text, page_number, False, False
    else:
        log.warning(f"  ⚠ Formato non supportato: {suffix}")
        return "", page_number, False, False


# ---------------------------------------------------------------------------
# Helpers — indici numerici di sezione
# ---------------------------------------------------------------------------

def _is_valid_section_index(idx: str) -> bool:
    """
    Restituisce True se idx è un indice di sezione valido.

    Criteri:
      1. Almeno 2 livelli (N.N): "3.2" sì, "5" no
      2. Ogni parte deve essere numerica pura: "3.2" sì, "2F.04" no
      3. Non deve essere un numero di revisione tipo "5.0"
         (esattamente 2 livelli con secondo livello = 0)
      4. Non più di 6 livelli (difesa da codici tecnici anomali)
    """
    parts = idx.split(".")
    if len(parts) < 2:
        return False
    for part in parts:
        if not part.isdigit():
            return False
    if len(parts) == 2 and parts[1] == "0":
        return False
    if len(parts) > 6:
        return False
    return True


def _clean_title(raw: str) -> str:
    """
    Rimuove caratteri spuri all'inizio di un titolo di sezione.
    Tipici nei PDF tecnici ferroviari:
      "+Pantograph - Lifting"  → "Pantograph - Lifting"
      "•Country Code"          → "Country Code"
      "\uf02aPantograph"       → "Pantograph"
    """
    cleaned = re.sub(r"^[\+\-–—•\*·►▪▸\uf02a\uf0b7\uf0d8\uf020\s]+", "", raw)
    return cleaned.strip()


def _extract_all_indexes(text: str) -> list[tuple[str, str]]:
    """
    Estrae TUTTI gli indici di sezione dall'intero testo della pagina.
    Restituisce lista di (indice, titolo).

    Stessa logica di _extract_all_indexes_full ma senza offset.
    Passa righe precedente/successiva a _is_section_heading_line.
    """
    normalized = text.replace("\xa0", " ").replace("\t", " ")
    lines = [ln.strip() for ln in normalized.splitlines()]

    results: list[tuple[str, str]] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1] if i + 1 < len(lines) else ""

        # ── Formato A ─────────────────────────────────────────────────
        m = re.match(r"^(\d+(?:\.\d+){1,})\s+(.+)$", line)
        if m:
            idx   = m.group(1).strip()
            title = _clean_title(re.sub(r"\s+", " ", m.group(2)).strip())
            if (_is_valid_section_index(idx) and
                    _is_section_heading_line(line, idx, prev_line, next_line)):
                results.append((idx, title))
            i += 1
            continue

        # ── Formato B ─────────────────────────────────────────────────
        m2 = re.match(r"^(\d+(?:\.\d+){1,})\s*$", line)
        if m2:
            idx = m2.group(1).strip()
            if (_is_valid_section_index(idx) and
                    _is_section_heading_line(line, idx, prev_line, next_line)):
                title = ""
                for lookahead in range(1, 4):
                    if i + lookahead >= len(lines):
                        break
                    candidate = lines[i + lookahead].strip()
                    if not candidate:
                        continue
                    if re.match(r"^\d+(?:\.\d+)+", candidate):
                        break
                    cleaned = _clean_title(candidate)
                    if cleaned and re.search(r"[a-zA-Z]", cleaned):
                        title = re.sub(r"\s+", " ", cleaned).strip()
                        break
                results.append((idx, title))
            i += 1
            continue

        i += 1

    # Applica filtro progressività
    results_with_dummy = [(idx, title, i) for i, (idx, title) in enumerate(results)]
    filtered = _filter_progressive_indexes(results_with_dummy)
    return [(idx, title) for idx, title, _ in filtered]

def _is_section_heading_line(
    line: str,
    idx: str,
    prev_line: str = "",
    next_line: str = "",
) -> bool:
    """
    Verifica che l'indice `idx` trovato nella riga `line` sia un titolo
    di sezione reale e NON un riferimento incrociato nel testo.

    Gestisce tutti i casi osservati nei documenti ETR/Bombardier:

    CASO 1 — Indice nel mezzo della riga (riferimento incrociato):
        "voltage selector, see chapter 3.3.5"
        → 3.3.5 non è all'inizio della riga → ESCLUSO

    CASO 2 — Indice da solo ma riga successiva inizia con virgolette:
        "3.2.5"
        '"Pantograph selection").'
        → la riga successiva inizia con " → ESCLUSO

    CASO 3 — Riga precedente contiene parole chiave di riferimento:
        "see chapter"
        "3.2.5"
        → riga prima contiene "chapter"/"see"/"refer" → ESCLUSO

    CASO 4 — Indice da solo su riga (Formato B valido):
        "3.2.1"
        "Pantograph - Lifting"
        → riga da sola, successiva inizia con lettera → INCLUSO ✅

    CASO 5 — Indice + titolo sulla stessa riga (Formato A valido):
        "3.2.1.1.1 Normal Condition"
        → inizia con indice seguito da testo senza virgolette → INCLUSO ✅
    """
    stripped = line.strip()

    # ── Controllo 1: l'indice deve essere all'INIZIO della riga ──────────
    # Se la riga NON inizia con l'indice, è un riferimento nel mezzo del testo
    if not re.match(r"^\d+(?:\.\d+)+", stripped):
        return False

    # ── Controllo 2: riga precedente contiene parole di riferimento ───────
    REFERENCE_WORDS = {
        "chapter", "see", "refer", "section", "paragraph",
        "capitolo", "vedi", "cfr", "paragrafo", "par", "sezione",
    }
    if prev_line:
        prev_words = set(re.findall(r"[a-zA-Z]{2,}", prev_line.lower()))
        if prev_words & REFERENCE_WORDS:
            log.debug(
                f"  [heading] '{idx}' escluso: riga precedente contiene "
                f"parola di riferimento ({prev_words & REFERENCE_WORDS})"
            )
            return False

    # ── Formato A: indice + titolo sulla stessa riga ──────────────────────
    m = re.match(r"^(\d+(?:\.\d+)+)\s+(.+)$", stripped)
    if m:
        after = m.group(2).strip()
        # Se il testo dopo l'indice inizia con virgolette o parentesi
        # è un riferimento incrociato: 3.2.5 "Pantograph selection"
        if re.match(r'^["\'\(\[]', after):
            log.debug(
                f"  [heading] '{idx}' escluso: titolo inizia con "
                f"carattere di citazione ('{after[:20]}')"
            )
            return False
        return True

    # ── Formato B: indice da solo sulla riga ──────────────────────────────
    if re.match(r"^\d+(?:\.\d+)+\s*$", stripped):
        # Se la riga successiva inizia con virgolette o parentesi
        # è un riferimento incrociato: 3.2.5 / "Pantograph selection").
        if next_line:
            next_stripped = next_line.strip()
            if re.match(r'^["\'\(\[]', next_stripped):
                log.debug(
                    f"  [heading] '{idx}' escluso: riga successiva inizia "
                    f"con carattere di citazione ('{next_stripped[:20]}')"
                )
                return False
            # Se la riga successiva è la continuazione di una frase
            # (inizia con minuscolo e non è un titolo), potrebbe essere
            # un riferimento: es. "3.2.5" / "selection)."
            if re.match(r'^[a-z]', next_stripped) and re.search(r'[)\.]$', next_stripped):
                log.debug(
                    f"  [heading] '{idx}' escluso: riga successiva sembra "
                    f"continuazione frase ('{next_stripped[:30]}')"
                )
                return False
        return True

    return False

def _extract_all_indexes_full(text: str) -> list[tuple[str, str, int]]:
    """
    Scansiona TUTTO il testo e restituisce tutti gli indici di sezione
    con la loro posizione (offset carattere).

    Passa le righe precedente e successiva a _is_section_heading_line
    per distinguere titoli reali da riferimenti incrociati come:
      - "see chapter 3.3.5"   (indice nel mezzo della riga)
      - "3.2.5"               (indice solo, riga dopo inizia con virgolette)
      - riga prima = "chapter" poi "3.2.5" su riga dedicata

    Applica poi _filter_progressive_indexes per eliminare
    salti non sequenziali residui.
    """
    normalized = text.replace("\xa0", " ").replace("\t", " ")
    results: list[tuple[str, str, int]] = []

    lines_with_pos: list[tuple[str, int]] = []
    pos = 0
    for line in normalized.splitlines(keepends=True):
        lines_with_pos.append((line.rstrip("\n\r"), pos))
        pos += len(line)

    i = 0
    while i < len(lines_with_pos):
        raw_line, line_offset = lines_with_pos[i]
        line = raw_line.strip()

        prev_line = lines_with_pos[i - 1][0] if i > 0 else ""
        next_line = lines_with_pos[i + 1][0] if i + 1 < len(lines_with_pos) else ""

        # ── Formato A: indice + titolo sulla stessa riga ──────────────
        m = re.match(r"^(\d+(?:\.\d+){1,})\s+(.+)$", line)
        if m:
            idx   = m.group(1).strip()
            title = _clean_title(re.sub(r"\s+", " ", m.group(2)).strip())
            if (_is_valid_section_index(idx) and
                    _is_section_heading_line(line, idx, prev_line, next_line)):
                results.append((idx, title, line_offset))
            i += 1
            continue

        # ── Formato B: indice da solo sulla riga ──────────────────────
        m2 = re.match(r"^(\d+(?:\.\d+){1,})\s*$", line)
        if m2:
            idx = m2.group(1).strip()
            if (_is_valid_section_index(idx) and
                    _is_section_heading_line(line, idx, prev_line, next_line)):
                title = ""
                for lookahead in range(1, 4):
                    if i + lookahead >= len(lines_with_pos):
                        break
                    next_l = lines_with_pos[i + lookahead][0].strip()
                    if not next_l:
                        continue
                    if re.match(r"^\d+(?:\.\d+)+", next_l):
                        break
                    cleaned = _clean_title(next_l)
                    if cleaned and re.search(r"[a-zA-Z]", cleaned):
                        title = re.sub(r"\s+", " ", cleaned).strip()
                        break
                results.append((idx, title, line_offset))
            i += 1
            continue

        i += 1

    results.sort(key=lambda x: x[2])
    results = _filter_progressive_indexes(results)
    return results

def _index_is_sequential(prev: str, curr: str) -> bool:
    """
    Verifica che `curr` sia un passo sequenziale valido dopo `prev`
    nella struttura ad albero del documento.

    Passi validi:
      - Approfondimento (figlio):    "3.2.1" → "3.2.1.1"
      - Fratello successivo:         "3.2.1" → "3.2.2"
      - Ritorno a livello superiore: "3.2.1" → "3.3"
      - Stesso indice (ripetuto):    "3.2.1" → "3.2.1"

    Passi NON validi (salti anomali tipici di riferimenti incrociati):
      - Salto in avanti sullo stesso livello con gap > soglia:
        "3.2.1" → "3.2.5"  (salta 3.2.2, 3.2.3, 3.2.4)
        Solo se il gap è > MAX_SIBLING_GAP (default 3)

    Nota: i salti in avanti nel documento sono normali (es. si passa
    da 3.2.1 a 3.3 saltando 3.2.2 perché quella pagina non è presente),
    ma un salto di 4+ fratelli sullo stesso livello nello stesso testo
    è quasi certamente un riferimento incrociato.
    """
    MAX_SIBLING_GAP = 3

    prev_parts = [int(x) for x in prev.rstrip(".").split(".")]
    curr_parts = [int(x) for x in curr.rstrip(".").split(".")]

    # Stesso indice: ok
    if prev_parts == curr_parts:
        return True

    # Figlio (curr più profondo e inizia con prev): ok
    if (len(curr_parts) > len(prev_parts) and
            curr_parts[:len(prev_parts)] == prev_parts):
        return True

    # Ritorno a livello superiore o cambio di ramo: ok
    # (es. 3.2.1.1 → 3.2.2  oppure  3.2.1 → 3.3)
    common_depth = min(len(prev_parts), len(curr_parts))
    for d in range(common_depth):
        if curr_parts[d] > prev_parts[d]:
            # curr avanza rispetto a prev a profondità d
            # Verifica il gap solo se sono allo stesso livello esatto
            if len(curr_parts) == len(prev_parts) == d + 1:
                gap = curr_parts[d] - prev_parts[d]
                if gap > MAX_SIBLING_GAP:
                    return False
            return True
        elif curr_parts[d] < prev_parts[d]:
            # curr torna indietro (es. 3.2.2 → 3.1.x): non sequenziale
            return False

    return True


def _filter_progressive_indexes(
    indexes: list[tuple[str, str, int]],
) -> list[tuple[str, str, int]]:
    """
    Dato un elenco di (indice, titolo, offset) già ordinato per offset,
    rimuove gli indici che non sono sequenzialmente coerenti con il
    precedente indice confermato.

    Questo elimina i riferimenti incrociati come "see chapter 3.2.5"
    che appaiono come indici validi ma interrompono la progressione.
    """
    if not indexes:
        return []

    filtered = [indexes[0]]

    for item in indexes[1:]:
        idx_curr = item[0]
        idx_prev = filtered[-1][0]

        if _index_is_sequential(idx_prev, idx_curr):
            filtered.append(item)
        else:
            log.debug(
                f"  [progressività] '{idx_curr}' scartato dopo '{idx_prev}' "
                f"— salto non sequenziale (probabile riferimento incrociato)"
            )

    return filtered

def _normalize_for_match(text: str) -> set[str]:
    """
    Normalizza testo per confronto: rimuove underscore/trattini,
    converte in minuscolo, restituisce parole di almeno 4 caratteri.

    Es. "LV_Pantograph_Lifting" → {"pantograph", "lifting"}
    """
    cleaned = re.sub(r"[_\-/\\]", " ", text.lower())
    cleaned = re.sub(r"[^a-z\s]", " ", cleaned)
    return {w for w in cleaned.split() if len(w) >= 4}


def _find_function_index(
    indexes: list[tuple[str, str]],
    func_desc: str,
    func_id: str = "",
) -> Optional[str]:
    """
    Dato l'elenco di (indice, titolo) e il nome/descrizione della funzione,
    restituisce l'indice che meglio corrisponde alla funzione.

    FIX: usa ENTRAMBI func_id e func_desc per il confronto perché:
      - func_id  è in inglese  (es. "LV_Pantograph_Lifting")
      - func_desc può essere in italiano (es. "Comando di alzamento...")
      - I titoli nel PDF sono in inglese → solo func_id trova match

    Priorità:
      1. Maggiore sovrapposizione di parole chiave tra titolo e
         (func_id + func_desc combinati)
      2. Parità di score → indice più specifico (più livelli)
      3. Fallback → indice più profondo se score = 0 per tutti
    """
    if not indexes:
        log.info("  _find_function_index: lista indici VUOTA")
        return None

    # Combina func_id (inglese) + func_desc (italiano/inglese)
    combined   = f"{func_id} {func_desc}"
    func_words = _normalize_for_match(combined)

    log.debug(f"  [match] func_words = {func_words}")
    log.debug(f"  [match] indici candidati: {[(i, t) for i, t in indexes]}")

    best_index = None
    best_score = 0
    best_depth = -1

    for idx, title in indexes:
        title_words = _normalize_for_match(title)
        score       = len(func_words & title_words)
        depth       = idx.count(".")

        if score > best_score or (score == best_score and depth > best_depth):
            best_score = score
            best_depth = depth
            best_index = idx

    if best_score > 0:
        log.info(
            f"  🎯 Indice funzione: '{best_index}' "
            f"(score={best_score}, func_id='{func_id}')"
        )
    else:
        log.info(
            f"  🔍 Nessuna corrispondenza testuale per '{func_id}' / '{func_desc}' "
            f"— uso indice più profondo: '{best_index}'"
        )
    return best_index


def _index_belongs_to_section(candidate: str, section: str) -> bool:
    """
    True se `candidate` è uguale a `section` oppure è un suo sotto-indice.

    section = "3.2.1":
      "3.2.1"     → True   (stesso nodo)
      "3.2.1.1"   → True   (figlio)
      "3.2.1.1.9" → True   (nipote)
      "3.2.2"     → False  (fratello)
      "3.3"       → False  (zio)
      "3.2"       → False  (padre)
    """
    s = section.rstrip(".")
    c = candidate.rstrip(".")
    return c == s or c.startswith(s + ".")


# ---------------------------------------------------------------------------
# Helper — tronca testo alla prima sezione estranea
# ---------------------------------------------------------------------------

def _truncate_at_new_section(
    page_text: str,
    section_index: str,
) -> tuple[str, bool]:
    """
    Scansiona tutto il testo di una pagina e lo tronca al punto in cui
    appare il primo indice che NON appartiene alla sezione corrente.

    Restituisce:
        (testo_troncato, is_partial)
        is_partial = True se il testo è stato effettivamente troncato
    """
    all_idx = _extract_all_indexes_full(page_text)

    for idx, title, offset in all_idx:
        if not _index_belongs_to_section(idx, section_index):
            troncato = page_text[:offset].strip()
            log.info(
                f"  ✂ Testo troncato: indice estraneo '{idx} {title}' "
                f"trovato a offset {offset} — pagina parziale"
            )
            return troncato, True

    return page_text, False


# ---------------------------------------------------------------------------
# Similarità testuale  (Strategia B)
# ---------------------------------------------------------------------------

def _keyword_overlap(text_a: str, text_b: str, top_n: int = 30) -> float:
    """
    Frazione di parole chiave in comune tra due testi (solo parole ≥ 5 car.).
    Restituisce un valore in [0.0, 1.0].
    """
    from collections import Counter

    def keywords(t: str) -> set[str]:
        words = re.findall(r"[a-zA-Z]{5,}", t.lower())
        return {w for w, _ in Counter(words).most_common(top_n)}

    kw_a = keywords(text_a)
    kw_b = keywords(text_b)
    if not kw_a or not kw_b:
        return 0.0
    return len(kw_a & kw_b) / len(kw_a | kw_b)


# ---------------------------------------------------------------------------
# Estrazione PDF con logica adattiva A/B + rilevamento pagine parziali
# ---------------------------------------------------------------------------

def _extract_pdf(
    doc_path: Path,
    page_number: int,
    func_desc: str = "",
    func_id: str = "",
    max_extra_pages: int = 15,
) -> tuple[str, int, bool, bool]:
    """
    Legge il PDF dalla pagina iniziale in avanti con due strategie:

    Strategia A (indice trovato e abbinato):
      - Cerca tutti gli indici nella pagina iniziale
      - Seleziona quello che corrisponde a func_id + func_desc
      - Tronca pagina iniziale se c'è testo di altra sezione prima
      - Avanza: figli inclusi, fratelli/superiori → STOP
      - Tronca l'ultima pagina se contiene una nuova sezione dopo

    Strategia B (nessun indice abbinabile):
      - Confronto keyword overlap con la pagina iniziale
      - Sotto SIMILARITY_THRESHOLD → STOP
    """
    SIMILARITY_THRESHOLD = cfg.SIMILARITY_THRESHOLD

    try:
        import fitz
    except ImportError:
        log.error("PyMuPDF non installato. Esegui: pip install pymupdf")
        return "", page_number, False, False

    try:
        pdf = fitz.open(str(doc_path))
    except Exception as exc:
        log.error(f"  Impossibile aprire PDF '{doc_path.name}': {exc}")
        return "", page_number, False, False

    start_idx = max(0, page_number - 1)

    if start_idx >= pdf.page_count:
        log.warning(f"  ⚠ Pagina {page_number} oltre la fine del PDF.")
        pdf.close()
        return "", page_number, False, False

    # ── Leggi la pagina iniziale ──────────────────────────────────────────
    start_text_raw = pdf[start_idx].get_text().strip()

    if not start_text_raw:
        log.warning(
            f"  ⚠ Nessun testo a pag.{page_number} di '{doc_path.name}'\n"
            "    Il PDF potrebbe essere scansionato (immagine senza testo)."
        )
        pdf.close()
        return "", page_number, False, False

    # ── Identifica l'indice della funzione ────────────────────────────────
    all_indexes   = _extract_all_indexes(start_text_raw)
    section_index = _find_function_index(all_indexes, func_desc, func_id=func_id)

    start_is_partial = False
    start_text       = start_text_raw

    if section_index:
        log.info(
            f"  📑 Strategia A — indice funzione: '{section_index}' "
            f"su pag.{page_number}"
        )
        # Verifica se c'è testo PRIMA dell'indice → pagina iniziale parziale
        all_idx_full = _extract_all_indexes_full(start_text_raw)
        for idx, title, offset in all_idx_full:
            if idx == section_index.rstrip("."):
                if offset > 0:
                    start_is_partial = True
                    start_text = start_text_raw[offset:].strip()
                    log.info(
                        f"  ✂ Pagina iniziale parziale: testo prima di "
                        f"'{section_index}' escluso (offset={offset})"
                    )
                break
    else:
        log.info(
            f"  📄 Strategia B — nessun indice abbinabile a "
            f"'{func_id}' / '{func_desc}' su pag.{page_number}, "
            "uso similarità testuale"
        )

    texts: list[str]  = [f"[Pagina {page_number}]\n{start_text}"]
    last_page          = page_number
    end_is_partial     = False

    # ── Leggi le pagine successive ────────────────────────────────────────
    limit = min(pdf.page_count, start_idx + 1 + max_extra_pages)

    for p_idx in range(start_idx + 1, limit):
        page_text = pdf[p_idx].get_text().strip()

        # Pagina vuota: includi e prosegui
        if not page_text:
            log.debug(f"  Pag.{p_idx + 1}: vuota — inclusa, continuo")
            texts.append(f"[Pagina {p_idx + 1}]\n")
            last_page = p_idx + 1
            continue

        # ── Strategia A ───────────────────────────────────────────────
        if section_index:
            page_indexes = _extract_all_indexes(page_text)

            if not page_indexes:
                log.debug(f"  Pag.{p_idx + 1}: nessun indice — continuazione, inclusa")
                texts.append(f"[Pagina {p_idx + 1}]\n{page_text}")
                last_page = p_idx + 1

            else:
                first_idx_on_page = page_indexes[0][0]

                if _index_belongs_to_section(first_idx_on_page, section_index):
                    troncato, is_partial = _truncate_at_new_section(
                        page_text, section_index
                    )
                    texts.append(f"[Pagina {p_idx + 1}]\n{troncato}")
                    last_page = p_idx + 1

                    if is_partial:
                        log.info(
                            f"  ✅✂ Pag.{p_idx + 1}: inclusa parzialmente "
                            f"('{first_idx_on_page}' ⊆ '{section_index}', "
                            "poi nuova sezione) — lettura interrotta"
                        )
                        end_is_partial = True
                        break
                    else:
                        log.info(
                            f"  ✅ Pag.{p_idx + 1}: '{first_idx_on_page}' ⊆ "
                            f"'{section_index}' — inclusa"
                        )
                else:
                    troncato, is_partial = _truncate_at_new_section(
                        page_text, section_index
                    )
                    if troncato:
                        texts.append(f"[Pagina {p_idx + 1}]\n{troncato}")
                        last_page     = p_idx + 1
                        end_is_partial = True
                        log.info(
                            f"  ✅✂ Pag.{p_idx + 1}: testo precedente a "
                            f"'{first_idx_on_page}' incluso — poi STOP"
                        )
                    else:
                        log.info(
                            f"  🛑 Pag.{p_idx + 1}: '{first_idx_on_page}' ∉ "
                            f"'{section_index}' — lettura interrotta"
                        )
                    break

        # ── Strategia B ───────────────────────────────────────────────
        else:
            similarity = _keyword_overlap(start_text, page_text)

            if similarity >= SIMILARITY_THRESHOLD:
                log.info(
                    f"  ✅ Pag.{p_idx + 1}: similarità {similarity:.2f} "
                    f"≥ {SIMILARITY_THRESHOLD} — inclusa"
                )
                texts.append(f"[Pagina {p_idx + 1}]\n{page_text}")
                last_page = p_idx + 1
            else:
                log.info(
                    f"  🛑 Pag.{p_idx + 1}: similarità {similarity:.2f} "
                    f"< {SIMILARITY_THRESHOLD} — lettura interrotta"
                )
                break

    pdf.close()

    log.info(
        f"  📖 Estratte pagine {page_number}–{last_page} "
        f"({'parziale inizio, ' if start_is_partial else ''}"
        f"{'parziale fine' if end_is_partial else 'completa'})"
        f" da '{doc_path.name}'"
    )
    return "\n\n".join(texts), last_page, start_is_partial, end_is_partial


# ---------------------------------------------------------------------------
# Estrazione DOCX
# ---------------------------------------------------------------------------

def _extract_docx(doc_path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(doc_path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:3000]
    except ImportError:
        log.error(
            "python-docx non installato.\n"
            "Esegui: pip install python-docx"
        )
        return ""
    except Exception as exc:
        log.error(f"  Impossibile aprire DOCX '{doc_path.name}': {exc}")
        return ""