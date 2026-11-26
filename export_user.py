"""
export_user.py
--------------
Aggiorna la cartella User/ per l'UTENTE FINALE (nessuna installazione):

  User/AskTrainMind.html   pagina web completa e OFFLINE (doppio click):
                           Esplora, Chiedi e Guida con tutti i dati del
                           DB Flotte e la conoscenza dell'AI incorporati;
                           i PDF si aprono dai link SharePoint del file Excel
                           (config.USER_PDF_SOURCE = "local": cartella docs/)
  User/<DB Flotte>.xlsx    copia del file Excel all'ultimo aggiornamento
  User/LEGGIMI.txt         istruzioni per l'utente (la guida completa è README.md)

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
import stat
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import config as cfg

PROGRAM_DIR = Path(__file__).resolve().parent
STATIC = PROGRAM_DIR / "webapp" / "static"
log = logging.getLogger("export_user")


def guide_markdown() -> str:
    """Guida della pagina web (pulsante ❔ Guida): Parte 2 di README.md, fra i marcatori GUIDA."""
    try:
        text = (PROGRAM_DIR / "README.md").read_text(encoding="utf-8")
        m = re.search(r"<!-- GUIDA:INIZIO -->\s*(.*?)\s*<!-- GUIDA:FINE -->", text, re.S)
    except OSError:
        m = None
    if not m:
        return "# Guida\n\nGuida non trovata: vedi README.md."
    out, fence = [], False
    for line in m.group(1).splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and re.match(r"#{3,6} ", line):
            line = line[2:]             # nel README la guida è annidata di due livelli
        out.append(line)
    return "\n".join(out)


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


def export(progress=print, out_dir: Path | None = None, page_name: str = "AskTrainMind.html",
           readonly_excel: bool = True) -> Path:
    """
    Pagina web offline + copia del file Excel. Predefinito: cartella User
    (voce 13). OPZIONE 0 TOTAL usa out_dir = dist/<data> e page_name =
    DBFlotte1000.html, con una copia del file Excel modificabile.
    """
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

    out = Path(out_dir) if out_dir else user_dir()
    out.mkdir(parents=True, exist_ok=True)
    # PDF dai link SharePoint del file Excel (predefinito): all'utente bastano la
    # pagina e il file Excel, senza la cartella docs. "local" = link relativi a docs/.
    remote = str(getattr(cfg, "USER_PDF_SOURCE", "sharepoint")).strip().lower() != "local"
    progress("  Preparazione di Esplora (funzioni, requisiti, documenti)…")
    tree = explorer.tree(model, snap.key)
    details, files, copied = {}, {}, {}
    for fid in sorted(model["functions"]):
        d = explorer.function_detail(model, fid, None, ai=True)
        if not d:
            continue
        d.pop("rnm", None)
        d.pop("index", None)
        for k in d["cards"]:
            k.pop("index", None)
            for r in [k.get("ref"), *(k.get("links") or [])]:
                if not (r and r.get("fid")):
                    continue
                p = D.FILES.path(r["fid"])
                if remote:
                    u = (r.get("url") or "").split("#", 1)[0]
                    if u:
                        files.setdefault(r["fid"], u)
                elif p and os.path.isfile(p):
                    if r["fid"] not in files:
                        files[r["fid"]] = _href(Path(p), out, copied)
                else:
                    r["fid"] = ""
        details[fid] = d
    for f in tree["funcs"].values():
        f.pop("rnm", None)
    try:
        import req_ai_comparator as reqai
        reqai.save_concepts()
    except Exception:
        log.exception("cache differenze concettuali")

    progress("  Indice del testo dei documenti (Chiedi legge i PDF)…")
    import docsearch

    def file_of(r):
        p = D.FILES.path(r["fid"]) if r.get("fid") else None
        if not p or not os.path.isfile(p):
            return "", ""
        if r["fid"] not in files and not remote:
            files[r["fid"]] = _href(Path(p), out, copied)
        return p, r["fid"]

    try:
        dx = docsearch.build_index(model, details, file_of, progress)
    except Exception as e:       # l'indice è un di più: la pagina funziona anche senza
        log.exception("indice documenti")
        progress(f"  ⚠️ indice dei documenti non creato: {e}")
        dx = None

    if remote:
        # i riquadri dei documenti usano il link SharePoint (ref.url) del file Excel;
        # "files" resta solo per aprire i passaggi trovati da Chiedi (stesso link)
        for d in details.values():
            for k in d["cards"]:
                for r in [k.get("ref"), *(k.get("links") or [])]:
                    if r:
                        r["fid"] = ""
                        r["local"] = False
    # Altri documenti del foglio CONFIG (FPD, FS, WT, EPL, GEN, ICD)
    for items in (tree.get("confdocs") or {}).values():
        for x in items:
            p = D.FILES.path(x["fid"]) if x.get("fid") else None
            if remote or not (p and os.path.isfile(p)):
                x["fid"], x["local"] = "", False
            elif x["fid"] not in files:
                files[x["fid"]] = _href(Path(p), out, copied)

    progress("  Conoscenza dell'AI…")
    kn = knowledge.export_snapshot()
    for t in kn["terms"]:
        try:
            t["funcs"] = qa.related_functions(model, t, 12)
        except Exception:
            t["funcs"] = []
    vocab = sorted(qa.domain_vocab(model))

    fn = model["functions"]
    meta = dict(snap.meta)
    meta.pop("sheets", None)
    meta.pop("missing", None)
    meta["file"] = xp.name
    data = {
        "meta": {"app": "AskTrainMind", "mode": "static", "key": snap.key, "meta": meta,
                 "pdf": "sharepoint" if remote else "local",
                 "exported": datetime.now().strftime("%d/%m/%Y %H:%M"), "ready": True},
        "tree": tree,
        "details": details,
        "files": files,
        "suggestions": {"items": qa.suggestions(model), "functions": [[k, fn[k].get("desc", "")] for k in sorted(fn)],
                        "configs": model["configs"], "colors": meta.get("colors", {})},
        "guide": guide_markdown(),
        "knowledge": kn,
        "vocab": vocab,
        "dx": dx,
    }
    html = _inline((STATIC / "index.html").read_text(encoding="utf-8"), data)
    page = out / page_name
    tmp = page.with_suffix(".tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(tmp, page)

    # copia del file Excel (solo se cambiato)
    dst = out / xp.name
    if not dst.is_file() or dst.stat().st_mtime < xp.stat().st_mtime or dst.stat().st_size != xp.stat().st_size:
        try:
            if dst.is_file():
                os.chmod(dst, stat.S_IREAD | stat.S_IWRITE)
            shutil.copy2(xp, dst)
            if readonly_excel:
                os.chmod(dst, stat.S_IREAD)     # l'utente consulta soltanto: Excel lo apre in sola lettura
        except PermissionError:
            progress(f"  ⚠️ {dst.name} è aperto in Excel: copia non aggiornata (chiudere il file e rilanciare).")
    for old in out.glob("*.xlsx"):
        if old.name != xp.name and not old.name.startswith("~$"):
            os.chmod(old, stat.S_IREAD | stat.S_IWRITE)
            old.unlink(missing_ok=True)
    (out / "NEWUSER.md").unlink(missing_ok=True)      # sostituita da README.md (guida unica)
    (out / "LEGGIMI.txt").write_text(README.format(page=page.name, xlsx=xp.name, date=data["meta"]["exported"],
                                                   n=len(details), k=len(kn["terms"])), encoding="utf-8")
    missing = sum(1 for d in details.values() for k in d["cards"]
                  if k.get("ref") and not (k["ref"].get("url") if remote else k["ref"].get("fid")))
    progress(f"  ✔ {page} aggiornata in {time.time() - t0:.0f} s: {len(details)} funzioni, {len(files)} PDF collegati"
             f"{' (link SharePoint del file Excel)' if remote else ''}"
             f"{f' ({len(copied)} copiati in User/docs)' if copied else ''}, {len(kn['terms'])} concetti dell'AI"
             f"{f', {missing} riferimenti senza ' + ('link SharePoint' if remote else 'PDF locale') if missing else ''}"
             f"; {page.stat().st_size / 1e6:.1f} MB")
    return page


README = """AskTrainMind - DB Flotte ETR1000
================================

