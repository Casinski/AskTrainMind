"""
opzione0.py — OPZIONE 0 TOTAL e OPZIONE 0 CREA DB CONFIG.

OPZIONE 0 CREA DB CONFIG
    Legge il foglio CONFIG e salva la memoria "FOGLIO CONFIG CODICE-REV FRS
    PER CONFIGURAZIONE" (config_db.py): Codice e Rev di ogni DOC ID per
    ogni configurazione.

OPZIONE 0 TOTAL (aggiornamento incrementale dopo una modifica del foglio CONFIG)
    STEP 0  nuova memoria del foglio CONFIG e confronto con la precedente:
            un documento e' cambiato se ha Codice o Rev diversi.
    STEP 1  per ogni FRS cambiato, nelle funzioni con quel DOC ID e quella
            configurazione:
              - file presente nella cartella <cfg>/CONFIG/FRS → Rif. Pagina e
                Funzioni AI svuotati (sfondo bianco);
              - file assente → Link e Rif. Pagina svuotati, Funzioni AI =
                "LINK DOCUMENTALE NON INSERITO" (sfondo salmone);
            in entrambi i casi le celle del foglio Requisiti della
            configurazione vengono svuotate (riga eliminata se resta vuota).
            Documenti non FRS cambiati e collegati nel foglio Funzioni: "X"
            rossa in Rif. Pagina (la pagina web non li mostra finche' l'utente
            non reinserisce il riferimento di pagina).
    STEP 2  nuovo Rif. Pagina (stessa ricerca dell'opzione 3); i riferimenti
            mancanti o non numerici li inserisce l'utente nel file Excel. Le
            celle rimaste vuote → "FUNZIONE NON PRESENTE" (sfondo giallo).
    STEP 3  CHECK dei casi ammessi (1 link mancante, 2 funzione non presente,
            3 da ricalcolare); le anomalie le sana l'utente.
    STEP 4  Funzioni AI e Requisiti ricalcolati (opzione 1) solo per le
            celle del caso 3.
    STEP 5  salvataggio, pagina web dist/<AAAA-MM-GG>/DBFlotte1000.html e
            copia del file Excel nella stessa cartella; la nuova memoria del
            foglio CONFIG diventa quella di riferimento.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Color, Font, PatternFill

import config as cfg
import config_db

log = logging.getLogger("opzione0")

YELLOW, RESET = "\033[93m", "\033[0m"
QUESTION_RIF = ("Posso controllare il file excel per valutare se tutte le funzioni "
                "con link hanno un riferimento di pagina?")
QUESTION_CHECK = ("Posso ricontrollare il file excel per valutare se le anomalie "
                  "sono state sanate?")

FONT_STATUS = Font(color="FF000000", bold=True)
FONT_X = Font(color="FFFF0000", bold=True)
FILL_WHITE = PatternFill(fill_type="solid", fgColor="FFFFFFFF")


class Aborted(Exception):
    """L'utente ha interrotto l'opzione (risposta «q»)."""


# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------

def say(msg: str = "") -> None:
    print(msg, flush=True)


def yellow(msg: str) -> None:
    """Istruzioni per l'utente: in giallo."""
    for line in str(msg).splitlines() or [""]:
        print(f"{YELLOW}{line}{RESET}", flush=True)


def ask_go(question: str, extra: dict[str, str] | None = None) -> str:
    """
    Attende la conferma dell'utente: «S» per continuare, «q» per
    interrompere, oppure una delle chiavi di 'extra' (es. C = correggi).
    """
    keys = {"s": "S"} | {k.lower(): k for k in (extra or {})}
    hint = "S = sì" + "".join(f", {k} = {v}" for k, v in (extra or {}).items()) + ", q = interrompi"
    while True:
        try:
            v = input(f"{YELLOW}  ➜ {question} [{hint}]: {RESET}").strip().lower()
        except EOFError:
            raise Aborted()
        if v in ("s", "si", "sì", "y", "yes"):
            return "S"
        if v in ("q", "esci", "exit"):
            raise Aborted()
        if v in keys:
            return keys[v]
        yellow("    Risposta non valida: scrivi S quando hai finito di modificare il file Excel.")


# ---------------------------------------------------------------------------
# Stili delle celle "Funzioni AI"
# ---------------------------------------------------------------------------

def fill_link_missing() -> PatternFill:
    theme = getattr(cfg, "FILL_LINK_MISSING_THEME", None)
    if theme:
        return PatternFill(fill_type="solid", fgColor=Color(theme=theme[0], tint=theme[1]))
    return PatternFill(fill_type="solid", fgColor="FF" + cfg.FILL_LINK_MISSING_RGB)


