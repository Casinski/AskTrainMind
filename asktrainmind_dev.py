"""
asktrainmind_dev.py
-------------------
TERMINALE DEVELOPER di AskTrainMind (doppio click su AVVIA_DEVELOPER.bat).

Da qui il developer:
  * OPZIONE 0 TOTAL (voce 0): aggiornamento incrementale dopo una modifica
    di Codice/Rev nel foglio CONFIG, con pagina dist/<data>/DBFlotte1000.html;
    OPZIONE 0 CREA DB CONFIG (voce 0C): solo la memoria del foglio CONFIG;
    voce 0W: solo la pagina DBFlotte1000.html dal file Excel (AVVIA_WEB.bat);
  * lancia le analisi che aggiornano il file Excel DB Flotte (opzioni 1-5);
  * ADDESTRA l'AI sui documenti tecnici, risponde alle sue domande,
    insegna/corregge i concetti (vedi README.md, Parte 4);
  * prova la sezione «Chiedi» con la conoscenza aggiornata;
  * modifica i parametri di config.py (CONFIG) e verifica i prerequisiti;
  * aggiorna la cartella User/ (pagina web offline + Excel) per gli utenti.

Uso non interattivo (script, pianificazioni):
    python asktrainmind_dev.py --run 13          # esegue una voce del menu ed esce
    python asktrainmind_dev.py --run 0           # OPZIONE 0 TOTAL
    python asktrainmind_dev.py --run 0C          # OPZIONE 0 CREA DB CONFIG
    python asktrainmind_dev.py --run 0W          # pagina web DBFlotte1000.html
    python asktrainmind_dev.py --questionai-export [percorso.xlsx]
    python asktrainmind_dev.py --questionai-import percorso.xlsx [--from-id N]
"""
from __future__ import annotations

import argparse
import logging
import os
import re
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


_HANG = re.compile(r"^(\s*(?:STEP \d+\s+|[•\-–]\s+|\d+[.)]\s+|[A-Z]\s=\s))")


def wrap(text: str, indent: str = "  ") -> str:
    """
    Testo a capo a W colonne. Le righe di elenco («STEP 1  …», «• …», «- …»,
    «1. …») vanno a capo allineate dopo il segno, così l'elenco resta leggibile.
    """
    out = []
    for line in str(text).splitlines() or [""]:
        if not line.strip():
            out.append("")
            continue
        m = _HANG.match(line)
        hang = indent + " " * len(m.group(1)) if m else indent
        out.append(textwrap.fill(line, W, initial_indent=indent, subsequent_indent=hang))
    return "\n".join(out)


def header(title: str) -> None:
    print("\n" + "═" * W + f"\n  {title}\n" + "═" * W)


