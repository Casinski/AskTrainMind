"""
funzioni_ai_filter.py
---------------------
Entry point e orchestratore dell'automazione "Funzioni AI".

VERSIONE OTTIMIZZATA:
  - Fase 1 (parsing): regex istantaneo, nessuna LLM
  - Fase 2 (deterministico): regex, nessuna LLM
  - Fase 3-6 (LLM): UNA SOLA chiamata Ollama per gruppo (non per configurazione)
  - Risultato LLM riutilizzato per tutte le configurazioni dello stesso gruppo

Stima tempo: ~1-3 minuti per gruppo invece di ~20 minuti.

COLORAZIONE CELLE:
  Verde  (00AA00): equivalenti
  Rosso  (CC0000): differenze tecniche
  Nero   (000000): unica config OPPURE caso incerto
  Grigio (888888): errore/fallback
"""
from __future__ import annotations

import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment

import app_logging
import config as cfg
import support_loader
import excel_scanner
import rif_pagina
import document_handler
import ai_synthesizer
from ai_synthesizer import ConfigText, SynthesisResult, synthesize_with_comparison
from function_parser import parse_function_structure, ParsedFunction
from deterministic_comparator import compare_all

import requirements_extractor
import history_tracker
from requisiti_writer import RequisitiWriter, _norm as _req_norm
import func_ai_comparator
import index_funzioni
import confronto_reqs
import interrupt_guard
import req_ai_comparator
import old_archive
import reqs_not_matched
import sheet_setup
import requisiti_sorter
import run_options
import analysis_scope
from analysis_scope import Scope
from run_options import Option1Params


# ---------------------------------------------------------------------------
# Colori celle
# ---------------------------------------------------------------------------

FONT_GREEN = Font(color="00AA00", bold=False)
FONT_RED   = Font(color="CC0000", bold=False)
FONT_BLACK = Font(color="000000", bold=False)
FONT_GRAY  = Font(color="888888", bold=False, italic=True)

# Stili del confronto per configurazione (stessa semantica del foglio
# Requisiti): MATCHED verde grassetto, differenze rosse, testo nero.
FONT_MATCHED = Font(color="FF008000", bold=True)   # Verde bold: 90-100
FONT_HIGH    = Font(color="FF008000", bold=False)  # Verde:      80-90
FONT_MEDIUM  = Font(color="FFFFA500", bold=False)  # Arancione:  50-80
FONT_DIFF    = Font(color="FFC00000", bold=False)  # Rosso:      25-50
FONT_DIFF_HIGH = Font(color="FFC00000", bold=True)  # Rosso:    0-25
FONT_PLAIN   = Font(color="FF000000", bold=False)  # Nero


def _write_func_cell(cell, testo: str, font: Font) -> None:
    cell.value = testo
    cell.font = font
    cell.alignment = Alignment(wrap_text=True, vertical="top")


def _apply_cell_style(cell, result: SynthesisResult) -> None:
    text = result.text
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
app_logging.setup(logging.INFO)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verifica prerequisiti
# ---------------------------------------------------------------------------

def check_prerequisites() -> bool:
    ok = True
    if not ai_synthesizer.check_ollama():
        ok = False
    if not cfg.EXCEL_PATH.exists():
        log.error(f"File Excel non trovato: {cfg.EXCEL_PATH}")
        ok = False
    return ok


# ---------------------------------------------------------------------------
# Salvataggio workbook
# ---------------------------------------------------------------------------

def _save_atomic(wb, target: Path) -> None:
    """
    Scrive su un file temporaneo e poi lo sostituisce all'originale: se il
    processo viene chiuso durante la scrittura il file Excel resta integro.
    """
    if not interrupt_guard.ENABLED:
        wb.save(str(target))
        return
    tmp = target.with_name(f".{target.stem}.saving{target.suffix}")
    try:
        wb.save(str(tmp))
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def save_workbook(wb) -> None:
    with interrupt_guard.protected():
        _save_workbook(wb)


def _save_workbook(wb) -> None:
    import time as _time
    max_wait, retry_interval, elapsed = 60, 5, 0
    # Prima del primo salvataggio dell'opzione: copia della versione
    # precedente del file nella cartella _OLD (una sola volta per esecuzione)
    old_archive.archive_before_save(Path(cfg.EXCEL_PATH))
    if not run_options.update_db():
        # L'utente non vuole aggiornare il DB: solo il file RESULTS
        try:
            out = run_options.save_results(
                wb, old_archive.option() or "?", old_archive.sheets(),
                stamp=old_archive.session_time())
            old_archive.set_results(out)
        except Exception as exc:
            log.error(f"File RESULTS non salvato: {exc}", exc_info=True)
        return
    while elapsed <= max_wait:
        try:
            _save_atomic(wb, Path(cfg.EXCEL_PATH))
            log.info(f"✅ File Excel salvato: {cfg.EXCEL_PATH}")
            return
        except PermissionError:
            if elapsed == 0:
                log.warning(f"⚠ File bloccato. Riprovo ogni {retry_interval}s...")
            _time.sleep(retry_interval)
            elapsed += retry_interval

    backup = cfg.EXCEL_PATH.with_name(
        cfg.EXCEL_PATH.stem + "_backup" + cfg.EXCEL_PATH.suffix
    )
    try:
        wb.save(str(backup))
        log.warning(f"⚠ Timeout. Backup salvato: {backup}")
    except Exception as exc:
        log.error(f"Errore salvataggio backup: {exc}")


# ---------------------------------------------------------------------------
# Orchestrazione principale
# ---------------------------------------------------------------------------
def run(start_from_func_id: str = "", params: Option1Params | None = None) -> int:
    """
    Opzione 1 con i parametri scelti dall'utente (Option1Params: numero di
    celle, sovrascrittura, FUNC ID di partenza, FRS, "Reqs not matched"). Se l'esecuzione viene interrotta (Ctrl+C) e SAVE_PROGRESS e'
    attivo, le celle "Funzioni AI" e le righe "Requisiti" gia' scritte
    vengono salvate nel file Excel insieme a storico e cache; la funzione in
    lavorazione diventa il punto di ripresa della prossima esecuzione.
    """
    params = params or Option1Params(start=start_from_func_id)
    if start_from_func_id and not params.start:
        params.start = start_from_func_id
    ctx: dict = {"wb": None, "func_id": "", "filled": 0, "req_rows": 0,
                 "dirty": False, "params": params, "scope": set(),
                 "processed": set(), "partial": list(params.partial_reasons())}
    try:
        n = _run(params.start, ctx)
    except KeyboardInterrupt as exc:
        interrupt_guard.handle(exc, f"opzione 1, funzione '{ctx['func_id']}'")
        ctx["partial"].append(f"esecuzione interrotta a {ctx['func_id']}")
        _finalize_requisiti(ctx, ai=False)
        _save_progress(ctx)
        interrupt_guard.save_checkpoint("1", ctx["func_id"])
        log.info(
            f"  CELLE 'Funzioni AI' COMPILATE : {ctx['filled']}\n"
            f"  RIGHE 'Requisiti' SCRITTE     : {ctx['req_rows']}"
        )
        return ctx["filled"]
    if not interrupt_guard.interrupted:
        interrupt_guard.clear_checkpoint("1")
    return n


