"""
asktrainmind_dev.py
-------------------
TERMINALE DEVELOPER di AskTrainMind (doppio click su AVVIA_DEVELOPER.bat).

Da qui il developer:
  * lancia le analisi che aggiornano il file Excel DB Flotte (opzioni 1-5);
  * ADDESTRA l'AI sui documenti tecnici, risponde alle sue domande,
    insegna/corregge i concetti (vedi TRAINING_AI.md);
  * prova la sezione «Chiedi» con la conoscenza aggiornata;
  * modifica i parametri di config.py (CONFIG) e verifica i prerequisiti;
  * aggiorna la cartella User/ (pagina web offline + Excel) per gli utenti.

Uso non interattivo (script, pianificazioni):
    python asktrainmind_dev.py --run 13          # esegue una voce del menu ed esce
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

PROGRAM_DIR = Path(__file__).resolve().parent
os.chdir(PROGRAM_DIR)
sys.path.insert(0, str(PROGRAM_DIR))

import config as cfg  # noqa: E402

W = 100   # larghezza del testo


# ---------------------------------------------------------------------------
# Utilità di terminale
# ---------------------------------------------------------------------------

def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if os.name == "nt":
        os.system("")          # abilita i colori ANSI nella console di Windows


def ask(prompt: str, default: str = "") -> str:
    try:
        v = input(prompt)
    except EOFError:
        raise SystemExit(0)
    return v.strip() or default


def yes(prompt: str, default: bool = True) -> bool:
    v = ask(f"{prompt} [{'S/n' if default else 's/N'}]: ").lower()
    return default if not v else v in ("s", "si", "sì", "y", "yes")


def wrap(text: str, indent: str = "  ") -> str:
    out = []
    for line in str(text).splitlines() or [""]:
        out.append(textwrap.fill(line, W, initial_indent=indent, subsequent_indent=indent) if line.strip() else "")
    return "\n".join(out)


def header(title: str) -> None:
    print("\n" + "═" * W + f"\n  {title}\n" + "═" * W)


def pause() -> None:
    ask("\n  Premi INVIO per tornare al menu… ")


def python_cmd() -> list[str]:
    return [sys.executable, "-W", "ignore"]


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def _analysis_items():
    from webapp.tools import OPTIONS
    return [(o["mode"], o["title"], o["desc"] + f"\n  Fogli aggiornati: {o['sheets']}"
             + "\n\n  Parametri chiesti dopo la scelta:\n" + option_params_text(o["mode"])) for o in OPTIONS]


def menu_items() -> list[tuple[str, str, str, callable]]:
    items = [(m, t, d, (lambda m=m: run_option(m))) for m, t, d in _analysis_items()]
    items += [
        ("6", "Addestra l'AI: leggi i documenti tecnici (PDF/DOCX/TXT) e impara sigle e concetti",
         "Legge i documenti delle cartelle indicate (default KNOWLEDGE_TRAIN_DIRS = docs/), estrae definizioni e "
         "frasi utili e prepara le domande per te. Interrompibile con Ctrl+C: riprende dal punto raggiunto.", train),
        ("7", "Rispondi alle domande dell'AI (conferma, correggi o completa ciò che ha capito)",
         "L'AI chiede il significato delle sigle che non ha capito e approfondimenti (componenti, sensori, "
         "centraline, tarature, eventi TCMS, costruttore, treni…). Puoi fermarti quando vuoi con «q».", answer_questions),
        ("8", "Insegna o correggi un concetto (sigla, loop, sensore, centralina, configurazione…)",
         "Scrivi tu cosa deve sapere l'AI su un termine, anche se non è mai comparso nei documenti.", teach),
        ("9", "Consulta la conoscenza dell'AI (cerca, conferma le proposte, verifica i file)",
         "Riepilogo, ricerca dei concetti, conferma in blocco delle definizioni proposte, controllo dei file "
         "in knowledge/ dopo una modifica a mano.", browse_knowledge),
        ("10", "Prova la sezione «Chiedi» con la conoscenza aggiornata",
         "Fai una domanda come la farebbe un utente e vedi la risposta (incluse le schede dei concetti).", try_ask),
        ("11", "CONFIG: visualizza e modifica i parametri del programma (config.py)",
         "I valori modificati sono salvati in config_overrides.json e hanno priorità su config.py.", config_menu),
        ("12", "Verifica i prerequisiti (Python, pacchetti, Ollama, modello AI, Excel, documenti)",
         "Controlla che tutto il necessario per le analisi sia installato e raggiungibile.", prerequisites),
        ("13", "Aggiorna la cartella User (pagina web offline + Excel per gli utenti)",
         "Ricrea User/AskTrainMind.html con i dati e la conoscenza attuali e copia il file Excel.", export_user),
        ("14", "Apri l'anteprima web developer (server locale, con AI Ollama e ricerca nei PDF)",
         "Avvia asktrainmind_web.py: stessa interfaccia degli utenti + spiegazione AI e ricerca nel testo dei PDF.",
         web_preview),
    ]
    return items


def show_menu(items) -> None:
    header("AskTrainMind — TERMINALE DEVELOPER")
    try:
        import knowledge
        s = knowledge.summary()
        print(f"  🧠 AI: {s['terms']} concetti ({s['confirmed']} confermati, {s['proposed']} da confermare), "
              f"{s['pending']} domande in attesa · {s['sources_done']}/{s['sources']} documenti letti")
    except Exception as exc:
        print(f"  🧠 AI: conoscenza non leggibile ({exc}) — usa la voce 9 per verificare i file")
    page = Path(getattr(cfg, "USER_DIR", PROGRAM_DIR / "User")) / "AskTrainMind.html"
    if page.is_file():
        print(f"  👤 Cartella User aggiornata il {time.strftime('%d/%m/%Y %H:%M', time.localtime(page.stat().st_mtime))}")
    groups = [("ANALISI DEL DB FLOTTE (aggiornano il file Excel)", ("1", "2", "3", "4", "5")),
              ("INTELLIGENZA ARTIFICIALE (addestramento e conoscenza)", ("6", "7", "8", "9", "10")),
              ("CONFIGURAZIONE E PUBBLICAZIONE", ("11", "12", "13", "14"))]
    by = {k: t for k, t, _, _ in items}
    for title, keys in groups:
        print(f"\n  ── {title}")
        for k in keys:
            print(f"  {k:>3}) {by[k]}")
    print("\n    0) Esci       (scrivi «h N» per la descrizione della voce N)")


def main_menu() -> None:
    items = menu_items()
    actions = {k: (t, d, f) for k, t, d, f in items}
    while True:
        show_menu(items)
        c = ask("\n  Scelta: ").lower()
        if c in ("0", "q", "esci", "exit"):
            print("  Arrivederci.")
            return
        if c.startswith("h ") and c[2:].strip() in actions:
            t, d, _ = actions[c[2:].strip()]
            header(t)
            print(wrap(d))
            pause()
            continue
        if c not in actions:
            print("  Scelta non valida.")
            continue
        t, d, f = actions[c]
        header(t)
        print(wrap(d) + "\n")
        try:
            f()
        except KeyboardInterrupt:
            print("\n  Interrotto.")
        except Exception as exc:
            logging.getLogger("dev").exception(exc)
            print(f"\n  ⚠️ Errore: {exc}")
        pause()


# ---------------------------------------------------------------------------
# Analisi (opzioni 1-5) e pubblicazione
# ---------------------------------------------------------------------------

# Parametri chiesti dopo la scelta di ogni opzione (come nel menu di
# funzioni_ai_filter.py). I default proposti sono quelli di CONFIG (voce 11).
_DB = ("Aggiornare direttamente il file DB Flotte? (n = crea solo il file RESULTS "
       "in RESULTS/, il DB non viene modificato)", "UPDATE_DB_DEFAULT")
OPTION_PARAMS = {
    "1": [_DB,
          ("Riprendere dalla funzione in cui si è interrotta l'esecuzione precedente? "
           "(solo se c'è un'interruzione)", None),
          ("Numero massimo di celle «Funzioni AI» da compilare (0 = tutte)", None),
          ("Sovrascrivere le celle già compilate? A = automatico (solo se il documento è "
           "cambiato), S = rielabora tutte, N = solo celle vuote", None),
          ("FUNC ID da cui partire", "START_FROM_FUNC_ID"),
          ("FRS da compilare (numeri o nomi, Invio = tutti)", None),
          ("Aggiornare il foglio «Reqs not matched» al termine?", "REQS_NOT_MATCHED_AFTER_OPTION1")],
    "2": [_DB],
    "3": [_DB,
          ("Riprendere dalla funzione in cui si è interrotta l'esecuzione precedente? "
           "(solo se c'è un'interruzione; altrimenti parte da START_FROM_FUNC_ID)", "START_FROM_FUNC_ID")],
    "4": [_DB, ("DOC ID da confrontare (numeri o nomi separati da virgola)", None)],
    "5": [_DB, ("Configurazioni da confrontare, separate da virgola (Invio = tutte)", None)],
}


def option_params_text(mode: str) -> str:
    rows = []
    for i, (q, key) in enumerate(OPTION_PARAMS.get(mode, []), 1):
        d = f"   [CONFIG {key} = {getattr(cfg, key, '')!r}]" if key else ""
        rows.append(f"  {i}. {q}{d}")
    return "\n".join(rows)


def run_option(mode: str) -> None:
    print("  Parametri che ti verranno chiesti (Invio = valore proposto):")
    print(option_params_text(mode) + "\n")
    r = subprocess.call([*python_cmd(), "funzioni_ai_filter.py", "--mode", mode, "--ask"])
    print(f"\n  Opzione {mode} terminata (codice {r}).")
    auto_export()


def auto_export() -> None:
    if getattr(cfg, "USER_AUTO_EXPORT", True):
        print("\n  Aggiornamento automatico della cartella User…")
        export_user()
    else:
        print("\n  (USER_AUTO_EXPORT = False: usa la voce 13 per aggiornare la cartella User)")


def export_user() -> None:
    import export_user as E
    E.export(progress=print)


def web_preview() -> None:
    port = ask("  Porta [8765]: ", "8765")
    print("  Chiudi con Ctrl+C.\n")
    try:
        subprocess.call([*python_cmd(), "asktrainmind_web.py", "--port", port])
    except KeyboardInterrupt:
        pass


def prerequisites() -> None:
    from webapp import tools
    r = tools.prerequisites()
    for c in r["checks"]:
        print(f"  {'✔' if c['ok'] else '✖'} {c['label']}: {c['detail']}")
        if not c["ok"]:
            print(wrap("→ " + c["fix"], "      "))
    print(f"\n  Python: {r['python']}\n  Cartella del programma: {r['program_dir']}")


# ---------------------------------------------------------------------------
# AI: addestramento, domande, insegnamento
# ---------------------------------------------------------------------------

def _model():
    from webapp import workbook as Wb
    xp = Wb.excel_path()
    return Wb.load_snapshot(xp).model if xp else None


def train() -> None:
    import knowledge
    dirs = [str(p) for p in getattr(cfg, "KNOWLEDGE_TRAIN_DIRS", [PROGRAM_DIR / "docs"])]
    print("  Cartelle/documenti predefiniti (KNOWLEDGE_TRAIN_DIRS):")
    for d in dirs:
        print(f"    • {d}")
    extra = ask("\n  Altri percorsi da leggere (separati da ;) oppure INVIO per i predefiniti: ")
    paths = [p.strip().strip('"') for p in extra.split(";") if p.strip()] if extra else dirs
    if extra and yes("  Aggiungere anche i percorsi predefiniti?", False):
        paths += dirs
    print("\n  ⏳ Lettura in corso — Ctrl+C per fermare (si riprende dal punto raggiunto)…\n")
    t0 = time.time()
    st = knowledge.train(paths, progress=lambda m: print("  " + m))
    m = _model()
    if m:
        n = knowledge.seed_configs(m)
        if n:
            print(f"  + {n} schede create per le configurazioni del treno (dal DB Flotte)")
    print(f"\n  Addestramento {'INTERROTTO' if st['stopped'] else 'completato'} in {time.time() - t0:.0f} s: "
          f"{st['read']} documenti letti ({st['skipped']} già noti), {st['pages']} pagine, "
          f"{st['definitions']} definizioni trovate, {st['questions']} nuove domande, {st['passages']} frasi utili.")
    s = knowledge.summary()
    print(f"  Ora l'AI ha {s['terms']} concetti e {s['pending']} domande per te (voce 7).")
    if not st["stopped"]:
        auto_export()


def _show_question(x: dict, i: int, n: int) -> None:
    import knowledge
    print("\n" + "─" * W)
    t = knowledge.get(x["term"])
    kind = "SIGNIFICATO" if x["field"] == "meaning" else knowledge.field_label(x["field"]).upper()
    print(f"  [{i}/{n}] 🧠 {x['term']}  ·  {kind}" + (f"  ·  {t['meaning'][:80]}" if t and x['field'] != 'meaning' else ""))
    print(wrap("❓ " + x["question"]))
    if x.get("context"):
        print(wrap(f"📄 «{x['context'][:400]}»" + (f"  — {x['source']}, pag. {x['page']}" if x.get("source") else ""), "     "))
    if x.get("proposal"):
        print(wrap(f"💡 Proposta: {x['proposal']}", "     "))


QHELP = """  Rispondi scrivendo il testo. Comandi:
    INVIO = salta (la domanda torna in fondo)     s / ok = conferma la proposta
    x = non chiedere più questa domanda            xx = ignora del tutto questo termine
    ai = chiedi un suggerimento all'AI locale       q = basta domande per ora"""


