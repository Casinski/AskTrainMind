# 🧠 Addestrare l'AI di AskTrainMind

Questa guida è per il **developer**. Spiega come l'AI di AskTrainMind acquisisce conoscenza tecnica ferroviaria, come le si risponde, come si corregge ciò che ha imparato e come la conoscenza arriva agli utenti.

> In breve: **AVVIA_DEVELOPER.bat** → **6** (leggi i documenti) → **7** (rispondi alle sue domande) oppure **15 → 16** (rispondi in blocco nel foglio Excel «questionAI») → **8** (insegna o correggi) → **10** (prova «Chiedi») → **13** (pubblica per gli utenti).

---

## 1. Come ragiona l'AI

L'AI non si limita a cercare la parola «DNRA» nel foglio Excel. Costruisce un **glossario tecnico di concetti**. Ogni concetto è una *scheda* con:

| Campo | Esempio per DNRA |
|---|---|
| **termine** e **alias** | DNRA · *Detection of Non-Rotating Axle*, asse bloccato |
| **categoria** | sottosistema, **loop**, funzione, sensore, centralina, relè, attuatore, componente, segnale, **configurazione**, concetto, sigla |
| **significato** | «Rilevamento degli assi non rotanti (asse bloccato) …» |
| **come funziona** (dettagli) | testo libero |
| **relazioni** | elementi del treno coinvolti, sensori, centraline, **valori di taratura / soglie**, **eventi TCMS**, concetti correlati |
| **fatti** (dipendono dalla categoria) | per una configurazione: costruttore, anno, treni, linee, baseline… |
| **per configurazione** | differenze per VZI_Base, VZ_FR, VZ_ES… |
| **stato** | `proposto` (ricavato dai documenti, da verificare) oppure `confermato` (validato da te) |
| **fonti** | documento e pagina da cui l'ha imparato |

Oltre al glossario l'AI conserva i **passaggi** dei documenti, cioè le frasi tecniche in cui compare un concetto, e li cita nelle risposte.

Quando non capisce qualcosa, **genera domande** per te, per esempio:

- *«Ho capito che «TCMS» significa: «Train Control and Management System». È corretto?»*
- *«Cos'è un «loop»?»* · *«Quali sensori sono coinvolti in DNRA?»* · *«Ci sono valori di taratura?»* · *«Il TCMS ha eventi per DNRA?»*
- *«VZI_Base: chi è il costruttore? Quando è stato costruito? Dove viaggiano i treni?»*
- *«Cos'è un pantografo?»*

Ogni risposta migliora la scheda e può generare nuove domande di approfondimento. L'apprendimento è **continuo**: puoi fermarlo e riprenderlo quando vuoi, e anche ciò che è già consolidato resta sempre modificabile.

---

## 2. Dove si trova la conoscenza (file modificabili)

Tutta la conoscenza è nella cartella **`knowledge/`**, in file JSON leggibili e modificabili anche a mano:

| File | Contenuto |
|---|---|
| `glossario.json` | le **schede dei concetti** (`terms`: chiave = termine in maiuscolo) — **il cuore dell'apprendimento** |
| `domande.json` | `pending` = domande in attesa · `ignored` = domande scartate · `ignored_terms` = termini da non considerare |
| `passaggi.json` | frasi dei documenti per ogni concetto (testo, documento, pagina) |
| `fonti.json` | documenti già letti (firma del file, ultima pagina letta, completato sì/no) |
| `questionari.json` | questionari «questionAI» caricati (stato, ID di ripresa, risposte già acquisite) |

Esempio di scheda in `glossario.json`:

```json
"DNRA": {
  "term": "DNRA",
  "aliases": ["Detection of Non-Rotating Axle", "asse bloccato"],
  "category": "funzione",
  "meaning": "Rilevamento degli assi non rotanti: …",
  "details": "Il loop DNRA confronta le velocità degli assi …",
  "relations": {
    "componenti": ["carrello", "assi"], "sensori": ["sensori di velocità asse"],
    "centraline": ["BCU"], "tarature": ["soglia di differenza di velocità …"],
    "eventi_tcms": ["CON_DNRA_Alarm"], "correlati": ["LOOP", "WSP"]
  },
  "facts": {}, "configs": {"VZ_FR": "…"},
  "answers": [{"q": "Come funziona il DNRA?", "a": "Confronta la velocità di ogni asse …", "field": "details", "source": "questionAI", "date": "…"}],
  "status": "confermato", "sources": ["sviluppatore", "3ECP….pdf p.12"]
}
```

