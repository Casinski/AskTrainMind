"""
formula_eval.py — Excel formula resolver for AskTrainMind.

Evaluates HYPERLINK / CONCATENATE / &-operator / cell-reference formulas
found in openpyxl Cell objects and returns the real URL and friendly title.

Design principles:
- Never raises.  All error paths return (None, best_effort_text).
- Does NOT recurse into formula cells referenced by other cells (uses their
  cached/displayed value only).
- Resolves same-row implicit references ($D5 when the cell is on row 5).
"""
from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Internal helpers: column and cell-reference parsing
# ---------------------------------------------------------------------------

def _col_to_index(col: str) -> int:
    """Convert a column letter string ('A', 'BC', …) to a 1-based column index."""
    result = 0
    for c in col.upper():
        result = result * 26 + (ord(c) - ord("A") + 1)
    return result


_CELL_REF_RE = re.compile(r"^\$?([A-Za-z]+)\$?(\d*)$")


def _get_cell_value(ws, col_idx: int, row_num: int) -> str:
    """Return the plain string value of a worksheet cell (no formula recursion)."""
    try:
        cell = ws.cell(row=row_num, column=col_idx)
        val = cell.value
        if val is None:
            return ""
        if isinstance(val, str) and val.startswith("="):
            # Avoid recursing into formula cells; return empty
            return ""
        return str(val).strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# String literal parser
# ---------------------------------------------------------------------------

def _parse_string_literal(s: str) -> str:
    """
    Parse a double-quoted Excel string literal (with "" escaping).

    Input must start with a '"'.  Returns the unescaped Python string.
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
                break  # closing quote
        else:
            result.append(inner[i])
            i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# Tokenisers (respect string literals and nested parens)
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
    Split comma-separated function arguments in *inner*, respecting string
    literals and nested parentheses.
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
        elif c == "," and not in_str and depth == 0:
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
# Expression evaluator
# ---------------------------------------------------------------------------

def _eval_atom(expr: str, ws, current_row: int) -> str:
    """
    Evaluate a single atom: string literal, number, cell reference,
    CONCATENATE(), or other function call (evaluated as empty for unknown fns).
    """
    expr = expr.strip()
    if not expr:
        return ""

    # String literal
    if expr.startswith('"'):
        return _parse_string_literal(expr)

    # Number literal
    try:
        n = float(expr)
        return str(int(n)) if n == int(n) else str(n)
    except ValueError:
        pass

    # Function call: NAME(...)
    func_m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(", expr)
    if func_m:
        fname = func_m.group(1).upper()
        open_p = expr.index("(")
        close_p = _find_matching_paren(expr, open_p)
        inner = expr[open_p + 1 : close_p]
        args = _split_func_args(inner)
        if fname == "CONCATENATE":
            return "".join(_eval_expr(a, ws, current_row) for a in args)
        # Unknown function — return empty
        return ""

    # Cell reference: optional $ + letters + optional $ + optional digits
    cell_m = _CELL_REF_RE.match(expr)
    if cell_m:
        col_idx = _col_to_index(cell_m.group(1))
        row_str = cell_m.group(2)
        row_num = int(row_str) if row_str else current_row
        return _get_cell_value(ws, col_idx, row_num)

    # Parenthesised sub-expression
    if expr.startswith("(") and expr.endswith(")"):
        return _eval_expr(expr[1:-1], ws, current_row)

    return expr


def _eval_expr(expr: str, ws, current_row: int) -> str:
    """Evaluate *expr* including '&'-concatenation."""
    parts = _split_on_amp(expr)
    return "".join(_eval_atom(p, ws, current_row) for p in parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_hyperlink(
    cell, worksheet
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve *cell*'s formula/value to ``(url, friendly_title)``.

    Resolution order:
    1. Real ``cell.hyperlink.target`` (preferred as URL).
    2. ``=HYPERLINK(link_location, [friendly_name])`` — both args evaluated.
    3. ``=CONCATENATE(...)`` / ``&``-concatenation — evaluated; result stored
       as the URL candidate (caller should verify with ``is_openable_url``).
    4. Plain cell value (no formula) — returned as ``(None, text)``.
    5. Any parse error → ``(None, best_effort_text)`` or ``(None, None)``.

    Never raises.
    """
    try:
        return _resolve_impl(cell, worksheet)
    except Exception:
        try:
            text = str(cell.value or "").strip()
            return None, text or None
        except Exception:
            return None, None


def _resolve_impl(
    cell, worksheet
) -> tuple[Optional[str], Optional[str]]:
    current_row = cell.row

    # -----------------------------------------------------------------------
    # 1. Real hyperlink on the cell object
    # -----------------------------------------------------------------------
    if cell.hyperlink and getattr(cell.hyperlink, "target", None):
        url = str(cell.hyperlink.target).strip()
        display = str(getattr(cell.hyperlink, "display", "") or "").strip() or None
        if not display:
            # Try plain cell value as title
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
    # openpyxl sometimes stores the formula in _value even when data_only=False
    elif hasattr(cell, "_value") and isinstance(getattr(cell, "_value", None), str):
        _v = cell._value
        if _v and _v.startswith("="):
            formula = _v[1:]

    if formula is None:
        # Plain value
        text = str(raw_value).strip() if raw_value is not None else ""
        return (None, text) if text else (None, None)

    formula = formula.strip()

    # -----------------------------------------------------------------------
    # 3. HYPERLINK(link_location [, friendly_name])
    # -----------------------------------------------------------------------
    hyperlink_m = re.match(r"HYPERLINK\s*\(", formula, re.IGNORECASE)
    if hyperlink_m:
        open_p = formula.index("(")
        close_p = _find_matching_paren(formula, open_p)
        inner = formula[open_p + 1 : close_p]
        args = _split_func_args(inner)
        if not args:
            return None, None
        url = _eval_expr(args[0], worksheet, current_row).strip()
        title: Optional[str] = None
        if len(args) > 1:
            t = _eval_expr(args[1], worksheet, current_row).strip()
            title = t if t else None
        # Friendly display from cell hyperlink object, if present and no title
        if not title and cell.hyperlink and getattr(cell.hyperlink, "display", None):
            title = str(cell.hyperlink.display).strip() or None
        # Friendly display from cell displayed text
        if not title and isinstance(raw_value, str) and not raw_value.startswith("="):
            title = raw_value.strip() or None
        return url or None, title

    # -----------------------------------------------------------------------
    # 4. General expression (CONCATENATE, &-concat, plain cell ref)
    # -----------------------------------------------------------------------
    result = _eval_expr(formula, worksheet, current_row).strip()
    if result:
        return result, None
    # Nothing resolved
    return None, None