def answer_questions() -> None:
    import knowledge
    pend = knowledge.pending()
    if not pend:
        print("  Nessuna domanda in attesa. Lancia l'addestramento (voce 6) o insegna un concetto (voce 8).")
        return
    flt = ask(f"  {len(pend)} domande in attesa. Filtra per termine (INVIO = tutte, nell'ordine di priorità): ")
    if flt:
        pend = [x for x in pend if flt.lower() in x["term"].lower()]
    print(QHELP)
    done = 0
    for i, x in enumerate(pend, 1):
        _show_question(x, i, len(pend))
        while True:
            r = ask("  ✍ Risposta: ")
            low = r.lower()
            if low == "q":
                print(f"\n  Fermato: {done} risposte salvate.")
                if done:
                    auto_export()
                return
            if not r:
                knowledge.skip(x["id"])
                break
            if low == "x":
                knowledge.drop(x["id"])
                break
            if low == "xx":
                knowledge.drop(x["id"], whole_term=True)
                print(f"  «{x['term']}» ignorato.")
                break
            if low == "ai":
                print("  …")
                try:
                    s = knowledge.suggest(x["term"], x.get("context", ""), x.get("proposal", ""))
                    print(wrap(f"🤖 {s.get('meaning')}  [categoria: {s.get('category', '')}]", "     "))
                    print("     (scrivi «s» per usare la proposta originale oppure riscrivi la risposta)")
                except Exception as exc:
                    print(f"  ⚠️ AI locale non disponibile: {exc}")
                continue
            if low in knowledge.YES and not x.get("proposal"):
                print("  Non c'è una proposta da confermare: scrivi la risposta.")
                continue
            cat = ""
            if x["field"] == "meaning" and low not in knowledge.YES:
                cat = _pick_category(knowledge.guess_category(x["term"], x.get("context", "") + " " + r))
            try:
                print("  ✔ " + knowledge.answer(x["id"], r, cat))
                done += 1
            except (KeyError, ValueError) as exc:
                print(f"  ⚠️ {exc}")
            break
    print(f"\n  Domande finite: {done} risposte salvate.")
    if done:
        auto_export()


