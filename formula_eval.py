"""
formula_eval.py — Excel formula resolver for AskTrainMind.

Evaluates HYPERLINK / CONCATENATE / &-operator / cell-reference formulas
found in openpyxl Cell objects and returns the real URL and friendly title.

Supports both English and Italian Excel function names.

Design principles:
- Never raises.  All error paths return (None, best_effort_text).
- Resolves cross-sheet references (FoglioNome!$A$1) when a workbook is passed.
- Resolves same-row implicit references ($D5 when the cell is on row 5).
"""
from __future__ import annotations

import re
from typing import Optional, Any


# ---------------------------------------------------------------------------
# Italian → English function name aliases
# ---------------------------------------------------------------------------

_ITALIAN_ALIASES: dict[str, str] = {
    # Hyperlink / testo
    "COLLEG.IPERTESTUALE": "HYPERLINK",
    "CONCATENA":           "CONCATENATE",
    "STRINGA.ESTRAI":      "MID",
    "TROVA":               "FIND",
    "SINISTRA":            "LEFT",
    "DESTRA":              "RIGHT",
    "LUNGHEZZA":           "LEN",
    "MAIUSC":              "UPPER",
    "MINUSC":              "LOWER",
    "ANNULLA.SPAZI":       "TRIM",
    "SOSTITUISCI":         "SUBSTITUTE",
    # Lookup / riferimento
    "CONFRONTA":           "MATCH",
    "INDIRETTO":           "INDIRECT",
    "INDIRIZZO":           "ADDRESS",
    "INDICE":              "INDEX",
    "CERCA.VERT":          "VLOOKUP",
    "SCARTO":              "OFFSET",
    "RIGHE":               "ROWS",
    "COLONNE":             "COLUMNS",
    # Logiche
    "SE":                  "IF",
    "E":                   "AND",
    "O":                   "OR",
    "NON":                 "NOT",
    "VAL.ERRORE":          "ISERROR",
    "VAL.NON.DISP":        "ISNA",
    "SE.ERRORE":           "IFERROR",
    # Matematica
    "ARROTONDA":           "ROUND",
    "INTERO":              "INT",
}


def _normalize_fname(name: str) -> str:
    """Normalizza il nome di una funzione Excel: upper-case + alias italiano→inglese."""
    upper = name.upper()
    return _ITALIAN_ALIASES.get(upper, upper)


# ---------------------------------------------------------------------------
# Column / row helpers
# ---------------------------------------------------------------------------

def _col_to_index(col: str) -> int:
    """Convert a column letter string ('A', 'BC', …) to a 1-based column index."""
    result = 0
    for c in col.upper():
        result = result * 26 + (ord(c) - ord("A") + 1)
    return result


