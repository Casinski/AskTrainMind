"""
verify_ai.py
------------
Verifica automatica dell'AI di «Chiedi» (voce 17 del terminale developer):

  1. CONOSCENZA  per un campione dei concetti a cui il developer ha risposto
                 (domande dell'AI, voce 7 / foglio questionAI voce 16) o che ha
                 confermato, chiede «cos'è X?» e controlla che la risposta
                 contenga la scheda 🧠 con il significato insegnato; controlla
                 anche che i concetti siano nella conoscenza esportata nella
                 pagina offline (User/AskTrainMind.html).
  2. DOCUMENTI   pone domande sul contenuto dei documenti e controlla che la
                 risposta «📄 Dai documenti» citi il requisito atteso
                 (DOC_CASES, ampliabile).
  3. PRESTAZIONI tempo di caricamento della conoscenza e di risposta.

Rapporto in RESULTS/verify_ai.txt (accanto al file Excel).

    python verify_ai.py [--sample 40]
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

PROGRAM_DIR = Path(__file__).resolve().parent

# (domanda, ID del requisito atteso fra i primi passaggi, configurazione del documento atteso o "")
DOC_CASES = [
    ("nel documento FRS Air Supply legato al Controllo del compressore principale nel VZI_New14 a che valore di "
     "pressione devono attivarsi i compressori?", "2F_06.03.Zefiro-Europe.CONCEPT.46", "VZI_New14"),
    ("a che pressione si fermano i compressori?", "2F_06.03.Zefiro-Europe.CONCEPT.93", ""),
    ("dopo quanto tempo si chiudono le porte?", "2F_14.Zefiro-Europe.CONCEPT.294", ""),
]


def run(sample: int = 40, progress=print) -> bool:
    import knowledge
    from webapp import qa
    from webapp import workbook as W

    lines: list[str] = []

    def out(msg: str = "") -> None:
        lines.append(msg)
        progress(msg)

    ok_all = True
    qa.RECORD_UNKNOWN = False       # la verifica non deve accodare domande all'addestramento
    snap = W.load_snapshot(W.excel_path())
    model = snap.model

    # 1. conoscenza ---------------------------------------------------------
    t0 = time.time()
    g = knowledge.load()
    t_load = time.time() - t0
    t0 = time.time()
    knowledge.load()
    t_reload = time.time() - t0
    taught = [t for t in g["terms"].values()
              if any(a.get("a") for a in (t.get("answers") or [])) or t.get("status") == "confermato"]
    out(f"CONOSCENZA: {len(g['terms'])} concetti, {len(taught)} con risposte/conferme del developer "
        f"(caricamento {t_load:.2f} s, ricarica {t_reload * 1000:.0f} ms)")
    exported = {t["term"]: t for t in knowledge.export_snapshot()["terms"]}
    random.seed(1)
    pick = random.sample(taught, min(sample, len(taught)))
    fail = []
    for t in pick:
        q = f"cos'è {t['term']}?"
        qa.clear_cache()
        r = qa.ask(q, model, snap.key)
        know = " ".join(b.get("md", "") for b in r["blocks"] if b.get("tone") == "know")
        meaning = (t.get("meaning") or "").strip()
        good = f"«{t['term']}»" in know and (not meaning or meaning[:40] in know)
        offline = t["term"] in exported and (exported[t["term"]].get("meaning") or "") == (t.get("meaning") or "")
        if not (good and offline):
            fail.append(f"   ✖ {t['term']}: " + ("risposta senza la scheda appresa" if not good else "non esportato"))
    out(f"  {len(pick) - len(fail)}/{len(pick)} concetti appresi mostrati da Chiedi (server e pagina offline)")
    lines.extend(fail)
    for f in fail[:10]:
        progress(f)
    ok_all &= not fail

    # 2. documenti ----------------------------------------------------------
    out("\nDOCUMENTI: costruzione dell'indice del testo dei PDF…")
    t0 = time.time()
    while qa.doc_searcher(model, snap.key) is None and time.time() - t0 < 900:
        if not qa._dx["building"]:
            break
        time.sleep(1)
    S = qa.doc_searcher(model, snap.key)
    if S is None:
        out("  ✖ indice dei documenti non disponibile (PDF non trovati?)")
        ok_all = False
    else:
        out(f"  indice pronto in {time.time() - t0:.0f} s: {len(S.ix['items'])} passaggi, {len(S.ix['docs'])} documenti")
        for q, rid, cf in DOC_CASES:
            qa.clear_cache()
            t1 = time.time()
            r = qa.ask(q, model, snap.key)
            ms = (time.time() - t1) * 1000
            md = next((b["md"] for b in r["blocks"] if b.get("type") == "text" and "Dai documenti" in b.get("md", "")), "")
            hits = S.search(q, r["configs"], r["functions"])
            ids = [h["id"] for h in hits[:3]]
            good = rid in md
            doc_ok = True
            if cf and hits and hits[0]["id"] == rid:
                ref = qa.doc_ref(model, model["functions"][hits[0]["fid"]], cf)
                doc_ok = bool(ref) and (ref.get("code") or "") in md
            ok_all &= good and doc_ok
            out(f"  {'✔' if good and doc_ok else '✖'} {q[:90]}{'…' if len(q) > 90 else ''}\n"
                f"      atteso {rid}{' (documento ' + cf + ')' if cf else ''} · primi passaggi: {', '.join(i or '(paragrafo)' for i in ids)} · {ms:.0f} ms")
            if good:
                out("      " + md.split("\n\n")[1][:300])

    out("\nESITO: " + ("✔ tutto verificato" if ok_all else "✖ alcuni controlli non superati (vedi sopra)"))
    rep = Path(W.excel_path()).parent / "RESULTS" / "verify_ai.txt"
    try:
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text(time.strftime("%d/%m/%Y %H:%M") + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
        progress(f"Rapporto: {rep}")
    except OSError:
        pass
    return ok_all


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Verifica la conoscenza e la lettura dei documenti dell'AI di Chiedi")
    ap.add_argument("--sample", type=int, default=40, help="numero di concetti appresi da provare")
    a = ap.parse_args()
    return 0 if run(a.sample) else 1


if __name__ == "__main__":
    sys.exit(main())