def outcome(name: str, rc: int) -> None:
    """Esito di un'opzione eseguita in un processo separato."""
    print("\n" + "─" * W)
    if rc == 0:
        print(f"  ✅ {name} completata.")
    elif rc == 130:
        print(f"  ⛔ {name} interrotta.")
    else:
        print(f"  ❌ {name} terminata con errori (codice {rc}): leggi i messaggi sopra o il log asktrainmind.log.")
    print("─" * W)


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
    items = [
        ("0", "OPZIONE 0 TOTAL: aggiorna DB Flotte e pagina web dopo una modifica di Codice/Rev nel foglio CONFIG",
         "Aggiornamento incrementale guidato, in 5 step:\n"
         "All'avvio il file Excel viene copiato in «DB_FLOTTE HISTORY OPZ. 0/<data_ora>/» (la copia resta "
         "solo se l'opzione termina con successo).\n"
         "STEP 0  crea la memoria «FOGLIO CONFIG CODICE-REV FRS PER CONFIGURAZIONE» (Codice e Rev di ogni "
         "DOC ID per configurazione) e la confronta con quella precedente: un documento è cambiato se ha "
         "Codice o Rev diversi.\n"
         "STEP 1  FRS cambiati: se il file è nella cartella <configurazione>/CONFIG/FRS, nel foglio Funzioni "
         "svuota Rif. Pagina e Funzioni AI (sfondo bianco); se manca, svuota Link e Rif. Pagina e scrive "
         "«LINK DOCUMENTALE NON INSERITO». Nel foglio Requisiti svuota le celle della configurazione "
         "(riga eliminata se resta vuota). Documenti non FRS cambiati (FPD, FS, WT, EPL, GEN, ICD) collegati "
         "nel foglio Funzioni: «X» rossa in Rif. Pagina, da sostituire a mano con la nuova pagina.\n"
         "STEP 2  cerca il nuovo Rif. Pagina (come la voce 3); quelli mancanti o non numerici li inserisci tu "
         "nel file Excel e confermi con S; le celle lasciate vuote diventano «FUNZIONE NON PRESENTE».\n"
         "STEP 3  CHECK: ogni funzione aggiornata deve essere nel caso 1 (senza link), 2 (funzione non "
         "presente) o 3 (da ricalcolare); le anomalie le sani tu (S) o il programma (C).\n"
         "STEP 4  ricalcola Funzioni AI e Requisiti (come la voce 1) solo per le funzioni e le configurazioni "
         "dei documenti aggiornati; compila anche le celle «Funzioni AI» VUOTE di altri documenti (cancellate per "
         "sbaglio) che hanno link e Rif. Pagina, lasciando invariate quelle compilate, e te le elenca.\n"
         "STEP 5  salva il file Excel e crea dist/<AAAA-MM-GG>/DBFlotte1000.html con la copia del file Excel.\n"
         "Le istruzioni per te sono scritte in GIALLO. La versione precedente del file Excel è archiviata in _OLD/.",
         opzione0_total),
        ("0C", "OPZIONE 0 CREA DB CONFIG: crea solo la memoria Codice/Rev del foglio CONFIG",
         "Legge il foglio CONFIG e salva la memoria «FOGLIO CONFIG CODICE-REV FRS PER CONFIGURAZIONE» in "
         "db_config/config_db.json (copia leggibile config_db.csv): DOC ID (col B), tipo di documento (FRS, FPD, "
         "FS, WT, EPL, GEN, ICD), configurazione, Codice e Rev. È il riferimento con cui la successiva OPZIONE 0 "
         "TOTAL riconosce i documenti cambiati: usala per ripartire da zero dopo aver allineato a mano il DB. "
         "All'avvio il file Excel viene copiato in «DB_FLOTTE HISTORY OPZ. 0/<data_ora>/».",
         opzione0_crea_db_config),
        ("0W", "Crea solo la pagina web DBFlotte1000.html dal file Excel attuale (come AVVIA_WEB.bat)",
         "Crea dist/<AAAA-MM-GG>/DBFlotte1000.html con la copia del file Excel, senza eseguire l'OPZIONE 0 e "
         "senza modificare il file Excel, poi la apre nel browser.", opzione0_web),
    ]
    items += [(m, t, d, (lambda m=m: run_option(m))) for m, t, d in _analysis_items()]
    items += [
        ("6", "Addestra l'AI: leggi i documenti tecnici (PDF/DOCX/TXT) e impara sigle e concetti",
         "Legge i documenti delle cartelle indicate (default KNOWLEDGE_TRAIN_DIRS = docs/), estrae definizioni e "
         "frasi utili e prepara le domande per te. Interrompibile con Ctrl+C: riprende dal punto raggiunto.", train),
        ("7", "Rispondi alle domande dell'AI (conferma, correggi o completa ciò che ha capito)",
         "L'AI chiede il significato delle sigle che non ha capito e approfondimenti (componenti, sensori, "
         "centraline, tarature, eventi TCMS, costruttore, treni…). Puoi fermarti quando vuoi con «q».", answer_questions),
        ("15", "Genera il foglio Excel «questionAI» con le domande dell'AI (da compilare con calma)",
         "Crea questionAI.xlsx: una riga per domanda, colonna gialla «LA TUA RISPOSTA» da compilare con "
         "testo libero (sì / no / correzione / spiegazione). Le istruzioni sono nel foglio «Istruzioni».",
         export_question_sheet),
        ("16", "Carica il foglio «questionAI» compilato: l'AI legge, cataloga e impara le tue risposte",
         "Indica il percorso del file compilato. L'AI cataloga ogni risposta (conferma, correzione, "
         "spiegazione…) e la integra nella conoscenza usata da Chiedi. Interrompibile con Ctrl+C: quanto "
         "appreso resta salvato e ti dice da quale ID ricaricare. Ricaricare un file già caricato fa "
         "approfondire i concetti (nuove domande).", import_question_sheet),
        ("8", "Insegna o correggi un concetto (sigla, loop, sensore, centralina, configurazione…)",
         "Scrivi tu cosa deve sapere l'AI su un termine, anche se non è mai comparso nei documenti.", teach),
        ("9", "Consulta la conoscenza dell'AI (cerca, conferma le proposte, verifica i file)",
         "Riepilogo, ricerca dei concetti, conferma in blocco delle definizioni proposte, controllo dei file "
         "in knowledge/ dopo una modifica a mano.", browse_knowledge),
        ("10", "Prova la sezione «Chiedi» con la conoscenza aggiornata",
         "Fai una domanda come la farebbe un utente e vedi la risposta (incluse le schede dei concetti).", try_ask),
        ("17", "Verifica l'AI: la conoscenza appresa e la lettura dei documenti arrivano in «Chiedi»?",
         "Controllo automatico: per un campione di concetti a cui hai risposto (voce 7/16) verifica che Chiedi "
         "mostri la tua spiegazione; poi pone domande sul contenuto dei documenti (es. pressione di attivazione "
         "dei compressori nel VZI_New14) e controlla che la risposta citi il requisito giusto. Rapporto in "
         "LOG/verify_ai.txt.", verify_ai),
        ("18", "Completa le Description mancanti nel foglio «Requisiti» (rilegge i PDF)",
         "Per le celle del foglio Requisiti che hanno solo l'etichetta (MISS…/differenze) senza il testo del "
         "requisito, rilegge il PDF della configurazione e aggiunge la Description, così Esplora → Requisiti "
         "mostra sempre il testo. Il file originale viene archiviato in _OLD/ prima del salvataggio.", backfill_desc),
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
    dist = sorted(Path(getattr(cfg, "DIST_DIR", PROGRAM_DIR / "dist")).glob(f"*/{getattr(cfg, 'OPZIONE0_PAGE_NAME', 'DBFlotte1000.html')}"))
    if dist:
        last = max(dist, key=lambda x: x.stat().st_mtime)
        print(f"  🌐 Ultima pagina {last.name} creata il "
              f"{time.strftime('%d/%m/%Y %H:%M', time.localtime(last.stat().st_mtime))} in {last.parent}")
    groups = [("OPZIONE 0 (aggiornamento incrementale dal foglio CONFIG + pagina DBFlotte1000.html)", ("0", "0C", "0W")),
              ("ANALISI DEL DB FLOTTE (aggiornano il file Excel)", ("1", "2", "3", "4", "5", "18")),
              ("INTELLIGENZA ARTIFICIALE (addestramento e conoscenza)", ("6", "7", "15", "16", "8", "9", "10", "17")),
              ("CONFIGURAZIONE E PUBBLICAZIONE", ("11", "12", "13", "14"))]
    by = {k: t for k, t, _, _ in items}
    for title, keys in groups:
        print(f"\n  ── {title}")
        for k in keys:
            print(f"  {k:>3}) {by[k]}")
    print("\n    q) Esci       (scrivi «h N» per la descrizione della voce N)")


def main_menu() -> None:
    items = menu_items()
    actions = {k: (t, d, f) for k, t, d, f in items}
    while True:
        show_menu(items)
        c = ask("\n  Scelta: ").upper()
        if c in ("Q", "ESCI", "EXIT"):
            print("  Arrivederci.")
            return
        if c.startswith("H ") and c[2:].strip() in actions:
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
_SCOPE = [("Ambito — FRS da analizzare (es. «FRS_Line Voltage»; numeri, intervalli 1-3 o nomi; "
           "Invio = proposto, * = tutti)", None),
          ("Ambito — funzioni degli FRS scelti (es. «LV_Pantograph_Lifting»; Invio = tutte)", None),
          ("Ambito — configurazioni di treno (es. «VZI_Base, VZ_FR»; Invio = tutte)", None)]

OPTION_PARAMS = {
    "1": [_DB, *_SCOPE,
          ("Riprendere dalla funzione in cui si è interrotta l'esecuzione precedente? "
           "(solo se c'è un'interruzione)", None),
          ("Numero massimo di celle «Funzioni AI» da compilare (0 = tutte)", None),
          ("Sovrascrivere le celle già compilate? A = automatico (solo se il documento è "
           "cambiato), S = rielabora tutte, N = solo celle vuote", None),
          ("FUNC ID da cui partire", "START_FROM_FUNC_ID"),
          ("Aggiornare il foglio «Reqs not matched» al termine?", "REQS_NOT_MATCHED_AFTER_OPTION1")],
    "2": [_DB, *_SCOPE],
    "3": [_DB, *_SCOPE,
          ("Riprendere dalla funzione in cui si è interrotta l'esecuzione precedente? "
           "(solo se c'è un'interruzione; altrimenti parte da START_FROM_FUNC_ID)", "START_FROM_FUNC_ID")],
    "4": [_DB,
          ("Ambito — FRS (DOC ID) da confrontare, almeno uno", "CONFRONTO_REQS_DOC_IDS"),
          _SCOPE[1], _SCOPE[2]],
    "5": [_DB, _SCOPE[0], _SCOPE[1],
          ("Ambito — configurazioni da confrontare, almeno due (Invio = tutte)",
           "REQS_NOT_MATCHED_CONFIGS")],
}


def option_params_text(mode: str) -> str:
    rows = []
    for i, (q, key) in enumerate(OPTION_PARAMS.get(mode, []), 1):
        d = f"   [CONFIG {key} = {getattr(cfg, key, '')!r}]" if key else ""
        rows.append(f"  {i}. {q}{d}")
    return "\n".join(rows)


def opzione0_total() -> None:
    outcome("OPZIONE 0 TOTAL", subprocess.call([*python_cmd(), "opzione0.py"]))


def opzione0_crea_db_config() -> None:
    outcome("OPZIONE 0 CREA DB CONFIG", subprocess.call([*python_cmd(), "opzione0.py", "--crea-db-config"]))


def opzione0_web() -> None:
    outcome("Pagina web DBFlotte1000.html", subprocess.call([*python_cmd(), "opzione0.py", "--web"]))


def run_option(mode: str) -> None:
    print("  Parametri che ti verranno chiesti (Invio = valore proposto):")
    print(option_params_text(mode) + "\n")
    print("─" * W)
    r = subprocess.call([*python_cmd(), "funzioni_ai_filter.py", "--mode", mode, "--ask"])
    outcome(f"Opzione {mode}", r)
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


def verify_ai() -> None:
    import verify_ai as V
    V.run(progress=print)


def backfill_desc() -> None:
    import req_desc_backfill as B
    if ask("  Solo conteggio, senza modificare il file Excel? [s/N]: ").lower() in ("s", "si", "sì", "y"):
        B.run(dry_run=True)
        return
    B.run(dry_run=False)
    print("  Ricorda la voce 13 per aggiornare la cartella User.")


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
          f"{st['definitions']} definizioni trovate, {st['questions']} nuove domande, {st['passages']} frasi utili."
          + (f" {st['errors']} documenti saltati per errori (vedi ⚠ sopra)." if st.get("errors") else ""))
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


