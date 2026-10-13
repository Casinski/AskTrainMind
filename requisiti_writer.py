"""
requisiti_writer.py
-------------------
Compila il foglio "Requisiti" replicando la struttura gerarchica
del foglio "Funzioni".

  LIVELLO 1 — riga funzione (già esistente nel foglio)
      Col A: FUNC ID       "LV_Country_code_selection"
      Col B: DESCRIZIONE   "Selezione su IDU del paese corrente..."

  LIVELLO 2 — righe requisito (INSERITE dal codice sotto la funzione)
      Col A: vuota   ← discriminatore
      Col B: vuota
      Col C: Nr requisito
      Col D: Configurazione di appartenenza, colorata

FUNZIONAMENTO
  1. Cerca la riga della funzione scorrendo la colonna A (FUNC ID).
     Fallback: confronto sulla DESCRIZIONE (col B) se il FUNC ID non è
     trovato, utile quando l'ID è scritto in modo leggermente diverso.
  2. Determina la fine del blocco di secondo livello (prima riga con
     col A valorizzata, oppure fine foglio).
  3. I requisiti già presenti nel blocco vengono AGGIORNATI sul posto
     (idempotenza); quelli nuovi vengono INSERITI in coda al blocco
     con ws.insert_rows(), così le funzioni successive scalano in basso.
  4. Dopo ogni inserimento l'indice interno viene riallineato: senza
     questo passaggio le funzioni successive verrebbero scritte nelle
     righe sbagliate.
"""
from __future__ import annotations
import logging

from openpyxl.styles import Font, Alignment

import config as cfg
import config_colors
import req_ai_comparator as reqai

log = logging.getLogger(__name__)

try:
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    _RICH = True
except Exception:          # openpyxl < 3.1 → nessun rich text
    _RICH = False