def _finalize_requisiti(ctx: dict, ai: bool | None = None) -> None:
    """
    Chiusura dell'opzione 1 sul foglio Requisiti (anche se interrotta):
      1. elimina i requisiti non piu' presenti nei documenti delle funzioni
         analizzate per intero (REQ_REMOVE_STALE_ROWS);
      2. riordina i blocchi funzione come nel foglio Funzioni
         (REQ_SORT_LIKE_FUNZIONI);
      3. ricrea il foglio "Reqs not matched" su tutte le configurazioni
         (REQS_NOT_MATCHED_AFTER_OPTION1).
    """
    wb, writer = ctx.get("wb"), ctx.get("req_writer")
    if wb is None or ctx.get("finalized"):
        return
    ctx["finalized"] = True
    params: Option1Params = ctx.get("params") or Option1Params()
    if writer is None:
        _mark_scope(ctx)
        return
    try:
        with interrupt_guard.protected():
            if getattr(cfg, "REQ_REMOVE_STALE_ROWS", True):
                for fid, st in (ctx.get("req_track") or {}).items():
                    if st["skipped"] or st["done"] < st["total"] or not st["configs"]:
                        continue
                    if writer.prune_function(fid, st["desc"], st["keys"], st["configs"]):
                        ctx["dirty"] = True
            reqs_not_matched.save_descriptions()
            if getattr(cfg, "REQ_SORT_LIKE_FUNZIONI", True) \
                    and cfg.SHEET_FUNZIONI in wb.sheetnames:
                if requisiti_sorter.sort_sheet(writer.ws, wb[cfg.SHEET_FUNZIONI]):
                    ctx["dirty"] = True
                    writer._scan_level1()
            _track_requisiti(ctx, writer)
            _mark_scope(ctx)
    except Exception as exc:
        log.error(f"  [Requisiti] Pulizia/ordinamento non completati: {exc}",
                  exc_info=True)
    if not params.reqs_not_matched:
        log.info("  [Reqs not matched] Non aggiornato (scelta dell'utente).")
    elif getattr(cfg, "REQS_NOT_MATCHED_AFTER_OPTION1", True):
        try:
            if reqs_not_matched.run(wb, selection="", ai=ai) is not None:
                ctx["dirty"] = True
                ws_r = wb[reqs_not_matched.SHEET_NAME]
                run_options.tracker.rebuilt(
                    ws_r.title, f"A1:{ws_r.cell(ws_r.max_row, ws_r.max_column).coordinate}, "
                                f"{max(ws_r.max_row - 1, 0)} righe")
        except KeyboardInterrupt as exc:
            interrupt_guard.handle(exc, "Reqs not matched")
        except Exception as exc:
            log.error(f"  [Reqs not matched] Foglio non aggiornato: {exc}",
                      exc_info=True)


def _track_requisiti(ctx: dict, writer) -> None:
    """Blocchi del foglio Requisiti riscritti (dopo l'ordinamento)."""
    for fid in sorted(ctx.get("processed") or ()):
        row = writer.func_rows.get(_req_norm(fid))
        if not row:
            continue
        end = max(writer._block_end(row), row)
        last = writer.ws.cell(end, writer.ws.max_column).column_letter
        run_options.tracker.add(writer.ws.title, fid, f"A{row}:{last}{end}")


def _mark_scope(ctx: dict) -> None:
    """Commenti "Not updated" sulle celle escluse da un'esecuzione parziale."""
    wb = ctx.get("wb")
    if wb is None or cfg.SHEET_FUNZIONI not in wb.sheetnames:
        return
    ws_req = wb[cfg.SHEET_REQUISITI] if cfg.SHEET_REQUISITI in wb.sheetnames else None
    partial = bool(ctx.get("partial"))
    try:
        run_options.mark_not_updated(
            wb[cfg.SHEET_FUNZIONI], ws_req, ctx.get("scope") or set(),
            ctx.get("processed") or set(), ctx.get("partial") or [], partial)
        ctx["dirty"] = True
    except Exception as exc:
        log.error(f"  Commenti '{run_options.NOT_UPDATED}' non applicati: {exc}",
                  exc_info=True)


def _save_progress(ctx: dict, final: bool = True) -> None:
    """Salva cache, storico e (se modificato) il file Excel."""
    with interrupt_guard.protected():
        req_ai_comparator.save_cache()
        history_tracker.save_state()
        if not final and not run_options.update_db():
            # Modalita' RESULTS: il file viene scritto solo a fine esecuzione
            return
        if ctx.get("wb") is not None and ctx.get("dirty"):
            save_workbook(ctx["wb"])
            ctx["dirty"] = False
        elif ctx.get("wb") is not None:
            log.info("  Nessuna modifica al file Excel da salvare.")


