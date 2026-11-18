"""
analysis_scope.py
-----------------
Ambito comune alle opzioni di analisi 1-5: l'utente sceglie

  * gli FRS (DOC ID del foglio CONFIG col B / Funzioni col D),
    es. "FRS_Line Voltage";
  * le funzioni degli FRS scelti (FUNC ID del foglio Funzioni),
    es. "FRS_Pantograph Lifting", "FRS_Pantograph Control";
  * le configurazioni di treno, es. "VZI_Base, VZ_FR".

Vuoto = tutti. Le scelte si indicano con numeri dell'elenco, intervalli
(es. "1-4"), nomi o parte univoca del nome, separati da virgola.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from openpyxl import load_workbook

import config as cfg

log = logging.getLogger(__name__)

_INVALID_DOC = {"", "\\", "/", "tbd"}


def norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(text or "").strip().lower())


def _s(v) -> str:
    return "" if v is None or not isinstance(v, (str, int, float)) else str(v).strip()


# ---------------------------------------------------------------------------
# Ambito
# ---------------------------------------------------------------------------

@dataclass
class Scope:
    frs: list[str] = field(default_factory=list)       # vuoto = tutti
    funcs: list[str] = field(default_factory=list)     # vuoto = tutte
    configs: list[str] = field(default_factory=list)   # vuoto = tutte

    def __post_init__(self) -> None:
        self._frs = {norm(x) for x in self.frs}
        self._funcs = {norm(x) for x in self.funcs}
        self._configs = {norm(x) for x in self.configs}

    def copy(self) -> "Scope":
        return Scope(list(self.frs), list(self.funcs), list(self.configs))

    @property
    def is_full(self) -> bool:
        return not (self.frs or self.funcs or self.configs)

    def frs_ok(self, doc_id: str) -> bool:
        return not self.frs or norm(doc_id) in self._frs

    def func_ok(self, func_id: str) -> bool:
        return not self.funcs or norm(func_id) in self._funcs

    def config_ok(self, name: str) -> bool:
        return not self.configs or norm(name) in self._configs

    def filter_configs(self, configs: list[str]) -> list[str]:
        return [c for c in configs if self.config_ok(c)]

    def partial_reasons(self) -> list[str]:
        out = []
        if self.frs:
            out.append(f"solo FRS {', '.join(self.frs)}")
        if self.funcs:
            out.append(f"solo funzioni {', '.join(self.funcs)}")
        if self.configs:
            out.append(f"solo configurazioni {', '.join(self.configs)}")
        return out

    def describe(self) -> dict:
        return {
            "FRS": ", ".join(self.frs) or "tutti",
            "Funzioni": ", ".join(self.funcs) or "tutte",
            "Configurazioni": ", ".join(self.configs) or "tutte",
        }


# ---------------------------------------------------------------------------
# Catalogo (dal file Excel)
# ---------------------------------------------------------------------------

@dataclass
class Catalog:
    frs: list[str] = field(default_factory=list)
    funcs: list[str] = field(default_factory=list)                     # ordine foglio
    func_desc: dict[str, str] = field(default_factory=dict)
    funcs_by_frs: dict[str, list[str]] = field(default_factory=dict)   # {norm(frs): [func]}
    configs: list[str] = field(default_factory=list)

    def funcs_of(self, frs: list[str]) -> list[str]:
        if not frs:
            return list(self.funcs)
        wanted = set()
        for d in frs:
            wanted.update(self.funcs_by_frs.get(norm(d), []))
        return [f for f in self.funcs if f in wanted]


def load_catalog(path=None) -> Catalog:
    """FRS, funzioni per FRS e configurazioni dai fogli CONFIG, Funzioni, Requisiti."""
    try:
        wb = load_workbook(str(path or cfg.EXCEL_PATH), read_only=True, data_only=True)
    except Exception as exc:
        log.warning(f"  Elenco FRS/funzioni/configurazioni non disponibile: {exc}")
        return Catalog()
    try:
        return catalog_from_wb(wb)
    finally:
        wb.close()


def catalog_from_wb(wb) -> Catalog:
    """Come load_catalog, su un workbook gia' aperto (non viene chiuso)."""
    cat = Catalog()
    seen_frs: set[str] = set()
    seen_cfg: set[str] = set()

    def add_frs(d: str) -> None:
        if d and d.lower() not in _INVALID_DOC and norm(d) not in seen_frs \
                and not d.lower().startswith("func_"):
            seen_frs.add(norm(d))
            cat.frs.append(d)

    def add_cfg(c: str) -> None:
        c = c.replace("\n", " / ").strip()
        if c and norm(c) not in seen_cfg:
            seen_cfg.add(norm(c))
            cat.configs.append(c)

    try:
        sheet_cfg = getattr(cfg, "SHEET_CONFIG", "CONFIG")
        if sheet_cfg in wb.sheetnames:
            skip = {"doc description", "doc id", "doc ext", "doe ext"}
            ws = wb[sheet_cfg]
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    for v in row:
                        if _s(v) and _s(v).lower() not in skip:
                            add_cfg(_s(v))
                    continue
                if len(row) > 1:
                    add_frs(_s(row[1]))

        if cfg.SHEET_FUNZIONI in wb.sheetnames:
            ws = wb[cfg.SHEET_FUNZIONI]
            fid = ""
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                row = tuple(row) + (None,) * max(0, 5 - len(row))
                if i == 0:
                    for v in row[5:-1]:
                        add_cfg(_s(v))
                    continue
                if _s(row[0]):
                    fid = _s(row[0])
                    if fid not in cat.func_desc:
                        cat.funcs.append(fid)
                        cat.func_desc[fid] = _s(row[1])
                    continue
                d = _s(row[3])
                if fid and _s(row[2]) and d and d.lower() not in _INVALID_DOC:
                    add_frs(d)
                    lst = cat.funcs_by_frs.setdefault(norm(d), [])
                    if fid not in lst:
                        lst.append(fid)

        if cfg.SHEET_REQUISITI in wb.sheetnames:
            ws = wb[cfg.SHEET_REQUISITI]
            for row in ws.iter_rows(min_row=cfg.REQ_HEADER_ROW, max_row=cfg.REQ_HEADER_ROW,
                                    values_only=True):
                for v in row[cfg.REQ_CONFIG_COLS_START - 1:]:
                    add_cfg(_s(v))
    except Exception as exc:
        log.warning(f"  Catalogo dell'ambito incompleto: {exc}")
    return cat


