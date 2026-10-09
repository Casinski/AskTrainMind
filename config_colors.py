"""
config_colors.py
----------------
Assegna un colore univoco a ogni configurazione di treno.

Le configurazioni note sono in cfg.CONFIG_COLOR_MAP.
Se l'utente aggiunge una NUOVA configurazione al file Excel, questa riceve
automaticamente un colore preso da CONFIG_COLOR_PALETTE, garantendo che
non collida con i colori già assegnati. L'assegnazione è stabile
(deterministica) tra esecuzioni diverse grazie all'ordinamento alfabetico.
"""
from __future__ import annotations
import hashlib
import logging

import config as cfg

log = logging.getLogger(__name__)

_resolved: dict[str, str] = {}


def register_configs(config_names: list[str]) -> dict[str, str]:
    """
    Da chiamare UNA VOLTA all'avvio con l'elenco completo delle
    configurazioni lette dalla riga 1 del foglio.
    Restituisce la mappa {config_name: "RRGGBB"}.
    """
    global _resolved
    _resolved = {}
    used: set[str] = set()

    # 1. Configurazioni note → colore fisso
    for name in config_names:
        fixed = cfg.CONFIG_COLOR_MAP.get(name)
        if fixed:
            _resolved[name] = fixed.upper()
            used.add(fixed.upper())

    # 2. Configurazioni nuove → palette, in ordine alfabetico (stabile)
    nuove = sorted(n for n in config_names if n not in _resolved)
    palette = [c.upper() for c in cfg.CONFIG_COLOR_PALETTE if c.upper() not in used]

    for i, name in enumerate(nuove):
        if i < len(palette):
            color = palette[i]
        else:
            # 3. Esaurita la palette → colore derivato dall'hash del nome
            color = _hash_color(name, used)
        _resolved[name] = color
        used.add(color)
        log.info(f"  [Colori] Nuova configurazione '{name}' → #{color}")

    log.info(f"  [Colori] Mappa configurazioni: {_resolved}")
    return _resolved


def color_for(config_name: str) -> str:
    """Colore esadecimale della configurazione. Nero se sconosciuta."""
    if config_name in _resolved:
        return _resolved[config_name]
    return _hash_color(config_name, set(_resolved.values()))


def _hash_color(name: str, used: set[str]) -> str:
    """Colore scuro deterministico derivato dal nome, evitando collisioni."""
    for salt in range(50):
        h = hashlib.md5(f"{name}#{salt}".encode()).hexdigest()
        r, g, b = (int(h[i:i + 2], 16) % 170 for i in (0, 2, 4))
        color = f"{r:02X}{g:02X}{b:02X}"
        if color not in used:
            return color
    return "000000"


def legend() -> dict[str, str]:
    """Mappa completa, utile per scrivere una legenda nel foglio."""
    return dict(_resolved)