def _run(start_from_func_id: str, ctx: dict) -> int:
    params: Option1Params = ctx.get("params") or Option1Params()
    start = start_from_func_id.strip() or cfg.START_FROM_FUNC_ID.strip()
    if start:
        log.info(f"⏩ Partenza da funzione: '{start}'")
    scope = params.scope
    if scope.configs and not scope.config_ok(cfg.REQ_BASE_CONFIG):
        # La configurazione base serve da riferimento al confronto
        scope = Scope(scope.frs, scope.funcs, scope.configs + [cfg.REQ_BASE_CONFIG])
    for reason in params.scope.partial_reasons():
        log.info(f"🎯 Ambito: {reason}")
    if scope is not params.scope:
        log.info(f"🎯 {cfg.REQ_BASE_CONFIG} inclusa come configurazione di riferimento")
    max_cells = params.max_cells if params.max_cells > 0 else cfg.MAX_CELLS_PER_RUN

    # ── Apri workbook ─────────────────────────────────────────────────────
    try:
        wb_data = load_workbook(str(cfg.EXCEL_PATH), data_only=True)
        ws_data = wb_data[cfg.SHEET_FUNZIONI]
    except Exception as exc:
        log.error(f"Impossibile aprire il file (data_only): {exc}")
        return 0

    try:
        wb_write = load_workbook(str(cfg.EXCEL_PATH), data_only=False)
        ws_write = wb_write[cfg.SHEET_FUNZIONI]
    except PermissionError:
        log.error("Il file Excel è aperto. Chiudilo prima di eseguire lo script.")
        return 0
    except Exception as exc:
        log.error(f"Impossibile aprire il file (write): {exc}")
        return 0

    # ── Foglio Requisiti (creato se manca) ─────────────────────────────────
    req_created = cfg.SHEET_REQUISITI not in wb_write.sheetnames
    ws_req = sheet_setup.ensure_requisiti(wb_write)
    if req_created:
        ctx["dirty"] = True

    # ── Stato storico (controllo incrementale) ────────────────────────────
    history_tracker.load_state()

    # ── Fogli di supporto ─────────────────────────────────────────────────
    sd = support_loader.load(wb_data)
    if not sd.is_valid():
        log.error("Fogli di supporto non validi (base URL mancante).")
        return 0

    # ── FASE 0: Rif. Pagina dinamico ─────────────────────────────────────
    # Va eseguita PRIMA di excel_scanner.scan(): gli URL dei FillTarget
    # leggono la cella "Rif. Pagina" per comporre il frammento "#page=".
    if getattr(cfg, "RIF_PAGINA_DYNAMIC", False):
        try:
            rif_stats = rif_pagina.run_pass(
                ws_write, ws_data, sd, start_from_func_id=start,
                scope=None if scope.is_full else scope,
            )
            if rif_stats.written:
                save_workbook(wb_write)
            if rif_stats.interrupted:
                # Interrotto durante la FASE 0: i riferimenti trovati sono
                # salvati, si riprende dalla funzione in lavorazione.
                interrupt_guard.save_checkpoint("1", rif_stats.interrupted_at)
                history_tracker.save_state()
                return 0
        except Exception as exc:
            log.error(f"Rif. Pagina dinamico non completato: {exc}", exc_info=True)

    # ── FillTarget ────────────────────────────────────────────────────────
    all_targets = list(
        excel_scanner.scan(ws_write, ws_data, sd, start_from_func_id=start,
                           include_filled=params.include_filled)
    )
    if not scope.is_full:
        all_targets = [t for t in all_targets
                       if scope.frs_ok(t.doc_id or "") and scope.func_ok(t.func_id)
                       and scope.config_ok(t.config_name)]
    old_archive.add_scope(
        f"Foglio {cfg.SHEET_FUNZIONI}: {len(all_targets)} celle 'Funzioni AI' "
        f"candidate in {len({t.func_id for t in all_targets})} funzioni"
        + (f" ({'; '.join(params.scope.partial_reasons())})"
           if not params.scope.is_full else "")
        + (f", partenza da {start}" if start else "")
        + (f", al massimo {params.max_cells} celle" if params.max_cells > 0 else ""))
    if not all_targets:
        log.info("Nessuna cella da compilare.")
        ctx["wb"] = wb_write
        if ws_req is not None:
            ctx["req_writer"] = RequisitiWriter(ws_req)
        _finalize_requisiti(ctx)
        if ctx["dirty"]:
            save_workbook(wb_write)
            ctx["dirty"] = False
        return 0

    groups: dict[tuple[str, str], list] = defaultdict(list)
    for target in all_targets:
        groups[(target.func_id, target.doc_id)].append(target)

    # Requisiti estratti per funzione: a fine esecuzione le righe non piu'
    # presenti nei documenti vengono eliminate (vedi _finalize_requisiti)
    # Il totale conta TUTTI i documenti della funzione nel foglio Funzioni
    # (anche quelli esclusi da filtro FRS/sovrascrittura): una funzione
    # elaborata solo in parte non deve perdere i requisiti degli altri FRS.
    docs_of: dict[str, set] = defaultdict(set)
    for fid, doc, *_ in excel_scanner.iter_funzioni_ai_cells(ws_write):
        docs_of[fid].add(doc)
    req_track: dict[str, dict] = {}
    for (fid, _doc), tg in groups.items():
        st = req_track.setdefault(fid, {"total": max(len(docs_of.get(fid, ())), 1),
                                        "done": 0, "skipped": False,
                                        "keys": set(), "configs": set(),
                                        "desc": tg[0].func_desc})
    ctx["req_track"] = req_track

    log.info(
        f"\nFillTarget: {len(all_targets)} celle "
        f"in {len(groups)} gruppi"
    )

    # ── INTERVENTO 1: cache LLM ──────────────────────────────────────────
    # Le cache di sessione vengono svuotate a ogni run.
    ai_synthesizer._group_cache.clear()
    ai_synthesizer.clear_summary_cache()
    func_ai_comparator.clear_cache()

    # La cache dei confronti sui requisiti NON si svuota: viene riletta dal
    # disco per riusare gli esiti dei run precedenti ed evitare di
    # reinterpellare il modello sugli stessi requisiti.
    # Per forzare la rianalisi cancella il file
    #   %LOCALAPPDATA%\FunzioniAI\req_ai_cache.json
    req_ai_comparator.load_cache()

    # Il writer indicizza una sola volta le funzioni di livello 1 del foglio
    # Requisiti e mantiene l'allineamento delle righe durante gli inserimenti.
    req_writer = RequisitiWriter(ws_req) if ws_req is not None else None
    if req_writer is not None and scope.configs:
        # Le colonne delle configurazioni fuori ambito restano invariate
        req_writer.scope_configs = list(scope.configs)
    req_rows_written = 0
    ctx["wb"] = wb_write
    ctx["req_writer"] = req_writer
    autosaver = interrupt_guard.Autosaver(lambda: _save_progress(ctx, final=False))
    if req_writer and not req_writer.func_rows:
        log.warning(
            f"  [Requisiti] Nessuna funzione di livello 1 rilevata in colonna "
            f"{cfg.REQ_FUNC_ID_COL} del foglio '{cfg.SHEET_REQUISITI}'. "
            f"Verifica che i FUNC ID siano in colonna A."
        )

    filled_count = 0
    limit_hit = False

    for (func_id, doc_id), group_targets in groups.items():
        if limit_hit:
            break
        # Contatori e punto di ripresa aggiornati a ogni gruppo: servono al
        # salvataggio su interruzione (run) e al salvataggio automatico.
        ctx["filled"], ctx["req_rows"] = filled_count, req_rows_written
        if ctx["func_id"] != func_id:
            if ctx["func_id"]:
                autosaver.tick(ctx["dirty"])
            ctx["func_id"] = func_id

        log.info(
            f"\n{'═'*55}\n"
            f"  {func_id} / {doc_id} "
            f"({len(group_targets)} config)\n"
            f"{'═'*55}"
        )

        # ──────────────────────────────────────────────────────────────────
        # CONTROLLO INCREMENTALE — LIVELLO 1 (impronta file: size + mtime)
        # ──────────────────────────────────────────────────────────────────
        recheck_mode = getattr(cfg, "RECHECK_MODE", "off")
        doc_paths: dict[str, object] = {}
        stamps:    dict[str, str]    = {}

        all_filled = all(t.already_filled for t in group_targets)
        # Celle "in ambito": raggiunte dall'elaborazione (scritte o
        # verificate invariate). Le altre, in un'esecuzione parziale,
        # ricevono il commento "Not updated".
        ctx["scope"].update((t.row, t.col) for t in group_targets)
        ctx["processed"].add(func_id)
        if params.force:
            recheck_mode = "off"   # sovrascrittura forzata: nessuno skip
        if all_filled and recheck_mode != "off":
            unchanged = True
            for target in group_targets:
                p = document_handler.download(target.url)
                doc_paths[target.config_name] = p
                st = history_tracker.file_stamp(p) if p else ""
                stamps[target.config_name] = st
                if not history_tracker.file_unchanged(
                    target.func_id, target.doc_id, target.config_name, st
                ):
                    unchanged = False
                    break
            if unchanged:
                for target in group_targets:
                    history_tracker.touch(
                        target.func_id, target.doc_id, target.config_name
                    )
                log.info("  ⏭ Invariato (livello 1: file identici) — gruppo saltato")
                req_track[func_id]["skipped"] = True
                continue
            log.info("  🔁 Documento modificato o mai analizzato — rianalisi")

        # ── Estrazione testi ──────────────────────────────────────────────
        config_texts: list[ConfigText] = []
        reqs_by_config: dict[str, list] = {}

        for target in group_targets:
            log.info(f"  [{target.config_name}] Estrazione pag.{target.page_number}...")
            doc_path = doc_paths.get(target.config_name) or document_handler.download(target.url)
            doc_paths[target.config_name] = doc_path
            if target.config_name not in stamps:
                stamps[target.config_name] = (
                    history_tracker.file_stamp(doc_path) if doc_path else ""
                )

            if not doc_path:
                config_texts.append(ConfigText(
                    config_name=target.config_name,
                    page_number=target.page_number,
                    text="",
                ))
                log.warning(f"  [{target.config_name}] Documento non trovato")
                continue

            page_text, page_end, start_partial, end_partial = (
                document_handler.extract_page_text(
                    doc_path, target.page_number,
                    func_desc=target.func_desc,
                    func_id=target.func_id,
                )
            )
            target.page_number_end  = page_end
            target.start_is_partial = start_partial
            target.end_is_partial   = end_partial

            config_texts.append(ConfigText(
                config_name=target.config_name,
                page_number=target.page_number,
                page_number_end=page_end,
                text=page_text,
            ))

            # ══════════════════════════════════════════════════════════════
            # ESTRAZIONE REQUISITI — DUE STRATEGIE IN FUSIONE
            #
            # 1. Matrice (find_tables): necessaria per le tabelle
            #    orizzontali, dove il testo lineare spezza gli ID a metà
            #    colonna rendendoli irricostruibili.
            # 2. Testo lineare: necessaria per i blocchi verticali
            #    "ID / Description / Safety level" privi di cornice, che
            #    find_tables() non rileva.
            #
            # Le due strategie NON sono alternative: nella stessa sezione
            # convivono entrambi i layout (es. pag.7 di 3EGH489028-2358,
            # dove TRS.772 è verticale e i CONCEPT.* sono orizzontali).
            # Eseguire la seconda solo "se la prima non trova nulla"
            # faceva perdere silenziosamente i requisiti verticali.
            #
            # L'intervallo di pagine è ritagliato verticalmente tramite
            # l'indice di sezione; page_text è già troncato alla sezione,
            # quindi la fusione non introduce requisiti di altre funzioni.
            # ══════════════════════════════════════════════════════════════
            reqs = requirements_extractor.extract_from_tables(
                doc_path=doc_path,
                page_start=target.page_number,
                page_end=(target.page_number_end or target.page_number),
                config_name=target.config_name,
                section_index=getattr(
                    document_handler, "LAST_SECTION_INDEX", ""
                ),
                start_is_partial=target.start_is_partial,
                end_is_partial=target.end_is_partial,
                section_title=getattr(
                    document_handler, "LAST_SECTION_TITLE", ""
                ),
                end_titles=getattr(
                    document_handler, "LAST_SECTION_END_TITLES", []
                ),
            )

            reqs_text = requirements_extractor.extract(
                text=page_text,
                config_name=target.config_name,
                page_hint=target.page_number,
            )

            seen = {r.key() for r in reqs}
            by_key = {r.key(): r for r in reqs}
            recuperati = []
            for r in reqs_text:
                # Stesso requisito trovato in tabella senza Description
                # (colonne spostate nella pagina di continuazione): la
                # Description del testo lineare completa quella della tabella.
                t_req = by_key.get(r.key())
                if t_req is not None and not (t_req.description or "").strip():
                    t_req.description = r.description
                if r.key() not in seen:
                    seen.add(r.key())
                    reqs.append(r)
                    recuperati.append(r.req_id)

            if recuperati:
                log.info(
                    f"  [{target.config_name}] {len(recuperati)} requisiti "
                    f"recuperati dal testo lineare (assenti dalle tabelle): "
                    f"{', '.join(recuperati)}"
                )

            log.info(
                f"  [{target.config_name}] TOTALE {len(reqs)} requisiti "
                f"(tabelle: {len(reqs) - len(recuperati)}, "
                f"testo: {len(recuperati)})"
            )

            reqs_by_config[target.config_name] = reqs

        valid_texts = [ct for ct in config_texts if ct.text.strip()]
        log.info(f"  Testi: {len(valid_texts)}/{len(group_targets)}")

        # ──────────────────────────────────────────────────────────────────
        # CONTROLLO INCREMENTALE — LIVELLO 2 (impronta contenuto)
        # ──────────────────────────────────────────────────────────────────
        reports: dict[str, history_tracker.ChangeReport] = {}
        any_change = False
        for target in group_targets:
            txt = next(
                (ct.text for ct in config_texts
                 if ct.config_name == target.config_name), ""
            )
            rep = history_tracker.check_content(
                func_id=target.func_id,
                doc_id=target.doc_id,
                config_name=target.config_name,
                section_text=txt,
                requirements=reqs_by_config.get(target.config_name, []),
            )
            reports[target.config_name] = rep
            any_change = any_change or rep.changed
            if rep.changed and not rep.is_new:
                log.info(f"  [{target.config_name}] Differenza: {rep.summary()}")

        # ── Scrittura foglio Requisiti ────────────────────────────────────
        # ORDINE OBBLIGATORIO: i requisiti PRIMA delle funzioni.
        # Una funzione contiene le tabelle dei requisiti: il loro esito
        # viene riusato come scorciatoia nel confronto di funzione.
        req_verdict: dict | None = None
        if req_writer and any(reqs_by_config.values()):
            try:
                ctx["dirty"] = True
                req_rows_written += req_writer.write_group(
                    func_id=func_id,
                    func_desc=group_targets[0].func_desc,
                    reqs_by_config=reqs_by_config,
                    doc_id=doc_id,
                )
                ctx["req_rows"] = req_rows_written
                st = req_track[func_id]
                st["keys"] |= getattr(req_writer, "last_keys", set())
                st["configs"] |= {c for c, r in reqs_by_config.items() if r}
                req_verdict = getattr(req_writer, "last_verdict", None)
                if req_verdict:
                    log.info(
                        f"  [Requisiti→Funzioni] {func_id}: "
                        f"{req_verdict['n_req']} requisiti, "
                        f"{req_verdict['n_diff']} divergenti"
                        + (f" in {req_verdict['configs_diff']}"
                           if req_verdict['configs_diff'] else "")
                    )
            except Exception as exc:
                req_track[func_id]["skipped"] = True
                # Un errore sul foglio Requisiti non deve interrompere
                # la compilazione delle celle "Funzioni AI"
                log.error(
                    f"  [Requisiti] Errore scrittura per '{func_id}': {exc}",
                    exc_info=True,
                )
        elif req_writer:
            log.info(f"  [Requisiti] Nessun requisito estratto per '{func_id}'")
        req_track[func_id]["done"] += 1

        # Celle già piene e contenuto invariato → nessuna chiamata LLM
        if all_filled and not any_change and recheck_mode != "off":
            for target in group_targets:
                history_tracker.record(
                    func_id=target.func_id, doc_id=target.doc_id,
                    config_name=target.config_name,
                    file_stamp_value=stamps.get(target.config_name, ""),
                    section_text=next(
                        (ct.text for ct in config_texts
                         if ct.config_name == target.config_name), ""),
                    requirements=reqs_by_config.get(target.config_name, []),
                    report=reports.get(target.config_name),
                )
            log.info("  ⏭ Invariato (livello 2: contenuto identico) — LLM saltata")
            continue

        # ── Fase 1: parsing regex (istantaneo, nessuna LLM) ──────────────
        parsed_list: list[ParsedFunction] = []
        if len(valid_texts) > 1:
            for ct in valid_texts:
                pf = parse_function_structure(
                    config_name=ct.config_name,
                    text=ct.text,
                    func_id=func_id,
                    func_desc=group_targets[0].func_desc,
                )
                parsed_list.append(pf)

        # ── Fase 2: confronto deterministico (istantaneo, nessuna LLM) ───
        det_report: dict = {
            "any_objective_differences": False,
            "all_differences_summary": [],
        }
        if len(parsed_list) > 1:
            det_report = compare_all(parsed_list)
            n_diffs = len(det_report.get("all_differences_summary", []))
            if det_report["any_objective_differences"]:
                log.info(f"  ⚡ Diff. oggettive: {n_diffs} voci")
            else:
                log.info("  ✅ Nessuna diff. oggettiva")

        # ── Fase 3: una sola chiamata LLM per il gruppo (riassunto base) ──
        if len(valid_texts) > 1:
            log.info(
                f"  Riassunto della configurazione base + confronto "
                f"deterministico su {len(valid_texts)} configurazioni..."
            )

        for target in group_targets:
            my_text = next(
                (ct.text for ct in config_texts
                 if ct.config_name == target.config_name),
                "",
            )
            cell = ws_write.cell(target.row, target.col)

            if not my_text:
                err = SynthesisResult(
                    text=f"[Testo non estratto: pag.{target.page_number} di {target.doc_id}]",
                    has_differences=None,
                )
                cell.value = err.text
                _apply_cell_style(cell, err)
                run_options.tracker.add(ws_write.title, f"{func_id} / {doc_id}",
                                        cell.coordinate)
                filled_count += 1
                ctx["filled"], ctx["dirty"] = filled_count, True

                # Registra impronte e scrive lo storico delle differenze.
                # NOTA: qui 'result' non esiste ancora — il parametro score
                # va omesso, altrimenti si ha un NameError ogni volta che
                # un documento non viene trovato sul disco.
                history_tracker.record(
                    func_id=target.func_id,
                    doc_id=target.doc_id,
                    config_name=target.config_name,
                    file_stamp_value=stamps.get(target.config_name, ""),
                    section_text=my_text,
                    requirements=reqs_by_config.get(target.config_name, []),
                    report=reports.get(target.config_name),
                )
                continue

            # ════════════════════════════════════════════════════════════
            # INTERVENTO 2 — SCHEMA DELLA CELLA "Funzioni AI"
            #
            #   VZI_Base presente
            #     • cella VZI_Base  → RIASSUNTO della funzione, NERO
            #     • altre config    → "RIFERIMENTO VZI_BASE, % SIMILARITY
            #                          = X, X>90%"  verde grassetto
            #                         oppure "... X<90%" rosso
            #
            #   VZI_Base assente
            #     • ogni config     → "MISS VZI_BASE" + RIASSUNTO, NERO
            #
            # La percentuale viene da func_ai_comparator.text_similarity(),
            # deterministica e istantanea: nessuna chiamata LLM per le
            # configurazioni diverse dalla base.
            # ════════════════════════════════════════════════════════════
            base_ct = next(
                (ct for ct in valid_texts
                 if ct.config_name.strip().lower()
                 == cfg.REQ_BASE_CONFIG.strip().lower()),
                None,
            )
            is_base = (base_ct is not None
                       and base_ct.config_name == target.config_name)

            _dec = getattr(cfg, "FUNC_SIMILARITY_DECIMALS", 1)

            if base_ct is not None and is_base:
                # ── Cella della configurazione di riferimento ───────────
                testo_cella = ai_synthesizer.summarize_function(
                    func_id=target.func_id,
                    func_desc=target.func_desc,
                    doc_id=target.doc_id,
                    config_name=target.config_name,
                    text=my_text,
                )
                font_cella = FONT_PLAIN

            elif base_ct is not None:
                # ── Confronto con la base: solo la sigla di similarita' ──
                sim_pct = func_ai_comparator.text_similarity(
                    base_ct.text, my_text
                ) * 100.0
                pct_str = f"{sim_pct:.{_dec}f}%"
                soglia_green  = getattr(cfg, "FUNC_SIMILARITY_GREEN", 90.0)
                soglia_high  = getattr(cfg, "FUNC_SIMILARITY_HIGH", 80.0)
                soglia_medium = getattr(cfg, "FUNC_SIMILARITY_MEDIUM", 50.0)
                soglia_diff = getattr(cfg, "FUNC_SIMILARITY_MEDIUM", 50.0)

                # ── Scelta stile in base alla similarita' ──
                if sim_pct >= soglia_green:
                    testo_cella = cfg.FUNC_TXT_REF_BASE_OK.format(pct=pct_str)
                    font_cella = FONT_MATCHED
                    livello = "VERDE BOLD"

                elif sim_pct >= soglia_high:
                    testo_cella = cfg.FUNC_TXT_REF_BASE_DIFF.format(pct=pct_str)
                    font_cella = FONT_HIGH
                    livello = "VERDE"

                elif sim_pct >= soglia_medium:
                    testo_cella = cfg.FUNC_TXT_REF_BASE_DIFF.format(pct=pct_str)
                    font_cella = FONT_MEDIUM
                    livello = "ARANCIONE"

                elif sim_pct >= soglia_diff:
                    testo_cella = cfg.FUNC_TXT_REF_BASE_DIFF.format(pct=pct_str)
                    font_cella = FONT_DIFF
                    livello = "ROSSO"

                else:
                    testo_cella = cfg.FUNC_TXT_REF_BASE_DIFF.format(pct=pct_str)
                    font_cella = FONT_DIFF_HIGH
                    livello = "ROSSO BOLD"

                log.info(
                    f"  [{target.config_name}] similarity vs "
                    f"{base_ct.config_name}: {pct_str} "
                )

            else:
                # ── Base assente: riassunto di ogni configurazione ───────
                riassunto = ai_synthesizer.summarize_function(
                    func_id=target.func_id,
                    func_desc=target.func_desc,
                    doc_id=target.doc_id,
                    config_name=target.config_name,
                    text=my_text,
                )
                testo_cella = f"{cfg.FUNC_TXT_MISS_BASE}\n{riassunto}"
                font_cella  = FONT_PLAIN

            # testo_cella e' ora SEMPRE valorizzato: il ramo
            # synthesize_with_comparison() resta come rete di sicurezza ma
            # non viene piu' percorso (era la pipeline LLM ridondante).
            result: SynthesisResult = synthesize_with_comparison(
                func_id=target.func_id,
                func_desc=target.func_desc,
                doc_id=target.doc_id,
                config_name=target.config_name,
                page_number=target.page_number,
                page_text=my_text,
                all_config_texts=valid_texts,
                parsed_list=parsed_list,
                det_report=det_report,
            ) if testo_cella is None else SynthesisResult(
                text=testo_cella,
                has_differences=(font_cella is FONT_DIFF)
                if font_cella is not FONT_PLAIN else None,
                score=None,
            )

            # ── Nota pagina ───────────────────────────────────────────────
            page_end    = target.page_number_end or target.page_number
            start_label = (
                f"parte di pag.{target.page_number}"
                if getattr(target, "start_is_partial", False)
                else f"pag.{target.page_number}"
            )
            end_label = (
                f"parte di pag.{page_end}"
                if getattr(target, "end_is_partial", False)
                else f"pag.{page_end}"
            )
            page_nota = (
                f"\nPag. iniziale: {start_label} — Pag. finale: {end_label}."
                if page_end > target.page_number
                else f"\nPag. di riferimento: {start_label}."
            )

            final_result = SynthesisResult(
                text=result.text + page_nota,
                has_differences=result.has_differences,
                uncertain=result.uncertain,
                checklist=result.checklist,
                score=result.score,
                technical_differences=result.technical_differences,
                editorial_differences=result.editorial_differences,
                det_summary=result.det_summary,
            )

            if font_cella is not None:
                # Percorso nuovo: stile esplicito (verde/rosso/nero),
                # coerente con il foglio Requisiti.
                _write_func_cell(cell, final_result.text, font_cella)
            else:
                cell.value = final_result.text
                _apply_cell_style(cell, final_result)
            run_options.tracker.add(ws_write.title, f"{func_id} / {doc_id}",
                                    cell.coordinate)
            filled_count += 1
            ctx["filled"], ctx["dirty"] = filled_count, True

            # Registra impronte e storico anche nel percorso nominale
            history_tracker.record(
                func_id=target.func_id,
                doc_id=target.doc_id,
                config_name=target.config_name,
                file_stamp_value=stamps.get(target.config_name, ""),
                section_text=my_text,
                requirements=reqs_by_config.get(target.config_name, []),
                report=reports.get(target.config_name),
                score=result.score,
            )

            color_label = (
                "🟢 VERDE"           if result.has_differences is False else
                "🔴 ROSSO"           if result.has_differences is True  else
                "⚫ NERO (incerto)"  if result.uncertain               else
                "⚫ NERO"
            )
            log.info(
                f"  [{target.config_name}] {color_label} | "
                f"Score: {result.score}"
            )

            # ── INTERVENTO 3a: pausa solo se esplicitamente richiesta ────
            # Ollama e' locale: con AI_CALL_DELAY_SECONDS = 0 la pausa
            # viene saltata del tutto.
            if target == group_targets[0] and cfg.AI_CALL_DELAY_SECONDS > 0:
                time.sleep(cfg.AI_CALL_DELAY_SECONDS)

            # ── INTERVENTO 3b: uscita anticipata, salva anche la cache ──
            if max_cells > 0 and filled_count >= max_cells:
                log.info(f"Limite celle raggiunto ({max_cells}).")
                limit_hit = True
                # Le celle del gruppo non ancora scritte restano fuori ambito
                done = {(t.row, t.col) for t in group_targets[
                    :group_targets.index(target) + 1]}
                ctx["scope"].difference_update(
                    (t.row, t.col) for t in group_targets
                    if (t.row, t.col) not in done)
                if f"limite di {max_cells} celle raggiunto" not in ctx["partial"]:
                    ctx["partial"].append(f"limite di {max_cells} celle raggiunto")
                break

    log.info(
        f"\n{'='*60}\n"
        f"  CELLE 'Funzioni AI' COMPILATE : {filled_count}\n"
        f"  RIGHE 'Requisiti' SCRITTE     : {req_rows_written}\n"
        f"{'='*60}"
    )

    # ── Requisiti: pulizia, ordinamento e foglio "Reqs not matched" ─────
    _finalize_requisiti(ctx)

    # ── INTERVENTO 3c: persistenza della cache dei confronti requisiti ───
    req_ai_comparator.save_cache()
    history_tracker.save_state()
    if filled_count > 0 or req_rows_written > 0 or ctx["dirty"]:
        save_workbook(wb_write)
        ctx["dirty"] = False
    else:
        log.info("Nessuna cella compilata.")

    return filled_count



