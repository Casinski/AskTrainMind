

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

def extract_page_text(
    doc_path: Path,
    page_number: int,
    func_desc: str = "",
    max_extra_pages: int = 15,
) -> tuple[str, int, bool, bool]:
    """
    Estrae il testo a partire dalla pagina indicata (Rif. Pagina) fino alla
    fine della sezione/funzione corrente.

    Restituisce:
        testo_estratto   : testo concatenato delle pagine lette
        pagina_finale    : numero (1-based) dell'ultima pagina letta
        start_is_partial : True se la pagina iniziale contiene testo di
                           un'altra sezione PRIMA della funzione cercata
                           → label "parte di pagina X"
        end_is_partial   : True se l'ultima pagina è stata troncata perché
                           conteneva una nuova sezione dopo la funzione
                           → label "parte di pagina Y"
    """
    suffix = doc_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(doc_path, page_number, func_desc, max_extra_pages)
    elif suffix in (".docx", ".doc"):
        text = _extract_docx(doc_path)
        return text, page_number, False, False
    else:
        log.warning(f"  ⚠ Formato non supportato: {suffix}")
        return "", page_number, False, False


# ---------------------------------------------------------------------------
# Helpers — indici numerici di sezione
# ---------------------------------------------------------------------------

def _extract_all_indexes(text: str) -> list[tuple[str, str]]:
    """
    Estrae TUTTI gli indici di sezione presenti nelle prime 60 righe del testo.
    Restituisce una lista di tuple (indice, titolo).

    Gestisce i casi comuni nei PDF tecnici:
      - Spazi multipli / tabulazioni tra indice e titolo
      - Spazi unicode non-breaking (\\xa0)
      - Indice e titolo su righe separate
      - Caratteri spuri prima dell'indice (spazi, numeri di pagina)
      - Indice senza titolo sulla stessa riga (titolo sulla riga successiva)

    Riconosce solo indici con almeno 2 livelli (N.N) per evitare
    falsi positivi con valori tecnici tipo "24.5 V".
    """
    # Normalizza: sostituisci ogni tipo di spazio/tab con spazio singolo
    normalized = text.replace("\xa0", " ").replace("\t", " ")
    lines = [ln.strip() for ln in normalized.splitlines()]
    # Rimuovi righe vuote mantenendo la posizione per il look-ahead
    results: list[tuple[str, str]] = []

    i = 0
    while i < min(len(lines), 60):
        line = lines[i]

        # Pattern principale: indice seguito da titolo sulla stessa riga
        # Accetta uno o più spazi/tab tra indice e titolo
        m = re.match(r"^[\s\-–•]*(\d+(?:\.\d+){1,})\s+(.+)$", line)
        if m:
            idx   = m.group(1).strip()
            title = re.sub(r"\s+", " ", m.group(2)).strip()
            results.append((idx, title))
            i += 1
            continue

        # Pattern alternativo: indice da solo sulla riga (titolo sulla riga successiva)
        m2 = re.match(r"^[\s\-–•]*(\d+(?:\.\d+){1,})\s*$", line)
        if m2 and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # La riga successiva deve essere testo (non un altro indice)
            if next_line and not re.match(r"^\d+(?:\.\d+)+", next_line):
                idx   = m2.group(1).strip()
                title = re.sub(r"\s+", " ", next_line).strip()
                results.append((idx, title))
                i += 2
                continue

        i += 1

    return results