def _col_index_to_letter(n: int) -> str:
    """Convert 1-based column index to Excel letter(s)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


# ---------------------------------------------------------------------------
# Cross-sheet reference regex
# e.g.  Cartelle!$D$5   'Nome Foglio'!$A$1   CONFIG!B:B   MAN_CPR!$1:$1
# ---------------------------------------------------------------------------

_CROSS_SHEET_REF_RE = re.compile(
    r"^'?([^'!]+)'?!"          # sheet name (optionally quoted)
    r"(\$?[A-Za-z]+\$?\d*"    # col+row (cell) or just col (column range)
    r"(?::\$?[A-Za-z]*\$?\d*)?)"  # optional :range part
    r"$"
)

_CELL_REF_RE = re.compile(r"^\$?([A-Za-z]+)\$?(\d*)$")


# ---------------------------------------------------------------------------
# Cell value readers
# ---------------------------------------------------------------------------

def _get_cell_value(ws, col_idx: int, row_num: int) -> str:
    """Return the plain string value of a worksheet cell (no formula recursion)."""
    try:
        cell = ws.cell(row=row_num, column=col_idx)
        val = cell.value
        if val is None:
            return ""
        if isinstance(val, str) and val.startswith("="):
            return ""  # non ricorsivo
        return str(val).strip()
    except Exception:
        return ""


def _get_cross_sheet_value(workbook, sheet_name: str, col_idx: int, row_num: int) -> str:
    """
    Legge il valore plain (non formula) da un altro foglio del workbook.
    Restituisce stringa vuota se il foglio non esiste o la cella è una formula.
    """
    if workbook is None:
        return ""
    try:
        # Cerca il foglio ignorando maiuscole/minuscole
        target_ws = None
        sname_lower = sheet_name.strip("'").lower()
        for name in workbook.sheetnames:
            if name.lower() == sname_lower:
                target_ws = workbook[name]
                break
        if target_ws is None:
            return ""
        return _get_cell_value(target_ws, col_idx, row_num)
    except Exception:
        return ""


def _resolve_cross_sheet_ref(expr: str, workbook, current_row: int) -> Optional[str]:
    """
    Se expr è un riferimento cross-sheet (es. Cartelle!$D$5), ne legge il valore.
    Restituisce None se non è un riferimento cross-sheet.
    """
    m = _CROSS_SHEET_REF_RE.match(expr.strip())
    if not m:
        return None

    sheet_name = m.group(1).strip("'").strip()
    ref_part = m.group(2)

    # Gestiamo solo riferimenti a singola cella (non range complessi come $B:$B)
    # Per i range usiamo stringa vuota — non abbiamo un contesto di lookup completo
    single_cell_m = re.match(r"^\$?([A-Za-z]+)\$?(\d+)$", ref_part)
    if not single_cell_m:
        # Range (es. $B:$B, $1:$1) — non risolvibile senza MATCH/INDEX completo
        return ""

    col_idx = _col_to_index(single_cell_m.group(1))
    row_num = int(single_cell_m.group(2))
    return _get_cross_sheet_value(workbook, sheet_name, col_idx, row_num)


# ---------------------------------------------------------------------------
# String literal parser
# ---------------------------------------------------------------------------

def _parse_string_literal(s: str) -> str:
    """
    Parse a double-quoted Excel string literal (with "" escaping).
    Input must start with a '"'. Returns the unescaped Python string.
    """
    if not (s and s.startswith('"')):
        return s
    inner = s[1:]
    result: list[str] = []
    i = 0
    while i < len(inner):
        if inner[i] == '"':
            if i + 1 < len(inner) and inner[i + 1] == '"':
                result.append('"')
                i += 2
            else:
                break
        else:
            result.append(inner[i])
            i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# Tokenisers
# ---------------------------------------------------------------------------

def _split_on_amp(expr: str) -> list[str]:
    """Split *expr* on '&' while respecting string literals and nested parens."""
    parts: list[str] = []
    current: list[str] = []
    in_str = False
    depth = 0
    i = 0
    while i < len(expr):
        c = expr[i]
        if c == '"':
            if in_str and i + 1 < len(expr) and expr[i + 1] == '"':
                current.append('""')
                i += 2
                continue
            in_str = not in_str
            current.append(c)
        elif c == "(" and not in_str:
            depth += 1
            current.append(c)
        elif c == ")" and not in_str:
            depth -= 1
            current.append(c)
        elif c == "&" and not in_str and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(c)
        i += 1
    remainder = "".join(current).strip()
    if remainder:
        parts.append(remainder)
    return parts


def _split_func_args(inner: str) -> list[str]:
    """
    Split comma OR semicolon-separated function arguments in *inner*,
    respecting string literals and nested parentheses.
    (Italian Excel uses semicolons as argument separators.)
    """
    args: list[str] = []
    current: list[str] = []
    in_str = False
    depth = 0
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == '"':
            if in_str and i + 1 < len(inner) and inner[i + 1] == '"':
                current.append('""')
                i += 2
                continue
            in_str = not in_str
            current.append(c)
        elif c == "(" and not in_str:
            depth += 1
            current.append(c)
        elif c == ")" and not in_str:
            depth -= 1
            current.append(c)
        elif c in (",", ";") and not in_str and depth == 0:
            # Accetta sia virgola (EN) sia punto e virgola (IT) come separatore
            args.append("".join(current).strip())
            current = []
        else:
            current.append(c)
        i += 1
    remainder = "".join(current).strip()
    if remainder:
        args.append(remainder)
    return args


def _find_matching_paren(s: str, open_pos: int) -> int:
    """Return the position of the closing ')' matching the '(' at *open_pos*."""
    depth = 0
    in_str = False
    i = open_pos
    while i < len(s):
        c = s[i]
        if c == '"':
            if in_str and i + 1 < len(s) and s[i + 1] == '"':
                i += 2
                continue
            in_str = not in_str
        elif c == "(" and not in_str:
            depth += 1
        elif c == ")" and not in_str:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s) - 1


# ---------------------------------------------------------------------------
# Built-in function implementations
# ---------------------------------------------------------------------------

def _fn_mid(args: list[str]) -> str:
    """MID(text, start_num, num_chars) — estrae sottostringa."""
    if len(args) < 3:
        return ""
    try:
        text = args[0]
        start = max(1, int(float(args[1])))
        length = max(0, int(float(args[2])))
        return text[start - 1: start - 1 + length]
    except Exception:
        return ""


def _fn_find(args: list[str]) -> str:
    """FIND(find_text, within_text [, start_num]) — trova posizione (1-based)."""
    if len(args) < 2:
        return ""
    try:
        find_text = args[0]
        within = args[1]
        start = max(1, int(float(args[2]))) - 1 if len(args) > 2 else 0
        pos = within.find(find_text, start)
        return str(pos + 1) if pos >= 0 else ""
    except Exception:
        return ""


def _fn_left(args: list[str]) -> str:
    """LEFT(text, num_chars)."""
    if not args:
        return ""
    try:
        text = args[0]
        n = int(float(args[1])) if len(args) > 1 else 1
        return text[:max(0, n)]
    except Exception:
        return ""


def _fn_right(args: list[str]) -> str:
    """RIGHT(text, num_chars)."""
    if not args:
        return ""
    try:
        text = args[0]
        n = int(float(args[1])) if len(args) > 1 else 1
        return text[-max(0, n):] if n > 0 else ""
    except Exception:
        return ""


def _fn_len(args: list[str]) -> str:
    """LEN(text)."""
    if not args:
        return "0"
    return str(len(args[0]))


def _fn_upper(args: list[str]) -> str:
    return args[0].upper() if args else ""


def _fn_lower(args: list[str]) -> str:
    return args[0].lower() if args else ""


def _fn_trim(args: list[str]) -> str:
    return args[0].strip() if args else ""


def _fn_substitute(args: list[str]) -> str:
    """SUBSTITUTE(text, old_text, new_text [, instance_num])."""
    if len(args) < 3:
        return args[0] if args else ""
    try:
        return args[0].replace(args[1], args[2])
    except Exception:
        return args[0] if args else ""


def _fn_address(args: list[str]) -> str:
    """
    ADDRESS(row_num, col_num [, abs_num [, a1 [, sheet_text]]]).
    Restituisce la stringa di riferimento cella (es. "$A$1").
    Implementazione semplificata: supporta solo abs_num=1 (assoluto).
    """
    if len(args) < 2:
        return ""
    try:
        row = int(float(args[0]))
        col = int(float(args[1]))
        col_letter = _col_index_to_letter(col)
        return f"${col_letter}${row}"
    except Exception:
        return ""


def _fn_iferror(args: list[str]) -> str:
    """IFERROR(value, value_if_error) — restituisce value se non è errore."""
    if not args:
        return ""
    # Nel nostro contesto tutti i valori sono stringhe, mai errori Excel reali
    return args[0] if args else (args[1] if len(args) > 1 else "")


# Funzioni stub che richiederebbero lookup completo dell'intero foglio
# Restituiscono stringa vuota — l'URL viene comunque ottenuto via data_only

def _fn_match_stub(args: list[str]) -> str:
    """MATCH — stub, richiede lookup su range. Restituisce '' (usa data_only)."""
    return ""


def _fn_indirect_stub(args: list[str]) -> str:
    """INDIRECT — stub, richiede risoluzione runtime. Restituisce ''."""
    return ""


def _fn_index_stub(args: list[str]) -> str:
    """INDEX — stub, richiede range. Restituisce ''."""
    return ""


def _fn_vlookup_stub(args: list[str]) -> str:
    """VLOOKUP — stub. Restituisce ''."""
    return ""


# Dispatch table: nome funzione inglese → implementazione
_FUNCTIONS: dict[str, Any] = {
    "CONCATENATE": None,   # gestito inline in _eval_atom
    "HYPERLINK":   None,   # gestito inline in _resolve_impl
    "MID":         _fn_mid,
    "FIND":        _fn_find,
    "LEFT":        _fn_left,
    "RIGHT":       _fn_right,
    "LEN":         _fn_len,
    "UPPER":       _fn_upper,
    "LOWER":       _fn_lower,
    "TRIM":        _fn_trim,
    "SUBSTITUTE":  _fn_substitute,
    "ADDRESS":     _fn_address,
    "IFERROR":     _fn_iferror,
    "IF":          _fn_iferror,   # semplificato: restituisce il primo arg
    # Stub — richiedono lookup completo
    "MATCH":       _fn_match_stub,
    "INDIRECT":    _fn_indirect_stub,
    "INDEX":       _fn_index_stub,
    "VLOOKUP":     _fn_vlookup_stub,
    "OFFSET":      _fn_match_stub,
}


# ---------------------------------------------------------------------------
# Expression evaluator
# ---------------------------------------------------------------------------

def _eval_atom(expr: str, ws, current_row: int, workbook=None) -> str:
    """
    Evaluate a single atom: string literal, number, cross-sheet ref,
    same-sheet cell ref, CONCATENATE(), HYPERLINK first-arg, or other function.
    """
    expr = expr.strip()
    if not expr:
        return ""

    # Stringa letterale
    if expr.startswith('"'):
        return _parse_string_literal(expr)

    # Numero
    try:
        n = float(expr)
        return str(int(n)) if n == int(n) else str(n)
    except ValueError:
        pass

    # Riferimento cross-sheet: Foglio!$A$1
    cross = _resolve_cross_sheet_ref(expr, workbook, current_row)
    if cross is not None:
        return cross

    # Chiamata a funzione: NOME(...)
    func_m = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*\(", expr)
    if func_m:
        raw_name = func_m.group(1)
        fname = _normalize_fname(raw_name)
        open_p = expr.index("(")
        close_p = _find_matching_paren(expr, open_p)
        inner = expr[open_p + 1: close_p]
        args_raw = _split_func_args(inner)
        args_eval = [_eval_expr(a, ws, current_row, workbook) for a in args_raw]

        if fname == "CONCATENATE":
            return "".join(args_eval)

        if fname == "HYPERLINK":
            # Primo argomento = URL; lo restituiamo direttamente
            return args_eval[0] if args_eval else ""

        fn = _FUNCTIONS.get(fname)
        if fn is not None:
            return fn(args_eval)

        # Funzione sconosciuta → stringa vuota
        return ""

    # Riferimento cella stesso foglio: $D3, F$1, D3
    cell_m = _CELL_REF_RE.match(expr)
    if cell_m:
        col_idx = _col_to_index(cell_m.group(1))
        row_str = cell_m.group(2)
        row_num = int(row_str) if row_str else current_row
        return _get_cell_value(ws, col_idx, row_num)

    # Sottoespressione parentesizzata
    if expr.startswith("(") and expr.endswith(")"):
        return _eval_expr(expr[1:-1], ws, current_row, workbook)

    return expr


def _eval_expr(expr: str, ws, current_row: int, workbook=None) -> str:
    """Evaluate *expr* including '&'-concatenation."""
    parts = _split_on_amp(expr)
    return "".join(_eval_atom(p, ws, current_row, workbook) for p in parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_hyperlink(
    cell, worksheet, workbook=None
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve *cell*'s formula/value to ``(url, friendly_title)``.

    Resolution order:
    1. Real ``cell.hyperlink.target`` (preferred as URL).
    2. ``=HYPERLINK(...)`` / ``=COLLEG.IPERTESTUALE(...)`` — both args evaluated,
       including cross-sheet references and Italian function names.
    3. ``=CONCATENATE(...)`` / ``=CONCATENA(...)`` / ``&``-concatenation.
    4. Plain cell value (no formula).
    5. Any parse error → ``(None, best_effort_text)``.

    Pass *workbook* (the openpyxl Workbook object) to enable cross-sheet
    reference resolution (e.g. ``Cartelle!$D$5``).

    Never raises.
    """
    try:
        return _resolve_impl(cell, worksheet, workbook)
    except Exception:
        try:
            text = str(cell.value or "").strip()
            return None, text or None
        except Exception:
            return None, None


