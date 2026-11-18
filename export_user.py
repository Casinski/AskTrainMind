"""
export_user.py
--------------
Aggiorna la cartella User/ per l'UTENTE FINALE (nessuna installazione):

  User/AskTrainMind.html   pagina web completa e OFFLINE (doppio click):
                           Esplora, Chiedi e Guida con tutti i dati del
                           DB Flotte e la conoscenza dell'AI incorporati;
                           i PDF si aprono dalla cartella docs/ (link relativi)
  User/<DB Flotte>.xlsx    copia del file Excel all'ultimo aggiornamento
  User/LEGGIMI.txt         istruzioni per l'utente

Viene eseguito dal menu developer (asktrainmind_dev.py) dopo ogni
operazione che modifica i dati, oppure a mano:

    python export_user.py
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import config as cfg

PROGRAM_DIR = Path(__file__).resolve().parent
STATIC = PROGRAM_DIR / "webapp" / "static"
log = logging.getLogger("export_user")


def user_dir() -> Path:
    return Path(getattr(cfg, "USER_DIR", PROGRAM_DIR / "User"))


def _href(pdf: Path, out: Path, copied: dict) -> str:
    """Collegamento relativo dalla cartella User al PDF (copiato in User/docs se esterno)."""
    pdf = pdf.resolve()
    inside = PROGRAM_DIR in pdf.parents
    if not inside and getattr(cfg, "USER_COPY_EXTERNAL_PDFS", True):
        dst = out / "docs" / pdf.name
        if pdf not in copied:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.is_file() or dst.stat().st_size != pdf.stat().st_size:
                shutil.copy2(pdf, dst)
            copied[pdf] = dst
        pdf = copied[pdf]
    try:
        rel = os.path.relpath(pdf, out)
    except ValueError:          # unità diverse (Windows)
        return pdf.as_uri()
    return quote(rel.replace(os.sep, "/"))


def _inline(html: str, data: dict) -> str:
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="/static/app.css">', f"<style>\n{css}\n</style>")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    scripts = [f"<script>window.ATM_STATIC={blob};</script>"]
    for name in re.findall(r'<script src="/static/([\w.]+)"></script>', html):
        js = (STATIC / name).read_text(encoding="utf-8").replace("</script", "<\\/script")
        scripts.append(f"<script>/* {name} */\n{js}\n</script>")
    html = re.sub(r'(?:<script src="/static/[\w.]+"></script>\s*)+', lambda _m: "\n".join(scripts) + "\n", html, count=1)
    return html


def export(progress=print) -> Path:
    t0 = time.time()
    from webapp import documents as D
    from webapp import explorer, qa
    from webapp import workbook as W
    import knowledge

    xp = W.excel_path()
    if not xp:
        raise FileNotFoundError(f"File Excel non trovato: {cfg.EXCEL_PATH}")
    progress(f"  Lettura di {xp.name}…")
    snap = W.load_snapshot(xp)
    model = snap.model
    D.FILES.build_async()
    D.FILES.wait(120)

    out = user_dir()
    out.mkdir(parents=True, exist_ok=True)
    progress("  Preparazione di Esplora (funzioni, requisiti, documenti)…")
    tree = explorer.tree(model, snap.key)
    details, files, copied = {}, {}, {}
    for fid in sorted(model["functions"]):
        d = explorer.function_detail(model, fid, None)
        if not d:
            continue
        d.pop("rnm", None)
        d.pop("index", None)
        for k in d["cards"]:
            k.pop("index", None)
            r = k.get("ref")
            if r and r.get("fid"):
                p = D.FILES.path(r["fid"])
                if p and os.path.isfile(p):
                    if r["fid"] not in files:
                        files[r["fid"]] = _href(Path(p), out, copied)
                else:
                    r["fid"] = ""
        details[fid] = d
    for f in tree["funcs"].values():
        f.pop("rnm", None)

    progress("  Conoscenza dell'AI…")
    kn = knowledge.export_snapshot()
    for t in kn["terms"]:
        try:
            t["funcs"] = qa.related_functions(model, t, 12)
        except Exception:
            t["funcs"] = []
    vocab = sorted(qa.domain_vocab(model))

    guide = (PROGRAM_DIR / "GUIDA_WEB.md")
    fn = model["functions"]
    meta = dict(snap.meta)
    meta.pop("sheets", None)
    meta.pop("missing", None)
    meta["file"] = xp.name
    data = {
        "meta": {"app": "AskTrainMind", "mode": "static", "key": snap.key, "meta": meta,
                 "exported": datetime.now().strftime("%d/%m/%Y %H:%M"), "ready": True},
        "tree": tree,
        "details": details,
        "files": files,
        "suggestions": {"items": qa.suggestions(model), "functions": [[k, fn[k].get("desc", "")] for k in sorted(fn)],
                        "configs": model["configs"], "colors": meta.get("colors", {})},
        "guide": guide.read_text(encoding="utf-8") if guide.is_file() else "# Guida",
        "knowledge": kn,
        "vocab": vocab,
    }
    html = _inline((STATIC / "index.html").read_text(encoding="utf-8"), data)
    page = out / "AskTrainMind.html"
    tmp = page.with_suffix(".tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(tmp, page)

    # copia del file Excel (solo se cambiato)
    dst = out / xp.name
    if not dst.is_file() or dst.stat().st_mtime < xp.stat().st_mtime or dst.stat().st_size != xp.stat().st_size:
        try:
            shutil.copy2(xp, dst)
        except PermissionError:
            progress(f"  ⚠️ {dst.name} è aperto in Excel: copia non aggiornata (chiudere il file e rilanciare).")
    for old in out.glob("*.xlsx"):
        if old.name != xp.name and not old.name.startswith("~$"):
            old.unlink(missing_ok=True)
    (out / "LEGGIMI.txt").write_text(README.format(page=page.name, xlsx=xp.name, date=data["meta"]["exported"],
                                                   n=len(details), k=len(kn["terms"])), encoding="utf-8")
    missing = sum(1 for d in details.values() for k in d["cards"] if k.get("ref") and not k["ref"].get("fid"))
    progress(f"  ✔ {page} aggiornata in {time.time() - t0:.0f} s: {len(details)} funzioni, {len(files)} PDF collegati"
             f"{f' ({len(copied)} copiati in User/docs)' if copied else ''}, {len(kn['terms'])} concetti dell'AI"
             f"{f', {missing} riferimenti senza PDF locale' if missing else ''}; {page.stat().st_size / 1e6:.1f} MB")
    return page


README = """AskTrainMind - DB Flotte ETR1000
================================

Dati aggiornati al: {date}

COME SI USA (nessuna installazione richiesta)
  * {page}  -> doppio click: si apre nel browser (Edge, Chrome, Firefox).
      - Esplora: configurazioni -> FRS -> funzioni -> dettaglio con
        Funzioni AI, PDF affiancati delle configurazioni scelte, Requisiti
        (clic su un requisito = testi delle configurazioni a confronto).
      - Chiedi: domande in italiano su funzioni e concetti tecnici.
      - Guida: spiegazione di ogni pulsante.
  * {xlsx}  -> il file Excel completo, da aprire con Excel.

La pagina contiene {n} funzioni e {k} concetti tecnici appresi dall'AI.
I PDF si aprono dalla cartella "docs" che si trova accanto alla cartella
User: non spostare la cartella User fuori dalla cartella del programma.

Non modificare questi file: vengono rigenerati dal developer.
"""


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        export()
    except Exception as exc:
        print(f"\n  Errore nell'aggiornamento della cartella User: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
