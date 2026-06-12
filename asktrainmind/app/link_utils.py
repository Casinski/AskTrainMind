"""
link_utils.py — URL/path validation for AskTrainMind.

Provides is_openable_url() which guards against rendering dead <a href> links
when the workbook cell contains plain text instead of a real URL.
"""
from __future__ import annotations

import re


def is_openable_url(value: str | None) -> bool:
    """
    Return True only for values that represent a genuinely openable URL or path.

    Recognised as openable:
    - http:// / https:// / file:// / mailto: schemes
    - www. prefix (browsers will resolve)
    - UNC network paths (\\\\server\\share)
    - Windows absolute paths (C:\\ or C:/)

    Everything else (plain text, empty strings, Excel formula remnants starting
    with '=', partial filenames, …) returns False.
    """
    if not value:
        return False
    v = value.strip()
    if not v:
        return False
    # Standard URL schemes
    if re.match(r"^(https?|file|mailto)://", v, re.IGNORECASE):
        return True
    # www. prefix
    if v.lower().startswith("www."):
        return True
    # UNC network paths
    if v.startswith("\\\\"):
        return True
    # Windows absolute paths: C:\ or C:/
    if re.match(r"^[A-Za-z]:[/\\]", v):
        return True
    return False
