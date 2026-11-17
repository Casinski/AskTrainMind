"""
asktrainmind_web.py
-------------------
Avvia l'interfaccia web di AskTrainMind (fogli Excel, domande, strumenti).

    python asktrainmind_web.py                # http://127.0.0.1:8765/
    python asktrainmind_web.py --port 9000 --no-browser
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
    if _port_busy(host, port):
        url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}/"
        if _is_asktrainmind(url):
            print(f"\n  AskTrainMind web è già in esecuzione: {url}\n")
            if not args.no_browser:
                import webbrowser
                webbrowser.open(url)
            return 0
        print(f"\n  La porta {port} è già usata da un altro programma.\n"
              f"  Avviare con un'altra porta, ad esempio:  python asktrainmind_web.py --port {port + 1}\n")
        return 1
    run(args.host, args.port, False if args.no_browser else None)
    return 0


def _port_busy(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1" if host in ("0.0.0.0", "") else host, port)) == 0


def _is_asktrainmind(url: str) -> bool:
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(url + "api/meta", timeout=2) as r:
            return "sheets" in json.loads(r.read().decode("utf-8"))
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