def fill_not_present() -> PatternFill:
    return PatternFill(fill_type="solid", fgColor="FF" + getattr(cfg, "FILL_NOT_PRESENT_RGB", "FFFF00"))


def txt_link_missing() -> str:
    return getattr(cfg, "FUNC_TXT_LINK_MISSING", "LINK DOCUMENTALE NON INSERITO")


def txt_not_present() -> str:
    return getattr(cfg, "FUNC_TXT_NOT_PRESENT", "FUNZIONE NON PRESENTE")


def txt_invalid() -> str:
    return getattr(cfg, "RIF_PAGINA_INVALID_TXT", "X")


def _status(cell, text: str, fill: PatternFill) -> None:
    cell.value = text
    cell.font = FONT_STATUS
    cell.fill = fill
    cell.alignment = Alignment(wrap_text=True, vertical="top")


def set_link_missing(cell) -> None:
    _status(cell, txt_link_missing(), fill_link_missing())


def set_not_present(cell) -> None:
    _status(cell, txt_not_present(), fill_not_present())


def set_empty_white(cell) -> None:
    cell.value = None
    cell.fill = FILL_WHITE


def set_invalid_x(cell) -> None:
    cell.value = txt_invalid()
    cell.font = FONT_X
    cell.alignment = Alignment(horizontal="center", vertical="top")


def is_white(cell) -> bool:
    f = cell.fill
    if f is None or f.fill_type in (None, "none"):
        return True
    c = f.fgColor
    if c is None:
        return True
    if c.type == "rgb":
        return str(c.rgb).upper()[-6:] == "FFFFFF" or str(c.rgb) == "00000000"
    if c.type == "theme":
        return c.theme == 0 and not (c.tint or 0)
    return False


# ---------------------------------------------------------------------------
# Foglio Funzioni: blocchi funzione → documento
# ---------------------------------------------------------------------------

def _str(v) -> str:
    if v is None:
        return ""
    if "formula" in type(v).__name__.lower():
        return ""
    return str(v).strip()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _is_rif(label: str) -> bool:
    low = norm(label)
    return low.startswith("rif") or low == "pagina"


def _is_ai(label: str) -> bool:
    return norm(label) == "funzioni ai"


def has_link(ws, row: int, col: int) -> bool:
    """La cella Link contiene una formula o un testo (anche non valido)."""
    if not row:
        return False
    v = ws.cell(row, col).value
    if v is None:
        return False
    s = str(v).strip()
    return bool(s) and s not in ("\\", "/")


