"""
asktrainmind_web.py
-------------------
Anteprima "live" dell'interfaccia web per il DEVELOPER (Esplora, Chiedi,
Guida letti direttamente dal file Excel, con ricerca nei PDF e AI locale).

L'utente finale NON deve usare questo comando: apre con doppio click
User/AskTrainMind.html (pagina offline generata da export_user.py).

    python asktrainmind_web.py                # http://127.0.0.1:8765/
    python asktrainmind_web.py --port 9000 --no-browser

Se la porta e' occupata da una versione DIVERSA di AskTrainMind (o da un
altro programma) viene usata automaticamente la prima porta libera.
"""
from __future__ import annotations

import argparse
import logging
import sys


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Interfaccia web di AskTrainMind")
    ap.add_argument("--host", default=None, help="Indirizzo di ascolto (default WEB_HOST di config.py)")
    ap.add_argument("--port", type=int, default=None, help="Porta (default WEB_PORT di config.py)")
    ap.add_argument("--no-browser", action="store_true", help="Non aprire il browser all'avvio")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    try:
        from webapp.server import run
    except ImportError as exc:
        print(f"\n  Pacchetto mancante: {exc.name}\n  Installare le dipendenze con:\n"
              f'    "{sys.executable}" -m pip install -r requirements.txt\n')
        return 1
    import config as cfg
    host = args.host or getattr(cfg, "WEB_HOST", "127.0.0.1")
    port = args.port or int(getattr(cfg, "WEB_PORT", 8765))
    from webapp.server import BUILD
    first = port
    while _port_busy(host, port):
        url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}/"
        build = _running_build(url)
        if build == BUILD:
            print(f"\n  AskTrainMind web (stessa versione) è già in esecuzione: {url}\n")
            if not args.no_browser:
                import webbrowser
                webbrowser.open(url)
            return 0
        what = "una versione diversa di AskTrainMind" if build is not None else "un altro programma"
        print(f"  Porta {port} occupata da {what}: provo la {port + 1}.")
        port += 1
        if port > first + 20:
            print(f"\n  Nessuna porta libera fra {first} e {port - 1}. Usare --port.\n")
            return 1
    run(host, port, False if args.no_browser else None)
    return 0


def _port_busy(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1" if host in ("0.0.0.0", "") else host, port)) == 0


def _running_build(url: str):
    """Build dell'istanza AskTrainMind in ascolto ("" se e' una versione vecchia), None se non lo e'."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(url + "api/meta", timeout=2) as r:
            meta = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    if meta.get("app") == "AskTrainMind":
        return str(meta.get("build", ""))
    return "" if "sheets" in meta else None


if __name__ == "__main__":
    sys.exit(main())