class RequisitiWriter:
    """Scrive i requisiti come righe di secondo livello nel foglio Requisiti."""

    def __init__(self, ws):
        self.ws = ws
        # {func_id_normalizzato: riga di livello 1}
        self.func_rows: dict[str, int] = {}
        # {descrizione_normalizzata: riga di livello 1}
        self.desc_rows: dict[str, int] = {}
        self.rows_written = 0
        self._scan_level1()
        log.info(
            f"  [Requisiti] Foglio '{self.ws.title}': "
            f"{len(self.func_rows)} funzioni di livello 1 trovate"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Indicizzazione livello 1
    # ─────────────────────────────────────────────────────────────────────

    def _scan_level1(self) -> None:
        """
        Indicizza le righe di livello 1 e memorizza l'ultima riga con
        contenuto reale del foglio. ws.max_row conta anche le righe solo
        formattate e vuote: usarlo come confine di blocco faceva scrivere
        i requisiti migliaia di righe più in basso, lasciando il vuoto
        sotto la funzione.
        """
        self.func_rows.clear()
        self.desc_rows.clear()
        self.func_row_list = []           # righe di livello 1, ordinate

        self.last_content_row = self._last_content_row()

        for row in range(cfg.REQ_HEADER_ROW + 1, self.last_content_row + 1):
            fid = _s(self.ws.cell(row, cfg.REQ_FUNC_ID_COL).value)
            if not fid:
                continue
            self.func_rows.setdefault(_norm(fid), row)
            self.func_row_list.append(row)
            desc = _s(self.ws.cell(row, cfg.REQ_DESC_COL).value)
            if desc:
                self.desc_rows.setdefault(_norm(desc), row)


        self._scan_config_cols()
        self.func_row_list.sort()

    def _scan_config_cols(self) -> None:
                """{config_name: colonna} letto dalla riga di intestazione, da col E."""
                self.config_cols: dict[str, int] = {}
                self.next_free_col = cfg.REQ_CONFIG_COLS_START
                for col in range(cfg.REQ_CONFIG_COLS_START, self.ws.max_column + 1):
                    name = _s(self.ws.cell(cfg.REQ_HEADER_ROW, col).value)
                    if name:
                        self.config_cols[_norm(name)] = col
                        self.next_free_col = col + 1
    
    def _col_for_config(self, cname: str) -> int:
        """Colonna della configurazione; se manca, la crea in intestazione."""
        col = self.config_cols.get(_norm(cname))
        if col:
            return col
        col = self.next_free_col
        h = self.ws.cell(cfg.REQ_HEADER_ROW, col)
        h.value = cname
        h.font  = Font(color=config_colors.color_for(cname), bold=True)
        self.config_cols[_norm(cname)] = col
        self.next_free_col = col + 1
        log.info(f"  [Requisiti] Nuova colonna configurazione '{cname}' → {col}")
        return col    

    def _last_content_row(self) -> int:
        """
        Ultima riga con un valore reale, risalendo dal fondo.
        Ignora le righe vuote ma formattate incluse in ws.max_row.
        """
        max_col = min(self.ws.max_column, 12)
        for row in range(self.ws.max_row, cfg.REQ_HEADER_ROW, -1):
            for col in range(1, max_col + 1):
                if _s(self.ws.cell(row, col).value):
                    return row
        return cfg.REQ_HEADER_ROW


    def _shift(self, from_row: int, amount: int) -> None:
        """Riallinea indici e confini dopo un inserimento di righe."""
        if amount <= 0:
            return
        for d in (self.func_rows, self.desc_rows):
            for k, v in d.items():
                if v >= from_row:
                    d[k] = v + amount
        self.func_row_list = [
            (r + amount if r >= from_row else r) for r in self.func_row_list
        ]
        if self.last_content_row >= from_row:
            self.last_content_row += amount
        else:
            self.last_content_row = max(self.last_content_row, from_row + amount - 1)

    # ─────────────────────────────────────────────────────────────────────
    # Ricerca / creazione riga funzione
    # ─────────────────────────────────────────────────────────────────────

    def _find_function_row(self, func_id: str, func_desc: str) -> int | None:
        row = self.func_rows.get(_norm(func_id))
        if row:
            return row
        row = self.desc_rows.get(_norm(func_desc))
        if row:
            log.info(
                f"  [Requisiti] '{func_id}' non trovato per FUNC ID — "
                f"abbinato per DESCRIZIONE (riga {row})"
            )
            return row
        return None

    def _create_function_row(self, func_id: str, func_desc: str) -> int:
        row = self.last_content_row + 1
        c = self.ws.cell(row, cfg.REQ_FUNC_ID_COL)
        c.value = func_id
        c.font = Font(bold=True)
        d = self.ws.cell(row, cfg.REQ_DESC_COL)
        d.value = func_desc
        d.alignment = Alignment(wrap_text=True, vertical="top")
        self.func_rows[_norm(func_id)] = row
        if func_desc:
            self.desc_rows.setdefault(_norm(func_desc), row)
        log.info(f"  [Requisiti] Creata riga funzione '{func_id}' (riga {row})")
        self.func_row_list.append(row)
        self.func_row_list.sort()
        self.last_content_row = max(self.last_content_row, row)


        return row

    # ─────────────────────────────────────────────────────────────────────
    # Blocco di secondo livello
    # ─────────────────────────────────────────────────────────────────────

    def _block_end(self, func_row: int) -> int:
        """
        Ultima riga REALE del blocco di secondo livello della funzione.

        Confine superiore: la funzione di livello 1 successiva (presa
        dall'indice, non cercata fino a ws.max_row), altrimenti l'ultima
        riga con contenuto del foglio.

        All'interno del blocco si risale dal fondo fino all'ultima riga
        con un Nr requisito o una configurazione: le righe vuote in coda
        vengono così escluse e i nuovi requisiti finiscono subito sotto
        la funzione invece che dopo centinaia di righe bianche.
        """
        next_func = None
        for r in self.func_row_list:
            if r > func_row:
                next_func = r
                break
        limit = (next_func - 1) if next_func else self.last_content_row

        for row in range(limit, func_row, -1):
            if (_s(self.ws.cell(row, cfg.REQ_NUMBER_COL).value)
                    or _s(self.ws.cell(row, cfg.REQ_CONFIG_COL).value)):
                return row

        # Nessun requisito nel blocco: si inserisce subito sotto la funzione
        return func_row

    def _existing_reqs(self, func_row: int, block_end: int) -> dict[str, int]:
        """{nr_requisito_normalizzato: riga} già presenti nel blocco."""
        out = {}
        for row in range(func_row + 1, block_end + 1):
            nr = _s(self.ws.cell(row, cfg.REQ_NUMBER_COL).value)
            if nr:
                out[_norm(_strip_progressive(nr))] = row
        return out

    # ─────────────────────────────────────────────────────────────────────
    # API pubblica
    # ─────────────────────────────────────────────────────────────────────

    def write_group(
        self,
        func_id: str,
        func_desc: str,
        reqs_by_config: dict,
    ) -> int:
        """
        reqs_by_config: {config_name: [Requirement, ...]}

        Scrive/aggiorna le righe di secondo livello della funzione.
        Ritorna il numero di righe scritte o aggiornate.
        """
        entries = self._merge(reqs_by_config)
        if not entries:
            return 0

        func_row = self._find_function_row(func_id, func_desc)
        if func_row is None:
            if not cfg.REQ_CREATE_MISSING_FUNCTION:
                log.warning(
                    f"  [Requisiti] Funzione '{func_id}' non presente nel foglio — "
                    "requisiti non scritti"
                )
                return 0
            func_row = self._create_function_row(func_id, func_desc)

        block_end = self._block_end(func_row)
        existing  = self._existing_reqs(func_row, block_end)

        aggiornati, nuovi = [], []
        for e in entries:
            if _norm(e["req_id"]) in existing:
                aggiornati.append(e)
            else:
                nuovi.append(e)

        n = 0

        # ── Aggiorna le righe già presenti ────────────────────────────────
        for e in aggiornati:
            row = existing[_norm(e["req_id"])]
            self._fill_row(row, e, progressive=None)
            n += 1

        # ── Inserisce le righe nuove in coda al blocco ────────────────────
        if nuovi:
            insert_at = block_end + 1
            log.debug(
                f"    [Requisiti] inserimento di {len(nuovi)} righe "
                f"alla riga {insert_at} (funzione riga {func_row}, "
                f"fine blocco {block_end})"
            )
            self.ws.insert_rows(insert_at, amount=len(nuovi))
            self._shift(from_row=insert_at, amount=len(nuovi))

            base = len(existing)
            for i, e in enumerate(nuovi):
                row = insert_at + i
                prog = base + i + 1 if cfg.REQ_PROGRESSIVE_NUMBER else None
                self._fill_row(row, e, progressive=prog)
                n += 1

        self.rows_written += n
        log.info(
            f"  [Requisiti] '{func_id}' (riga {func_row}): "
            f"{len(nuovi)} nuovi, {len(aggiornati)} aggiornati"
        )
        return n

    # ─────────────────────────────────────────────────────────────────────
    # Composizione delle voci
    # ─────────────────────────────────────────────────────────────────────
    def _merge(self, reqs_by_config: dict) -> list[dict]:
        """
        Unisce i requisiti trovati nelle varie configurazioni.

        REQ_ONE_ROW_PER_CONFIG = False → una riga per ID, col D con
            l'elenco colorato di tutte le configurazioni in cui compare.
        REQ_ONE_ROW_PER_CONFIG = True  → una riga per (ID, configurazione).

        ORDINE DELLE VOCI
          In entrambi i rami la lista viene ordinata per pagina di
          provenienza e poi per ID. Senza questo ordinamento i requisiti di
          una tabella spezzata su piu' pagine (es. CONCEPT.735 a pag.8,
          CONCEPT.1099 e CONCEPT.1096 a pag.9) finirebbero nel foglio in
          ordine arbitrario, perche' dipendente dall'iterazione del
          dizionario di merge.

        ATTENZIONE
          Nel ramo "una riga per ID" il risultato si accumula in 'merged':
          la lista 'out' va materializzata PRIMA di ordinarla, altrimenti
          si ottiene UnboundLocalError.
        """
        def _sort_key(e: dict) -> tuple:
            return (
                getattr(e["req"], "page_hint", 0) or 0,
                (e["configs"][0] if e["configs"] else ""),
                _norm(e["req_id"]),
            )

        # ── Una riga per (ID, configurazione) ────────────────────────────
        if cfg.REQ_ONE_ROW_PER_CONFIG:
            out: list[dict] = []
            for cname in sorted(reqs_by_config):
                for r in reqs_by_config.get(cname) or []:
                    if not getattr(r, "req_id", ""):
                        continue
                    out.append({
                        "req_id": r.req_id,
                        "configs": [cname],
                        "req": r,
                        "by_config": {cname: r},
                    })
            out.sort(key=_sort_key)
            return out

        # ── Una riga per ID, con l'elenco delle configurazioni ───────────
        merged: dict[str, dict] = {}
        for cname in sorted(reqs_by_config):
            for r in reqs_by_config.get(cname) or []:
                if not getattr(r, "req_id", ""):
                    continue
                e = merged.setdefault(
                    _norm(r.req_id),
                    {"req_id": r.req_id, "configs": [], "req": r, "by_config": {}},
                )
                if cname not in e["configs"]:
                    e["configs"].append(cname)
                # versione del requisito specifica di QUESTA configurazione
                prev = e["by_config"].get(cname)
                if prev is None or _richness(r) > _richness(prev):
                    e["by_config"][cname] = r
                if _richness(r) > _richness(e["req"]):
                    e["req"] = r

        out = list(merged.values())
        out.sort(key=_sort_key)
        return out
    
    # ─────────────────────────────────────────────────────────────────────
    # Scrittura della singola riga di secondo livello
    # ─────────────────────────────────────────────────────────────────────

    def _fill_row(self, row: int, entry: dict, progressive: int | None) -> None:
        req_id  = entry["req_id"]
        configs = entry["configs"]
        primary = config_colors.color_for(configs[0]) if configs else "000000"

        # Col A e B restano VUOTE: è il discriminatore di secondo livello
        self.ws.cell(row, cfg.REQ_FUNC_ID_COL).value = None
        self.ws.cell(row, cfg.REQ_DESC_COL).value    = None

        # Col C — Nr requisito: SEMPRE NERO, non grassetto
        c = self.ws.cell(row, cfg.REQ_NUMBER_COL)
        c.value = f"{progressive}) {req_id}" if progressive else req_id
        c.font = Font(color="FF000000", bold=False)
        c.alignment = Alignment(wrap_text=True, vertical="top")

        # Col D — Configurazioni: colorate e in GRASSETTO
        d = self.ws.cell(row, cfg.REQ_CONFIG_COL)
        d.alignment = Alignment(wrap_text=True, vertical="top")
        if _RICH and len(configs) > 1:
            blocks = []
            for i, cname in enumerate(configs):
                if i:
                    blocks.append(TextBlock(InlineFont(color="FF000000", b=True), ", "))
                blocks.append(TextBlock(
                    InlineFont(color=config_colors.color_for(cname), b=True), cname
                ))
            d.value = CellRichText(*blocks)
        else:
            d.value = ", ".join(configs)
            d.font = Font(color=primary, bold=True)

        

        # Colonne extra opzionali (E, F, G...)
                # Colonne per-configurazione (E in poi)
        self._fill_config_cells(row, entry)

    # ─────────────────────────────────────────────────────────────────────
    # Colonne per-configurazione (E, F, G...)
    # ─────────────────────────────────────────────────────────────────────

    def _write_cell(self, row: int, col: int, value, color: str, bold: bool) -> None:
        c = self.ws.cell(row, col)
        c.value = value
        c.font = Font(color=color, bold=bold)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    def _fill_config_cells(self, row: int, entry: dict) -> None:
        """
        Regole:
          1) base + altre  → base: dump nero; altre: MATCHED verde/grassetto
                             oppure differenze LLM in rosso.
          2) solo base     → dump nero in colonna VZI_Base.
          3) senza base    → se tutte identiche: 'MISS VZI_BASE REQ, MATCHED'
                             verde/grassetto in ogni colonna; altrimenti
                             'MISS VZI_BASE REQ, FOUND DIFF' rosso/grassetto
                             seguito dal dump nero dei campi.
        """
        by_config: dict = entry.get("by_config") or {}
        if not by_config:
            return

        # Pulizia: colonne di configurazioni in cui il requisito NON c'è più
        presenti = {_norm(n) for n in by_config}
        for cname_norm, col in self.config_cols.items():
            if cname_norm not in presenti:
                self.ws.cell(row, col).value = None

        req_id = entry["req_id"]
        base_name = next(
            (n for n in by_config if _norm(n) == _norm(cfg.REQ_BASE_CONFIG)), None
        )
        others = [n for n in by_config if n != base_name]

        # ── Casi 1 e 2: il requisito esiste nella configurazione base ────
        if base_name:
            base_req = by_config[base_name]
            self._write_cell(
                row, self._col_for_config(base_name),
                reqai.dump_fields(base_req), cfg.REQ_COLOR_BLACK, False,
            )
            for cname in others:                       # caso 1
                col = self._col_for_config(cname)
                ok, diff = reqai.compare(req_id, base_req, cname, by_config[cname])
                if ok:
                    self._write_cell(row, col, cfg.REQ_TXT_MATCHED,
                                     cfg.REQ_COLOR_GREEN, True)
                else:
                    self._write_cell(row, col, diff, cfg.REQ_COLOR_RED, False)
            return

        # ── Caso 3: requisito assente nella configurazione base ──────────
        reqs = list(by_config.values())

        # Una sola configurazione non-base: nessun confronto possibile →
        # dump nero dei campi, preceduto dall'avviso di requisito mancante.
        # Una sola configurazione non-base: nessun confronto possibile.
        # Si scrive l'etichetta di requisito mancante nella base e, sotto,
        # la sola Description: il resto dei campi è contesto e appesantisce
        # la cella senza aggiungere informazione utile.
        if len(reqs) == 1:
            cname = next(iter(by_config))
            only = reqs[0]
            desc = (getattr(only, cfg.REQ_PRIMARY_FIELD, "") or "").strip()
            testo = (f"{cfg.REQ_TXT_MISS_ONLY}\n{desc}" if desc
                     else f"{cfg.REQ_TXT_MISS_ONLY}\n[Description non estratta "
                          f"dal documento]")
            self._write_cell(
                row, self._col_for_config(cname),
                testo, cfg.REQ_COLOR_BLACK, False,
            )
            return
        
        if reqai.identical(reqs):
            for cname in by_config:
                self._write_cell(row, self._col_for_config(cname),
                                 cfg.REQ_TXT_MISS_MATCHED,
                                 cfg.REQ_COLOR_GREEN, True)
            return

        # testi diversi: intestazione rossa in grassetto + dump nero
        ref_name = max(
            by_config,
            key=lambda n: len(
                (getattr(by_config[n], cfg.REQ_PRIMARY_FIELD, "") or "")
            ),
        )
        ref_req = by_config[ref_name]
        for cname, r in by_config.items():
            col  = self._col_for_config(cname)
            dump = reqai.dump_fields(r)
            if cname != ref_name:
                _, diff = reqai.compare(req_id, ref_req, cname, r)
                if diff:
                    dump = f"Differenze vs {ref_name}: {diff}{cfg.REQ_FIELD_SEP}{dump}"
            header = cfg.REQ_TXT_MISS_DIFF
            if _RICH:
                self.ws.cell(row, col).value = CellRichText(
                    TextBlock(InlineFont(color=cfg.REQ_COLOR_RED, b=True), header + "\n"),
                    TextBlock(InlineFont(color=cfg.REQ_COLOR_BLACK, b=False), dump),
                )
                self.ws.cell(row, col).alignment = Alignment(wrap_text=True, vertical="top")
            else:
                self._write_cell(row, col, f"{header}\n{dump}",
                                 cfg.REQ_COLOR_BLACK, False)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _s(v) -> str:
    if v is None:
        return ""
    t = type(v).__name__
    if "Formula" in t or "formula" in t:
        return ""
    return str(v).strip()


def _norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def _strip_progressive(s: str) -> str:
    """Rimuove un eventuale prefisso progressivo '12) ' dal Nr requisito."""
    import re
    return re.sub(r"^\s*\d+\)\s*", "", s or "")


def _richness(r) -> int:
    n = sum(bool(getattr(r, a, "")) for a in
            ("description", "req_type", "derived_to", "user_interface", "sil"))
    # Un requisito verticale ha per natura meno campi: non va penalizzato
    bonus = 2 if getattr(r, "layout", "") == "V" else 0
    return (n + bonus) * 1000 + len(getattr(r, "description", "") or "")