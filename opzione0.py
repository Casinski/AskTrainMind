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
            celle del caso 3; in piu' le celle "Funzioni AI" VUOTE di altri
            documenti (cancellate per sbaglio) con link e Rif. Pagina vengono
            compilate di nuovo; quelle compilate restano invariate.
    STEP 5  salvataggio, pagina web dist/<AAAA-MM-GG>/DBFlotte1000.html e
            copia del file Excel nella stessa cartella; la nuova memoria del
            foglio CONFIG diventa quella di riferimento.

All'avvio (TOTAL e CREA DB CONFIG) il file Excel viene copiato in
"DB_FLOTTE HISTORY OPZ. 0/<AAAA-MM-GG_hh-mm-ss>/": la copia resta solo se
l'opzione termina con successo.

python opzione0.py --web   solo la pagina dist/<data>/DBFlotte1000.html dal
                           file Excel attuale (AVVIA_WEB.bat)
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import textwrap
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


W = 100   # larghezza dei riquadri in console


def banner(title: str, subtitle: str = "") -> None:
    """Titolo dell'opzione, in un riquadro doppio."""
    say("\n" + "═" * W)
    say(f"  {title}")
    if subtitle:
        for line in textwrap.wrap(subtitle, W - 4):
            say(f"  {line}")
    say("═" * W)


def step_header(n: int | str, title: str, what: list[str] = ()) -> None:
    """Intestazione di uno STEP con l'elenco di cosa succede."""
    say("\n" + f"┌─ STEP {n} · {title} ".ljust(W, "─"))
    if what:
        say("│  Cosa succede in questo step:")
        for w in what:
            lines = textwrap.wrap(w, W - 8) or [""]
            say(f"│    • {lines[0]}")
            for line in lines[1:]:
                say(f"│      {line}")
    say("└" + "─" * (W - 1))


def info(msg: str, level: int = 1) -> None:
    """Riga di avanzamento rientrata (level 1 = sotto lo step, 2 = elenco)."""
    say("  " * level + msg)


def item(msg: str, level: int = 2) -> None:
    say("  " * level + "• " + msg)


def done(msg: str) -> None:
    say(f"  ✔ {msg}")


# Riepilogo mostrato al termine dell'OPZIONE 0 TOTAL
REPORT: dict[str, object] = {}


# ---------------------------------------------------------------------------
# Storico del DB Flotte (cartella DB_FLOTTE HISTORY OPZ. 0)
# ---------------------------------------------------------------------------