# ---------------------------------------------------------------------------
# Scelte
# ---------------------------------------------------------------------------

def resolve(text: str, choices: list[str],
            free: bool = True) -> tuple[list[str], list[str]]:
    """
    Voci separate da virgola o punto e virgola: numero dell'elenco,
    intervallo "a-b", nome (maiuscole, spazi, '_' e '-' ignorati) o parte
    univoca del nome. Ritorna (scelti nell'ordine dell'elenco, non riconosciuti).
    Senza elenco i nomi vengono accettati cosi' come sono (free=True).
    """
    toks = [t.strip() for t in re.split(r"[,;]", text or "") if t.strip()]
    if not choices:
        return (list(dict.fromkeys(toks)), []) if free else ([], toks)
    chosen: list[str] = []
    unknown: list[str] = []
    for tok in toks:
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", tok)
        if m:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            if a >= 1 and b <= len(choices):
                chosen.extend(choices[a - 1:b])
                continue
        if tok.isdigit() and 1 <= int(tok) <= len(choices):
            chosen.append(choices[int(tok) - 1])
            continue
        t = norm(tok)
        exact = [c for c in choices if norm(c) == t]
        part = [c for c in choices if t and t in norm(c)]
        found = exact[0] if exact else (part[0] if len(part) == 1 else None)
        if found is None:
            unknown.append(tok if len(part) < 2 else
                           f"{tok} (ambiguo: {', '.join(part[:4])}"
                           f"{', ...' if len(part) > 4 else ''})")
        else:
            chosen.append(found)
    keep = set(chosen)
    return [c for c in choices if c in keep], unknown


def resolve_scope(frs: str = "", funcs: str = "", configs: str = "",
                  catalog: Catalog | None = None) -> tuple[Scope, list[str]]:
    """Ambito da testo (riga di comando). Ritorna (ambito, errori)."""
    cat = catalog if catalog is not None else load_catalog()
    errors: list[str] = []
    f, u = resolve(frs, cat.frs)
    if u:
        errors.append(f"FRS non riconosciuti: {', '.join(u)}")
    fn, u = resolve(funcs, cat.funcs_of(f) if f else cat.funcs, free=not cat.funcs)
    if u:
        errors.append(f"funzioni non riconosciute{' negli FRS scelti' if f else ''}: "
                      f"{', '.join(u)}")
    c, u = resolve(configs, cat.configs)
    if u:
        errors.append(f"configurazioni non riconosciute: {', '.join(u)}")
    return Scope(f, fn, c), errors


def _inp(msg: str) -> str:
    try:
        return input(msg).strip()
    except EOFError:
        return ""


def _ask_list(title: str, choices: list[str], current: list[str], every: str,
              labels: dict[str, str] | None = None) -> list[str]:
    if choices:
        print(f"  {title}:")
        for i, c in enumerate(choices, 1):
            extra = " ".join((labels or {}).get(c, "").split())
            if len(extra) > 90:
                extra = extra[:89] + "…"
            print(f"    {i:3d}) {c}" + (f"  — {extra}" if extra else ""))
    while True:
        a = _inp(f"  Scelta (numeri, intervalli 1-3, nomi; '*' = {every}) "
                 f"[Invio = {', '.join(current) or every}]: ")
        if not a:
            return list(current)
        if a == "*":
            return []
        chosen, unknown = resolve(a, choices)
        if unknown:
            print(f"    Non riconosciuti: {', '.join(unknown)}")
            continue
        return chosen


def ask_scope(defaults: Scope, option: str, catalog: Catalog | None = None,
              note: str = "") -> Scope:
    """Domande interattive: FRS → funzioni degli FRS scelti → configurazioni."""
    cat = catalog if catalog is not None else load_catalog()
    print("\n" + "-" * 60)
    print(f"  Opzione {option} — ambito dell'analisi (Invio = proposto, '*' = tutti)")
    print("-" * 60)
    if note:
        print(f"  {note}")
    frs = _ask_list("FRS disponibili (foglio CONFIG col B / Funzioni col D)",
                    cat.frs, defaults.frs, "tutti")

    funcs_choices = cat.funcs_of(frs)
    cur_funcs = [f for f in defaults.funcs if f in funcs_choices]
    if frs and not funcs_choices:
        print("  Nessuna funzione del foglio Funzioni collegata agli FRS scelti.")
        funcs = []
    else:
        title = ("Funzioni degli FRS scelti" if frs
                 else "Funzioni del foglio Funzioni (tutti gli FRS)")
        funcs = _ask_list(title, funcs_choices, cur_funcs, "tutte", cat.func_desc)

    configs = _ask_list("Configurazioni di treno", cat.configs, defaults.configs, "tutte")
    scope = Scope(frs, funcs, configs)
    print("  Ambito: " + "; ".join(f"{k} = {v}" for k, v in scope.describe().items()))
    return scope