def page_number(value) -> int | None:
    """Numero di pagina se la cella contiene solo un numero, altrimenti None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 and float(value).is_integer() else None
    s = str(value).strip()
    return int(s) if re.fullmatch(r"\d+", s) and int(s) > 0 else None


@dataclass
class Block:
    func_id: str
    func_desc: str
    func_row: int
    doc_id: str
    cart: str
    link_row: int
    rif_row: int = 0
    ai_row: int = 0
    extra_rows: list[int] = field(default_factory=list)


@dataclass
class Sheet:
    blocks: list[Block]
    config_cols: dict[str, int]          # {nome configurazione: colonna}

    def col(self, config: str) -> int:
        n = norm(config)
        return next((c for k, c in self.config_cols.items() if norm(k) == n), 0)

    def find(self, func_id: str, doc_id: str) -> Block | None:
        f, d = norm(func_id), norm(doc_id)
        return next((b for b in self.blocks if norm(b.func_id) == f and norm(b.doc_id) == d), None)

    def with_doc(self, doc_id: str) -> list[Block]:
        d = norm(doc_id)
        return [b for b in self.blocks if norm(b.doc_id) == d]


def parse_funzioni(ws) -> Sheet:
    from excel_scanner import _build_header_map
    hm = _build_header_map(ws)
    id_col, desc_col, cart_col = hm["id"], hm["funzione"], hm["doc_cartella"]
    doc_col, info_col = hm["doc_id"], hm["info_doc"]
    config_cols = {}
    for c in range(info_col + 1, ws.max_column + 1):
        name = _str(ws.cell(1, c).value)
        if name:
            config_cols[name.replace("\n", " / ")] = c
    blocks: list[Block] = []
    func_id = func_desc = ""
    func_row = 0
    cur: Block | None = None
    invalid = {"", "\\", "/", "tbd"}
    for row in range(2, ws.max_row + 1):
        v_id = _str(ws.cell(row, id_col).value)
        if v_id:
            func_id, func_desc, func_row, cur = v_id, _str(ws.cell(row, desc_col).value), row, None
            continue
        if not func_id:
            continue
        v_cart = _str(ws.cell(row, cart_col).value)
        v_doc = _str(ws.cell(row, doc_col).value)
        if v_cart and v_doc:
            cur = None
            if v_doc.lower() not in invalid:
                cur = Block(func_id, func_desc, func_row, v_doc, v_cart, row)
                blocks.append(cur)
            continue
        if cur is None:
            continue
        label = _str(ws.cell(row, info_col).value)
        if not label:
            continue
        if _is_rif(label) and not cur.rif_row:
            cur.rif_row = row
        elif _is_ai(label) and not cur.ai_row:
            cur.ai_row = row
        else:
            cur.extra_rows.append(row)
    return Sheet(blocks, config_cols)


# ---------------------------------------------------------------------------
# Foglio Requisiti
# ---------------------------------------------------------------------------

def clear_requisiti(ws_req, items: set[tuple[str, str, str]]) -> tuple[int, int]:
    """
    Svuota, nel foglio Requisiti, le celle della configurazione dei requisiti
    estratti dal documento (col C = DOC ID) sotto la funzione, e toglie la
    configurazione dall'elenco di col E. Se la riga non ha piu' celle di
    configurazione compilate viene eliminata. items = {(func, doc, config)}.
    Ritorna (celle svuotate, righe eliminate).
    """
    if ws_req is None or not items:
        return 0, 0
    import requisiti_writer as RW
    writer = RW.RequisitiWriter(ws_req)
    by_func: dict[str, dict[str, set[str]]] = {}
    for f, d, c in items:
        by_func.setdefault(f, {}).setdefault(norm(d), set()).add(norm(c))
    cleared = deleted = 0
    for func, docs in by_func.items():
        func_row = writer.func_rows.get(RW._norm(func))
        if not func_row:
            continue
        func_docs = {norm(x) for x in writer.func_docs.get(RW._norm(func), [])}
        end = writer._block_end(func_row)
        to_delete = []
        for row in range(func_row + 1, end + 1):
            if _str(ws_req.cell(row, cfg.REQ_FUNC_ID_COL).value):
                break
            frs = norm(_str(ws_req.cell(row, cfg.REQ_FRS_COL).value))
            if frs:
                configs = docs.get(frs)
            elif len(func_docs) == 1 and next(iter(func_docs)) in docs:
                configs = docs[next(iter(func_docs))]
            else:
                configs = None
            if not configs:
                continue
            touched = False
            for name_n, col in writer.config_cols.items():
                if norm(name_n) in configs and ws_req.cell(row, col).value not in (None, ""):
                    ws_req.cell(row, col).value = None
                    cleared += 1
                    touched = True
            listed = [x.strip() for x in str(ws_req.cell(row, cfg.REQ_CONFIG_COL).value or "").split(",") if x.strip()]
            keep = [x for x in listed if norm(x) not in configs]
            if len(keep) != len(listed):
                _write_config_list(ws_req.cell(row, cfg.REQ_CONFIG_COL), keep)
                touched = True
            if touched and not any(_str(ws_req.cell(row, col).value) for col in writer.config_cols.values()):
                to_delete.append(row)
        for row in reversed(to_delete):
            ws_req.delete_rows(row, 1)
            deleted += 1
        if to_delete:
            writer._scan_level1()
    return cleared, deleted


def _write_config_list(cell, configs: list[str]) -> None:
    import config_colors
    import requisiti_writer as RW
    if not configs:
        cell.value = None
        return
    if RW._RICH and len(configs) > 1:
        blocks = []
        for i, c in enumerate(configs):
            if i:
                blocks.append(RW.TextBlock(RW.InlineFont(color="FF000000", b=True), ", "))
            blocks.append(RW.TextBlock(RW.InlineFont(color=config_colors.color_for(c), b=True), c))
        cell.value = RW.CellRichText(*blocks)
    else:
        cell.value = ", ".join(configs)
        cell.font = Font(color=config_colors.color_for(configs[0]), bold=True)


def requisiti_dirty(ws_req, items: set[tuple[str, str, str]]) -> set[tuple[str, str, str]]:
    """Elementi (func, doc, config) che hanno ancora celle nel foglio Requisiti."""
    if ws_req is None or not items:
        return set()
    import requisiti_writer as RW
    writer = RW.RequisitiWriter(ws_req)
    out = set()
    for f, d, c in items:
        func_row = writer.func_rows.get(RW._norm(f))
        col = writer.config_cols.get(RW._norm(c))
        if not func_row:
            continue
        func_docs = {norm(x) for x in writer.func_docs.get(RW._norm(f), [])}
        for row in range(func_row + 1, writer._block_end(func_row) + 1):
            if _str(ws_req.cell(row, cfg.REQ_FUNC_ID_COL).value):
                break
            frs = norm(_str(ws_req.cell(row, cfg.REQ_FRS_COL).value))
            if frs != norm(d) and not (not frs and func_docs == {norm(d)}):
                continue
            listed = {norm(x) for x in str(ws_req.cell(row, cfg.REQ_CONFIG_COL).value or "").split(",")}
            if (col and _str(ws_req.cell(row, col).value)) or norm(c) in listed:
                out.add((f, d, c))
                break
    return out


# ---------------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------------

def load(data_only: bool = False):
    while True:
        try:
            return load_workbook(str(cfg.EXCEL_PATH), data_only=data_only)
        except PermissionError:
            yellow(f"  Il file Excel {cfg.EXCEL_PATH.name} è bloccato: chiudilo in Excel.")
            ask_go("Ho chiuso il file Excel, posso riprovare?")


def save(wb) -> None:
    """Salva il DB Flotte (la prima volta archivia la versione precedente in _OLD)."""
    import interrupt_guard
    import old_archive
    from funzioni_ai_filter import _save_atomic
    old_archive.archive_before_save(Path(cfg.EXCEL_PATH))
    while True:
        try:
            with interrupt_guard.protected():
                _save_atomic(wb, Path(cfg.EXCEL_PATH))
            say(f"  💾 File Excel salvato: {cfg.EXCEL_PATH}")
            return
        except PermissionError:
            yellow(f"  Il file Excel {cfg.EXCEL_PATH.name} è aperto in Excel e non può essere salvato.\n"
                   "  Salva e chiudi il file in Excel, poi conferma.")
            ask_go("Ho chiuso il file Excel, posso salvare?")


# ---------------------------------------------------------------------------
# Elementi impattati
# ---------------------------------------------------------------------------

@dataclass
class Target:
    """Una funzione di un documento FRS cambiato, per una configurazione."""
    func_id: str
    doc_id: str
    config: str
    file: Path | None = None
    state: str = ""          # "missing" (caso 1) | "check" (da Rif. Pagina) | "not_present" (caso 2) | "ok" (caso 3)
    url: str = ""

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.func_id, self.doc_id, self.config)

    def label(self) -> str:
        return f"{self.func_id} · {self.doc_id} · {self.config}"


def _locate_file(ch: config_db.Change, sd) -> Path | None:
    if not ch.new_code:
        return None
    p = config_db.find_file(ch.config, ch.category, ch.new_code, ch.ext)
    if p:
        return p
    if getattr(cfg, "OPZIONE0_DOWNLOAD_CHECK", False) and sd is not None:
        import rif_pagina
        import url_builder
        url = url_builder.build(sd, ch.doc_id, ch.config, 0, doc_cartella="CONFIG")
        return rif_pagina.resolve_pdf(url) if url else None
    return None


def _url(sd, doc_id: str, config: str, cart: str) -> str:
    if sd is None:
        return ""
    try:
        import url_builder
        return url_builder.build(sd, doc_id, config, 0, doc_cartella=cart) or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# STEP 1
# ---------------------------------------------------------------------------

def step1(changes: list[config_db.Change], sd) -> tuple[list[Target], list[dict]]:
    say("\n── STEP 1 · Pulizia delle funzioni dei documenti aggiornati")
    wb = load()
    ws = wb[cfg.SHEET_FUNZIONI]
    ws_req = wb[cfg.SHEET_REQUISITI] if cfg.SHEET_REQUISITI in wb.sheetnames else None
    sh = parse_funzioni(ws)
    targets: list[Target] = []
    anomalies: list[dict] = []
    req_items: set[tuple[str, str, str]] = set()
    for ch in changes:
        col = sh.col(ch.config)
        blocks = sh.with_doc(ch.doc_id)
        if not blocks or not col:
            say(f"  · {ch.describe()} — nessuna funzione collegata nel foglio Funzioni")
            continue
        if ch.is_frs:
            f = _locate_file(ch, sd)
            say(f"  · {ch.describe()} — {len(blocks)} funzioni — file "
                + (f"presente ({f.name})" if f else "NON presente nella cartella "
                   + config_db.relative_path(ch.config, ch.category, ch.new_code or '?', ch.ext).rsplit('/', 1)[0]))
            for b in blocks:
                t = Target(b.func_id, b.doc_id, ch.config, f, url=_url(sd, b.doc_id, ch.config, b.cart))
                link = has_link(ws, b.link_row, col)
                if b.rif_row:
                    ws.cell(b.rif_row, col).value = None
                if f and link:
                    t.state = "check"
                    if b.ai_row:
                        set_empty_white(ws.cell(b.ai_row, col))
                else:
                    t.state = "missing"
                    if not f and link:
                        ws.cell(b.link_row, col).value = None
                    if b.ai_row:
                        set_link_missing(ws.cell(b.ai_row, col))
                targets.append(t)
                req_items.add(t.key)
        else:
            n = 0
            for b in blocks:
                if not has_link(ws, b.link_row, col) or not b.rif_row:
                    continue
                set_invalid_x(ws.cell(b.rif_row, col))
                anomalies.append({"func": b.func_id, "doc": b.doc_id, "config": ch.config,
                                  "cell": ws.cell(b.rif_row, col).coordinate, "change": ch.describe()})
                n += 1
            say(f"  · {ch.describe()} — {n} riferimenti di pagina invalidati con la X rossa")
    cleared, deleted = clear_requisiti(ws_req, req_items)
    say(f"  Requisiti: {cleared} celle svuotate, {deleted} righe eliminate")
    missing = [t for t in targets if t.state == "missing"]
    if missing:
        yellow(f"\n  {len(missing)} funzioni senza documento o senza link: «{txt_link_missing()}» nel campo Funzioni AI.")
        for t in missing[:30]:
            yellow(f"    - {t.label()}" + ("" if not t.file else " (file presente: puoi inserire il link nel foglio Funzioni)"))
        if len(missing) > 30:
            yellow(f"    … e altre {len(missing) - 30}")
    if anomalies:
        report_x(anomalies)
    save(wb)
    return targets, anomalies


def report_x(anomalies: list[dict]) -> None:
    yellow(f"\n  ⚠ {len(anomalies)} riferimenti di pagina di documenti NON FRS aggiornati sono stati "
           f"invalidati con una «{txt_invalid()}» rossa nel foglio «{cfg.SHEET_FUNZIONI}».\n"
           "  COSA FARE: apri il file Excel, cerca le celle indicate (Rif. Pagina sotto il link del documento),\n"
           "  apri il documento aggiornato e scrivi a mano il nuovo numero di pagina al posto della X.\n"
           "  Finché la X resta, la pagina web non mostra il documento né il PDF alla pagina associata.")
    for a in anomalies[:40]:
        yellow(f"    - cella {a['cell']}: {a['func']} · {a['doc']} · {a['config']}")
    if len(anomalies) > 40:
        yellow(f"    … e altre {len(anomalies) - 40}")


def pending_x() -> list[dict]:
    """Celle Rif. Pagina con la X rossa ancora presenti nel foglio Funzioni."""
    wb = load()
    ws = wb[cfg.SHEET_FUNZIONI]
    sh = parse_funzioni(ws)
    out = []
    for b in sh.blocks:
        if not b.rif_row:
            continue
        for name, col in sh.config_cols.items():
            if _str(ws.cell(b.rif_row, col).value).upper() == txt_invalid().upper():
                out.append({"func": b.func_id, "doc": b.doc_id, "config": name,
                            "cell": ws.cell(b.rif_row, col).coordinate})
    return out


# ---------------------------------------------------------------------------
# STEP 2
# ---------------------------------------------------------------------------

def step2(targets: list[Target], sd) -> None:
    check = [t for t in targets if t.state == "check"]
    say(f"\n── STEP 2 · Ricerca del nuovo Riferimento di pagina ({len(check)} funzioni)")
    if not check:
        return
    import rif_pagina
    from analysis_scope import Scope
    wb = load()
    ws = wb[cfg.SHEET_FUNZIONI]
    ws_data = load(data_only=True)[cfg.SHEET_FUNZIONI]
    sh = parse_funzioni(ws)
    cells = {}
    for t in check:
        b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
        if b and b.rif_row and col:
            cells[(b.rif_row, col)] = t
    scope = Scope(sorted({t.doc_id for t in check}), sorted({t.func_id for t in check}),
                  sorted({t.config for t in check}))
    try:
        functions = rif_pagina.scan_and_resolve(ws, ws_data, sd, "", scope)
        for fr in functions:
            fr.refs = [r for r in fr.refs if (r.row, r.col) in cells]
        stats = rif_pagina.write_refs(ws, [fr for fr in functions if fr.refs])
        say(f"  Riferimenti di pagina scritti: {stats.written}")
    except Exception as exc:
        log.error(f"Ricerca del Rif. Pagina non completata: {exc}", exc_info=True)
        yellow(f"  Ricerca automatica non riuscita ({exc}): i riferimenti vanno inseriti a mano.")
    save(wb)

    while True:
        wb = load()
        ws = wb[cfg.SHEET_FUNZIONI]
        sh = parse_funzioni(ws)
        todo = []
        for t in check:
            b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
            if not b or not b.rif_row or not col:
                continue
            v = ws.cell(b.rif_row, col).value
            if page_number(v) is None:
                todo.append((t, ws.cell(b.rif_row, col).coordinate, _str(v)))
        if not todo:
            break
        yellow(f"\n  ✋ AZIONE RICHIESTA: {len(todo)} funzioni con link non hanno un riferimento di pagina numerico.\n"
               f"  1) Apri il file {cfg.EXCEL_PATH.name}, foglio «{cfg.SHEET_FUNZIONI}».\n"
               "  2) Per ogni cella indicata apri il PDF (link soprastante) e scrivi SOLO il numero della pagina\n"
               "     in cui inizia la funzione (es. 14). Se il valore è «N utente - M dinamico» lascia un solo numero.\n"
               "  3) Se la funzione non esiste nel documento lascia la cella VUOTA: verrà scritto\n"
               f"     «{txt_not_present()}» nel campo Funzioni AI.\n"
               "  4) Salva e chiudi il file Excel, poi rispondi S.")
        for t, coord, v in todo[:60]:
            yellow(f"    - cella {coord}: {t.label()}" + (f"  (attuale: «{v}»)" if v else "  (vuota)")
                   + (f"\n        PDF: {t.url}" if t.url else ""))
        if len(todo) > 60:
            yellow(f"    … e altre {len(todo) - 60}")
        ask_go(QUESTION_RIF)
        wb = load()
        ws = wb[cfg.SHEET_FUNZIONI]
        sh = parse_funzioni(ws)
        non_numeric = []
        for t, _, _ in todo:
            b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
            if not b or not b.rif_row or not col:
                continue
            v = ws.cell(b.rif_row, col).value
            if page_number(v) is None and _str(v):
                non_numeric.append(t)
        if non_numeric:
            yellow(f"  {len(non_numeric)} riferimenti di pagina non sono ancora numerici: correggili.")
            continue
        break

    # Esito: vuoto → FUNZIONE NON PRESENTE; numero → Funzioni AI da ricalcolare
    wb = load()
    ws = wb[cfg.SHEET_FUNZIONI]
    ws_req = wb[cfg.SHEET_REQUISITI] if cfg.SHEET_REQUISITI in wb.sheetnames else None
    sh = parse_funzioni(ws)
    n_np = n_ok = 0
    for t in check:
        b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
        if not b or not col:
            continue
        rif = ws.cell(b.rif_row, col).value if b.rif_row else None
        ai = ws.cell(b.ai_row, col) if b.ai_row else None
        if page_number(rif) is None:
            t.state = "not_present"
            if ai is not None:
                set_not_present(ai)
            n_np += 1
        else:
            t.state = "ok"
            if ai is not None:
                set_empty_white(ai)
            n_ok += 1
    clear_requisiti(ws_req, {t.key for t in check})
    save(wb)
    say(f"  Funzioni con riferimento di pagina: {n_ok} · «{txt_not_present()}»: {n_np}")


# ---------------------------------------------------------------------------
# STEP 3
# ---------------------------------------------------------------------------

def classify(ws, sh: Sheet, t: Target) -> tuple[str, str]:
    """(caso, problema): caso '1' | '2' | '3' | '' se anomalo."""
    b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
    if not b or not col:
        return "-", ""
    link = has_link(ws, b.link_row, col)
    rif = ws.cell(b.rif_row, col).value if b.rif_row else None
    ai = ws.cell(b.ai_row, col) if b.ai_row else None
    ai_txt = _str(ai.value) if ai is not None else ""
    if ai is None:
        return ("3", "") if link and page_number(rif) else ("2", "")
    if not link:
        if norm(ai_txt) == norm(txt_link_missing()):
            return "1", ""
        return "", f"link assente: il campo Funzioni AI deve contenere «{txt_link_missing()}»"
    if not _str(rif):
        if norm(ai_txt) == norm(txt_not_present()):
            return "2", ""
        return "", f"link presente ma Rif. Pagina vuoto: inserisci il numero di pagina oppure scrivi «{txt_not_present()}» in Funzioni AI"
    if page_number(rif) is None:
        return "", f"Rif. Pagina non numerico («{_str(rif)}»): scrivi solo il numero di pagina"
    if ai_txt:
        return "", "link e Rif. Pagina presenti: il campo Funzioni AI deve essere vuoto (verrà ricalcolato)"
    if not is_white(ai):
        return "", "il campo Funzioni AI deve avere lo sfondo bianco"
    return "3", ""


def _autofix(ws, sh: Sheet, t: Target) -> bool:
    b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
    if not b or not col or not b.ai_row:
        return False
    link = has_link(ws, b.link_row, col)
    rif = ws.cell(b.rif_row, col).value if b.rif_row else None
    ai = ws.cell(b.ai_row, col)
    if not link:
        set_link_missing(ai)
    elif not _str(rif):
        set_not_present(ai)
    elif page_number(rif) is not None:
        set_empty_white(ai)
    else:
        return False
    return True


def step3(targets: list[Target]) -> list[Target]:
    say("\n── STEP 3 · CHECK")
    while True:
        wb = load()
        ws = wb[cfg.SHEET_FUNZIONI]
        ws_req = wb[cfg.SHEET_REQUISITI] if cfg.SHEET_REQUISITI in wb.sheetnames else None
        sh = parse_funzioni(ws)
        # Requisiti: le celle dei documenti aggiornati devono essere vuote
        dirty = requisiti_dirty(ws_req, {t.key for t in targets})
        if dirty:
            clear_requisiti(ws_req, dirty)
            save(wb)
            continue
        bad, counts = [], {"1": 0, "2": 0, "3": 0}
        for t in targets:
            case, problem = classify(ws, sh, t)
            if case in counts:
                counts[case] += 1
                t.state = {"1": "missing", "2": "not_present", "3": "ok"}[case]
            elif problem:
                b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
                bad.append((t, ws.cell(b.ai_row or b.rif_row or b.link_row, col).coordinate, problem))
        say(f"  CASO 1 (link mancante): {counts['1']} · CASO 2 (funzione non presente): {counts['2']} · "
            f"CASO 3 (da ricalcolare): {counts['3']}")
        if not bad:
            return [t for t in targets if t.state == "ok"]
        yellow(f"\n  ✋ AZIONE RICHIESTA: {len(bad)} anomalie da sanare nel foglio «{cfg.SHEET_FUNZIONI}».\n"
               "  Ogni funzione aggiornata deve trovarsi in uno di questi casi:\n"
               f"    CASO 1  nessun Link → Funzioni AI = «{txt_link_missing()}» (sfondo salmone)\n"
               f"    CASO 2  Link presente, Rif. Pagina vuoto → Funzioni AI = «{txt_not_present()}» (sfondo giallo)\n"
               "    CASO 3  Link presente, Rif. Pagina numerico → Funzioni AI vuoto (sfondo bianco)\n"
               "  Correggi le celle indicate, salva e chiudi il file Excel, poi rispondi S.\n"
               "  Rispondi C per far applicare al programma la correzione automatica (dove possibile).")
        for t, coord, problem in bad[:60]:
            yellow(f"    - {coord}: {t.label()} — {problem}")
        if len(bad) > 60:
            yellow(f"    … e altre {len(bad) - 60}")
        if ask_go(QUESTION_CHECK, {"C": "correggi automaticamente"}) == "C":
            wb = load()
            ws = wb[cfg.SHEET_FUNZIONI]
            sh = parse_funzioni(ws)
            n = sum(_autofix(ws, sh, t) for t, _, _ in bad)
            if n:
                save(wb)
            say(f"  Correzioni automatiche applicate: {n}")


# ---------------------------------------------------------------------------
# STEP 4
# ---------------------------------------------------------------------------

def step4(ok: list[Target]) -> int:
    say(f"\n── STEP 4 · Ricalcolo Funzioni AI e Requisiti ({len(ok)} funzioni)")
    if not ok:
        say("  Nessuna funzione da ricalcolare.")
        return 0
    import funzioni_ai_filter as FAF
    import run_options
    from analysis_scope import Scope
    wb = load()
    sh = parse_funzioni(wb[cfg.SHEET_FUNZIONI])
    only = set()
    for t in ok:
        b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
        if b and b.ai_row and col:
            only.add((b.ai_row, col))
    del wb
    base = getattr(cfg, "REQ_BASE_CONFIG", "VZI_Base")
    configs = sorted({t.config for t in ok} | {base})
    params = run_options.Option1Params(
        overwrite="S",
        scope=Scope(sorted({t.doc_id for t in ok}), sorted({t.func_id for t in ok}), configs),
        only_cells=only, rif_pagina=False, mark_not_updated=False)
    return FAF.run(params=params)


# ---------------------------------------------------------------------------
# STEP 5
# ---------------------------------------------------------------------------

def step5(new_table: dict, progress=print) -> Path:
    say("\n── STEP 5 · Pagina web e file Excel aggiornati")
    xs = pending_x()
    if xs:
        report_x(xs)
    import export_user
    out = Path(cfg.DIST_DIR) / datetime.now().strftime("%Y-%m-%d")
    page = export_user.export(progress=progress, out_dir=out, page_name=cfg.OPZIONE0_PAGE_NAME,
                              readonly_excel=False)
    config_db.save(new_table)
    say(f"  ✔ Memoria «{cfg.CONFIG_DB_TITLE}» aggiornata: {cfg.CONFIG_DB_FILE}")
    return Path(page) if page else out


# ---------------------------------------------------------------------------
# Orchestrazione
# ---------------------------------------------------------------------------

def _support():
    import support_loader
    try:
        sd = support_loader.load(load(data_only=True))
        return sd if sd.is_valid() else None
    except Exception as exc:
        log.warning(f"Fogli di supporto non leggibili: {exc}")
        return None


def crea_db_config(progress=print) -> dict:
    """OPZIONE 0 CREA DB CONFIG."""
    return config_db.create(progress)


def total(progress=print) -> int:
    """OPZIONE 0 TOTAL. Ritorna 0 se completata."""
    import old_archive
    import run_options
    if os.name == "nt":
        os.system("")
    run_options.set_update_db(True)
    old_archive.begin("0", "OPZIONE 0 TOTAL", details={}, sheets=[cfg.SHEET_FUNZIONI, cfg.SHEET_REQUISITI])
    old_archive.set_update_db(True)
    try:
        say(f"── STEP 0 · Memoria «{cfg.CONFIG_DB_TITLE}»")
        old = config_db.load()
        new = config_db.build()
        n = sum(len(d["codes"]) for d in new["docs"])
        say(f"  Letti dal foglio CONFIG: {len(new['docs'])} DOC ID, {n} coppie Codice/Rev")
        if old is None:
            yellow("  Nessuna memoria precedente del foglio CONFIG: la creo ora come riferimento.\n"
                   "  Le prossime esecuzioni dell'OPZIONE 0 TOTAL aggiorneranno solo i documenti cambiati\n"
                   "  rispetto a questa memoria (Codice o Rev diversi).")
            changes = []
        else:
            changes = config_db.diff(old, new)
            say(f"  Memoria precedente del {old.get('created', '?')}: {len(changes)} documenti cambiati")
        frs = [c for c in changes if c.is_frs]
        other = [c for c in changes if not c.is_frs]
        for c in changes:
            say(f"    {'FRS ' if c.is_frs else c.category + ' '}{c.describe()} ({c.kind})")
        old_archive.set_details({"Documenti cambiati": str(len(changes)),
                                 "FRS cambiati": ", ".join(sorted({c.doc_id for c in frs}))})
        ok: list[Target] = []
        if changes:
            sd = _support()
            targets, _ = step1(frs + other, sd)
            step2(targets, sd)
            ok = step3(targets)
            step4(ok)
        else:
            say("  Nessun documento cambiato: aggiorno solo pagina web e file Excel in dist/.")
        out = step5(new, progress)
        say(f"\n  ✅ OPZIONE 0 TOTAL completata. Risultati in: {out.parent if out.suffix else out}")
        old_archive.finish("completata")
        return 0
    except (Aborted, KeyboardInterrupt):
        yellow("\n  OPZIONE 0 TOTAL interrotta: la memoria del foglio CONFIG NON è stata aggiornata,\n"
               "  alla prossima esecuzione i documenti cambiati verranno rielaborati.")
        old_archive.finish("interrotta dall'utente")
        return 130


def main() -> int:
    import argparse
    import app_logging
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    app_logging.setup(logging.INFO)
    ap = argparse.ArgumentParser(description="OPZIONE 0 TOTAL / CREA DB CONFIG")
    ap.add_argument("--crea-db-config", action="store_true",
                    help="solo la memoria del foglio CONFIG (OPZIONE 0 CREA DB CONFIG)")
    a = ap.parse_args()
    if a.crea_db_config:
        crea_db_config()
        return 0
    return total()


if __name__ == "__main__":
    sys.exit(main())