def export_question_sheet(dest: str = "") -> None:
    import knowledge
    import question_sheet as QS
    pend = knowledge.pending()
    if not pend:
        print("  Nessuna domanda in attesa. Lancia l'addestramento (voce 6) o carica un questionAI già "
              "compilato per approfondire (voce 16).")
        return
    if not dest:
        print(f"  {len(pend)} domande in attesa.")
        dest = ask(f"  Percorso del file [INVIO = {QS.default_path()}]: ").strip('"')
        flt = ask("  Filtra per termine (INVIO = tutte, nell'ordine di priorità): ")
        mx = ask(f"  Numero massimo di domande [INVIO = {getattr(cfg, 'QUESTION_SHEET_MAX', 200) or 'tutte'}]: ")
    else:
        flt, mx = "", ""
    p = Path(dest) if dest else QS.default_path()
    if p.suffix.lower() == ".xlsx" and p.is_file() and not dest:
        if not yes(f"  {p.name} esiste già: sovrascriverlo? (No = crea un file con data e ora)", False):
            p = p.with_name(f"{p.stem}_{time.strftime('%Y%m%d_%H%M')}.xlsx")
    try:
        path, n = QS.export_sheet(p, int(mx) if mx.isdigit() else None, flt)
    except RuntimeError as exc:
        print(f"  ⚠️ {exc}")
        return
    print(f"\n  ✔ Creato {path} con {n} domande.")
    print("  Compila la colonna gialla «LA TUA RISPOSTA» (istruzioni nel foglio «Istruzioni»), poi caricalo con la voce 16.")