**Regole per le modifiche a mano**

- Chiudi prima il terminale developer e il server web, poi modifica il file con un editor UTF-8 (VS Code, Notepad++).
- `status: "confermato"` indica una scheda validata. Solo le schede confermate entrano nei prompt delle analisi AI.
- Prima di ogni salvataggio il programma crea una copia `*.json.bak`. Se un file si rovina, rinomina la copia `.bak` in `.json`.
- Per controllare i file: voce **9**, che segnala eventuali errori di formato.
- Per **ricominciare da zero**: cancella la cartella `knowledge/` e rilancia la voce **6**.

---

## 3. Il ciclo di addestramento (terminale developer)

Avvia **`AVVIA_DEVELOPER.bat`**, oppure `python asktrainmind_dev.py`. Scrivi `h N` per leggere la descrizione della voce N. Per eseguire direttamente una voce: `python asktrainmind_dev.py --run 6`.

### Voce 6 — Leggi i documenti tecnici

```
6) Addestra l'AI: leggi i documenti tecnici (PDF/DOCX/TXT) e impara sigle e concetti
```

- Legge le cartelle in `KNOWLEDGE_TRAIN_DIRS` (di default **`docs/`**). Al prompt puoi aggiungere **altri percorsi**, file o cartelle separati da `;`, per esempio `D:\Manuali\Freno;D:\Note\loop.txt`.
- Da ogni documento estrae sigle con definizione («DNRA – Detection of Non-Rotating Axle»), glossari, termini ricorrenti e frasi tecniche. Crea schede **proposte** e accoda le domande.
- Crea anche una scheda **confermata** per ogni configurazione del DB Flotte (nome della flotta, baseline, treni) e le domande per completarla (costruttore, anno, linee…).
- **Interruzione**: premi **Ctrl+C** in qualsiasi momento. Lo stato viene salvato pagina per pagina. Rilanciando la voce 6 riprende dal punto in cui si era fermata e salta i documenti già letti e non modificati.
- **File o cartelle non accessibili** vengono saltati con un avviso `⚠` e la lettura prosegue con gli altri documenti. Succede con percorsi mancanti, file OneDrive non sincronizzati, PDF corrotti o protetti. I percorsi più lunghi di 260 caratteri su Windows sono supportati. A fine lettura il riepilogo indica quanti documenti sono stati saltati. Al prossimo avvio la voce 6 li riprova.
- **File della conoscenza bloccati** (`Accesso negato` su `knowledge/*.json`, causato da antivirus, OneDrive, un editor aperto o la pagina web del developer): il salvataggio viene ritentato più volte. Se il blocco continua, i dati restano in memoria e vengono salvati al documento successivo, senza interrompere la lettura. Conviene comunque tenere la cartella del progetto **fuori da OneDrive** o mettere in pausa la sincronizzazione durante l'addestramento.
- Per far rileggere un documento modificato non serve fare nulla: la firma cambia e viene riletto.
- Con `KNOWLEDGE_USE_OLLAMA = True` (voce 11) l'AI locale propone anche i significati che i documenti non spiegano. È più lento.

### Voce 7 — Rispondi alle domande dell'AI

Le domande sono ordinate per priorità. Prima vengono quelle sui concetti più citati e quelle aperte dalle tue risposte. Puoi filtrarle per termine: scrivendo `DNRA` vedi solo le domande su DNRA.

```
  [12/674] DNRA · SIGNIFICATO   (fonte: 3ECP413176-0001.pdf p.7)
  Ho capito che «DNRA» significa: «Detection of Non-Rotating Axle». È corretto?
  …contesto dal documento…
  💡 Proposta: Detection of Non-Rotating Axle
  > _
```

| Scrivi | Effetto |
|---|---|
| un testo | è la tua risposta: corregge o completa la scheda |
| `s` / `ok` | conferma la proposta dell'AI |
| INVIO | salta: la domanda torna in fondo alla coda |
| `x` | non fare più questa domanda |
| `xx` | ignora del tutto questo termine (rumore, per esempio «OUT», «PB») |
| `ai` | chiedi un suggerimento all'AI locale (Ollama), che poi puoi confermare |
| `q` | **basta domande per ora**: tutto è già salvato, riprendi quando vuoi |

