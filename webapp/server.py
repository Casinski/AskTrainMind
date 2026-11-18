"""
webapp/server.py
----------------
Server Flask locale: pagina unica (static/index.html) + API JSON.
Usato dal developer per l'anteprima "live" (menu developer, opzione web).
L'utente finale usa invece la pagina offline User/AskTrainMind.html,
generata da export_user.py, che non richiede Python.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import threading
import time
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file, stream_with_context

import config as cfg

import knowledge

from . import documents as D
from . import explorer, qa
from .workbook import WorkbookStore

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "static"
STORE = WorkbookStore()


def _build_id() -> str:
    """Impronta dell'interfaccia e del server: distingue versioni diverse sulla stessa porta."""
    h = hashlib.sha1()
    for f in sorted([*STATIC.glob("*"), Path(__file__)]):
        if f.is_file():
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


BUILD = _build_id()


def _is_local() -> bool:
    return request.remote_addr in ("127.0.0.1", "::1", "localhost")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
    app.config["JSON_AS_ASCII"] = False
    app.json.ensure_ascii = False  # type: ignore[attr-defined]
    STORE.start()
    D.FILES.build_async()
    if getattr(cfg, "WEB_PDF_INDEX_AT_START", True):
        # indicizzazione incrementale in background: la ricerca e' subito veloce
        threading.Timer(3.0, lambda: D.text_index().update_async()).start()

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        if request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.get("/")
    def index():
        return send_file(STATIC / "index.html")

    # ── Dati ────────────────────────────────────────────────────────────
    @app.get("/api/meta")
    def meta():
        snap = STORE.get()
        return jsonify({
            "app": "AskTrainMind", "build": BUILD, "mode": "server",
            "ready": snap is not None, "loading": STORE.loading, "error": STORE.error,
            "key": snap.key if snap else "", "meta": snap.meta if snap else None,
            "ai": qa.ai_status(), "local": _is_local(),
            "docs": {"files": sum(len(v) for v in D.FILES.by_name.values()),
                     "building": D.FILES.building,
                     "roots": [str(r) for r in D.doc_roots()]},
        })

    @app.post("/api/reload")
    def reload():
        STORE.force_reload()
        return jsonify({"ok": True})

    # ── Documenti ───────────────────────────────────────────────────────
    @app.get("/api/doc")
    def doc():
        snap = STORE.get()
        if snap is None:
            abort(503)
        doc_id, c = request.args.get("doc", ""), request.args.get("cfg", "")
        path = D.resolve_doc(snap.model, doc_id, c)
        return jsonify({"fid": D.FILES.register(path) if path else "",
                        "file": Path(path).name if path else "",
                        "code": D.doc_code(snap.model, doc_id, c)})

    @app.get("/api/file/<fid>")
    def file(fid):
        p = D.FILES.path(fid)
        if not p or not os.path.isfile(p):
            abort(404)
        mt = mimetypes.guess_type(p)[0] or "application/octet-stream"
        return send_file(p, mimetype=mt, as_attachment=not p.lower().endswith(".pdf"),
                         download_name=Path(p).name, conditional=True, max_age=3600)

    @app.get("/api/page.png")
    def page_png():
        p = D.FILES.path(request.args.get("fid", ""))
        if not p:
            abort(404)
        page = int(request.args.get("page", "1") or 1)
        bbox = request.args.get("bbox")
        clip = tuple(float(x) for x in bbox.split(",")) if bbox else None
        dpi = max(50, min(220, int(request.args.get("dpi", "110"))))
        data = D.render_png(p, page, clip, dpi)
        if data is None:
            abort(404)
        resp = Response(data, mimetype="image/png")
        resp.headers["Cache-Control"] = "max-age=86400"
        return resp

    @app.post("/api/docindex")
    def docindex_update():
        D.FILES.build_async(force=True)
        D.text_index().update_async()
        return jsonify({"ok": True})

    # ── Chiedi ──────────────────────────────────────────────────────────
    @app.get("/api/suggestions")
    def suggestions():
        snap = STORE.get(wait=60)
        if snap is None:
            return jsonify({"items": [], "functions": []})
        fn = snap.model["functions"]
        return jsonify({"items": qa.suggestions(snap.model),
                        "functions": [[k, fn[k].get("desc", "")] for k in sorted(fn)],
                        "configs": snap.model["configs"], "colors": snap.meta.get("colors", {})})

    @app.get("/api/guide")
    def guide():
        p = STATIC.parent.parent / "GUIDA_WEB.md"
        text = p.read_text(encoding="utf-8") if p.is_file() else "# Guida\n\nFile GUIDA_WEB.md non trovato."
        return Response(text, mimetype="text/markdown; charset=utf-8")

    @app.post("/api/ask")
    def ask():
        snap = STORE.get(wait=60)
        if snap is None:
            return jsonify({"error": STORE.error or "File non ancora caricato"}), 503
        body = request.get_json(silent=True) or {}
        q = str(body.get("q", ""))[:2000]
        if not q.strip():
            return jsonify({"error": "Domanda vuota"}), 400
        t0 = time.time()
        res = qa.ask(q, snap.model, snap.key, bool(body.get("docs")))
        res["ms"] = int((time.time() - t0) * 1000)
        res["aiAvailable"] = qa.ai_status()["ok"]
        return jsonify(res)

    @app.get("/api/ask/ai/<aid>")
    def ask_ai(aid):
        return Response(stream_with_context(qa.ai_stream(aid)), mimetype="text/plain; charset=utf-8",
                        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    # ── Esplora (vista a blocchi) ───────────────────────────────────────
    @app.get("/api/explorer")
    def explorer_tree():
        snap = STORE.get(wait=60)
        if snap is None:
            return jsonify({"error": STORE.error or "File non ancora caricato"}), 503
        return jsonify(explorer.tree(snap.model, snap.key))

    @app.get("/api/explorer/func")
    def explorer_func():
        snap = STORE.get(wait=60)
        if snap is None:
            return jsonify({"error": STORE.error or "File non ancora caricato"}), 503
        cs = [c for c in request.args.get("cfg", "").split(",") if c]
        res = explorer.function_detail(snap.model, request.args.get("fid", ""), cs or None)
        if res is None:
            abort(404)
        return jsonify(res)

    # ── Ricerca rapida nei documenti del computer ───────────────────────
    @app.get("/api/search")
    def search_docs():
        q = request.args.get("q", "").strip()[:300]
        if not q:
            return jsonify({"groups": [], "stats": D.text_index().stats()})
        t0 = time.time()
        res = qa.quick_search(q, int(request.args.get("limit", "40") or 40))
        res["ms"] = int((time.time() - t0) * 1000)
        return jsonify(res)

    # ── Conoscenza dell'AI (sola lettura: si addestra dal menu developer) ──
    @app.get("/api/knowledge")
    def knowledge_list():
        return jsonify(knowledge.export_snapshot(include_proposed=True))

    return app


def run(host: str | None = None, port: int | None = None, open_browser: bool | None = None) -> None:
    host = host or getattr(cfg, "WEB_HOST", "127.0.0.1")
    port = int(port or getattr(cfg, "WEB_PORT", 8765))
    app = create_app()
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"
    print(f"\n  AskTrainMind Web in esecuzione: {url}\n  (Ctrl+C per chiudere)\n", flush=True)
    if open_browser if open_browser is not None else getattr(cfg, "WEB_OPEN_BROWSER", True):
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        from waitress import serve  # opzionale, piu' robusto
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
