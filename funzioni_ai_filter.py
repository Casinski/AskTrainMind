"""
funzioni_ai_filter.py
---------------------
Entry point e orchestratore dell'automazione "Funzioni AI".

COLORAZIONE CELLE:
  - Verde  (RGB 00AA00): configurazioni semanticamente equivalenti
  - Rosso  (RGB CC0000): differenze rilevate tra configurazioni
  - Nero   (RGB 000000): unica configurazione disponibile (nessun confronto)
  - Grigio (RGB 888888): testo di errore/fallback

SKIP CELLE GIÀ COMPILATE:
  Gestito in excel_scanner.py: se una cella "Funzioni AI" ha già un valore
  (testo o colore), viene saltata automaticamente e lo script passa alla
  configurazione o funzione successiva.
"""
from __future__ import annotations

import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

import config as cfg
import support_loader
import excel_scanner
import document_handler
import ai_synthesizer
from ai_synthesizer import ConfigText, SynthesisResult, synthesize_with_comparison


# ---------------------------------------------------------------------------
# Colori celle
# ---------------------------------------------------------------------------

# Testo verde scuro: configurazioni equivalenti
FONT_GREEN = Font(color="00AA00", bold=False)

# Testo rosso scuro: differenze tra configurazioni
FONT_RED = Font(color="CC0000", bold=False)

# Testo nero: unica configurazione o default
FONT_BLACK = Font(color="000000", bold=False)

# Testo grigio: errore / testo non disponibile
FONT_GRAY = Font(color="888888", bold=False, italic=True)


def _apply_cell_style(cell, result: SynthesisResult) -> None:
    """
    Applica il colore corretto alla cella in base al risultato della sintesi.

    has_differences = None  → nero  (unica configurazione)
    has_differences = False → verde (equivalenti)
    has_differences = True  → rosso (differenze rilevate)
    testo di errore         → grigio
    """
    text = result.text

    # Testo di errore/fallback → grigio
    if text.startswith("[") and text.endswith("]"):
        cell.font      = FONT_GRAY
        cell.alignment = Alignment(wrap_text=True)
        return

    if result.has_differences is None:
        cell.font = FONT_BLACK
    elif result.has_differences is False:
        cell.font = FONT_GREEN
    else:
        cell.font = FONT_RED

    cell.alignment = Alignment(wrap_text=True)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).parent / "funzioni_ai_filter.log",
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verifica prerequisiti
# ---------------------------------------------------------------------------

def check_prerequisites() -> bool:
    ok = True
    if not ai_synthesizer.check_ollama():
        ok = False
    if not cfg.EXCEL_PATH.exists():
        log.error(
            f"File Excel non trovato: {cfg.EXCEL_PATH}\n"
            "  Verifica che OneDrive sia sincronizzato e il percorso sia corretto."
        )
        ok = False
    return ok


# ---------------------------------------------------------------------------
# Salvataggio workbook
# ---------------------------------------------------------------------------

def save_workbook(wb) -> None:
    """Salva il workbook. In caso di file bloccato attende e riprova."""
    import time as _time
    max_wait       = 60
    retry_interval = 5
    elapsed        = 0

    while elapsed <= max_wait:
        try:
            wb.save(str(cfg.EXCEL_PATH))
            log.info(f"✅ File Excel salvato: {cfg.EXCEL_PATH}")
            return
        except PermissionError:
            if elapsed == 0:
                log.warning(
                    f"⚠ File bloccato (aperto in Excel?).\n"
                    f"  Chiudi il file. Riprovo ogni {retry_interval}s "
                    f"per max {max_wait}s..."
                )
            _time.sleep(retry_interval)
            elapsed += retry_interval

    backup = cfg.EXCEL_PATH.with_name(
        cfg.EXCEL_PATH.stem + "_funzioniAI_backup" + cfg.EXCEL_PATH.suffix
    )
    try:
        wb.save(str(backup))
        log.warning(
            f"⚠ Timeout attesa ({max_wait}s). Backup salvato: {backup}\n"
            "  Sostituisci manualmente il file originale con il backup."
        )
    except Exception as exc:
        log.error(f"Errore salvataggio backup: {exc}")


