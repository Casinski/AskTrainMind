"""
requisiti_writer.py
-------------------
Compila il foglio "Requisiti".

Struttura attesa (simile a "Funzioni"):
    Col FUNC ID | DESCRIZIONE FUNZIONE | ... | Requisito |
    Configurazione Appartenenza | <config 1> | <config 2> | ...

REGOLA DI SCRITTURA
  Una riga per ogni (funzione, requisito).
  - "Requisito"                  → ID, colorato col colore della configurazione
                                   in cui è stato trovato (prima occorrenza)
  - "Configurazione Appartenenza"→ elenco delle configurazioni in cui l'ID
                                   compare. Se openpyxl >= 3.1 è disponibile,
                                   ogni nome è colorato singolarmente
                                   (rich text); altrimenti l'intera cella usa
                                   il colore della prima configurazione.
  - colonne configurazione       → "X" colorata dove il requisito è presente

Il writer è IDEMPOTENTE: se la coppia (func_id, req_id) esiste già, aggiorna
la riga esistente invece di duplicarla.
"""
from __future__ import annotations
import logging
from openpyxl.styles import Font, Alignment

import config as cfg
import config_colors

log = logging.getLogger(__name__)

try:
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    _RICH = True
except Exception:          # openpyxl < 3.1
    _RICH = False


class RequisitiWriter:
    """Gestisce header, indice righe e scrittura sul foglio Requisiti."""

    def __init__(self, ws):
        self.ws = ws
        self.cols = self._map_headers()
        self.config_cols = self._map_config_cols()
        self.index = self._build_index()
        self.next_row = max(ws.max_row + 1, cfg.REQ_HEADER_ROW + 1)
        log.info(
            f"  [Requisiti] Colonne: {self.cols} | "
            f"config: {list(self.config_cols)} | righe esistenti: {len(self.index)}"
        )

    # ── Mappatura intestazioni ────────────────────────────────────────────
    def _map_headers(self) -> dict[str, int]:
        out = {}
        for col in range(1, self.ws.max_column + 1):
            v = self.ws.cell(cfg.REQ_HEADER_ROW, col).value
            if not v:
                continue
            k = str(v).strip().lower().replace("\n", " ")
            for name, target in (
                (cfg.REQ_COL_FUNC_ID,      "func_id"),
                (cfg.REQ_COL_DESCRIZIONE,  "desc"),
                (cfg.REQ_COL_REQUISITO,    "requisito"),
                (cfg.REQ_COL_APPARTENENZA, "appartenenza"),
                ("description",            "req_desc"),
                ("type",                   "req_type"),
                ("derived to",             "derived_to"),
                ("user interface",         "user_interface"),
                ("sil",                    "sil"),
            ):
                if target not in out and name in k:
                    out[target] = col
        if "func_id" not in out:
            out["func_id"] = 1
        if "requisito" not in out:
            log.error(
                f"  [Requisiti] Colonna '{cfg.REQ_COL_REQUISITO}' non trovata "
                f"nella riga {cfg.REQ_HEADER_ROW}: il foglio non sarà compilato."
            )
        return out

    def _map_config_cols(self) -> dict[str, int]:
        out = {}
        known = set(config_colors.legend())
        for col in range(1, self.ws.max_column + 1):
            v = self.ws.cell(cfg.REQ_HEADER_ROW, col).value
            if not v:
                continue
            name = str(v).strip().replace("\n", " / ")
            if name in known:
                out[name] = col
        return out

    def _build_index(self) -> dict[tuple[str, str], int]:
        idx = {}
        col_f = self.cols.get("func_id")
        col_r = self.cols.get("requisito")
        if not col_r:
            return idx
        func = ""
        for row in range(cfg.REQ_HEADER_ROW + 1, self.ws.max_row + 1):
            fv = self.ws.cell(row, col_f).value
            if fv:
                func = str(fv).strip()
            rv = self.ws.cell(row, col_r).value
            if rv:
                idx[(func, str(rv).strip().lower())] = row
        return idx

    # ── API pubblica ──────────────────────────────────────────────────────
    def write_group(self, func_id: str, func_desc: str, reqs_by_config: dict) -> int:
        """
        reqs_by_config: {config_name: [Requirement, ...]}
        Ritorna il numero di righe scritte o aggiornate.
        """
        if "requisito" not in self.cols:
            return 0

        merged: dict[str, dict] = {}
        for cname, reqs in reqs_by_config.items():
            for r in reqs:
                e = merged.setdefault(r.req_id, {"req": r, "configs": []})
                if cname not in e["configs"]:
                    e["configs"].append(cname)
                # preferisci la versione con più campi valorizzati
                if _richness(r) > _richness(e["req"]):
                    e["req"] = r

        n = 0
        for req_id, entry in merged.items():
            self._write_row(func_id, func_desc, entry["req"], entry["configs"])
            n += 1
        if n:
            log.info(f"  [Requisiti] {func_id}: {n} requisiti scritti/aggiornati")
        return n

    # ── Scrittura riga ────────────────────────────────────────────────────
    def _write_row(self, func_id, func_desc, req, configs: list[str]) -> None:
        key = (func_id, req.req_id.strip().lower())
        row = self.index.get(key)
        if row is None:
            row = self.next_row
            self.next_row += 1
            self.index[key] = row
            if "func_id" in self.cols:
                self.ws.cell(row, self.cols["func_id"]).value = func_id
            if "desc" in self.cols:
                self.ws.cell(row, self.cols["desc"]).value = func_desc

        primary = config_colors.color_for(configs[0]) if configs else "000000"

        c = self.ws.cell(row, self.cols["requisito"])
        c.value = req.req_id
        c.font = Font(color=primary, bold=False)
        c.alignment = Alignment(wrap_text=True, vertical="top")

        if "appartenenza" in self.cols:
            self._write_appartenenza(row, self.cols["appartenenza"], configs, primary)

        if cfg.REQ_WRITE_EXTRA_FIELDS:
            for field_name, attr in (
                ("req_desc", "description"), ("req_type", "req_type"),
                ("derived_to", "derived_to"),
                ("user_interface", "user_interface"), ("sil", "sil"),
            ):
                col = self.cols.get(field_name)
                val = getattr(req, attr, "")
                if col and val:
                    cc = self.ws.cell(row, col)
                    cc.value = val
                    cc.alignment = Alignment(wrap_text=True, vertical="top")

        for cname in configs:
            col = self.config_cols.get(cname)
            if col:
                cc = self.ws.cell(row, col)
                cc.value = "X"
                cc.font = Font(color=config_colors.color_for(cname), bold=True)
                cc.alignment = Alignment(horizontal="center")

    def _write_appartenenza(self, row, col, configs, primary) -> None:
        cell = self.ws.cell(row, col)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if _RICH and configs:
            blocks = []
            for i, cname in enumerate(configs):
                if i:
                    blocks.append(TextBlock(InlineFont(color="000000"), ", "))
                blocks.append(
                    TextBlock(InlineFont(color=config_colors.color_for(cname)), cname)
                )
            cell.value = CellRichText(*blocks)
        else:
            cell.value = ", ".join(configs)
            cell.font = Font(color=primary)


def _richness(r) -> int:
    return sum(bool(getattr(r, a, "")) for a in
               ("description", "req_type", "derived_to", "user_interface", "sil"))