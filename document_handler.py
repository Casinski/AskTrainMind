

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

def extract_page_text(doc_path: Path, page_number: int) -> str:
    """
    Estrae il testo dalla pagina indicata (1-based) del documento.
    Legge la pagina target + la successiva per avere contesto completo.

    Supporta:
      - PDF  → PyMuPDF (testo nativo; non funziona su PDF scansionati)
      - DOCX → python-docx (tutto il testo, senza paginazione precisa)
    """
    suffix = doc_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(doc_path, page_number)
    elif suffix in (".docx", ".doc"):
        return _extract_docx(doc_path)
    else:
        log.warning(f"  ⚠ Formato non supportato: {suffix}")
        return ""


def _extract_pdf(doc_path: Path, page_number: int) -> str:
    try:
        import fitz
    except ImportError:
        log.error(
            "PyMuPDF non installato.\n"
            "Esegui: pip install pymupdf"
        )
        return ""

    try:
        pdf = fitz.open(str(doc_path))
    except Exception as exc:
        log.error(f"  Impossibile aprire PDF '{doc_path.name}': {exc}")
        return ""

    # fitz è 0-based; leggiamo pagina target + successiva per contesto
    target = max(0, page_number - 1)
    texts  = []
    for p_idx in [target, target + 1]:
        if p_idx < pdf.page_count:
            testo = pdf[p_idx].get_text().strip()
            if testo:
                texts.append(f"[Pagina {p_idx + 1}]\n{testo}")

    pdf.close()

    if not texts:
        log.warning(
            f"  ⚠ Nessun testo a pag.{page_number} di '{doc_path.name}'\n"
            "    Il PDF potrebbe essere scansionato (immagine senza testo)."
        )
    return "\n\n".join(texts)


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