class History:
    """
    All'avvio copia il file Excel del DB Flotte in
    <OPZ0_HISTORY_DIR>/<AAAA-MM-GG_hh-mm-ss>/. Se l'opzione non termina con
    successo (errore, interruzione, codice diverso da 0) la cartella con la
    copia viene cancellata.
    """

    def __init__(self, label: str):
        self.label = label
        self.folder: Path | None = None
        self.ok = False

    def __enter__(self) -> "History":
        src = Path(cfg.EXCEL_PATH)
        base = Path(getattr(cfg, "OPZ0_HISTORY_DIR", Path(__file__).with_name("DB_FLOTTE HISTORY OPZ. 0")))
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder = base / stamp
        n = 1
        while folder.exists():
            n += 1
            folder = base / f"{stamp}_{n}"
        try:
            folder.mkdir(parents=True)
            shutil.copy2(src, folder / src.name)
            self.folder = folder
            info(f"🗂  Copia del DB Flotte salvata nello storico: {folder / src.name}")
            info("   (resta solo se l'opzione termina con successo)")
        except OSError as exc:
            shutil.rmtree(folder, ignore_errors=True)
            log.warning(f"Copia del DB Flotte nello storico non riuscita: {exc}")
            yellow(f"  ⚠ Copia del DB Flotte in «{base.name}» non riuscita ({exc}): proseguo senza storico.")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self.folder is None:
            return False
        if self.ok and exc_type is None:
            info(f"🗂  Storico DB Flotte conservato: {self.folder}")
        else:
            shutil.rmtree(self.folder, ignore_errors=True)
            info(f"🗑  {self.label} non completata: copia nello storico eliminata ({self.folder.name}).")
        return False


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
    step_header(1, "Pulizia delle funzioni dei documenti aggiornati", [
        "FRS con il file nella cartella <configurazione>/CONFIG/FRS: Rif. Pagina e Funzioni AI svuotati "
        "(sfondo bianco), da ricalcolare.",
        f"FRS senza file o senza link: Funzioni AI = «{txt_link_missing()}».",
        "Foglio Requisiti: svuotate le celle della configurazione (riga eliminata se resta vuota).",
        f"Documenti NON FRS aggiornati: «{txt_invalid()}» rossa in Rif. Pagina, da sostituire a mano.",
    ])
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
        info(f"📄 {ch.describe()}")
        if not blocks or not col:
            item("nessuna funzione collegata nel foglio Funzioni: niente da fare")
            continue
        if ch.is_frs:
            f = _locate_file(ch, sd)
            item(f"file presente: {f.name}" if f else "file NON presente nella cartella "
                 + config_db.relative_path(ch.config, ch.category, ch.new_code or '?', ch.ext).rsplit('/', 1)[0])
            n_check = n_missing = 0
            for b in blocks:
                t = Target(b.func_id, b.doc_id, ch.config, f, url=_url(sd, b.doc_id, ch.config, b.cart))
                link = has_link(ws, b.link_row, col)
                if b.rif_row:
                    ws.cell(b.rif_row, col).value = None
                if f and link:
                    t.state = "check"
                    n_check += 1
                    if b.ai_row:
                        set_empty_white(ws.cell(b.ai_row, col))
                else:
                    t.state = "missing"
                    n_missing += 1
                    if not f and link:
                        ws.cell(b.link_row, col).value = None
                    if b.ai_row:
                        set_link_missing(ws.cell(b.ai_row, col))
                targets.append(t)
                req_items.add(t.key)
            item(f"{len(blocks)} funzioni: {n_check} da ricalcolare, {n_missing} «{txt_link_missing()}»")
        else:
            n = 0
            for b in blocks:
                if not has_link(ws, b.link_row, col) or not b.rif_row:
                    continue
                set_invalid_x(ws.cell(b.rif_row, col))
                anomalies.append({"func": b.func_id, "doc": b.doc_id, "config": ch.config,
                                  "cell": ws.cell(b.rif_row, col).coordinate, "change": ch.describe()})
                n += 1
            item(f"documento non FRS: {n} riferimenti di pagina invalidati con la {txt_invalid()} rossa")
    cleared, deleted = clear_requisiti(ws_req, req_items)
    info(f"📋 Foglio Requisiti: {cleared} celle svuotate, {deleted} righe eliminate")
    REPORT["requisiti"] = (cleared, deleted)
    missing = [t for t in targets if t.state == "missing"]
    if missing:
        yellow(f"\n  ℹ {len(missing)} funzioni senza documento o senza link → «{txt_link_missing()}» in Funzioni AI:")
        for t in missing[:30]:
            yellow(f"      • {t.label()}" + ("" if not t.file else "  (file presente: puoi inserire il link nel foglio Funzioni)"))
        if len(missing) > 30:
            yellow(f"      … e altre {len(missing) - 30}")
    if anomalies:
        report_x(anomalies)
    save(wb)
    return targets, anomalies