def _pick_category(guess: str) -> str:
    import knowledge
    cats = list(knowledge.CATEGORIES)
    print("  Categoria: " + "  ".join(f"{i}={c}" for i, c in enumerate(cats, 1)))
    c = ask(f"  Numero categoria [INVIO = {guess}]: ")
    return cats[int(c) - 1] if c.isdigit() and 0 < int(c) <= len(cats) else guess


def _print_term(t: dict) -> None:
    import knowledge
    print(wrap(knowledge.term_markdown(t, with_passages=True).replace("**", "")))


def teach() -> None:
    import knowledge
    term = ask("  Termine (es. DNRA, loop, pantografo, VZI_Base): ")
    if not term:
        return
    t = knowledge.get(term)
    if t:
        print()
        _print_term(t)
    else:
        print("  Termine nuovo.")
    fields = [("meaning", "Significato (una frase)"), ("details", "Come funziona / dettagli"),
              ("category", "Categoria"), ("aliases", "Altri nomi / sinonimi (separati da ;)"),
              *[(f"relations.{k}", v) for k, v in knowledge.RELATIONS.items()],
              *[(f"facts.{k}", v) for k, v in knowledge.FACTS.items()], ("notes", "Note")]
    if not t:
        meaning = ask("  Significato: ")
        if not meaning:
            return
        cat = _pick_category(knowledge.guess_category(term, meaning))
        knowledge.upsert(term, meaning, cat, source="developer")
        knowledge.attach_passages(term)
        n = knowledge.deepen(term)
        print(f"  ✔ Imparato. {n} domande di approfondimento accodate (voce 7).")
    while True:
        print("\n  Campi: " + "  ".join(f"{i}={lab}" for i, (_, lab) in enumerate(fields, 1)))
        c = ask("  Numero del campo da scrivere (c = conferma la scheda, d = elimina, INVIO = fine): ").lower()
        if not c:
            break
        if c == "c":
            knowledge.confirm(term)
            print("  ✔ Confermato.")
            continue
        if c == "d":
            if yes(f"  Eliminare «{term}»?", False):
                knowledge.delete(term)
                print("  Eliminato.")
                break
            continue
        if not c.isdigit() or not 0 < int(c) <= len(fields):
            continue
        f, lab = fields[int(c) - 1]
        if f == "category":
            v = _pick_category((knowledge.get(term) or {}).get("category", "sigla"))
        else:
            v = ask(f"  {lab}: ")
        if v:
            knowledge.set_field(term, f, v, source="developer")
            print("  ✔ Salvato.")
    t = knowledge.get(term)
    if t:
        print()
        _print_term(t)
        auto_export()