MENU_OPTIONS = {
    "1": "Analisi completa FRS: sintesi AI delle funzioni + estrazione e confronto requisiti "
         "(fogli Funzioni, Requisiti, Reqs not matched)",
    "2": "Ricostruisci l'indice delle funzioni dai PDF FRS (foglio Index Funzioni)",
    "3": "Ricalcola il riferimento di pagina di ogni funzione nei PDF (Rif. Pagina del foglio Funzioni)",
    "4": "Confronto mirato dei requisiti per uno o più DOC ID (foglio Confronto Reqs)",
    "5": "Elenca i requisiti diversi fra configurazioni con note AI (foglio Reqs not matched)",
}

# Fogli che ogni opzione ricrea/aggiorna (riportati nel RICHIESTA.txt di _OLD)
OPTION_SHEETS = {
    "1": [cfg.SHEET_FUNZIONI, cfg.SHEET_REQUISITI, reqs_not_matched.SHEET_NAME],
    "2": [getattr(cfg, "SHEET_INDEX_FUNZIONI", "Index Funzioni")],
    "3": [cfg.SHEET_FUNZIONI],
    "4": [getattr(cfg, "SHEET_CONFRONTO_REQS", "Confronto Reqs")],
    "5": [reqs_not_matched.SHEET_NAME],
}