def report_x(anomalies: list[dict]) -> None:
    yellow(f"\n  ⚠ {len(anomalies)} riferimenti di pagina di documenti NON FRS aggiornati sono stati "
           f"invalidati con una «{txt_invalid()}» rossa\n"
           f"    nel foglio «{cfg.SHEET_FUNZIONI}».\n"
           "  COSA FARE:\n"
           "    1. apri il file Excel e vai alle celle elencate (Rif. Pagina sotto il link del documento);\n"
           "    2. apri il documento aggiornato e trova la pagina della funzione;\n"
           "    3. scrivi il nuovo numero di pagina al posto della X.\n"
           "  Finché la X resta, la pagina web non mostra il documento né il PDF alla pagina associata.")
    for a in anomalies[:40]:
        yellow(f"      • cella {a['cell']}: {a['func']} · {a['doc']} · {a['config']}")
    if len(anomalies) > 40:
        yellow(f"      … e altre {len(anomalies) - 40}")


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
    step_header(2, f"Ricerca del nuovo Riferimento di pagina ({len(check)} funzioni)", [
        "Il programma cerca nei PDF aggiornati la pagina in cui inizia ogni funzione (come la voce 3).",
        "I riferimenti mancanti o non numerici li inserisci tu nel file Excel, poi confermi con S.",
        f"Celle lasciate vuote → «{txt_not_present()}» in Funzioni AI (sfondo giallo).",
    ])
    if not check:
        info("Nessuna funzione da controllare: nessun FRS aggiornato ha file e link.")
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
        info(f"🔎 Riferimenti di pagina trovati e scritti: {stats.written} su {len(cells)}")
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
               "  COSA FARE:\n"
               f"    1. apri il file {cfg.EXCEL_PATH.name}, foglio «{cfg.SHEET_FUNZIONI}»;\n"
               "    2. per ogni cella elencata apri il PDF (link soprastante) e scrivi SOLO il numero della pagina\n"
               "       in cui inizia la funzione (es. 14); se c'è «N utente - M dinamico» lascia un solo numero;\n"
               "    3. se la funzione non esiste nel documento lascia la cella VUOTA: verrà scritto\n"
               f"       «{txt_not_present()}» nel campo Funzioni AI;\n"
               "    4. salva e chiudi il file Excel, poi rispondi S.\n"
               "  Celle da compilare:")
        for t, coord, v in todo[:60]:
            yellow(f"      • cella {coord}: {t.label()}" + (f"  (attuale: «{v}»)" if v else "  (vuota)")
                   + (f"\n          PDF: {t.url}" if t.url else ""))
        if len(todo) > 60:
            yellow(f"      … e altre {len(todo) - 60}")
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
            yellow(f"  ⚠ {len(non_numeric)} riferimenti di pagina non sono ancora numerici: correggili.")
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
    done(f"Esito STEP 2: {n_ok} funzioni con riferimento di pagina, {n_np} «{txt_not_present()}»")


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
    step_header(3, "CHECK delle funzioni aggiornate", [
        f"CASO 1: nessun Link → Funzioni AI = «{txt_link_missing()}» (sfondo salmone).",
        f"CASO 2: Link presente, Rif. Pagina vuoto → Funzioni AI = «{txt_not_present()}» (sfondo giallo).",
        "CASO 3: Link presente, Rif. Pagina numerico → Funzioni AI vuoto (sfondo bianco), da ricalcolare.",
        "In tutti i casi le celle del foglio Requisiti delle funzioni aggiornate devono essere vuote.",
    ])
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
        info("Situazione attuale:")
        item(f"CASO 1 (link mancante)        : {counts['1']}")
        item(f"CASO 2 (funzione non presente): {counts['2']}")
        item(f"CASO 3 (da ricalcolare)       : {counts['3']}")
        item(f"anomalie da sanare            : {len(bad)}")
        REPORT["casi"] = dict(counts)
        if not bad:
            return [t for t in targets if t.state == "ok"]
        yellow(f"\n  ✋ AZIONE RICHIESTA: {len(bad)} anomalie da sanare nel foglio «{cfg.SHEET_FUNZIONI}».\n"
               "  Ogni funzione aggiornata deve trovarsi in uno di questi casi:\n"
               f"    CASO 1  nessun Link → Funzioni AI = «{txt_link_missing()}» (sfondo salmone)\n"
               f"    CASO 2  Link presente, Rif. Pagina vuoto → Funzioni AI = «{txt_not_present()}» (sfondo giallo)\n"
               "    CASO 3  Link presente, Rif. Pagina numerico → Funzioni AI vuoto (sfondo bianco)\n"
               "  COSA FARE:\n"
               "    • correggi le celle elencate, salva e chiudi il file Excel, poi rispondi S;\n"
               "    • oppure rispondi C per far applicare al programma la correzione automatica (dove possibile).\n"
               "  Celle da sanare:")
        for t, coord, problem in bad[:60]:
            yellow(f"      • {coord}: {t.label()}\n          → {problem}")
        if len(bad) > 60:
            yellow(f"      … e altre {len(bad) - 60}")
        if ask_go(QUESTION_CHECK, {"C": "correggi automaticamente"}) == "C":
            wb = load()
            ws = wb[cfg.SHEET_FUNZIONI]
            sh = parse_funzioni(ws)
            n = sum(_autofix(ws, sh, t) for t, _, _ in bad)
            if n:
                save(wb)
            done(f"Correzioni automatiche applicate: {n}")


