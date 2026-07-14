

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
    max_extra_pages: int = 15,
) -> tuple[str, int]:
    """
    Estrae il testo a partire dalla pagina indicata (1-based, da Rif. Pagina)
    fino alla fine della sezione/funzione corrente.

    Strategia A — indice numerico rilevato nella pagina iniziale
      La pagina iniziale contiene un titolo con indice tipo "3.1".
      Si continuano a leggere le pagine successive finché si trovano
      sottosezioni (3.1.x, 3.1.x.y …).
      Ci si ferma al primo indice fratello o superiore (3.2, 4., ecc.).

    Strategia B — nessun indice rilevato
      Si confronta la sovrapposizione di parole chiave di ogni pagina
      con la pagina iniziale. Ci si ferma quando il contenuto cambia
      significativamente o si raggiunge max_extra_pages.

    Restituisce:
        (testo_estratto, pagina_finale_1based)
    """
    suffix = doc_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(doc_path, page_number, max_extra_pages)
    elif suffix in (".docx", ".doc"):
        text = _extract_docx(doc_path)
        return text, page_number
    else:
        log.warning(f"  ⚠ Formato non supportato: {suffix}")
        return "", page_number


# ---------------------------------------------------------------------------
# Rilevamento indici numerici di sezione  (es. "3.1", "3.1.1.9")
# ---------------------------------------------------------------------------

def _extract_section_index(text: str) -> Optional[str]:
    """
    Cerca nelle prime 25 righe non vuote del testo un indice di sezione
    nel formato  N.N  /  N.N.N  /  N.N.N.N  (almeno due livelli numerici).

    Esempi riconosciuti  →  "3.1"  "3.1.1"  "3.1.1.9"  "12.4.2"
    NON riconosce        →  "3."   "pag.3"  "ver. 1.5"  (un solo livello)

    La ricerca si limita alle prime 25 righe per evitare falsi positivi
    nel corpo del testo (es. valori tecnici come "24.5 V").

    Restituisce l'indice come stringa (es. "3.1") oppure None.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:25]:
        # L'indice deve essere all'inizio della riga (eventualmente
        # preceduto da spazi già rimossi) e seguito da uno spazio + testo
        m = re.match(r"^(\d+(?:\.\d+){1,})\s+\S", line)
        if m:
            return m.group(1)
    return None


def _index_belongs_to_section(candidate: str, section: str) -> bool:
    """
    True se `candidate` è uguale a `section` oppure è un suo sotto-indice.

    Esempi con section = "3.1":
      "3.1"       → True   (stessa sezione)
      "3.1.1"     → True   (figlio diretto)
      "3.1.1.9"   → True   (nipote)
      "3.2"       → False  (fratello → nuova sezione)
      "3.10"      → False  (fratello con numero maggiore)
      "4.1"       → False  (genitore diverso)
      "3.0"       → False  (fratello precedente)
    """
    s = section.rstrip(".")
    c = candidate.rstrip(".")
    return c == s or c.startswith(s + ".")


# ---------------------------------------------------------------------------
# Similarità testuale tra pagine  (Strategia B)
# ---------------------------------------------------------------------------

def _keyword_overlap(text_a: str, text_b: str, top_n: int = 30) -> float:
    """
    Calcola la frazione di parole chiave in comune tra due testi.
    Considera solo parole di almeno 5 caratteri per escludere articoli
    e preposizioni. Usa le top_n parole più frequenti come "firma" del testo.

    Restituisce un valore in [0.0, 1.0]:
      0.0 = nessuna parola in comune
      1.0 = insiemi identici
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
# Estrazione PDF con logica adattiva A/B
# ---------------------------------------------------------------------------