def ask_mode() -> str:
    """Menu iniziale: restituisce la chiave scelta in MENU_OPTIONS."""
    print("\n" + "=" * 60)
    print("  AskTrainMind — cosa vuoi eseguire?")
    print("=" * 60)
    for key, label in MENU_OPTIONS.items():
        print(f"  {key}) {label}")
    keys = list(MENU_OPTIONS)
    while True:
        try:
            choice = input(f"\nScelta [{'/'.join(keys)}]: ").strip()
        except EOFError:
            return "1"
        if choice in MENU_OPTIONS:
            return choice
        print(f"  Scelta non valida: digita {', '.join(keys[:-1])} oppure {keys[-1]}.")


def run_ricerca_funzioni(scope: Scope | None = None) -> int:
    """Opzione 2: crea/aggiorna il foglio 'Index Funzioni' (ambito: FRS, funzioni, configurazioni)."""
    log.info(f"  Documenti : {cfg.ONEDRIVE_DOCS_ROOT}")
    t0 = time.time()
    try:
        wb_data = load_workbook(str(cfg.EXCEL_PATH), data_only=True)
        wb_write = load_workbook(str(cfg.EXCEL_PATH), data_only=False)
    except Exception as exc:
        log.error(f"Impossibile aprire il file Excel: {exc}")
        return 0
    n = index_funzioni.run(wb_data, wb_write, scope=scope)
    _track_rebuilt(wb_write, getattr(cfg, "SHEET_INDEX_FUNZIONI", "Index Funzioni"))
    save_workbook(wb_write)
    if interrupt_guard.interrupted:
        log.warning("  Foglio 'Index Funzioni' PARZIALE salvato: rilancia "
                    "l'opzione 2 per completarlo.")
    log.info(f"  Tempo totale: {time.time() - t0:.1f}s")
    return n


