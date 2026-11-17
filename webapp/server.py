"""
webapp/server.py
----------------
Server Flask locale: pagina unica (static/index.html) + API JSON.
"""
from __future__ import annotations

import gzip
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
from . import explorer, qa, tools
from .workbook import SHEETS, WorkbookStore

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "static"
STORE = WorkbookStore()
_prereq_cache = {"t": 0.0, "res": None}


def _is_local() -> bool:
    return request.remote_addr in ("127.0.0.1", "::1", "localhost")


def _prereq(force: bool = False) -> dict:
    if force or _prereq_cache["res"] is None or time.time() - _prereq_cache["t"] > 15:
        _prereq_cache.update(t=time.time(), res=tools.prerequisites())
    return _prereq_cache["res"]


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
    app.config["JSON_AS_ASCII"] = False
    app.json.ensure_ascii = False  # type: ignore[attr-defined]
    STORE.start()
    D.FILES.build_async()
    if getattr(cfg, "WEB_PDF_INDEX_AT_START", True):
        # indicizzazione incrementale in background: la ricerca e' subito veloce
        threading.Timer(3.0, lambda: D.text_index().update_async()).start()
    tools.RUNNER.on_finish = lambda job: STORE.force_reload()

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
        job = tools.RUNNER.job
        return jsonify({
            "ready": snap is not None, "loading": STORE.loading, "error": STORE.error,
            "key": snap.key if snap else "", "meta": snap.meta if snap else None,
            "sheets": SHEETS, "ai": qa.ai_status(), "local": _is_local(),
            "docs": {"files": sum(len(v) for v in D.FILES.by_name.values()),
                     "building": D.FILES.building,
                     "roots": [str(r) for r in D.doc_roots()]},
            "job": job.info() if job else None,
        })

    @app.get("/api/sheet/<path:name>")
    def sheet(name):
        snap = STORE.get(wait=60)
        if snap is None:
            return jsonify({"error": STORE.error or "File non ancora caricato"}), 503
        data = snap.sheet_gz.get(name)
        if data is None:
            abort(404)
        etag = f'"{snap.key}-{abs(hash(name)) % 10**8}"'
        if request.headers.get("If-None-Match") == etag:
            return Response(status=304)
        if "gzip" in request.headers.get("Accept-Encoding", ""):
            resp = Response(data, mimetype="application/json")
            resp.headers["Content-Encoding"] = "gzip"
        else:
            resp = Response(gzip.decompress(data), mimetype="application/json")
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "no-cache"
        return resp

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

    @app.get("/api/docindex")
    def docindex():
        return jsonify(D.text_index().stats())

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

    # ── Conoscenza dell'AI ──────────────────────────────────────────────
    @app.get("/api/knowledge")
    def knowledge_list():
        d = knowledge.load()
        return jsonify({"terms": knowledge.all_terms(), "categories": knowledge.CATEGORIES,
                        "sources": d.get("sources", {}), "ignored": len(d.get("ignored", [])),
                        "file": str(knowledge.path()), "ai": qa.ai_status()["ok"],
                        "enabled": bool(getattr(cfg, "KNOWLEDGE_USE_IN_ANALYSIS", True))})

    @app.post("/api/knowledge/term")
    def knowledge_save():
        b = request.get_json(silent=True) or {}
        try:
            rec = knowledge.upsert(str(b.get("term", "")), str(b.get("meaning", "")),
                                   str(b.get("category", "")), str(b.get("notes", "")),
                                   str(b.get("source", "")), [str(x) for x in b.get("aliases", []) or []])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        qa.clear_cache()
        return jsonify(rec)

    @app.delete("/api/knowledge/term")
    def knowledge_delete():
        ok = knowledge.delete(request.args.get("term", ""))
        qa.clear_cache()
        return jsonify({"ok": ok})

    @app.post("/api/knowledge/ignore")
    def knowledge_ignore():
        knowledge.ignore(str((request.get_json(silent=True) or {}).get("term", "")))
        return jsonify({"ok": True})

    @app.get("/api/knowledge/docs")
    def knowledge_docs():
        D.FILES.wait(10)
        snap = STORE.get()
        q = request.args.get("q", "").lower().strip()
        sources = knowledge.load().get("sources", {})
        items = []
        for name, paths in sorted(D.FILES.by_name.items()):
            if not name.endswith(".pdf") or (q and q not in name):
                continue
            p = paths[0]
            items.append({"fid": D.FILES.register(p), "file": Path(p).name, "folder": str(Path(p).parent),
                          "learned": sources.get(Path(p).name)})
            if len(items) >= 300:
                break
        funcs = sorted(snap.model["functions"]) if snap else []
        return jsonify({"items": items, "functions": funcs, "configs": snap.model["configs"] if snap else []})

    @app.post("/api/knowledge/learn")
    def knowledge_learn():
        b = request.get_json(silent=True) or {}
        first, last = int(b.get("first") or 0), int(b.get("last") or 0)
        path, source = None, ""
        if b.get("fid"):
            path = D.FILES.path(str(b["fid"]))
        elif b.get("func"):
            snap = STORE.get(wait=30)
            f = snap.model["functions"].get(str(b["func"])) if snap else None
            if not f:
                return jsonify({"error": "Funzione non trovata"}), 404
            c = str(b.get("cfg") or qa.base_config(snap.model["configs"]))
            ref = qa.doc_ref(snap.model, f, c)
            if not ref or not ref["local"]:
                return jsonify({"error": f"Il documento della funzione per {c} non è presente sul computer"}), 404
            path = D.FILES.path(ref["fid"])
            first, last = first or ref["first"] or 1, last or ref["last"] or ref["first"] or 0
            source = f"{ref['file']} ({b['func']}, {c})"
        if not path or not os.path.isfile(path):
            return jsonify({"error": "Documento non trovato"}), 404
        res = knowledge.learn_from_pdf(path, first, last, source)
        knowledge.mark_source(Path(path).name, len(res["items"]))
        res["fid"] = D.FILES.register(path)
        return jsonify(res)

    @app.post("/api/knowledge/suggest")
    def knowledge_suggest():
        b = request.get_json(silent=True) or {}
        if not qa.ai_status()["ok"]:
            return jsonify({"error": "AI locale non disponibile: " + qa.ai_status()["msg"]}), 503
        try:
            return jsonify(knowledge.suggest(str(b.get("term", "")), str(b.get("context", "")),
                                             str(b.get("proposal", ""))))
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503

    # ── Strumenti (solo da questo PC) ───────────────────────────────────
    def _local_only():
        if not _is_local():
            abort(403, "La sezione Strumenti è disponibile solo sul PC che esegue il server.")

    @app.get("/api/tools/prereq")
    def prereq():
        _local_only()
        return jsonify(_prereq(force=request.args.get("force") == "1"))

    @app.get("/api/tools/config")
    def config_list():
        _local_only()
        items = tools.config_items()
        unlocked = _prereq()["ok"]
        if not unlocked:
            items = [i for i in items if i["name"] in tools.SETUP_VARS]
        return jsonify({"items": items, "unlocked": unlocked, "file": str(tools.CONFIG_FILE),
                        "overrides_file": str(tools.OVERRIDES_FILE)})

    @app.post("/api/tools/config")
    def config_set():
        _local_only()
        body = request.get_json(silent=True) or {}
        if str(body.get("name", "")) not in tools.SETUP_VARS and not _prereq()["ok"]:
            return jsonify({"error": "Completare prima la guida di installazione."}), 412
        try:
            res = tools.set_override(str(body.get("name", "")), body.get("value"))
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        _prereq_cache["res"] = None
        if res["name"] in ("EXCEL_PATH",):
            STORE.force_reload()
        if res["name"] in ("ONEDRIVE_DOCS_ROOT", "WEB_EXTRA_DOC_DIRS", "CACHE_DIR"):
            D.FILES.build_async(force=True)
        return jsonify(res)

    @app.post("/api/tools/config/reset")
    def config_reset():
        _local_only()
        body = request.get_json(silent=True) or {}
        if body.get("name") not in tools.SETUP_VARS and not _prereq()["ok"]:
            return jsonify({"error": "Completare prima la guida di installazione."}), 412
        tools.reset_override(body.get("name") or None)
        _prereq_cache["res"] = None
        STORE.force_reload()
        return jsonify({"ok": True})

    @app.get("/api/tools/options")
    def options():
        _local_only()
        snap = STORE.get()
        return jsonify({"options": tools.OPTIONS, "configs": snap.model.get("configs", []) if snap else [],
                        "functions": sorted(snap.model["functions"]) if snap else [],
                        "job": tools.RUNNER.job.info() if tools.RUNNER.job else None,
                        "history": tools.RUNNER.history})

    @app.get("/api/tools/frs")
    def frs():
        _local_only()
        return jsonify({"items": tools.frs_choices()})

    @app.post("/api/tools/run")
    def run():
        _local_only()
        pr = _prereq(force=True)
        if not pr["ok"]:
            return jsonify({"error": "Prerequisiti mancanti: completare la guida di installazione.",
                            "prereq": pr}), 412
        try:
            job = tools.RUNNER.start(request.get_json(silent=True) or {})
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(job.info())

    @app.post("/api/tools/stop")
    def stop():
        _local_only()
        return jsonify({"ok": tools.RUNNER.stop()})

    @app.get("/api/tools/log")
    def job_log():
        _local_only()
        since = int(request.args.get("since", "0") or 0)
        lines, total = tools.RUNNER.lines_since(since)
        job = tools.RUNNER.job
        return jsonify({"lines": lines, "next": total, "job": job.info() if job else None})

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