Quando confermi un significato ti viene chiesta la **categoria**: sigla, loop, sensore, configurazione… La categoria decide le domande successive. Per un *loop* chiederà gli elementi coinvolti, i sensori, le tarature e gli eventi TCMS; per una *configurazione*, il costruttore, l'anno e le linee.

Nelle risposte con un elenco (sensori, componenti…) separa gli elementi con virgola o `;`.

### Voci 15 e 16 — Questionario Excel «questionAI» (il modo più veloce)

Invece di rispondere una domanda alla volta nel terminale (voce 7), puoi farti dare **tutte le domande in un foglio Excel**, compilarlo con calma e caricarlo in un colpo solo.

**1. Crea il foglio (voce 15)**

```
15) Genera il foglio Excel «questionAI» con le domande dell'AI (da compilare con calma)
  2974 domande in attesa.
  Percorso del file [INVIO = …\questionAI.xlsx]:
  Filtra per termine (INVIO = tutte, nell'ordine di priorità): DNRA
  Numero massimo di domande [INVIO = 200]:
  ✔ Creato …\questionAI.xlsx con 37 domande.
```

Da riga di comando: `python asktrainmind_dev.py --questionai-export` (percorso di default) oppure `--questionai-export D:\Note\questionAI.xlsx`.

Il file contiene il foglio **questionAI** e il foglio **Istruzioni**:

| Colonna | Contenuto |
|---|---|
| ID | numero progressivo della domanda (serve per riprendere un caricamento) |
| Termine / concetto · Tipo di domanda | di cosa parla la domanda (significato, verifica della proposta, approfondimento, categoria…) |
| Domanda dell'AI · Proposta dell'AI · Dove l'ho trovato | la domanda, l'eventuale proposta e la frase del documento da cui nasce |
| **LA TUA RISPOSTA** (gialla) | **l'unica colonna da compilare** |
| Note | facoltative, vengono lette insieme alla risposta |

**2. Compila la colonna gialla** come risponderesti a una persona, **senza schema fisso**. L'AI cataloga da sola la risposta:

| Scrivi, per esempio | L'AI capisce |
|---|---|
| `sì` · `ok` · `esatto` · `corretto` | conferma la proposta |
| `Sì, ed è installata sotto cassa nella M2` | conferma e aggiunge il dettaglio alla scheda |
| `no` | la proposta è sbagliata: la domanda tornerà senza proposta |
| `No, è la Brake Control Unit` · `In realtà significa …` | correzione: il significato giusto è quello che hai scritto |
| una o più frasi libere | spiegazione discorsiva: viene salvata come «💬 Spiegazione dell'esperto», usata da **Chiedi**, e ne vengono estratti sigle con significato («la BCU (Brake Control Unit)»), valori con unità (`8,5 bar`, `110 V`), configurazioni citate (`sul VZ_FR …`) |
| righe `Sensori: …`, `Centraline: …`, `Tarature: …`, `Eventi TCMS: …`, `VZ_FR: …` | facoltative: riempiono direttamente i campi della scheda |
| `non so` · `?` | la domanda resta in attesa |
| `x` | non chiedere più questa domanda |
| `xx` · `ignora` | il termine non interessa (nessuna altra domanda) |
| vuoto | riga saltata: puoi compilare il foglio a più riprese |

Non modificare le colonne ID, _qid e _campo (nascoste). Puoi riordinare o filtrare le righe e salvare con un altro nome. Con `QUESTION_SHEET_USE_AI = True` e Ollama attivo, le risposte discorsive lunghe vengono anche strutturate dall'AI locale (componenti, sensori, tarature…); senza Ollama la catalogazione funziona lo stesso.

**3. Carica il foglio compilato (voce 16)**

```
16) Carica il foglio «questionAI» compilato: l'AI legge, cataloga e impara le tue risposte
  Percorso del questionAI compilato [INVIO = …\questionAI.xlsx]: D:\Note\questionAI.xlsx
  Da quale ID partire? [INVIO = dall'inizio]:
  ⏳ Caricamento in corso — Ctrl+C per fermare (quanto appreso resta salvato)…
```