def run_rif_pagina(start_from_func_id: str = "", scope: Scope | None = None) -> int:
    """
    Opzione 3: compila solo le celle "Rif. Pagina" del foglio Funzioni
    ricavando la pagina dall'indice dei PDF (stesso passaggio eseguito
    all'inizio dell'opzione 1). Non usa Ollama.
    """
    t0 = time.time()
    try:
        wb_data = load_workbook(str(cfg.EXCEL_PATH), data_only=True)
        ws_data = wb_data[cfg.SHEET_FUNZIONI]
        wb_write = load_workbook(str(cfg.EXCEL_PATH), data_only=False)
        ws_write = wb_write[cfg.SHEET_FUNZIONI]
    except PermissionError:
        log.error("Il file Excel è aperto. Chiudilo prima di eseguire lo script.")
        return 0
    except Exception as exc:
        log.error(f"Impossibile aprire il file Excel: {exc}")
        return 0

    sd = support_loader.load(wb_data)
    if not sd.is_valid():
        log.error("Fogli di supporto non validi (base URL mancante).")
        return 0

    try:
        stats = rif_pagina.run_pass(ws_write, ws_data, sd,
                                    start_from_func_id=start_from_func_id,
                                    scope=scope)
    except Exception as exc:
        log.error(f"Rif. Pagina non completato: {exc}", exc_info=True)
        return 0
    if stats.written:
        save_workbook(wb_write)
    else:
        log.info("Nessuna cella 'Rif. Pagina' scritta.")
    if stats.interrupted:
        interrupt_guard.save_checkpoint("3", stats.interrupted_at)
    else:
        interrupt_guard.clear_checkpoint("3")
    log.info(
        f"\n{'═' * 55}\n  RIEPILOGO RIFERIMENTI DA VERIFICARE\n{'═' * 55}\n"
        + rif_pagina.format_report(stats)
    )
    log.info(f"  Tempo totale: {time.time() - t0:.1f}s")
    return stats.written


def run_confronto_reqs(selection: str = "", interactive: bool = True,
                       scope: Scope | None = None) -> int:
    """
    Opzione 4: confronta per Description i requisiti dei documenti di uno o
    piu' DOC ID (foglio CONFIG) in tutte le configurazioni e scrive il
    foglio "Confronto Reqs". Non usa Ollama.
    """
    log.info(f"  Documenti : {cfg.ONEDRIVE_DOCS_ROOT}")
    t0 = time.time()
    try:
        wb_data = load_workbook(str(cfg.EXCEL_PATH), data_only=True)
        wb_write = load_workbook(str(cfg.EXCEL_PATH), data_only=False)
    except PermissionError:
        log.error("Il file Excel è aperto. Chiudilo prima di eseguire lo script.")
        return 0
    except Exception as exc:
        log.error(f"Impossibile aprire il file Excel: {exc}")
        return 0
    n = confronto_reqs.run(wb_data, wb_write, selection=selection,
                           interactive=interactive, scope=scope)
    if n is None:
        return 0
    _note_scope(wb_write, getattr(cfg, "SHEET_CONFRONTO_REQS", "Confronto Reqs"), scope)
    _track_rebuilt(wb_write, getattr(cfg, "SHEET_CONFRONTO_REQS", "Confronto Reqs"))
    save_workbook(wb_write)
    log.info(f"  Tempo totale: {time.time() - t0:.1f}s")
    return n