# ---------------------------------------------------------------------------
# STEP 4
# ---------------------------------------------------------------------------

@dataclass
class EmptyScan:
    """Celle «Funzioni AI» di documenti NON aggiornati, controllate allo STEP 4."""
    recover: list[Target] = field(default_factory=list)       # vuote, link + pagina → da compilare
    no_page: list[tuple[Target, str]] = field(default_factory=list)  # vuote, link senza pagina valida
    filled: int = 0                                           # compilate → lasciate invariate
    cells: set[tuple[int, int]] = field(default_factory=set)  # (riga, colonna) delle celle in recover


def scan_empty_ai(ws, sh: Sheet, exclude: set[tuple[str, str, str]]) -> EmptyScan:
    """
    Cerca nel foglio Funzioni le celle «Funzioni AI» vuote (per esempio
    cancellate per sbaglio) di funzioni e documenti NON coinvolti
    nell'aggiornamento del foglio CONFIG. Sono da compilare le celle con link
    e Rif. Pagina numerico; quelle compilate restano come sono.
    """
    out = EmptyScan()
    excl = {(norm(f), norm(d), norm(c)) for f, d, c in exclude}
    last = ws.max_column          # come excel_scanner: l'ultima colonna non e' una configurazione
    for b in sh.blocks:
        if not b.ai_row:
            continue
        for name, col in sh.config_cols.items():
            if col >= last or (norm(b.func_id), norm(b.doc_id), norm(name)) in excl:
                continue
            if not has_link(ws, b.link_row, col):
                continue
            if _str(ws.cell(b.ai_row, col).value):
                out.filled += 1
                continue
            t = Target(b.func_id, b.doc_id, name, state="recover")
            rif = ws.cell(b.rif_row, col).value if b.rif_row else None
            if page_number(rif) is not None:
                out.recover.append(t)
                out.cells.add((b.ai_row, col))
            elif _str(rif).upper() != txt_invalid().upper():     # le X sono segnalate a parte
                out.no_page.append((t, ws.cell(b.rif_row or b.ai_row, col).coordinate))
    return out


