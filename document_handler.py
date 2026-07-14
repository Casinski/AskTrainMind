

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
    max_extra_pages: int = 10,
) -> tuple[str, int]:
    """
    Estrae il testo a partire dalla pagina indicata (1-based) fino alla fine
    della sezione/funzione corrente.

    "Rif. Pagina" è trattato come PAGINA INIZIALE; la lettura continua
    fino a quando viene rilevato l'inizio di una nuova sezione oppure
    si raggiunge max_extra_pages pagine aggiuntive.

    Restituisce:
        (testo_estratto, pagina_finale_effettiva)
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


def _is_new_section_start(text: str) -> bool:
    """
    Euristica per rilevare se una pagina inizia una NUOVA sezione/funzione.
    Criteri:
      - Inizia con un numero di paragrafo tipo "3.2", "4.", "A.1" ecc.
      - Oppure le prime righe sono un titolo tutto maiuscolo
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False

    first = lines[0]

    # Pattern tipo "3.2", "3.2.1", "A.1", "12." — inizio di nuovo paragrafo
    if re.match(r"^[A-Z0-9]+(\.[0-9]+)+\.?\s+\S", first):
        return True

    # Titolo tutto maiuscolo (almeno 4 caratteri, nessuna minuscola)
    if len(first) >= 4 and first == first.upper() and re.search(r"[A-Z]", first):
        return True

    return False


def _extract_pdf(
    doc_path: Path,
    page_number: int,
    max_extra_pages: int = 10,
) -> tuple[str, int]:
    """
    Legge il PDF dalla pagina iniziale (Rif. Pagina) fino alla fine della
    sezione/funzione corrente.

    Restituisce:
        (testo_concatenato, indice_1based_ultima_pagina_letta)
    """
    try:
        import fitz
    except ImportError:
        log.error(
            "PyMuPDF non installato.\n"
            "Esegui: pip install pymupdf"
        )
        return "", page_number

    try:
        pdf = fitz.open(str(doc_path))
    except Exception as exc:
        log.error(f"  Impossibile aprire PDF '{doc_path.name}': {exc}")
        return "", page_number

    start_idx = max(0, page_number - 1)   # 0-based
    texts: list[str] = []
    last_page_read = page_number           # 1-based, aggiornato man mano

    for p_idx in range(start_idx, min(pdf.page_count, start_idx + 1 + max_extra_pages)):
        testo = pdf[p_idx].get_text().strip()

        # Dalla seconda pagina in poi: controlla se è l'inizio di una nuova sezione
        if p_idx > start_idx and testo and _is_new_section_start(testo):
            log.info(
                f"  📄 Nuova sezione rilevata a pag.{p_idx + 1} — "
                "lettura interrotta."
            )
            break

        if testo:
            texts.append(f"[Pagina {p_idx + 1}]\n{testo}")
            last_page_read = p_idx + 1   # converti in 1-based

    pdf.close()

    if not texts:
        log.warning(
            f"  ⚠ Nessun testo a pag.{page_number} di '{doc_path.name}'\n"
            "    Il PDF potrebbe essere scansionato (immagine senza testo)."
        )
        return "", page_number

    log.info(
        f"  📖 Estratte pagine {page_number}–{last_page_read} "
        f"da '{doc_path.name}' ({len(texts)} pag.)"
    )
    return "\n\n".join(texts), last_page_read


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