def run_reqs_not_matched(selection: str = "", interactive: bool = True,
                         scope: Scope | None = None) -> int:
    """
    Opzione 5: ricrea il foglio "Reqs not matched" con i requisiti del
    foglio Requisiti non MATCHED fra le configurazioni scelte dall'utente
    (Invio = tutte). Le "Note AI" usano Ollama se disponibile.
    """
    t0 = time.time()
    try:
        wb_write = load_workbook(str(cfg.EXCEL_PATH), data_only=False)
    except PermissionError:
        log.error("Il file Excel è aperto. Chiudilo prima di eseguire lo script.")
        return 0
    except Exception as exc:
        log.error(f"Impossibile aprire il file Excel: {exc}")
        return 0
    n = reqs_not_matched.run(wb_write, selection=selection, interactive=interactive,
                             scope=scope)
    if n is None:
        return 0
    _note_scope(wb_write, reqs_not_matched.SHEET_NAME, scope)
    _track_rebuilt(wb_write, reqs_not_matched.SHEET_NAME)
    sel = getattr(reqs_not_matched, "LAST_SELECTED", None)
    if sel:
        old_archive.add_scope(f"Configurazioni confrontate: {', '.join(sel)}")
    save_workbook(wb_write)
    log.info(f"  Tempo totale: {time.time() - t0:.1f}s")
    return n


def _note_scope(wb, sheet: str, scope: Scope | None) -> None:
    """Commento in A1 del foglio ricreato con un ambito limitato."""
    if scope is None or scope.is_full or sheet not in wb.sheetnames:
        return
    from openpyxl.comments import Comment
    c = Comment("Ambito dell'analisi: " + "; ".join(scope.partial_reasons()),
                "AskTrainMind")
    c.width, c.height = 320, 90
    wb[sheet].cell(1, 1).comment = c


def _track_rebuilt(wb, sheet: str) -> None:
    if sheet in wb.sheetnames:
        ws = wb[sheet]
        run_options.tracker.rebuilt(
            sheet, f"A1:{ws.cell(max(ws.max_row, 1), max(ws.max_column, 1)).coordinate}")


def resume_start(mode: str, cli_start: str, interactive: bool) -> str:
    """
    FUNC ID di partenza: --start, altrimenti il punto di ripresa lasciato da
    un'esecuzione interrotta (RESUME_FROM_CHECKPOINT), altrimenti
    START_FROM_FUNC_ID.
    """
    if cli_start.strip():
        return cli_start.strip()
    default = cfg.START_FROM_FUNC_ID.strip()
    cp = interrupt_guard.load_checkpoint(mode)
    func_id = (cp.get("func_id") or "").strip()
    if not func_id or func_id == default:
        return default
    msg = (f"L'esecuzione precedente e' stata interrotta ({cp.get('time', '?')}) "
           f"alla funzione '{func_id}'.")
    if interactive:
        print(f"\n  {msg}")
        try:
            ans = input("  Riprendere da quella funzione? [S/n]: ").strip().lower()
        except EOFError:
            ans = ""
        if ans in ("n", "no"):
            return default
    log.info(f"  ⏯ {msg} Ripresa da '{func_id}'.")
    return func_id


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Compila le celle 'Funzioni AI' (opzione 1), il foglio "
                    "'Index Funzioni' (opzione 2) o le celle 'Rif. Pagina' "
                    "(opzione 3), il foglio 'Confronto Reqs' (opzione 4) o il foglio "
                    "'Reqs not matched' (opzione 5) nel file Excel ETR1000.",
    )
    parser.add_argument("--frs", metavar="DOC_IDS", default="",
                        help="Opzioni 1-5: FRS (DOC ID foglio CONFIG col B / Funzioni "
                             "col D) da analizzare: numeri dell'elenco, intervalli "
                             "(1-3), nomi o parte univoca, separati da virgola "
                             "(es. \"FRS_Line Voltage\"). Vuoto = tutti.")
    parser.add_argument("--funcs", "-f", metavar="FUNC_IDS", default="",
                        help="Opzioni 1-5: funzioni (FUNC ID del foglio Funzioni) "
                             "degli FRS scelti, separate da virgola (es. "
                             "\"LV_Pantograph_Lifting, LV_Pantograph_Selection\"). "
                             "Vuoto = tutte.")
    parser.add_argument("--configs", "-c", metavar="CONFIGS", default="",
                        help="Opzioni 1-5: configurazioni di treno da analizzare, "
                             "separate da virgola (es. \"VZI_Base, VZI_New14, VZ_FR\"). "
                             "Vuoto = tutte. Da sola, senza --mode, avvia l'opzione 5.")
    parser.add_argument("--start", "-s", metavar="FUNC_ID", default="",
                        help="FUNC ID della funzione da cui iniziare (opzioni 1 e 3).")
    parser.add_argument("--mode", "-m", choices=list(MENU_OPTIONS),
                        help="Salta il menu: 1 = Funzioni AI e Requisiti, "
                             "2 = Ricerca Funzioni, 3 = Cerca riferimento pagina, "
                             "4 = Confronto specifico Funzioni-Requisiti, "
                             "5 = Requisiti non MATCHED tra configurazioni.")
    parser.add_argument("--doc", "-d", metavar="DOC_IDS", default="",
                        help="Come --frs; da solo, senza --mode, avvia l'opzione 4 "
                             "(es. \"FRS_Coupler\").")
    parser.add_argument("--max-cells", type=int, default=None, metavar="N",
                        help="Opzione 1: numero massimo di celle 'Funzioni AI' "
                             "da compilare (0 = tutte).")
    parser.add_argument("--overwrite", choices=["A", "S", "N", "a", "s", "n"],
                        default=None,
                        help="Opzione 1: celle gia' compilate. A = automatico "
                             "(solo se il documento e' cambiato), S = rielabora "
                             "tutte, N = solo celle vuote.")
    parser.add_argument("--no-reqs-not-matched", action="store_true",
                        help="Opzione 1: non aggiornare il foglio 'Reqs not matched'.")
    parser.add_argument("--ask", action="store_true",
                        help="Pone comunque le domande sui parametri dell'opzione "
                             "(aggiornamento DB Flotte/RESULTS, ambito FRS/funzioni/"
                             "configurazioni, parametri dell'opzione 1, "
                             "ripresa da interruzione) anche con --mode: i valori passati "
                             "da riga di comando diventano i default proposti. "
                             "Usato dal terminale developer.")
    parser.add_argument("--results-only", action="store_true",
                        help="Non modificare il DB Flotte: scrive i fogli "
                             "impattati in RESULTS/RESULTS_<data>_Opzione_<N>.xlsx.")
    args = parser.parse_args()

    interrupt_guard.install_handlers()
    opt1_cli = (args.max_cells is not None or args.overwrite
                or args.no_reqs_not_matched)
    scope_cli = any(x.strip() for x in (args.frs, args.doc, args.funcs, args.configs))
    interactive = args.ask or (not args.mode and not args.start.strip()
                               and not scope_cli and not opt1_cli
                               and not args.results_only)
    try:
        if args.mode:
            mode = args.mode
        elif args.doc.strip():
            mode = "4"
        elif args.configs.strip() and not (args.frs.strip() or args.funcs.strip()):
            mode = "5"
        elif args.start.strip() or opt1_cli or args.frs.strip() or args.funcs.strip():
            mode = "1"
        else:
            mode = ask_mode()
        old_archive.begin(
            mode, MENU_OPTIONS[mode],
            details={},
            sheets=OPTION_SHEETS.get(mode),
        )
        update = (not args.results_only) and getattr(cfg, "UPDATE_DB_DEFAULT", True)
        if interactive and not args.results_only:
            update = run_options.ask_yes_no(
                "Aggiornare direttamente il file DB Flotte? (n = crea solo il "
                "file RESULTS con i risultati)", update)
        run_options.set_update_db(update)
        old_archive.set_update_db(update)
        old_archive.set_details({"Aggiornamento DB Flotte":
                                 "si'" if update else "no, solo file RESULTS"})
        _main(mode, args, interactive)
        old_archive.finish("interrotta, dati parziali salvati"
                           if interrupt_guard.interrupted else "completata")
    except KeyboardInterrupt:
        old_archive.finish("interrotta dall'utente")
        log.warning("Esecuzione interrotta dall'utente.")
        sys.exit(130)
    if interrupt_guard.interrupted:
        log.warning(
            "Esecuzione interrotta: i dati elaborati sono stati salvati. "
            "Rilancia la stessa opzione per riprendere."
        )
        sys.exit(130)