def step4(ok: list[Target]) -> int:
    step_header(4, "Ricalcolo Funzioni AI e Requisiti", [
        "Per le funzioni del CASO 3 dei documenti aggiornati: sintesi «Funzioni AI», similarità e match "
        "del foglio Requisiti (come la voce 1), solo per la loro configurazione.",
        "Controllo delle altre celle «Funzioni AI» (documenti non aggiornati): quelle VUOTE con link e "
        "Rif. Pagina vengono compilate e i loro requisiti rimatchati; quelle compilate restano invariate.",
    ])
    wb = load()
    ws = wb[cfg.SHEET_FUNZIONI]
    sh = parse_funzioni(ws)
    es = scan_empty_ai(ws, sh, {t.key for t in ok})
    info(f"🧠 Funzioni aggiornate da ricalcolare (CASO 3): {len(ok)}")
    for t in ok[:30]:
        item(t.label(), 2)
    if len(ok) > 30:
        info(f"    … e altre {len(ok) - 30}")
    info("🔍 Controllo delle altre celle «Funzioni AI» (documenti non aggiornati):")
    item(f"già compilate, lasciate invariate: {es.filled}")
    item(f"vuote, da compilare di nuovo     : {len(es.recover)}")
    item(f"vuote, senza Rif. Pagina valido  : {len(es.no_page)}")
    if es.recover:
        yellow(f"\n  ℹ {len(es.recover)} celle «Funzioni AI» di documenti NON aggiornati sono vuote (forse cancellate\n"
               "    per sbaglio): il programma le compila di nuovo e rifà il match dei loro requisiti.")
        for t in es.recover[:40]:
            yellow(f"      • {t.label()}")
        if len(es.recover) > 40:
            yellow(f"      … e altre {len(es.recover) - 40}")
    if es.no_page:
        yellow(f"\n  ℹ {len(es.no_page)} celle «Funzioni AI» vuote hanno il link ma non un Rif. Pagina numerico:\n"
               "    non possono essere compilate. Se vuoi compilarle inserisci il numero di pagina nella cella\n"
               "    indicata e riesegui l'OPZIONE 0 TOTAL (o la voce 1).")
        for t, coord in es.no_page[:40]:
            yellow(f"      • cella {coord}: {t.label()}")
        if len(es.no_page) > 40:
            yellow(f"      … e altre {len(es.no_page) - 40}")
    REPORT["recuperate"] = len(es.recover)
    REPORT["ricalcolate"] = len(ok)
    todo = list(ok) + es.recover
    if not todo:
        info("Nessuna cella «Funzioni AI» da compilare.")
        return 0
    only = set(es.cells)
    for t in ok:
        b, col = sh.find(t.func_id, t.doc_id), sh.col(t.config)
        if b and b.ai_row and col:
            only.add((b.ai_row, col))
    del wb
    import funzioni_ai_filter as FAF
    import run_options
    from analysis_scope import Scope
    base = getattr(cfg, "REQ_BASE_CONFIG", "VZI_Base")
    configs = sorted({t.config for t in todo} | {base})
    params = run_options.Option1Params(
        overwrite="S",
        scope=Scope(sorted({t.doc_id for t in todo}), sorted({t.func_id for t in todo}), configs),
        only_cells=only, rif_pagina=False, mark_not_updated=False)
    info(f"⏳ Avvio dell'analisi AI su {len(only)} celle (il dettaglio segue nel log)…\n")
    rc = FAF.run(params=params)
    say("")
    if rc == 0:
        done("STEP 4 terminato")
    else:
        yellow(f"  ⚠ L'analisi AI è terminata con codice {rc}: controlla i messaggi sopra (es. Ollama non avviato).")
    return rc


# ---------------------------------------------------------------------------
# STEP 5
# ---------------------------------------------------------------------------

def export_web(progress=print) -> Path:
    """
    Pagina web DBFlotte1000.html + copia del file Excel in dist/<AAAA-MM-GG>/,
    dal contenuto attuale del file Excel del progetto (STEP 5 e AVVIA_WEB.bat).
    """
    import export_user
    out = Path(cfg.DIST_DIR) / datetime.now().strftime("%Y-%m-%d")
    page = export_user.export(progress=lambda m: progress("  " + str(m).strip() if str(m).strip() else ""),
                              out_dir=out, page_name=cfg.OPZIONE0_PAGE_NAME, readonly_excel=False)
    return Path(page) if page else out / cfg.OPZIONE0_PAGE_NAME


def step5(new_table: dict, progress=print) -> Path:
    step_header(5, "Pagina web e file Excel aggiornati", [
        f"Crea dist/<AAAA-MM-GG>/{cfg.OPZIONE0_PAGE_NAME} con la copia del file Excel aggiornato.",
        f"La memoria «{cfg.CONFIG_DB_TITLE}» diventa il nuovo riferimento.",
    ])
    xs = pending_x()
    REPORT["x"] = len(xs)
    if xs:
        report_x(xs)
    info("⏳ Creazione della pagina web (può richiedere qualche minuto)…")
    page = export_web(progress)
    config_db.save(new_table)
    done(f"Memoria «{cfg.CONFIG_DB_TITLE}» aggiornata: {cfg.CONFIG_DB_FILE}")
    return page


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