def browse_knowledge() -> None:
    import knowledge
    errs = knowledge.validate()
    if errs:
        print("  ⚠️ Problemi nei file della conoscenza:")
        for e in errs:
            print(wrap("• " + e, "    "))
    s = knowledge.summary()
    print(f"  Cartella: {s['dir']}\n  {s['terms']} concetti ({s['confirmed']} confermati, {s['proposed']} proposti), "
          f"{s['pending']} domande in attesa, {s['sources_done']}/{s['sources']} documenti letti.")
    changed = False
    while True:
        c = ask("\n  Cerca un termine (testo), «p» = elenco proposte da confermare, «cats» = per categoria, INVIO = fine: ")
        if not c:
            break
        terms = knowledge.all_terms(True)
        if c.lower() == "cats":
            from collections import Counter
            for k, n in Counter(t.get("category", "") for t in terms).most_common():
                print(f"    {knowledge.CATEGORIES.get(k, k)}: {n}")
            continue
        if c.lower() == "p":
            prop = [t for t in terms if t.get("status") == "proposto"]
            for i, t in enumerate(prop, 1):
                print(f"  {i:>3}) {t['term']:<18} {t['meaning'][:75]}")
            sel = ask("  Numeri da confermare (es. 1,4,7-12; «tutti»; INVIO = nessuno): ")
            idx = range(1, len(prop) + 1) if sel.lower() == "tutti" else _ranges(sel)
            for i in idx:
                if 0 < i <= len(prop):
                    knowledge.confirm(prop[i - 1]["term"])
                    changed = True
            print(f"  ✔ {len(list(idx))} confermati." if sel else "")
            continue
        hits = [t for t in terms if c.lower() in (t["term"] + " " + " ".join(t.get("aliases", [])) + " "
                                                   + t.get("meaning", "")).lower()]
        for t in hits[:15]:
            print("\n" + "·" * 40)
            _print_term(t)
        if not hits:
            print("  Nessun concetto trovato. Usa la voce 8 per insegnarlo.")
    if changed:
        auto_export()