def _extract_pdf(
    doc_path: Path,
    page_number: int,
    max_extra_pages: int = 15,
) -> tuple[str, int]:
    """
    Legge il PDF dalla pagina iniziale (Rif. Pagina) in avanti,
    applicando la Strategia A se viene rilevato un indice di sezione,
    altrimenti la Strategia B basata sulla similarità testuale.

    Strategia A — indice trovato (es. "3.1")
      • Ogni pagina successiva viene analizzata:
          - se contiene un indice che appartiene a "3.1" (es. 3.1.x) → inclusa
          - se contiene un indice estraneo (es. 3.2, 4.1)            → STOP
          - se non contiene alcun indice                              → inclusa
            (si assume continuazione della stessa sezione)

    Strategia B — nessun indice
      • Si confronta ogni pagina successiva con la pagina iniziale
        tramite sovrapposizione di parole chiave.
        Soglia: SIMILARITY_THRESHOLD (default 0.25).
          - similarità ≥ soglia → inclusa
          - similarità < soglia → STOP (cambio di argomento)

    Restituisce:
        (testo_concatenato, indice_1based_ultima_pagina_letta)
    """
    SIMILARITY_THRESHOLD = cfg.SIMILARITY_THRESHOLD   # Strategia B: abbassa se taglia troppo presto

    try:
        import fitz
    except ImportError:
        log.error("PyMuPDF non installato. Esegui: pip install pymupdf")
        return "", page_number

    try:
        pdf = fitz.open(str(doc_path))
    except Exception as exc:
        log.error(f"  Impossibile aprire PDF '{doc_path.name}': {exc}")
        return "", page_number

    start_idx = max(0, page_number - 1)   # converti in 0-based
    texts: list[str] = []
    last_page = page_number               # 1-based, aggiornato man mano

    # ── Leggi la pagina iniziale ──────────────────────────────────────────
    if start_idx >= pdf.page_count:
        log.warning(f"  ⚠ Pagina {page_number} oltre la fine del PDF.")
        pdf.close()
        return "", page_number

    start_text = pdf[start_idx].get_text().strip()

    if not start_text:
        log.warning(
            f"  ⚠ Nessun testo a pag.{page_number} di '{doc_path.name}'\n"
            "    Il PDF potrebbe essere scansionato (immagine senza testo)."
        )
        pdf.close()
        return "", page_number

    texts.append(f"[Pagina {page_number}]\n{start_text}")

    # ── Determina la strategia da usare ──────────────────────────────────
    section_index = _extract_section_index(start_text)

    if section_index:
        log.info(
            f"  📑 Strategia A — indice sezione: '{section_index}' "
            f"(pag.{page_number})"
        )
    else:
        log.info(
            f"  📄 Strategia B — nessun indice a pag.{page_number}, "
            "uso similarità testuale"
        )

    # ── Leggi le pagine successive ────────────────────────────────────────
    limit = min(pdf.page_count, start_idx + 1 + max_extra_pages)
    for p_idx in range(start_idx + 1, limit):

        page_text = pdf[p_idx].get_text().strip()

        # Pagina vuota o scansionata: includi e prosegui senza fermarsi
        if not page_text:
            log.debug(f"  Pag.{p_idx + 1}: vuota — inclusa, continuo")
            texts.append(f"[Pagina {p_idx + 1}]\n")
            last_page = p_idx + 1
            continue

        # ── Strategia A: controlla indice ─────────────────────────────
        if section_index:
            page_index = _extract_section_index(page_text)

            if page_index is None:
                # Nessun indice nella pagina: è continuazione della sezione
                log.debug(
                    f"  Pag.{p_idx + 1}: nessun indice — "
                    "assumo continuazione, inclusa"
                )
                texts.append(f"[Pagina {p_idx + 1}]\n{page_text}")
                last_page = p_idx + 1

            elif _index_belongs_to_section(page_index, section_index):
                # Indice figlio/nipote: appartiene alla sezione corrente
                log.info(
                    f"  ✅ Pag.{p_idx + 1}: '{page_index}' ⊆ "
                    f"'{section_index}' — inclusa"
                )
                texts.append(f"[Pagina {p_idx + 1}]\n{page_text}")
                last_page = p_idx + 1

            else:
                # Indice fratello o superiore: nuova sezione → STOP
                log.info(
                    f"  🛑 Pag.{p_idx + 1}: '{page_index}' ∉ "
                    f"'{section_index}' — lettura interrotta"
                )
                break

        # ── Strategia B: controlla similarità ────────────────────────
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
        f"da '{doc_path.name}' ({len(texts)} pag.)"
    )
    return "\n\n".join(texts), last_page


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