def _extract_all_indexes_full(text: str) -> list[tuple[str, str, int]]:
    """
    Come _extract_all_indexes ma scansiona TUTTO il testo e restituisce
    anche la posizione carattere (offset) dove inizia ogni indice.
    Usata per trovare dove inizia una nuova sezione all'interno di una pagina.

    Gestisce le stesse varianti di _extract_all_indexes.

    Restituisce lista di (indice, titolo, offset_carattere).
    """
    # Normalizza spazi unicode
    normalized = text.replace("\xa0", " ").replace("\t", " ")
    results: list[tuple[str, str, int]] = []

    # Scansione con re.finditer su tutto il testo
    # Pattern 1: indice + titolo sulla stessa riga
    for m in re.finditer(
        r"(?:^|(?<=\n))[\s\-–•]*(\d+(?:\.\d+){1,})[ \t]+(\S[^\n]*)",
        normalized,
    ):
        idx   = m.group(1).strip()
        title = re.sub(r"\s+", " ", m.group(2)).strip()
        results.append((idx, title, m.start()))

    # Pattern 2: indice da solo su riga, titolo sulla riga successiva
    # Cerca casi non già coperti dal Pattern 1
    existing_offsets = {r[2] for r in results}
    for m in re.finditer(
        r"(?:^|(?<=\n))[\s\-–•]*(\d+(?:\.\d+){1,})[ \t]*\n([\w][^\n]+)",
        normalized,
    ):
        if m.start() not in existing_offsets:
            idx   = m.group(1).strip()
            title = re.sub(r"\s+", " ", m.group(2)).strip()
            results.append((idx, title, m.start()))

    # Ordina per posizione nel testo
    results.sort(key=lambda x: x[2])
    return results


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
) -> Optional[str]:
    """
    Dato l'elenco di (indice, titolo) e il nome della funzione,
    restituisce l'indice che meglio corrisponde alla funzione.

    Priorità:
      1. Maggiore sovrapposizione di parole chiave tra titolo e func_desc
      2. Parità → indice più specifico (più livelli)
      3. Fallback → indice più profondo se nessuna parola in comune
    """
    if not indexes:
        return None

    func_words = _normalize_for_match(func_desc)
    best_index = None
    best_score = 0
    best_depth = -1

    for idx, title in indexes:
        title_words = _normalize_for_match(title)
        score = len(func_words & title_words)
        depth = idx.count(".")

        if score > best_score or (score == best_score and depth > best_depth):
            best_score = score
            best_depth = depth
            best_index = idx

    if best_score > 0:
        log.info(
            f"  🎯 Indice funzione: '{best_index}' "
            f"(score={best_score}, func='{func_desc}')"
        )
    else:
        log.info(
            f"  🔍 Nessuna corrispondenza per '{func_desc}' — "
            f"uso indice più profondo: '{best_index}'"
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
    max_extra_pages: int = 15,
) -> tuple[str, int, bool, bool]:
    """
    Legge il PDF dalla pagina iniziale in avanti con due strategie:

    Strategia A (indice trovato):
      - Identifica l'indice della funzione nella pagina iniziale
      - Tronca la pagina iniziale al testo che precede l'indice
        se c'è contenuto di un'altra sezione prima (start_is_partial)
      - Legge avanti: figli inclusi, fratelli/superiori → STOP
      - Se l'ultima pagina contiene una nuova sezione dopo la funzione,
        tronca il testo a quel punto (end_is_partial)

    Strategia B (nessun indice):
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
    section_index = _find_function_index(all_indexes, func_desc)

    start_is_partial = False
    start_text       = start_text_raw

    if section_index:
        log.info(
            f"  📑 Strategia A — indice funzione: '{section_index}' "
            f"su pag.{page_number}"
        )

        # Verifica se c'è testo PRIMA dell'indice della funzione
        # (= la pagina inizia con un'altra sezione → pagina parziale)
        all_idx_full = _extract_all_indexes_full(start_text_raw)
        for idx, title, offset in all_idx_full:
            if idx == section_index.rstrip("."):
                if offset > 0:
                    # C'è testo prima del nostro indice
                    start_is_partial = True
                    # Tieni solo il testo dalla nostra sezione in poi
                    start_text = start_text_raw[offset:].strip()
                    log.info(
                        f"  ✂ Pagina iniziale parziale: testo prima di "
                        f"'{section_index}' escluso (offset={offset})"
                    )
                break

    else:
        log.info(
            f"  📄 Strategia B — nessun indice abbinabile a '{func_desc}' "
            f"su pag.{page_number}, uso similarità testuale"
        )

    texts: list[str] = [f"[Pagina {page_number}]\n{start_text}"]
    last_page    = page_number
    end_is_partial = False

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
                # Nessun indice: continuazione della sezione
                log.debug(
                    f"  Pag.{p_idx + 1}: nessun indice — "
                    "continuazione, inclusa"
                )
                texts.append(f"[Pagina {p_idx + 1}]\n{page_text}")
                last_page = p_idx + 1

            else:
                first_idx_on_page = page_indexes[0][0]

                if _index_belongs_to_section(first_idx_on_page, section_index):
                    # La pagina inizia con un figlio della sezione.
                    # Verifica però se più avanti nella stessa pagina
                    # compare un indice estraneo (pagina finale parziale).
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
                    # Il PRIMO indice è già estraneo: la pagina potrebbe
                    # contenere la fine della nostra sezione prima del
                    # nuovo indice. Tronca e includi solo quella parte.
                    troncato, is_partial = _truncate_at_new_section(
                        page_text, section_index
                    )
                    if troncato:
                        texts.append(f"[Pagina {p_idx + 1}]\n{troncato}")
                        last_page = p_idx + 1
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