Da riga di comando: `python asktrainmind_dev.py --questionai-import "D:\Note\questionAI.xlsx"` (con `--from-id N` per partire dall'ID N). Alla fine il riepilogo indica le risposte imparate, le conferme, le correzioni, le spiegazioni, le domande nuove nate dalle tue risposte e le righe saltate. Se ci sono domande nuove, il programma propone di creare subito un nuovo questionAI.

**Prestazioni.** Il caricamento è incrementale: la conoscenza viene ricompletata solo per i concetti modificati e il file viene salvato ogni `QUESTION_SHEET_SAVE_EVERY` righe ma non più spesso di `QUESTION_SHEET_SAVE_SECONDS` secondi (20). Un questionario di ~3000 risposte si carica in meno di un minuto senza Ollama (prima rallentava riga dopo riga).

**Se il caricamento si interrompe** (Ctrl+C, finestra chiusa, errore): tutto ciò che l'AI ha imparato **fino a quel momento resta salvato** (salvataggio ogni `QUESTION_SHEET_SAVE_EVERY` righe e all'interruzione). Il programma indica da quale ID ricaricare:

```
  ⏸ Caricamento interrotto all'ID 62. La conoscenza appresa fino a qui è salvata: ricarica il file
    questionAI.xlsx dall'ID 62 in poi (al prossimo caricamento dello stesso file riparto da lì in automatico).
  ▶ Per completare: voce 16 con lo stesso file (riparte dall'ID 62) oppure
    python asktrainmind_dev.py --questionai-import "D:\Note\questionAI.xlsx" --from-id 62
```

Ricaricando lo stesso file con la voce 16 il programma propone in automatico l'ID di ripresa (`1` = dall'inizio). Le righe già caricate non vengono applicate due volte.

**Ricaricare un file già caricato** serve ad **approfondire**: le risposte già imparate non vengono duplicate, ma per ogni concetto di cui hai parlato l'AI prepara nuove domande di approfondimento basate su quello che le avevi spiegato. Esportale con la voce 15. Se nel frattempo hai **modificato una risposta**, la nuova versione viene letta e applicata.

I questionari caricati sono registrati in `knowledge/questionari.json` (stato, ultimo ID, interruzioni).

### Voce 8 — Insegna o correggi un concetto

Serve per insegnare qualcosa che non è nei documenti o per correggere una scheda, anche se già confermata.

```
  Termine (es. DNRA, loop, pantografo, VZI_Base): loop
  Termine nuovo.
  Categoria: concetto
  Significato: circuito di sicurezza in serie che attraversa il treno; se si apre un contatto …
  ✔ Imparato. 5 domande di approfondimento accodate (voce 7).
   1) Significato  2) Come funziona  3) Alias  4) Categoria  5) Elementi coinvolti  …
  Numero del campo da scrivere (c = conferma la scheda, d = elimina, INVIO = fine):
```

- Scrivi il **numero** del campo per modificarlo: dettagli, alias, relazioni, tarature, eventi TCMS, fatti, note per configurazione.
- `c` conferma la scheda. `d` la elimina.
- Le schede insegnate da te sono subito **confermate**, con fonte «sviluppatore».

### Voce 9 — Consulta la conoscenza

- Mostra lo stato (concetti confermati e proposti, domande, documenti letti) e **controlla i file**.
- Scrivi un testo per **cercare** fra le schede e vederne il contenuto completo.
- `p` elenca le **proposte** da confermare in blocco: `1,4,7-12`, oppure `tutti`.
- `cats` mostra il numero di concetti per categoria.

### Voce 10 — Prova «Chiedi»

Fai una domanda come la farebbe l'utente e vedi la risposta con la conoscenza **aggiornata**, prima di pubblicarla.

```
  Domanda: come funziona il loop DNRA sul VZI_Base?
  🧠 Cosa so di «LOOP» …   🧠 Cosa so di «DNRA» …
  ⚙️ Funzioni collegate: BRK_Detection_of_Non-Rotating_Axle_(DNRA), CON_DNRA_Alarm …
```

Le parole che restano in **«🤔 Non conosco ancora…»** sono le prossime da insegnare con la voce 8.

Alla prima domanda la voce 10 prepara l'indice del testo dei documenti (circa un minuto): le risposte includono anche **«📄 Dai documenti»**, cioè il requisito o il paragrafo del PDF che risponde alla domanda.

### Voce 17 — Verifica l'AI