# ---------------------------------------------------------------------------
# Orchestrazione principale
# ---------------------------------------------------------------------------

def run() -> int:
    """
    Esegue l'intero flusso di automazione.
    Restituisce il numero di celle compilate.

    FLUSSO PER OGNI GRUPPO (func_id, doc_id):
      1. Raccoglie tutti i FillTarget del gruppo
      2. Scarica ed estrae il testo per TUTTE le configurazioni del gruppo
      3. Valutazione semantica Ollama (una sola chiamata per gruppo)
      4. Genera la sintesi per ogni configurazione con il colore corretto
      5. Scrive testo + colore nella cella Excel

    SKIP AUTOMATICO:
      Le celle già compilate (con qualsiasi testo) vengono saltate
      automaticamente da excel_scanner.scan() prima ancora di arrivare
      qui — nessuna elaborazione viene avviata per esse.
    """
    # ── Apri workbook data_only=True ──────────────────────────────────────
    log.info(f"Apertura workbook (data_only=True): {cfg.EXCEL_PATH}")
    try:
        wb_data = load_workbook(str(cfg.EXCEL_PATH), data_only=True)
        ws_data = wb_data[cfg.SHEET_FUNZIONI]
    except Exception as exc:
        log.error(f"Impossibile aprire il file (data_only): {exc}")
        return 0

    # ── Apri workbook data_only=False ─────────────────────────────────────
    log.info("Apertura workbook (data_only=False) per scrittura...")
    try:
        wb_write = load_workbook(str(cfg.EXCEL_PATH), data_only=False)
        ws_write = wb_write[cfg.SHEET_FUNZIONI]
    except PermissionError:
        log.error(
            "Il file Excel è aperto in Excel.\n"
            "Chiudilo prima di eseguire lo script."
        )
        return 0
    except Exception as exc:
        log.error(f"Impossibile aprire il file (write): {exc}")
        return 0

    # ── Carica fogli di supporto ──────────────────────────────────────────
    log.info("\nCaricamento fogli di supporto...")
    sd = support_loader.load(wb_data)

    if not sd.is_valid():
        log.error(
            "Fogli di supporto non validi (base URL mancante).\n"
            "Verifica che il foglio 'Cartelle' esista e che D6 contenga l'URL."
        )
        return 0

    # ── Raccoglie tutti i FillTarget (celle vuote da compilare) ───────────
    # excel_scanner.scan() salta automaticamente le celle già compilate
    all_targets = list(excel_scanner.scan(ws_write, ws_data, sd))

    if not all_targets:
        log.info(
            "Nessuna cella da compilare:\n"
            "  • Tutte le 'Funzioni AI' sono già compilate, oppure\n"
            "  • Non ci sono righe 'Funzioni AI' nel foglio, oppure\n"
            "  • Nessun link trovato per le configurazioni disponibili"
        )
        return 0

    # ── Raggruppa per (func_id, doc_id) per il confronto semantico ────────
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for target in all_targets:
        groups[(target.func_id, target.doc_id)].append(target)

    log.info(
        f"\nFillTarget da compilare: {len(all_targets)} "
        f"in {len(groups)} gruppi (func_id × doc_id)"
    )

    filled_count = 0

    for (func_id, doc_id), group_targets in groups.items():

        log.info(
            f"\n{'═' * 55}\n"
            f"  Gruppo: {func_id} / {doc_id} "
            f"({len(group_targets)} configurazioni da compilare)\n"
            f"{'═' * 55}"
        )

        # ── Passo 1: scarica e estrai testo per tutte le configurazioni ───
        config_texts: list[ConfigText] = []

        for target in group_targets:
            log.info(
                f"  [{target.config_name}] Estrazione testo "
                f"(pagina {target.page_number})..."
            )
            doc_path = document_handler.download(target.url)
            if not doc_path:
                config_texts.append(ConfigText(
                    config_name=target.config_name,
                    page_number=target.page_number,
                    text="",
                ))
                log.warning(
                    f"  [{target.config_name}] Documento non trovato — "
                    "testo vuoto, cella segnata come errore"
                )
                continue

            page_text = document_handler.extract_page_text(
                doc_path, target.page_number
            )
            config_texts.append(ConfigText(
                config_name=target.config_name,
                page_number=target.page_number,
                text=page_text,
            ))

        valid_texts = [ct for ct in config_texts if ct.text.strip()]
        log.info(
            f"  Testi disponibili: {len(valid_texts)}/{len(group_targets)} "
            "configurazioni"
        )

        # ── Passo 2: genera sintesi e applica colori ───────────────────────
        for target in group_targets:

            my_text = next(
                (ct.text for ct in config_texts
                 if ct.config_name == target.config_name),
                "",
            )

            cell = ws_write.cell(target.row, target.col)

            # Documento non scaricabile → testo errore grigio
            if not my_text:
                error_result = SynthesisResult(
                    text=f"[Testo non estratto: pag.{target.page_number} "
                         f"di {target.doc_id}]",
                    has_differences=None,
                )
                cell.value = error_result.text
                _apply_cell_style(cell, error_result)
                filled_count += 1
                continue

            log.info(
                f"  [{target.config_name}] → "
                f"Ollama ({cfg.OLLAMA_MODEL}) con confronto "
                f"({len(valid_texts)} configurazioni)..."
            )

            # Genera sintesi con valutazione semantica e flag colore
            result: SynthesisResult = synthesize_with_comparison(
                func_id=target.func_id,
                func_desc=target.func_desc,
                doc_id=target.doc_id,
                config_name=target.config_name,
                page_number=target.page_number,
                page_text=my_text,
                all_config_texts=valid_texts,
            )

            # Scrivi testo nella cella
            cell.value = result.text

            # Applica il colore corretto
            _apply_cell_style(cell, result)

            filled_count += 1

            color_label = (
                "🟢 VERDE"  if result.has_differences is False else
                "🔴 ROSSO"  if result.has_differences is True  else
                "⚫ NERO"
            )
            log.info(
                f"  [{target.config_name}] ✅ {color_label} — "
                f"{result.text[:90]}..."
            )

            time.sleep(cfg.AI_CALL_DELAY_SECONDS)

            # Rispetta il limite per esecuzione
            if cfg.MAX_CELLS_PER_RUN > 0 and filled_count >= cfg.MAX_CELLS_PER_RUN:
                log.info(
                    f"Limite MAX_CELLS_PER_RUN={cfg.MAX_CELLS_PER_RUN} raggiunto."
                )
                save_workbook(wb_write)
                return filled_count

    # ── Salva ─────────────────────────────────────────────────────────────
    log.info(f"\n{'=' * 60}")
    log.info(f"  CELLE COMPILATE: {filled_count}")
    log.info(f"{'=' * 60}")

    if filled_count > 0:
        save_workbook(wb_write)
        log.info(
            "OneDrive sincronizzerà le modifiche su SharePoint automaticamente."
        )
    else:
        log.info("Nessuna cella compilata.")

    return filled_count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("\n" + "=" * 60)
    log.info("  funzioni_ai_filter — avvio")
    log.info("=" * 60)
    log.info(f"  Excel     : {cfg.EXCEL_PATH}")
    log.info(f"  AI model  : Ollama / {cfg.OLLAMA_MODEL}")
    log.info(f"  Cache dir : {cfg.CACHE_DIR}")

    if not check_prerequisites():
        sys.exit(1)

    run()
    log.info("Fine.")


if __name__ == "__main__":
    main()