def _console() -> None:
    if os.name == "nt":
        os.system("")          # colori ANSI nella console di Windows


def crea_db_config(progress=print) -> int:
    """OPZIONE 0 CREA DB CONFIG. Ritorna 0 se completata."""
    _console()
    banner("OPZIONE 0 CREA DB CONFIG",
           f"Legge il foglio CONFIG e salva la memoria «{cfg.CONFIG_DB_TITLE}» (Codice e Rev di ogni DOC ID "
           "per configurazione). Il DB Flotte non viene modificato.")
    with History("OPZIONE 0 CREA DB CONFIG") as hist:
        try:
            say("")
            config_db.create(progress)
        except KeyboardInterrupt:
            yellow("\n  OPZIONE 0 CREA DB CONFIG interrotta: la memoria non è stata aggiornata.")
            return 130
        hist.ok = True
    say("")
    done("OPZIONE 0 CREA DB CONFIG completata.")
    return 0


def _summary(changes: list, page: Path, hist: History) -> None:
    say("\n" + "═" * W)
    say("  ✅ OPZIONE 0 TOTAL completata — RIEPILOGO")
    say("═" * W)
    rows = [("Documenti cambiati nel foglio CONFIG", len(changes))]
    if changes:
        rows.append(("  di cui FRS", sum(c.is_frs for c in changes)))
    casi = REPORT.get("casi") or {}
    if casi:
        rows += [("Funzioni CASO 1 (link mancante)", casi.get("1", 0)),
                 ("Funzioni CASO 2 (funzione non presente)", casi.get("2", 0)),
                 ("Funzioni CASO 3 (ricalcolate)", casi.get("3", 0))]
    if "requisiti" in REPORT:
        c, d = REPORT["requisiti"]
        rows.append(("Requisiti: celle svuotate / righe eliminate", f"{c} / {d}"))
    if "recuperate" in REPORT:
        rows.append(("Celle Funzioni AI vuote ricompilate (altri documenti)", REPORT["recuperate"]))
    rows.append((f"Rif. Pagina con la {txt_invalid()} rossa da sanare", REPORT.get("x", 0)))
    for k, v in rows:
        say(f"  {k:<56} {v}")
    say("")
    say(f"  🌐 Pagina web     : {page}")
    say(f"  📊 File Excel     : {cfg.EXCEL_PATH}")
    if hist.folder:
        say(f"  🗂  Storico DB     : {hist.folder}")
    say(f"  🧾 Memoria CONFIG : {cfg.CONFIG_DB_FILE}")
    if REPORT.get("x"):
        yellow(f"\n  ⚠ Ricorda: sostituisci le {REPORT['x']} «{txt_invalid()}» rosse con il nuovo numero di pagina.")
    say("═" * W)