SCOPE_NOTES = {
    "1": f"La configurazione di riferimento {cfg.REQ_BASE_CONFIG} viene sempre "
         f"elaborata insieme a quelle scelte (serve al confronto).",
    "2": "Il foglio 'Index Funzioni' viene ricreato con il solo ambito scelto.",
    "3": "Vengono ricalcolate solo le celle 'Rif. Pagina' dell'ambito scelto.",
    "4": "Serve almeno un FRS: i requisiti dei suoi documenti vengono confrontati "
         "fra le configurazioni scelte.",
    "5": "Servono almeno due configurazioni da confrontare.",
}


def option_scope(mode: str, args, interactive: bool) -> Scope:
    """
    Ambito FRS / funzioni / configurazioni dell'opzione: da riga di comando
    (--frs/--doc, --funcs, --configs) e/o domande interattive. Opzione 4 e 5:
    se non indicati valgono CONFRONTO_REQS_DOC_IDS e REQS_NOT_MATCHED_CONFIGS.
    """
    catalog = analysis_scope.load_catalog()
    frs_text = ", ".join(x.strip() for x in (args.frs, args.doc) if x.strip())
    scope, errors = analysis_scope.resolve_scope(frs_text, args.funcs,
                                                 args.configs, catalog)
    if errors:
        # Mai ricadere su "tutto" per un errore di battitura
        log.error(f"  {'; '.join(errors)} — esecuzione annullata.")
        sys.exit(2)
    if mode == "4" and not scope.frs:
        dflt, _ = analysis_scope.resolve(
            ", ".join(getattr(cfg, "CONFRONTO_REQS_DOC_IDS", []) or []), catalog.frs)
        scope = Scope(dflt, scope.funcs, scope.configs)
    if mode == "5" and not scope.configs:
        dflt, _ = analysis_scope.resolve(
            ", ".join(getattr(cfg, "REQS_NOT_MATCHED_CONFIGS", []) or []), catalog.configs)
        scope = Scope(scope.frs, scope.funcs, dflt)
    ask = interactive or (sys.stdin.isatty() and not any(
        x.strip() for x in (args.frs, args.doc, args.funcs, args.configs)))
    while True:
        if ask:
            scope = analysis_scope.ask_scope(scope, mode, catalog, SCOPE_NOTES.get(mode, ""))
        problem = ""
        if mode == "4" and not scope.frs:
            problem = "Opzione 4: scegli almeno un FRS da confrontare."
        elif mode == "5" and len(scope.configs) == 1:
            problem = "Opzione 5: servono almeno due configurazioni (Invio/'*' = tutte)."
        if not problem:
            break
        log.error(f"  {problem}")
        if not ask:
            sys.exit(2)
    for k, v in scope.describe().items():
        log.info(f"  {k:<17}: {v}")
    old_archive.set_details(scope.describe())
    for line in scope.partial_reasons():
        old_archive.add_scope(f"Ambito: {line}")
    return scope


def option1_params(args, interactive: bool, scope: Scope) -> Option1Params:
    """Parametri dell'opzione 1 da riga di comando e/o domande interattive."""
    params = Option1Params(
        max_cells=max(args.max_cells or 0, 0),
        overwrite=(args.overwrite or "A").upper(),
        start=resume_start("1", args.start, interactive),
        scope=scope,
        reqs_not_matched=(not args.no_reqs_not_matched)
        and getattr(cfg, "REQS_NOT_MATCHED_AFTER_OPTION1", True),
    )
    if interactive:
        params = run_options.ask_option1(params)
    return params


def _check_sheets() -> None:
    """Il foglio Funzioni deve esserci; i fogli generati mancanti verranno creati."""
    try:
        wb = load_workbook(str(cfg.EXCEL_PATH), read_only=True)
        names = list(wb.sheetnames)
        try:
            sheet_setup.require_funzioni(wb)
        finally:
            wb.close()
    except sheet_setup.MissingSheetError as exc:
        log.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        log.warning(f"  Controllo dei fogli non eseguito: {exc}")
        return
    missing = [s for s in (cfg.SHEET_REQUISITI, reqs_not_matched.SHEET_NAME,
                           getattr(cfg, "SHEET_INDEX_FUNZIONI", "Index Funzioni"))
               if s not in names]
    if missing:
        log.info(f"  Fogli mancanti, verranno creati quando servono: {', '.join(missing)}")


def _main(mode: str, args, interactive: bool) -> None:

    log.info("\n" + "=" * 60)
    log.info(f"  funzioni_ai_filter — {MENU_OPTIONS[mode]}")
    log.info("=" * 60)
    log.info(f"  Excel     : {cfg.EXCEL_PATH}")

    if not cfg.EXCEL_PATH.exists():
        log.error(f"File Excel non trovato: {cfg.EXCEL_PATH}")
        sys.exit(1)
    _check_sheets()
    scope = option_scope(mode, args, interactive)

    if mode == "2":
        run_ricerca_funzioni(scope)
        log.info("Fine.")
        return

    if mode == "3":
        start = resume_start("3", args.start, interactive)
        log.info(f"  Partenza  : {'funzione ' + repr(start) if start else 'inizio foglio'}")
        old_archive.set_details({"FUNC ID partenza": start or "inizio foglio"})
        run_rif_pagina(start_from_func_id=start, scope=scope)
        log.info("Fine.")
        return

    if mode == "4":
        run_confronto_reqs(interactive=False, scope=scope)
        log.info("Fine.")
        return

    if mode == "5":
        run_reqs_not_matched(interactive=False, scope=scope)
        log.info("Fine.")
        return

    log.info(f"  AI model  : Ollama / {cfg.OLLAMA_MODEL}")
    params = option1_params(args, interactive, scope)
    log.info(f"  Partenza  : {'funzione ' + repr(params.start) if params.start else 'inizio foglio'}")
    for k, v in params.describe().items():
        log.info(f"  {k:<17}: {v}")
    old_archive.set_details(params.describe())
    if not params.reqs_not_matched:
        old_archive.set_sheets([s for s in old_archive.sheets()
                                if s != reqs_not_matched.SHEET_NAME])

    if not check_prerequisites():
        sys.exit(1)

    run(params=params)
    log.info("Fine.")


if __name__ == "__main__":
    main()