def import_question_sheet(src: str = "", start_id: int | None = None) -> None:
    import question_sheet as QS
    if not src:
        src = ask(f"  Percorso del questionAI compilato [INVIO = {QS.default_path()}]: ").strip('"') or str(QS.default_path())
        rp = QS.resume_point(Path(src))
        if rp:
            print(f"  Il caricamento precedente di questo file si era interrotto all'ID {rp}.")
            v = ask(f"  Da quale ID riprendere? [INVIO = {rp}, 1 = dall'inizio]: ")
            start_id = int(v) if v.isdigit() else rp
        else:
            v = ask("  Da quale ID partire? [INVIO = dall'inizio]: ")
            start_id = int(v) if v.isdigit() else None
    print("\n  ⏳ Caricamento in corso — Ctrl+C per fermare (quanto appreso resta salvato)…\n")
    try:
        st = QS.import_sheet(src, start_id, progress=lambda m: print("  " + m))
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"  ⚠️ {exc}")
        return
    print("\n" + wrap(QS.report(st)))
    import knowledge
    s = knowledge.summary()
    print(f"  Ora l'AI ha {s['terms']} concetti e {s['pending']} domande per te.")
    if st["stopped"]:
        print(f"\n  ▶ Per completare: voce 16 con lo stesso file (riparte dall'ID {st['resume_from']}) oppure\n"
              f"    python asktrainmind_dev.py --questionai-import \"{src}\" --from-id {st['resume_from']}")
        return
    if st["applied"]:
        auto_export()
    if st["new_questions"] + st["deepen"] and sys.stdin.isatty() and \
            yes("  Creare subito un nuovo questionAI con le nuove domande?", True):
        export_question_sheet()


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
    if qa.doc_searcher(snap.model, snap.key) is None:
        print("  Lettura del testo dei documenti (indice per le risposte «📄 Dai documenti», ~1 minuto)…")
        t0 = time.time()
        while qa.doc_searcher(snap.model, snap.key) is None and qa._dx["building"] and time.time() - t0 < 600:
            time.sleep(1)
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
    elif t == "hits":
        print(f"\n  {b.get('title', '')}:")
        for it in b.get("items", [])[:6]:
            print(wrap(f"• {it.get('file', '')} pag. {it.get('page', '')}: {it.get('snippet', '').replace('[[', '').replace(']]', '')[:220]}", "    "))
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
    ap.add_argument("--questionai-export", metavar="PERCORSO", nargs="?", const="-",
                    help="crea il foglio questionAI.xlsx con le domande in attesa")
    ap.add_argument("--questionai-import", metavar="PERCORSO",
                    help="carica il foglio questionAI compilato (risposte all'AI)")
    ap.add_argument("--from-id", type=int, metavar="N", help="con --questionai-import: riparte dall'ID N")
    a = ap.parse_args()
    if a.questionai_export:
        import question_sheet as QS
        export_question_sheet(str(QS.default_path()) if a.questionai_export == "-" else a.questionai_export)
        return 0
    if a.questionai_import:
        try:
            import_question_sheet(a.questionai_import, a.from_id)
        except KeyboardInterrupt:
            print()
        return 0
    if a.run:
        acts = {k: f for k, _, _, f in menu_items()}
        a.run = a.run.upper()
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