def total(progress=print) -> int:
    """OPZIONE 0 TOTAL. Ritorna 0 se completata."""
    import old_archive
    import run_options
    _console()
    REPORT.clear()
    banner("OPZIONE 0 TOTAL",
           "Aggiornamento incrementale del DB Flotte dopo una modifica di Codice/Rev nel foglio CONFIG: "
           "STEP 0 memoria · STEP 1 pulizia · STEP 2 Rif. Pagina · STEP 3 CHECK · STEP 4 Funzioni AI e "
           "Requisiti · STEP 5 pagina web. Le istruzioni per te sono scritte in GIALLO.")
    with History("OPZIONE 0 TOTAL") as hist:
        run_options.set_update_db(True)
        old_archive.begin("0", "OPZIONE 0 TOTAL", details={}, sheets=[cfg.SHEET_FUNZIONI, cfg.SHEET_REQUISITI])
        old_archive.set_update_db(True)
        try:
            step_header(0, f"Memoria «{cfg.CONFIG_DB_TITLE}»", [
                "Legge Codice e Rev di ogni DOC ID per configurazione dal foglio CONFIG.",
                "Li confronta con la memoria precedente: un documento è cambiato se Codice o Rev sono diversi.",
            ])
            old = config_db.load()
            new = config_db.build()
            n = sum(len(d["codes"]) for d in new["docs"])
            info(f"📖 Letti dal foglio CONFIG: {len(new['docs'])} DOC ID, {n} coppie Codice/Rev")
            if old is None:
                yellow("  ℹ Nessuna memoria precedente del foglio CONFIG: la creo ora come riferimento.\n"
                       "    Le prossime esecuzioni dell'OPZIONE 0 TOTAL aggiorneranno solo i documenti cambiati\n"
                       "    rispetto a questa memoria (Codice o Rev diversi). Il DB Flotte non viene modificato.")
                changes = []
            else:
                changes = config_db.diff(old, new)
                info(f"🧾 Memoria precedente del {old.get('created', '?')}: {len(changes)} documenti cambiati")
            frs = [c for c in changes if c.is_frs]
            other = [c for c in changes if not c.is_frs]
            for c in changes:
                item(f"{'FRS' if c.is_frs else c.category:<4} {c.describe()}  ({c.kind})")
            old_archive.set_details({"Documenti cambiati": str(len(changes)),
                                     "FRS cambiati": ", ".join(sorted({c.doc_id for c in frs}))})
            if changes:
                sd = _support()
                targets, _ = step1(frs + other, sd)
                step2(targets, sd)
                ok = step3(targets)
                step4(ok)
            elif old is not None:
                info("Nessun documento cambiato: salto gli STEP 1-3.")
                step4([])
            else:
                info("Prima esecuzione: salto gli STEP 1-4.")
            page = step5(new, progress)
            old_archive.finish("completata")
            hist.ok = True
        except (Aborted, KeyboardInterrupt):
            yellow("\n  ⛔ OPZIONE 0 TOTAL interrotta: la memoria del foglio CONFIG NON è stata aggiornata,\n"
                   "     alla prossima esecuzione i documenti cambiati verranno rielaborati.")
            old_archive.finish("interrotta dall'utente")
            return 130
    _summary(changes, page, hist)
    return 0


def web(open_page: bool = True, progress=print) -> int:
    """AVVIA_WEB.bat: crea dist/<data>/DBFlotte1000.html dal file Excel del progetto e la apre."""
    _console()
    from webapp import workbook as W
    xp = W.excel_path()           # EXCEL_PATH oppure il file Excel nella cartella del progetto
    banner(f"PAGINA WEB {cfg.OPZIONE0_PAGE_NAME}",
           f"Crea la pagina dal file Excel del progetto ({xp.name if xp else Path(cfg.EXCEL_PATH).name}) "
           "senza eseguire l'OPZIONE 0: il file Excel non viene modificato.")
    if not xp:
        yellow(f"  ✖ File Excel non trovato: {cfg.EXCEL_PATH} (né «DB Flotte*.xlsx» nella cartella del progetto)")
        return 1
    info(f"📊 File Excel: {xp}")
    info("⏳ Creazione della pagina web (può richiedere qualche minuto)…")
    page = export_web(progress)
    say("")
    done(f"Pagina web creata: {page}")
    if open_page and page.is_file():
        import webbrowser
        info("🌐 Apertura nel browser…")
        try:
            if os.name == "nt":
                os.startfile(str(page))          # type: ignore[attr-defined]
            else:
                webbrowser.open(page.resolve().as_uri())
        except Exception as exc:
            yellow(f"  Apertura automatica non riuscita ({exc}): apri a mano {page}")
    return 0


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
    ap.add_argument("--web", action="store_true",
                    help=f"crea solo la pagina dist/<data>/{cfg.OPZIONE0_PAGE_NAME} dal file Excel (AVVIA_WEB.bat)")
    ap.add_argument("--no-open", action="store_true", help="con --web: non aprire la pagina nel browser")
    a = ap.parse_args()
    if a.web:
        return web(open_page=not a.no_open)
    if a.crea_db_config:
        return crea_db_config()
    return total()


if __name__ == "__main__":
    sys.exit(main())