def _ranges(s: str) -> list[int]:
    out = []
    for p in s.replace(" ", "").split(","):
        if "-" in p:
            a, b = p.split("-", 1)
            if a.isdigit() and b.isdigit():
                out += range(int(a), int(b) + 1)
        elif p.isdigit():
            out.append(int(p))
    return out


def try_ask() -> None:
    from webapp import qa
    from webapp import workbook as Wb
    xp = Wb.excel_path()
    snap = Wb.load_snapshot(xp)
    while True:
        q = ask("\n  Domanda (INVIO = fine): ")
        if not q:
            return
        r = qa.ask(q, snap.model, snap.key)
        print(f"\n  [intento: {r.get('intent')} · funzioni: {', '.join(r.get('functions', [])) or '—'} · "
              f"configurazioni: {', '.join(r.get('configs', [])) or '—'}]")
        for b in r.get("blocks", []):
            _print_block(b)


def _print_block(b: dict) -> None:
    t = b.get("type")
    if t == "title":
        print("\n  ■ " + b.get("text", "") + (f" — {b['sub']}" if b.get("sub") else ""))
    elif t == "text":
        print(wrap(b.get("md", "").replace("**", "").replace("### ", "")))
    elif t in ("chips", "cards", "docs", "figures", "search", "stats"):
        if b.get("title"):
            print(f"\n  {b['title']}:")
        for it in b.get("items", [])[:12]:
            if isinstance(it, dict):
                lab = it.get("label") or it.get("fid") or it.get("doc") or it.get("title") or it.get("k") or ""
                desc = it.get("desc") or it.get("text") or it.get("v") or it.get("code") or ""
                print(wrap(f"• {lab}: {str(desc)[:160]}", "    "))
    elif t == "table":
        print(f"\n  {b.get('title', '')}")
        cols = b.get("columns", [])
        print("    " + " | ".join(map(str, cols)))
        for row in b.get("rows", [])[:20]:
            print("    " + " | ".join(str(x)[:40] for x in row))
    elif t == "cfgblocks":
        for it in b.get("items", []):
            print(wrap(f"▸ {it.get('config', '')}: {str(it.get('ai') or it.get('text') or '')[:300]}", "    "))


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