def _resolve_impl(
    cell, worksheet, workbook=None
) -> tuple[Optional[str], Optional[str]]:
    current_row = cell.row

    # -----------------------------------------------------------------------
    # 1. Hyperlink diretto sull'oggetto cella
    # -----------------------------------------------------------------------
    if cell.hyperlink and getattr(cell.hyperlink, "target", None):
        url = str(cell.hyperlink.target).strip()
        display = str(getattr(cell.hyperlink, "display", "") or "").strip() or None
        if not display:
            raw = cell.value
            if isinstance(raw, str) and not raw.startswith("="):
                display = raw.strip() or None
        return url or None, display

    # -----------------------------------------------------------------------
    # 2. Formula?
    # -----------------------------------------------------------------------
    raw_value = cell.value
    formula: Optional[str] = None
    if isinstance(raw_value, str) and raw_value.startswith("="):
        formula = raw_value[1:]
    elif hasattr(cell, "_value") and isinstance(getattr(cell, "_value", None), str):
        _v = cell._value
        if _v and _v.startswith("="):
            formula = _v[1:]

    if formula is None:
        text = str(raw_value).strip() if raw_value is not None else ""
        return (None, text) if text else (None, None)

    formula = formula.strip()

    # -----------------------------------------------------------------------
    # 3. HYPERLINK / COLLEG.IPERTESTUALE
    # -----------------------------------------------------------------------
    # Cerca sia il nome inglese che italiano normalizzato
    # Il pattern deve catturare il nome fino alla prima parentesi
    func_name_m = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*\(", formula)
    if func_name_m:
        fname = _normalize_fname(func_name_m.group(1))
        if fname == "HYPERLINK":
            open_p = formula.index("(")
            close_p = _find_matching_paren(formula, open_p)
            inner = formula[open_p + 1: close_p]
            args = _split_func_args(inner)
            if not args:
                return None, None

            url = _eval_expr(args[0], worksheet, current_row, workbook).strip()
            title: Optional[str] = None
            if len(args) > 1:
                t = _eval_expr(args[1], worksheet, current_row, workbook).strip()
                title = t if t else None
            if not title and cell.hyperlink and getattr(cell.hyperlink, "display", None):
                title = str(cell.hyperlink.display).strip() or None
            if not title and isinstance(raw_value, str) and not raw_value.startswith("="):
                title = raw_value.strip() or None
            return url or None, title

    # -----------------------------------------------------------------------
    # 4. Espressione generica (CONCATENA, &-concat, riferimento cella)
    # -----------------------------------------------------------------------
    result = _eval_expr(formula, worksheet, current_row, workbook).strip()
    if result:
        return result, None
    return None, None