Controllo automatico, da eseguire prima di consegnare la cartella User:

```
CONOSCENZA: 485 concetti, 63 con risposte/conferme del developer (caricamento 0.02 s, ricarica 0 ms)
  40/40 concetti appresi mostrati da Chiedi (server e pagina offline)
DOCUMENTI: indice pronto in 26 s: 20764 passaggi, 66 documenti
  ✔ nel documento FRS Air Supply … nel VZI_New14 a che valore di pressione devono attivarsi i compressori?
      Nel documento FRS_Air Supply (3ECP413719-0603), pag. 7 — … il requisito 2F_06.03.Zefiro-Europe.CONCEPT.46 stabilisce che: …
```

- **Conoscenza**: per un campione di concetti a cui hai risposto (voci 7/16) o confermati, chiede «cos'è X?» e verifica che la scheda 🧠 mostri ciò che hai insegnato, sia nell'anteprima sia nella pagina offline.
- **Documenti**: pone le domande di `DOC_CASES` (in `verify_ai.py`, aggiungine di tue) e verifica che la risposta citi il requisito atteso e il PDF della configurazione chiesta.
- Rapporto in `RESULTS/verify_ai.txt`. Da riga di comando: `python verify_ai.py --sample 40`. La verifica non accoda domande all'addestramento.

---

## 4. Esempio completo: «come funziona il loop DNRA sul VZI_Base?»

1. **Voce 6**: l'AI legge i FRS in `docs/`, trova «DNRA» con la definizione e crea la scheda *proposta*. Crea anche la scheda *VZI_Base* dal DB Flotte.
2. **Voce 10**: provi la domanda. L'AI riconosce DNRA e VZI_Base, ma segnala *«Non conosco ancora: loop»*.
3. **Voce 8 → `loop`**: insegni che cos'è un loop. In alternativa, con la **voce 6** le dai un documento che ne parla, come un manuale o un `.txt` con la tua spiegazione.
4. **Voce 7, filtro `DNRA`**: confermi il significato (`s`), scegli la categoria *funzione* o *loop* e rispondi alle domande successive (sensori coinvolti, centralina che lo gestisce, soglie di taratura, eventi TCMS).
5. **Voce 7, filtro `VZI_BASE`**: rispondi su costruttore, anno, treni e linee.
6. **Voce 10**: ora la risposta contiene le schede *loop*, *DNRA* e *VZI_Base* con relazioni e fonti, oltre alle funzioni del DB Flotte.
7. **Voce 13**: pubblichi la conoscenza per gli utenti.

Lo stesso vale per *«Cos'è un pantografo?»*, *«Cos'è una configurazione dell'ETR1000?»* e simili.

---

## 5. Dove viene usata la conoscenza

| Dove | Come |
|---|---|
| **💬 Chiedi** (web) | schede «🧠 Cosa so di…» con relazioni, fonti e funzioni collegate; elenco delle parole sconosciute. Le sigle apprese e i loro alias (es. *MR = main reservoir*) ampliano anche la **lettura dei documenti** («📄 Dai documenti») |
| **🧭 Esplora** (web) | nel dettaglio funzione, barra **🧠 Concetti**; nei testi i termini noti sono sottolineati e cliccabili |
| **Analisi da terminale** (voci 1-5) | le schede **confermate** che riguardano la funzione analizzata vengono aggiunte al prompt dell'AI locale (`KNOWLEDGE_USE_IN_ANALYSIS`, max `KNOWLEDGE_MAX_TERMS_IN_PROMPT`). Le sintesi diventano così tecniche e non solo letterali |

---

## 5b. Come l'AI legge i documenti (`docsearch.py`)

Oltre alla conoscenza, Chiedi **legge il testo dei documenti**:

1. **Indice** (alla voce 13 per la pagina offline; in background al primo uso nell'anteprima): per ogni funzione del DB Flotte vengono raccolti i **requisiti** (Description per ogni variante di testo, con le configurazioni, il documento e la pagina di ciascuna) e i **paragrafi** delle pagine della funzione nei PDF. Intestazioni e piè di pagina ripetuti vengono scartati. Circa 20.000 passaggi da 66 documenti.
2. **Domanda → concetti**: le parole italiane vengono tradotte nei termini inglesi dei documenti con il dizionario `SYN` di `docsearch.py` (es. *pressione → pressure*, *attivarsi → run/start/activate*, *compressore → compressor*), estendibile a mano, e ridotte alla radice. Le sigle apprese aggiungono i loro alias.
3. **Contesto e contenuto**: le parole che nominano il documento (*FRS Air Supply*) o la funzione (*Controllo del compressore principale*) servono a scegliere **dove** cercare; le altre (*pressione*, *attivarsi*) sono **cosa** cercare. Le configurazioni citate (*VZI_New14*) filtrano i passaggi e scelgono il PDF da citare.
4. **Punteggio** BM25 con bonus per la funzione o il documento citati, per la configurazione e, se la domanda chiede un valore, per i passaggi con numeri e unità (*kPa*, *s*, *km/h*…).
5. **Risposta**: il passaggio migliore viene citato («il requisito … stabilisce che …») e, nell'anteprima con Ollama, i passaggi vengono passati anche all'AI per la spiegazione.

La stessa ricerca è replicata in JavaScript nella pagina offline (`offline.js → DocSearch`), con risultati identici.

## 6. Pubblicare per gli utenti

Gli utenti **non** hanno l'AI in addestramento: vedono una **fotografia** della conoscenza, inclusa nella pagina `User/AskTrainMind.html` al momento della pubblicazione.

- **Voce 13** rigenera la cartella `User/`: pagina web offline con dati, conoscenza e guida, più una copia dell'Excel.
- Con `USER_AUTO_EXPORT = True` la cartella User viene aggiornata automaticamente dopo ogni voce che modifica i dati o la conoscenza (1-9).
- Con `USER_EXPORT_PROPOSED = True` anche le schede *proposte* vengono pubblicate, con l'avviso «non ancora confermato». Imposta `False` per pubblicare solo quelle confermate.
- In alto a destra nella pagina utente compare la data della fotografia.

---

## 7. Parametri (voce 11 → sezione Conoscenza / Utente)

| Parametro | Default | Significato |
|---|---|---|
| `KNOWLEDGE_DIR` | `knowledge/` | cartella dei file della conoscenza |
| `KNOWLEDGE_TRAIN_DIRS` | `[docs/]` | cartelle e file letti dalla voce 6 |
| `KNOWLEDGE_MAX_PAGES` | `0` | massimo di pagine per documento (0 = tutte) |
| `KNOWLEDGE_MAX_QUESTIONS` | `40` | massimo di domande nuove accodate per ogni documento letto |
| `KNOWLEDGE_MAX_PASSAGES` | `8` | frasi conservate per concetto |
| `KNOWLEDGE_USE_OLLAMA` | `False` | usa l'AI locale durante l'addestramento |
| `KNOWLEDGE_USE_IN_ANALYSIS` | `True` | inserisce i concetti confermati nei prompt delle analisi |
| `KNOWLEDGE_MAX_TERMS_IN_PROMPT` | `25` | massimo di concetti per prompt |
| `KNOWLEDGE_MAX_ANSWERS_PER_TERM` | `30` | spiegazioni dell'esperto (risposte libere) conservate per concetto |
| `QUESTION_SHEET_DIR` | cartella del programma | dove la voce 15 crea `questionAI.xlsx` |
| `QUESTION_SHEET_MAX` | `200` | domande per questionario (0 = tutte) |
| `QUESTION_SHEET_USE_AI` | `True` | con Ollama attivo, struttura le risposte discorsive lunghe |
| `QUESTION_SHEET_SAVE_EVERY` | `10` | righe caricate fra un salvataggio e l'altro (resilienza alle interruzioni) |
| `QUESTION_SHEET_SAVE_SECONDS` | `20` | intervallo minimo fra due salvataggi durante il caricamento (velocità con migliaia di risposte) |
| `USER_DIR` | `User/` | cartella per gli utenti |
| `USER_AUTO_EXPORT` | `True` | aggiorna User automaticamente |
| `USER_COPY_EXTERNAL_PDFS` | `True` | copia in `User/docs` i PDF che si trovano fuori dalla cartella del programma |
| `USER_EXPORT_PROPOSED` | `True` | pubblica anche le schede proposte |

Le modifiche fatte dalla voce 11 vengono salvate in `config_overrides.json` e non toccano `config.py`. Con `-` ripristini un parametro, con `r` li ripristini tutti.