Dati aggiornati al: {date}

COME SI APRE (nessuna installazione richiesta)
  Servono solo due file: {page} e {xlsx}
  (la cartella "docs" NON serve).
  1. Scarica {page} sul PC (da SharePoint/OneDrive/Teams: "Scarica").
  2. Doppio click su {page}: si apre nel browser (Edge, Chrome,
     Firefox) con indirizzo file:///...
  I PDF si aprono da SharePoint con gli stessi link del file Excel (foglio
  Funzioni): serve l'accesso al sito SharePoint del DB Flotte.

  Nell'anteprima web di SharePoint, OneDrive, Teams o Outlook la pagina si
  vede ma alcune funzioni del browser sono limitate: per l'uso normale
  scaricala e aprila con doppio click.

COSA PUOI FARE
  * Esplora: configurazioni -> FRS -> funzioni -> dettaglio con Funzioni AI,
    documenti delle configurazioni scelte, Requisiti con Description ed
    esito MATCHED / NOT MATCHED fra le configurazioni scelte; per i testi
    diversi, la spiegazione delle differenze di concetto rispetto al
    riferimento.
  * Chiedi: domande in italiano. L'AI capisce la domanda e risponde in due
    sezioni: "Risposta AI" (come un ingegnere ferroviario che conosce le
    configurazioni del treno, es. "a che pressione si fermano i
    compressori?" -> 1000 kPa, requisito CONCEPT.93) e "Sezione documentale"
    (i requisiti e i paragrafi dei documenti, clic = PDF alla pagina).
  * Guida: spiegazione di ogni pulsante.
  * {xlsx}  -> il file Excel completo a cui si riferisce la pagina.

La pagina contiene {n} funzioni e {k} concetti tecnici appresi dall'AI.

Accesso in sola consultazione: non modificare questi file, vengono
rigenerati dal developer. Se l'AI non conosce un termine usa "Copia la
domanda" e inviala al developer. Guida completa: pulsante "Guida" nella
pagina. La pagina e il file Excel sono autonomi: non serve il programma
AskTrainMind, si possono copiare e inviare insieme a chiunque.
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
