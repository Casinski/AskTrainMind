"""
Controllo e creazione dei fogli del DB Flotte usati dalle opzioni di analisi.

- "Funzioni" e' obbligatorio: senza di esso nessuna opzione puo' lavorare.
- "Requisiti" viene creato (intestazione + colonne delle configurazioni) se
  manca; l'opzione 1 lo compila.
- "Reqs not matched", "Index Funzioni" e "Confronto Reqs" vengono ricreati
  ad ogni esecuzione dalle rispettive opzioni, quindi se mancano nascono li'.
"""
from __future__ import annotations

import logging

from openpyxl.styles import Alignment, Font

import config as cfg
import config_colors

log = logging.getLogger(__name__)

REQ_HEADERS = {
    cfg.REQ_FUNC_ID_COL: ("FUNC ID", 60),
    cfg.REQ_DESC_COL: ("DESCRIZIONE", 65),
    cfg.REQ_FRS_COL: (getattr(cfg, "REQ_FRS_HEADER", "FRS"), 26),
    cfg.REQ_NUMBER_COL: ("REQUISITO", 35),
    cfg.REQ_CONFIG_COL: ("CONFIGURAZIONE APPARTENENZA", 35),
}


class MissingSheetError(RuntimeError):
    pass


def require_funzioni(wb) -> None:
    """Errore chiaro se il foglio Funzioni non c'e'."""
    if cfg.SHEET_FUNZIONI not in wb.sheetnames:
        raise MissingSheetError(
            f"Il file Excel non contiene il foglio '{cfg.SHEET_FUNZIONI}', necessario a tutte "
            f"le opzioni di analisi. Fogli presenti: {', '.join(wb.sheetnames)}.")


def requisiti_configs(wb) -> list[str]:
    """Configurazioni del treno (CONFIG/Funzioni), con la configurazione base per prima."""
    import analysis_scope
    configs = list(analysis_scope.catalog_from_wb(wb).configs)
    base = cfg.REQ_BASE_CONFIG
    rest = [c for c in configs if analysis_scope.norm(c) != analysis_scope.norm(base)]
    return [base] + rest


def ensure_requisiti(wb):
    """Ritorna il foglio Requisiti, creandolo dopo "Funzioni" se manca."""
    if cfg.SHEET_REQUISITI in wb.sheetnames:
        return wb[cfg.SHEET_REQUISITI]
    pos = (wb.sheetnames.index(cfg.SHEET_FUNZIONI) + 1
           if cfg.SHEET_FUNZIONI in wb.sheetnames else len(wb.sheetnames))
    ws = wb.create_sheet(cfg.SHEET_REQUISITI, pos)
    hrow = cfg.REQ_HEADER_ROW
    for col, (title, width) in REQ_HEADERS.items():
        c = ws.cell(hrow, col, title)
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[c.column_letter].width = width
    configs = requisiti_configs(wb)
    for i, name in enumerate(configs):
        c = ws.cell(hrow, cfg.REQ_CONFIG_COLS_START + i, name)
        c.font = Font(bold=True, color=config_colors.color_for(name))
        ws.column_dimensions[c.column_letter].width = 35 if i == 0 else 20
    ws.freeze_panes = ws.cell(hrow + 1, 1)
    log.warning(f"  Foglio '{cfg.SHEET_REQUISITI}' non presente: creato con "
                f"{len(configs)} configurazioni ({', '.join(configs)}).")
    return ws


def requisiti_empty(ws) -> bool:
    return not any(ws.cell(r, cfg.REQ_FUNC_ID_COL).value or ws.cell(r, cfg.REQ_NUMBER_COL).value
                   for r in range(cfg.REQ_HEADER_ROW + 1, ws.max_row + 1))
