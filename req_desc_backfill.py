"""
req_desc_backfill.py
--------------------
Completa il foglio «Requisiti» con la Description di OGNI configurazione.

Le versioni precedenti di requisiti_writer scrivevano solo un'etichetta in
alcune celle, senza il testo del requisito:

  * "MISS VZI_BASE REQ, MATCHED"         (requisito uguale in tutte le
                                          configurazioni ma assente in VZI_Base)
  * differenze AI rispetto a VZI_Base    (spiegazione in rosso, senza il testo
                                          della configurazione)
  * "MISS VZI_BASE REQ" + "[Description non estratta dal documento]"
  * celle VZI_Base senza "Description:"

Così Esplora, Chiedi e il file Excel non potevano mostrare cosa dice il
requisito in quella configurazione. Questo script rilegge le pagine della
funzione nei PDF (stesse strategie dell'opzione 1: tabelle + testo lineare,
nessuna AI) e aggiunge in coda alla cella il blocco nero
"Description: … / Type … / SIL …". Le etichette e le spiegazioni esistenti
non vengono toccate.

    python req_desc_backfill.py            (anche dal menu developer)
    python req_desc_backfill.py --dry-run  (solo conteggio, nessuna scrittura)
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import config as cfg

log = logging.getLogger("req_desc_backfill")


def _text_of(v) -> str:
    if v is None:
        return ""
    return str(v)


def _extract(doc_path: Path, ref: dict, func_id: str, func_desc: str, config: str, cache: dict) -> dict:
    """{id_key: Requirement} delle pagine della funzione (cache per documento/pagine)."""
    import document_handler
    import requirements_extractor as RX
    key = (str(doc_path), ref.get("page") or ref.get("first") or 0, ref.get("last") or 0, func_id)
    if key in cache:
        return cache[key]
    out: dict = {}
    page = int(ref.get("page") or ref.get("first") or 0)
    try:
        if page:
            text, end, sp, ep = document_handler.extract_page_text(doc_path, page, func_desc=func_desc,
                                                                   func_id=func_id)
            reqs = RX.extract_from_tables(
                doc_path=doc_path, page_start=page, page_end=end or page, config_name=config,
                section_index=getattr(document_handler, "LAST_SECTION_INDEX", ""),
                start_is_partial=sp, end_is_partial=ep,
                section_title=getattr(document_handler, "LAST_SECTION_TITLE", ""),
                end_titles=getattr(document_handler, "LAST_SECTION_END_TITLES", []))
            for r in reqs + RX.extract(text=text, config_name=config, page_hint=page):
                k = RX.id_key(r.req_id)
                old = out.get(k)
                if old is None or (not (old.description or "").strip() and (r.description or "").strip()):
                    out[k] = r
    except Exception as exc:
        log.warning("Estrazione non riuscita %s p.%s: %s", doc_path.name, page, exc)
    cache[key] = out
    return out


def _whole_doc(doc_path: Path, config: str, cache: dict) -> dict:
    """Riserva: requisiti di tutto il documento (testo lineare), se l'ID non e' nelle pagine della funzione."""
    import fitz
    import requirements_extractor as RX
    key = ("ALL", str(doc_path))
    if key in cache:
        return cache[key]
    out: dict = {}
    try:
        with fitz.open(str(doc_path)) as doc:
            text = "\n".join(f"[Pagina {i + 1}]\n{p.get_text()}" for i, p in enumerate(doc))
        for r in RX.extract(text=text, config_name=config, page_hint=1):
            if (r.description or "").strip():
                out.setdefault(RX.id_key(r.req_id), r)
    except Exception as exc:
        log.warning("Lettura di %s non riuscita: %s", doc_path.name, exc)
    cache[key] = out
    return out


def run(dry_run: bool = False, progress=print) -> dict:
    import openpyxl
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    from openpyxl.styles import Alignment, Font

    import req_ai_comparator as reqai
    import reqs_not_matched as rnm
    import requirements_extractor as RX
    from webapp import documents as D
    from webapp import qa
    from webapp import workbook as W

    t0 = time.time()
    xp = W.excel_path()
    if not xp:
        raise FileNotFoundError(f"File Excel non trovato: {cfg.EXCEL_PATH}")
    progress(f"Lettura di {xp.name}…")
    model = W.load_snapshot(xp).model
    D.FILES.build_async()
    D.FILES.wait(180)
    wb = openpyxl.load_workbook(xp, rich_text=True)
    ws = wb[cfg.SHEET_REQUISITI]
    head = [_text_of(c.value).strip() for c in ws[1]]
    cols = {h: i + 1 for i, h in enumerate(head) if h in model["configs"]}
    sep = cfg.REQ_FIELD_SEP
    stats = {"targets": 0, "filled": 0, "not_found": 0, "no_doc": 0, "rows": 0}
    cache: dict = {}
    fid = ""
    missing: list[str] = []
    for row in range(2, ws.max_row + 1):
        a = _text_of(ws.cell(row, 1).value).strip()
        if a:
            fid = a
            continue
        rid = _text_of(ws.cell(row, 4).value).strip()
        f = model["functions"].get(fid)
        if not rid or not f:
            continue
        listed = {rnm._n(x) for x in _text_of(ws.cell(row, 5).value).split(",") if x.strip()}
        touched = False
        for c, col in cols.items():
            cell = ws.cell(row, col)
            txt = _text_of(cell.value)
            st = rnm.cell_state(c, txt, listed)
            if st.kind in ("absent", "match_base") or rnm.description_from_cell(st):
                continue
            stats["targets"] += 1
            ref = qa.doc_ref(model, f, c)
            path = D.FILES.path(ref["fid"]) if ref and ref.get("fid") else None
            if not path:
                stats["no_doc"] += 1
                continue
            k = RX.id_key(re.sub(r"^\s*\d+\)\s*", "", rid))
            req = _extract(Path(path), ref, fid, f.get("desc", ""), c, cache).get(k)
            if req is None or not (req.description or "").strip():
                req = _whole_doc(Path(path), c, cache).get(k) or req
            if req is None or not (req.description or "").strip():
                stats["not_found"] += 1
                missing.append(f"{fid} · {rid} · {c}")
                continue
            dump = reqai.dump_fields(req)
            stats["filled"] += 1
            touched = True
            if dry_run:
                continue
            if st.kind == "ref":
                cell.value = dump
                cell.font = Font(color=cfg.REQ_COLOR_BLACK, bold=False)
            elif st.kind == "only":
                cell.value = f"{cfg.REQ_TXT_MISS_ONLY}\n{req.description.strip()}"
                cell.font = Font(color=cfg.REQ_COLOR_BLACK, bold=False)
            else:
                if isinstance(cell.value, CellRichText):
                    blocks = list(cell.value)
                else:
                    color = cfg.REQ_COLOR_GREEN if st.kind == "match_nobase" else cfg.REQ_COLOR_RED
                    if cell.font is not None and cell.font.color is not None and isinstance(cell.font.color.rgb, str):
                        color = cell.font.color.rgb[-6:]
                    blocks = [TextBlock(InlineFont(color=color, b=bool(cell.font and cell.font.b)), txt.rstrip())]
                blocks.append(TextBlock(InlineFont(color=cfg.REQ_COLOR_BLACK, b=False), sep + dump))
                cell.value = CellRichText(*blocks)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        if touched:
            stats["rows"] += 1
        if row % 500 == 0:
            progress(f"  riga {row}/{ws.max_row}: {stats['filled']} Description aggiunte "
                     f"({len(cache)} sezioni di documento lette, {time.time() - t0:.0f} s)")
    if not dry_run and stats["filled"]:
        try:
            import old_archive
            old_archive.begin("BF", "Completamento Description dei requisiti")
            old_archive.archive_before_save(xp)
        except Exception as exc:
            log.warning("Archivio _OLD non aggiornato: %s", exc)
        tmp = xp.with_name(xp.stem + ".tmp.xlsx")
        wb.save(tmp)
        shutil.move(str(tmp), str(xp))
    stats["missing"] = missing
    stats["seconds"] = round(time.time() - t0)
    progress(f"✔ {stats['filled']} Description aggiunte in {stats['rows']} righe "
             f"(celle senza testo: {stats['targets']}, non trovate nei PDF: {stats['not_found']}, "
             f"senza documento: {stats['no_doc']}) in {stats['seconds']} s"
             + (" — prova, nessuna scrittura" if dry_run else ""))
    if missing:
        progress("  Non trovate (prime 15): " + "; ".join(missing[:15]))
    return stats


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="conta soltanto, non scrive il file Excel")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        run(args.dry_run)
    except PermissionError:
        print("\n  Il file Excel è aperto: chiuderlo e riprovare.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