def config_menu() -> None:
    from webapp import tools
    while True:
        items = tools.config_items()
        secs = []
        for it in items:
            if it["section"] not in secs:
                secs.append(it["section"])
        print("  Sezioni:")
        for i, s in enumerate(secs, 1):
            n = sum(1 for it in items if it["section"] == s and it["overridden"])
            print(f"   {i:>2}) {s}" + (f"  ({n} modificati)" if n else ""))
        c = ask("\n  Numero sezione, nome di un parametro (es. OLLAMA_MODEL), «r» = ripristina tutto, INVIO = fine: ")
        if not c:
            return
        if c.lower() == "r":
            if yes("  Ripristinare TUTTI i valori di config.py?", False):
                tools.reset_override()
            continue
        if c.isdigit() and 0 < int(c) <= len(secs):
            sec = [it for it in items if it["section"] == secs[int(c) - 1]]
            for it in sec:
                print(f"\n  {'✎ ' if it['overridden'] else ''}{it['name']} = {_short(it['value'])}")
                print(wrap(it["description"][:400], "      "))
            c = ask("\n  Nome del parametro da modificare (INVIO = indietro): ")
            if not c:
                continue
        it = next((x for x in items if x["name"].lower() == c.lower()), None)
        if not it:
            print("  Parametro non trovato.")
            continue
        print(f"\n  {it['name']} ({it['kind']}) — valore attuale: {_short(it['value'])}")
        print(f"  Valore di config.py: {it['source']}")
        print(wrap(it["description"], "    "))
        if it["computed"]:
            print("  (in config.py è calcolato: il valore inserito lo sostituisce)")
        hint = {"bool": "s/n", "json": 'JSON, es. ["VZI_Base", "VZ_FR"]', "none": "testo o JSON"}.get(it["kind"], "")
        v = ask(f"  Nuovo valore{f' ({hint})' if hint else ''} — «-» = ripristina, INVIO = invariato: ")
        if v == "-":
            tools.reset_override(it["name"])
            print("  Ripristinato.")
        elif v:
            if it["kind"] == "bool":
                v = v.lower() in ("s", "si", "sì", "y", "yes", "true", "1")
            try:
                r = tools.set_override(it["name"], v)
                print(f"  ✔ {it['name']} = {_short(r.get('value', v))}")
            except Exception as exc:
                print(f"  ⚠️ {exc}")


def _short(v) -> str:
    s = repr(v)
    return s if len(s) < 120 else s[:117] + "…"


# ---------------------------------------------------------------------------

def main() -> int:
    _utf8()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Terminale developer di AskTrainMind")
    ap.add_argument("--run", metavar="N", help="esegue la voce N del menu ed esce")
    a = ap.parse_args()
    if a.run:
        acts = {k: f for k, _, _, f in menu_items()}
        if a.run not in acts:
            print(f"Voce non valida: {a.run}")
            return 2
        acts[a.run]()
        return 0
    try:
        main_menu()
    except (KeyboardInterrupt, SystemExit):
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
