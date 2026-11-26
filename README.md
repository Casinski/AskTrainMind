# AskTrainMind — DB Flotte ETR1000

AskTrainMind raccoglie in un unico strumento il **DB Flotte ETR1000** (file Excel), i **documenti FRS** (PDF) di ogni configurazione del treno e un'**AI** che risponde in italiano alle domande tecniche:

- l'**utente** apre una pagina web **offline** (`User/AskTrainMind.html`, doppio clic, nessuna installazione) per **🧭 Esplorare** configurazioni, FRS, funzioni, PDF e requisiti e per **💬 Chiedere** all'AI;
- il **developer** aggiorna il file Excel con le analisi automatiche (opzioni 1-5), addestra l'AI e rigenera la cartella `User/` da consegnare.

Questo README è l'**unica guida** del progetto: contiene tutte le istruzioni per il nuovo utente, la guida della pagina web (la stessa che si apre con il pulsante **❔ Guida**), le opzioni del developer, l'addestramento dell'AI e i dettagli di calcolo.

## Indice

- [Parte 1 — Nuovo utente: ricevere, aprire e usare la pagina](#parte-1--nuovo-utente-ricevere-aprire-e-usare-la-pagina)
  - [Come condividere la cartella con un nuovo utente (developer)](#11-come-condividere-la-cartella-con-un-nuovo-utente)
  - [Primo avvio](#12-primo-avvio)
  - [Errore «Failed to execute 'replaceState' on 'History'»](#13-errore-failed-to-execute-replacestate-on-history-pagina-aperta-in-sharepoint--onedrive)
  - [Usare l'AI di Chiedi](#14-usare-lai-di-chiedi)
  - [Problemi frequenti](#15-problemi-frequenti)
- [Parte 2 — Guida della pagina web (pulsante ❔ Guida)](#parte-2--guida-della-pagina-web)
- [Parte 3 — Developer: installazione, menu e opzioni 0-18](#parte-3--developer-installazione-menu-e-opzioni)
- [Parte 4 — L'AI: come ragiona, come si addestra, Ollama](#parte-4--lai-come-ragiona-e-come-si-addestra)
- [Parte 5 — Come vengono calcolati MATCHED e % SIMILARITY](#parte-5--come-vengono-calcolati-matched-e--similarity)

---

## Parte 1 — Nuovo utente: ricevere, aprire e usare la pagina

> **Non devi installare niente.** Ti serve solo un browser (Microsoft Edge, già presente su Windows, oppure Chrome o Firefox). Non servono Python, programmi aggiuntivi, diritti di amministratore né Internet.
>
> **Accesso in sola consultazione.** Puoi consultare tutto e fare domande all'AI. I dati, l'addestramento dell'AI e gli aggiornamenti sono gestiti dal **developer**: la pagina non modifica nessun file e il file Excel è in sola lettura.

### 1.1 Come condividere la cartella con un nuovo utente

La pagina funziona solo se l'utente ha **tutta la cartella `User`** sul proprio PC:

```
User/
├── AskTrainMind.html                        ← la pagina da aprire (doppio clic): contiene dati, AI e guida
├── docs/                                    ← i PDF dei documenti FRS (li apre la pagina) — OBBLIGATORIA per i PDF
├── DB Flotte ETR1000 Ver_1.9 Gabriele.xlsx  ← il file Excel completo (sola lettura, facoltativo)
└── LEGGIMI.txt                              ← promemoria rapido
```

Per il **developer** che consegna la cartella:

1. aggiorna i dati: `AVVIA_DEVELOPER.bat` → voce **13** (*Aggiorna la cartella User*), oppure `python export_user.py`;
2. comprimi **l'intera cartella `User`** (clic destro → *Invia a* → *Cartella compressa*) e invia lo **ZIP**, oppure condividi la cartella da OneDrive/SharePoint chiedendo all'utente di **scaricarla** (non di aprirla nel browser);
3. **non inviare solo `AskTrainMind.html` e il file Excel**: senza la cartella `docs` la pagina si apre, ma i PDF no.

### 1.2 Primo avvio

1. **Scarica la cartella sul PC.**
   - Da **SharePoint / OneDrive web / Teams**: seleziona la cartella `User` → **⋯ → Scarica**. Ottieni uno ZIP.
   - Oppure, con OneDrive installato: **Sincronizza** (o *Aggiungi collegamento a I miei file*) e apri la cartella da *Esplora file*.
2. **Estrai lo ZIP**: clic destro → **Estrai tutto…**, per esempio in `Documenti\AskTrainMind`. Non aprire la pagina dall'interno dello ZIP.
3. Apri la cartella estratta e fai **doppio clic su `AskTrainMind.html`**.
   - Se si apre con un programma sbagliato: clic destro → **Apri con** → **Microsoft Edge** (o Chrome/Firefox).
   - La barra degli indirizzi deve iniziare con **`file:///C:/…`**. Se inizia con `https://…sharepoint.com` o `blob:` stai guardando un'anteprima web (vedi 1.3).
4. In alto a destra controlla la **data dei dati** (*«Dati del … · aggiornati il … · AI: N concetti»*).
5. Se il browser mostra un avviso sui **contenuti locali**, consentili: la pagina funziona **offline** e **non invia dati**.

Il file Excel si apre con doppio clic, in **sola lettura** o *Visualizzazione protetta*: non serve abilitare la modifica.

### 1.3 Errore «Failed to execute 'replaceState' on 'History'» (pagina aperta in SharePoint / OneDrive)

Se compare un errore simile a:

```
Errore: Failed to execute 'replaceState' on 'History': A history state object with URL
'blob:https://….sharepoint.com/…#explore' cannot be created in a document with origin 'null'
and URL 'about:srcdoc'.
```

significa che la pagina è stata aperta **dentro l'anteprima web** di SharePoint, OneDrive, Teams o Outlook. L'anteprima esegue la pagina in un riquadro protetto, senza indirizzo proprio e senza accesso alla cartella `docs`: la pagina non può funzionare correttamente e i PDF non si aprono.

**Soluzione:**

1. chiudi l'anteprima;
2. **scarica tutta la cartella** (con `docs`) come descritto in 1.2, oppure sincronizzala con OneDrive;
3. estrai lo ZIP e apri `AskTrainMind.html` con **doppio clic dal PC** (indirizzo `file:///…`).

Dalla versione attuale la pagina riconosce da sola questa situazione: invece dell'errore mostra un **banner giallo «Stai guardando un'anteprima»** con gli stessi passi. Se manca la cartella `docs`, la pagina si apre ma i PDF no: chiedi al developer la cartella completa.

### 1.4 Usare l'AI di Chiedi

Apri **💬 Chiedi**, scrivi la domanda in italiano e premi **Invio**. L'AI **capisce il significato della domanda** (che cosa chiedi, di quale grandezza, in quale documento, funzione e configurazione) e risponde in **due sezioni**:

| Sezione | Cosa contiene |
|---|---|
| **🎓 Risposta AI** | la risposta che darebbe un ingegnere ferroviario che conosce tutte le configurazioni del treno: il dato richiesto con il significato in italiano (*Risposta: 1000 kPa — arresto compressori principali quando MR ≥ 1000 kPa*), oppure l'elenco ragionato di tutti i valori del perimetro chiesto, la spiegazione di un concetto o la sintesi di una funzione, sempre con il riferimento al requisito |
| **📄 Sezione documentale** | cosa dicono i documenti: i requisiti e i paragrafi citati con documento, codice, pagina e configurazioni (clic = apre il PDF alla pagina), le schede 🧠 dei concetti, i dati del DB Flotte e le funzioni collegate |

Esempi di domande:

- *Che valori di pressione ci sono all'interno di FRS Air Supply per il VZI_Base?*
- *A che pressione si fermano i compressori?* · *Dopo quanto tempo si chiudono le porte?*
- *Che temperatura massima possono raggiungere le boccole?*
- *Cos'è il DNRA?* · *Come funziona BOG_Hotbox_Detection?*
- *Quali sono le differenze di BOG_Hotbox_Detection tra VZI_Base e VZ_FR?*

Consigli: nomina la **configurazione** (*VZI_New14*, *VZ_FR*…) e, se lo conosci, il **documento** (*FRS Air Supply*) o la **funzione**; controlla la riga **🔍 Ho capito che chiedi** e, se non corrisponde, riformula. Verifica sempre il dato nel PDF. Se l'AI risponde **🤔 Non conosco ancora…**, usa **⧉ Copia la domanda** e inviala al developer.

La pagina offline contiene tutta l'AI (comprensione della domanda, conoscenza appresa e testo dei documenti) e **non usa Internet**. La spiegazione aggiuntiva con il modello **Ollama** è disponibile solo nell'anteprima web del developer (vedi [Parte 4](#parte-4--lai-come-ragiona-e-come-si-addestra)).

### 1.5 Problemi frequenti

| Problema | Soluzione |
|---|---|
| Errore *replaceState… origin 'null'* o banner *«Stai guardando un'anteprima»* | Vedi [1.3](#13-errore-failed-to-execute-replacestate-on-history-pagina-aperta-in-sharepoint--onedrive): scarica la cartella e apri la pagina dal PC |
| La pagina si apre in Blocco note o in un altro programma | Clic destro su `AskTrainMind.html` → **Apri con** → **Microsoft Edge** |
| Un PDF non si apre o resta bianco | La cartella `docs` deve essere accanto alla pagina; se hai uno ZIP, estrai tutto. Con ↗ apri il PDF in una nuova scheda |
| Pagina bianca o pulsanti che non rispondono | Usa una versione recente di Edge, Chrome o Firefox (non Internet Explorer); ricarica con **F5** |
| `AVVIA_WEB.bat` è bloccato dai criteri aziendali | Apri direttamente `User\AskTrainMind.html` con doppio clic |
| La pagina è lenta ad aprirsi la prima volta | È normale (circa 10 MB con dati e testo dei documenti): attendi qualche secondo |
| Excel chiede di «Abilitare la modifica» | Non serve: il file è in sola consultazione |
| I dati sembrano vecchi | Guarda la data in alto a destra e chiedi al developer la cartella aggiornata |

**Cosa non fare:** non usare `AVVIA_DEVELOPER.bat` né i file `.py` (sono strumenti del developer); non modificare né rinominare i file di `User` (vengono rigenerati); non separare `AskTrainMind.html` dalla cartella `docs`.

---

## Parte 2 — Guida della pagina web

Questa parte è la guida che si apre con il pulsante **❔ Guida** della pagina (viene incorporata in `AskTrainMind.html` da `export_user.py`).

<!-- GUIDA:INIZIO -->
### 📘 Guida di AskTrainMind

AskTrainMind mostra il **DB Flotte ETR1000** (funzioni, requisiti e documenti FRS di ogni configurazione del treno) e risponde a domande tecniche usando ciò che l'AI ha imparato dai documenti ferroviari.

| Voglio… | Pulsante |
|---|---|
| sfogliare configurazioni, FRS e funzioni, leggere i PDF affiancati e confrontare i requisiti | **🧭 Esplora** |
| fare una domanda in italiano su una funzione o su un concetto tecnico | **💬 Chiedi** |
| leggere questa guida | **❔ Guida** |

#### 1. 🚀 Come si apre

- Apri la cartella **User** e fai **doppio clic su `AskTrainMind.html`**, oppure fai doppio clic su **`AVVIA_WEB.bat`** nella cartella del programma. La pagina si apre nel browser (Edge, Chrome o Firefox). **Non serve installare nulla e non serve Internet.**
- Nella stessa cartella trovi il **file Excel** DB Flotte all'ultimo aggiornamento.
- In alto a destra c'è la data dei dati, per esempio *«Dati del 18/11/2026 · aggiornati il 18/11/2026 · AI: 206 concetti»*. Il developer rigenera la pagina dopo ogni aggiornamento.
- I PDF si aprono dalla cartella **docs** che si trova dentro la cartella **User**: tieni sempre insieme `AskTrainMind.html` e `docs`.
- **Non aprire la pagina nell'anteprima del browser di SharePoint, OneDrive, Teams o Outlook**: scaricala (con tutta la cartella) sul PC e aprila con doppio clic.

##### Colori e simboli

| Simbolo | Significato (funzioni) | | Simbolo | Significato (requisiti, vedi *📋 Requisiti*) |
|---|---|---|---|---|
| ★ | configurazione di riferimento (base) | | ★ / ☆ | riferimento VZI_Base / riferimento sostitutivo se VZI_Base manca |
| ✔ | simile alla base: verde (≥ 80 %, verde grassetto nel DB se ≥ 90 %) | | = | stesso testo del riferimento |
| ≈ | differenze moderate: arancione (50–80 %) | | ≠B | testo diverso (stessa lettera = stesso testo) |
| ≠ | differenze rilevanti: rosso (< 50 %) | | ✖ | requisito assente |
| ○ | collegata, non ancora analizzata | | ✔ MATCHED | presente in tutte con lo stesso testo |
| ⚠ | documento non disponibile: link mancante o da verificare | | ✖ NOT MATCHED | solo in una, manca in alcune o testo diverso |

Le parole sottolineate a puntini sono **concetti che l'AI conosce**. Cliccale per aprire la scheda: significato, come funziona, elementi del treno coinvolti, sensori, centraline, tarature, eventi TCMS, frasi tratte dai documenti e funzioni collegate. Una sottolineatura più chiara indica un significato ricavato dai documenti e non ancora confermato dal developer.

#### 2. 🧭 Esplora

Esplora mostra il DB come una **mappa a blocchi che si apre verso il basso**, livello dopo livello:

```
① 🚆 Configurazioni   VZI_Base · VZ_FR · VZ_ES …        (clic = seleziona, anche più di una)
        ▼
② 📘 FRS / DOC ID     FRS_Brake Control · FRS_Air Supply …
        ▼
③ ⚙️ Funzioni         BRK_Detection_of_Non-Rotating_Axle_(DNRA) …
        ▼
④ 🗂 Dettaglio funzioni   🧠 Funzioni AI · 📄 PDF affiancati · 📋 Requisiti
```

1. **① Configurazioni**: ogni blocco mostra il treno, la baseline, il numero di FRS 📚, di funzioni ⚙️ e di veicoli 🚆. Puoi cliccare **più configurazioni**, per esempio VZI_Base, VZ_FR e VZ_ES: tutto il resto verrà mostrato **affiancato** per quelle configurazioni. **☑ Tutte** le seleziona tutte.
2. **② FRS**: i documenti FRS delle configurazioni scelte. I pallini colorati indicano in quali configurazioni ogni documento è collegato. Sotto gli FRS il riquadro apribile **📂 Altri documenti della configurazione** elenca, per ogni configurazione scelta, i documenti del foglio CONFIG presenti nelle cartelle SharePoint `CONFIG/FPD` (Functional principle diagrams), `CONFIG/FS` (Functional schematics), `CONFIG/WT` (Wiring tables), `CONFIG/EPL` (Electrical part lists), `CONFIG/GEN` (General Vehicle Documents) e `CONFIG/ICD` (Interface control documents): clic su un documento per leggerlo. Compaiono solo le categorie che hanno documenti.
3. **③ Funzioni**: le funzioni dei documenti scelti, con l'esito per configurazione (★ ✔ ≈ ≠ ○ ⚠) e il numero di requisiti 📋.
4. **④ Dettaglio funzioni**: per ogni funzione selezionata si apre un pannello. In alto trovi:
   - **Selezionate / Tutte**: mostra solo le configurazioni scelte al punto ① oppure tutte quelle che trattano la funzione;
   - i badge colorati delle configurazioni mostrate;
   - **💬 Chiedi**: apre Chiedi con una domanda già pronta;
   - **✕**: chiude il pannello.

   Il pannello ha tre schede. La pagina ricorda l'ultima scheda aperta.

##### 🧠 Funzioni AI
Le schede, una per configurazione, sono **centrate nel pannello** e affiancate. Ogni scheda contiene la sintesi AI della funzione, la somiglianza con la base e il documento di riferimento (📄 apre il PDF alla pagina della funzione).

- **★ Riferimento** (configurazione base): la sintesi della funzione.
- **Varianti**: la **similarità funzionale** con la base (barra e percentuale con il colore dell'esito ✔ ≈ ≠). La similarità misura quanto le due funzioni **hanno lo stesso significato**: non conta l'impaginazione del PDF. Quando ci sono **differenze funzionali o d'impianto grandi**, la scheda le elenca nel riquadro rosso **«Differenze rilevanti rispetto a …»**:
  - *Valori/soglie diversi*: tensioni, tempi, correnti… che cambiano (per esempio `VZI_Base 18.5 kV → VZ_FR 30 kV`);
  - *Requisiti diversi*: requisiti presenti in una sola delle due configurazioni;
  - *Contenuto molto diverso*: una configurazione descrive la funzione con molto più testo;
  - *Componenti/sigle d'impianto diversi*: centraline, apparecchiature o segnali citati solo da una configurazione.

  Con differenze rilevanti la funzione non risulta mai «uguale» alla base (niente verde grassetto).

**Documento non disponibile (⚠).** Se per una configurazione manca il documento, la scheda mostra in **nero grassetto**:

| Messaggio | Cosa significa | Cosa fare |
|---|---|---|
| **LINK DOCUMENTALE NON INSERITO** | nel foglio *Funzioni* non c'è il link al documento per quella configurazione | chiedi al developer di inserire il link |
| **RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO** | il link c'è ma non porta a nessun documento (link errato, `#N/A`, PDF assente) | segnala il link al developer perché lo verifichi |

In questi casi la configurazione è **esclusa dal confronto** con le altre: non ha percentuale di similarità e i suoi requisiti non vengono confrontati.

**Approfondimenti e altri documenti della funzione.** Sotto *Funzioni AI* il developer può aggiungere nel foglio *Funzioni* altre righe con un titolo a scelta (per esempio *Approfondimenti (data 01/07/2026)*, *Componenti circuito elettrico (da 01/07/2026)*, *Descrizione circuitale (da 01/07/2026)*) e altri link a documenti (per esempio uno *Functional schematic* FS). Nella scheda della configurazione compaiono:

- ogni riga aggiunta che contiene testo, con il suo titolo;
- ogni link aggiunto (📎 documento, codice e pagine): 🌐 lo apre su SharePoint alla pagina indicata e il PDF è disponibile anche in *📄 PDF affiancati*;
- **✖ «documento aggiornato, riferimento di pagina da verificare — PDF non mostrato»**: il documento è stato aggiornato (nuovo Codice o Rev nel foglio CONFIG) e la pagina non è ancora stata ricontrollata dal developer, perciò il PDF non viene mostrato.

##### 📄 PDF affiancati
I PDF delle configurazioni scelte si aprono **uno accanto all'altro**, ognuno già alla **pagina in cui inizia la funzione**. Così puoi leggerli in parallelo senza aprire e chiudere un documento alla volta.

| Comando | Effetto |
|---|---|
| chip delle configurazioni (barra *Documenti*) | mostra o nasconde il PDF di quella configurazione |
| **Auto · 1 · 2 · 3 · 4** | numero di colonne (*Auto* le adatta alla larghezza dello schermo) |
| **⟲ Pagina funzione** | riporta tutti i PDF alla pagina della funzione |
| **⛶ Schermo intero** | i PDF affiancati occupano tutto lo schermo (Esc per uscire) |
| ◀ ▶ e casella numero (su ogni PDF) | pagina precedente o successiva, oppure vai alla pagina indicata |
| ↗ | apre il PDF in una nuova scheda del browser |
| **📎 colonne aggiuntive** | i documenti collegati alla funzione con i link aggiunti nel foglio *Funzioni* (FS, FPD…) si aprono accanto all'FRS, alla pagina indicata |
| **➕ Affianca documento CONFIG…** (menu a tendina) | aggiunge accanto agli FRS un altro documento della configurazione (FRS, Functional principle diagrams, Functional schematics, Wiring tables, Electrical part lists, General Vehicle Documents, Interface control documents); **✕** sull'intestazione lo toglie |

Dentro ogni PDF puoi usare anche i comandi del browser (zoom, ricerca con Ctrl+F, scorrimento).

##### 📋 Requisiti
È una tabella **requisito × configurazione** per le configurazioni scelte al punto ①. Ogni riga mostra **sempre l'ID e la Description del requisito**: si capisce subito cosa dice il requisito, senza aprirlo.

**In alto** trovi:
- il **riepilogo**: per ogni configurazione, quanti requisiti contiene e quanti ne ha *solo lei* (*«3 solo qui»*);
- il **riferimento**: ★ **VZI_Base** (configurazione base). Se VZI_Base **non è fra le configurazioni scelte**, o non contiene quel requisito, il riferimento diventa la **prima configurazione che lo contiene (☆)**: l'esito resta comunque chiaro per le configurazioni scelte;
- i **filtri**: **Tutti · ✔ MATCHED · ✖ NOT MATCHED**, il dettaglio dei NOT MATCHED (**① solo in una · ◐ manca in alcune · ≠ testo diverso · ? da verificare**), la casella *Filtra requisiti (ID o testo)…* e **▾ Espandi tutti / ▴ Comprimi tutti**;
- la **legenda** *«Come leggere la tabella»* (si apre e chiude con un clic; la pagina ricorda la scelta).

**Colonna «Esito»** — vale fra le configurazioni **mostrate**:

| Esito | Quando | Esempio con VZI_Base, VZ_FR, VZ_ES |
|---|---|---|
| **✔ MATCHED** (verde) | il requisito c'è in **tutte** le configurazioni, con lo **stesso testo** | ★ = = |
| **✖ NOT MATCHED** · *solo in una* | c'è in **una sola** configurazione | ✖ ☆ ✖ → *presente solo in VZ_FR* |
| **✖ NOT MATCHED** · *manca in alcune* | è condiviso da una parte delle configurazioni, **anche se è la maggioranza** | ★ = ✖ → *presente in 2 di 3 · manca in VZ_ES* |
| **✖ NOT MATCHED** · *testo diverso* | c'è in tutte, ma **alcune hanno un testo diverso** | ★A =A ≠B → *testo A: VZI_Base, VZ_FR · testo B: VZ_ES* |
| **? DA VERIFICARE** | c'è in tutte, ma per qualche configurazione il file Excel non riporta il testo | ★ = ? |
| **• PRESENTE** | è mostrata una sola configurazione: scegline altre per il confronto | |

Sotto l'esito una riga spiega il motivo (*«manca in VZ_ES»*, *«testo A: …, testo B: …»*). Se un requisito è condiviso solo da alcune configurazioni **e** ha testi diversi, l'esito li riporta entrambi.

**Simboli nelle celle delle configurazioni:**

| Simbolo | Significato |
|---|---|
| ★ | riferimento: VZI_Base |
| ☆ | riferimento sostitutivo: VZI_Base non c'è (o non è mostrata), si confronta con questa configurazione |
| = | stesso testo del riferimento |
| ≠B | testo diverso dal riferimento. **Le configurazioni con la stessa lettera (A, B, C…) hanno lo stesso testo**: così vedi quali sotto-configurazioni condividono la stessa variante |
| ✖ | requisito assente in questa configurazione |
| ? | requisito presente, testo non verificabile |

**Clicca su un requisito** per aprire sotto la riga i **testi completi raggruppati per variante**: un riquadro per ogni testo diverso, con le configurazioni che lo usano; le parole aggiunte rispetto al riferimento sono **evidenziate in verde** e quelle tolte **barrate in rosso**. Un riquadro elenca anche le configurazioni in cui il requisito **manca**. **I requisiti restano sempre al loro posto**: il dettaglio si apre solo sotto la riga cliccata, senza far scorrere la tabella. Clicca di nuovo sul requisito per richiuderlo; puoi tenere aperti più requisiti insieme.

##### Filtri di Esplora (barra in alto)

| Comando | Effetto |
|---|---|
| 🔎 *Cerca funzione, descrizione o FRS…* | filtra i blocchi mentre scrivi; anche senza selezionare nulla mostra subito le funzioni che corrispondono |
| ✔ ≈ ≠ ○ ⚠ (chip *Esito*) | mostra solo le funzioni con quell'esito in almeno una configurazione selezionata |
| 📋 Con requisiti | mostra solo le funzioni che hanno requisiti |
| ✖ Azzera | toglie selezioni e filtri |

La barra di navigazione (🧭 Esplora › configurazioni › FRS › funzioni) ti riporta a un livello con un clic. La pagina ricorda le tue selezioni anche quando la riapri.

#### 3. 💬 Chiedi

Scrivi una domanda in italiano e premi **Invio**. Alcuni esempi:

- *Come funziona il loop DNRA sul VZI_Base?*
- *Cos'è il TCMS?* · *Cos'è una configurazione dell'ETR1000?* · *Cos'è un pantografo?*
- *Quali sono le differenze di BOG_Hotbox_Detection tra VZI_Base e VZ_FR?*
- *Quali requisiti di AIR_Control_of_Main_Compressor sono diversi?*
- *In quali documenti è descritta CON_DNRA_Alarm?*
- *Nel documento FRS Air Supply, nel VZI_New14, a che valore di pressione devono attivarsi i compressori?*

Chiedi **capisce prima il significato della domanda** (cosa chiedi: un valore, una condizione, un significato, un confronto, i requisiti, i documenti…; di quale grandezza: pressione, temperatura, tempo…; in quale documento, funzione e configurazione) e poi legge, **insieme**, la conoscenza ferroviaria appresa e il testo dei documenti. In cima alla risposta trovi **🔍 Ho capito che chiedi: …**: se non è quello che intendevi, riformula la domanda.

La risposta ha **due sezioni**:

**🎓 Risposta AI** — come risponderebbe un ingegnere ferroviario che conosce tutte le configurazioni del treno:

- per le domande precise dà subito il dato, con il significato in italiano e il riferimento: *a che pressione si fermano i compressori?* → **Risposta: 1000 kPa** — arresto compressori principali quando serbatoio principale (MR) ≥ 1000 kPa (FRS_Air Supply, CONCEPT.93, pag. 8);
- per le domande aperte (*che valori di pressione ci sono in FRS Air Supply per il VZI_Base?*) elenca **tutti i valori del perimetro richiesto**, raggruppati per funzione e spiegati (*avvio compressori principali*, *arresto*, *segnalazione «Low main reservoir pressure»*…), con una **tabella riepilogativa** ordinabile;
- per *cos'è…?* spiega il concetto; per *come funziona…?*, *differenze…*, *requisiti…* riassume la funzione partendo dalle schede del DB Flotte.

**📄 Sezione documentale** — cosa dicono i documenti:

- **📄 Dai documenti**: il requisito o il paragrafo che risponde, con documento, codice, pagina e configurazioni, per esempio *nel documento FRS_Air Supply (3ECP413719-0603), pag. 7 — il requisito 2F_06.03.Zefiro-Europe.CONCEPT.46 stabilisce che «All main compressors shall be ordered to run … when MR pressure is less than 800 kPa…»*. Se nomini una configurazione viene citato il **PDF di quella configurazione**. Sotto trovi gli altri passaggi pertinenti: **cliccali per aprire il PDF alla pagina**. Le parole italiane della domanda sono tradotte nei termini inglesi dei documenti (es. *pressione → pressure*, *fermarsi → stop*, *boccole → axle box*);
- **🧠 Cosa so di «…»**: la scheda di ogni concetto citato (significato, funzionamento, elementi del treno, sensori, centraline, tarature, eventi TCMS, frasi dei documenti con pagina) e le **💬 spiegazioni dell'esperto** date dal developer;
- **i dati del DB Flotte**: sintesi per configurazione, differenze, requisiti e documenti, quando la domanda riguarda una funzione;
- **Funzioni citate nei passaggi**: cliccale per aprirle subito in 🧭 Esplora, con PDF affiancati e requisiti;
- **🤔 Non conosco ancora…**: le parole che l'AI non ha ancora imparato. Con **⧉ Copia la domanda** puoi inviarla al developer, che la insegnerà all'AI e aggiornerà la pagina.

La 🎓 Risposta AI è composta leggendo i documenti: **verifica sempre** il dato nella 📄 Sezione documentale e nel PDF.

A sinistra trovi le **domande suggerite** e la **cronologia** delle tue domande (🗑 per cancellarla).

#### 4. ❓ Problemi frequenti

| Problema | Soluzione |
|---|---|
| Errore *«Failed to execute 'replaceState' on 'History'… origin 'null'»*, oppure banner giallo *«Stai guardando un'anteprima»* | Hai aperto la pagina nell'**anteprima di SharePoint / OneDrive / Teams / Outlook**: lì la pagina non può funzionare. Scarica **tutta la cartella** (con `docs`), estraila e apri `AskTrainMind.html` con **doppio clic** dal PC (vedi *Come si apre*). |
| Un PDF non si apre o resta bianco | La cartella **docs** deve trovarsi accanto a `AskTrainMind.html` (dentro **User**). Se il file è dentro uno ZIP, estrai prima tutto. Se il documento manca, chiedilo al developer. |
| I PDF non si vedono affiancati | Allarga la finestra oppure scegli 1 o 2 colonne; con ↗ apri il PDF in una nuova scheda |
| Il browser mostra un avviso sui contenuti locali | Consenti il contenuto: la pagina funziona senza Internet e non invia dati |
| I dati sembrano vecchi | Controlla la data in alto a destra e chiedi al developer di aggiornare la cartella User |
| L'AI non conosce un termine | Usa **⧉ Copia la domanda** e invia il testo al developer |
| Una scheda dice «LINK DOCUMENTALE NON INSERITO» o «RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO» | Il documento di quella configurazione manca o il link è errato: segnalalo al developer (vedi *🧠 Funzioni AI*) |

---

*Primo utilizzo, developer e addestramento dell'AI: vedi **README.md** (un unico file con tutte le istruzioni). Le analisi, l'addestramento dell'AI e la CONFIG si gestiscono da **AVVIA_DEVELOPER.bat**.*
<!-- GUIDA:FINE -->

---

## Parte 3 — Developer: installazione, menu e opzioni

### Cos'è AskTrainMind

AskTrainMind è uno script Python che compila automaticamente le celle
**"Funzioni AI"** nel foglio Excel ETR1000, analizzando i documenti tecnici
PDF/DOCX presenti su OneDrive e confrontando le configurazioni di flotta.

All'avvio di `python funzioni_ai_filter.py` compare un menu:

```
  1) Esegui Funzioni AI e Requisiti
  2) Ricerca Funzioni
  3) Cerca riferimento pagina
  4) CONFRONTO SPECIFICO FUNZIONI-REQUISITI
  5) REQUISITI NON MATCHED TRA CONFIGURAZIONI
```

- **1** compila le celle "Funzioni AI" del foglio **Funzioni** e il foglio
  **Requisiti** (vedi [Opzione 1 — cosa succede nel file Excel](#opzione-1--cosa-succede-nel-file-excel)).
- **2** crea/aggiorna il foglio **Index Funzioni** con l'elenco delle funzioni
  dei documenti FRS di ogni configurazione e, per ognuna, il FUNC ID e la
  DESCRIZIONE FUNZIONE da usare nel foglio Funzioni (vedi [Opzione 2 — Ricerca Funzioni](#opzione-2--ricerca-funzioni-foglio-index-funzioni)).
- **3** compila solo le celle **Rif. Pagina** del foglio **Funzioni**
  (vedi [Opzione 3 — Cerca riferimento pagina](#opzione-3--cerca-riferimento-pagina)).
- **4** confronta per *Description* i requisiti dei documenti di un DOC ID
  (es. `FRS_Coupler`) in tutte le configurazioni e scrive l'esito nel foglio
  **Confronto Reqs** (vedi [Opzione 4 — Confronto specifico Funzioni-Requisiti](#opzione-4--confronto-specifico-funzioni-requisiti-foglio-confronto-reqs)).
- **5** elenca nel foglio **Reqs not matched** i requisiti del foglio
  Requisiti non MATCHED fra le configurazioni scelte (es. `VZI_Base`,
  `VZI_New14`, `VZ_FR`) con una nota che spiega la differenza (vedi
  [Opzione 5 — Requisiti non MATCHED](#opzione-5--requisiti-non-matched-tra-configurazioni-foglio-reqs-not-matched)).
  Viene eseguita automaticamente, su tutte le configurazioni, al termine
  dell'opzione 1.

Ogni opzione **cancella e ricrea** (o riscrive) i fogli che produce, così
contengono sempre l'ultimo aggiornamento (nessun testo vecchio accanto al
nuovo); prima di salvare, la versione precedente del file viene archiviata
in **`_OLD`** (vedi
[Archivio _OLD](#archivio-_old-versioni-precedenti-del-file-excel)).

All'avvio di ogni opzione viene chiesto se **aggiornare direttamente il
file DB Flotte** (default) oppure creare solo un **file RESULTS** (vedi
[File RESULTS](#file-results-db-flotte-non-modificato)).

#### Flusso di lavoro consigliato

1. **Opzione 2** → foglio *Index Funzioni* con le funzioni dei documenti e
   i FUNC ID / DESCRIZIONE FUNZIONE proposti;
2. nel foglio **Funzioni** si inseriscono le funzioni (col A = FUNC ID,
   col B = DESCRIZIONE FUNZIONE) e i link dei documenti;
3. **Opzione 3** → le celle *Rif. Pagina* vengono compilate dall'indice
   dei PDF;
4. **Opzione 1** → generazione di *Funzioni AI* e *Requisiti*.

### Utente e developer

AskTrainMind distingue due ruoli.

#### 👤 Utente (sola consultazione, non installa nulla)

All'utente si consegna la cartella **`User/`** (autonoma: `AskTrainMind.html`, Excel in sola lettura, PDF in
`User/docs/`, `LEGGIMI.txt`). Come consegnarla, aprirla e usarla è spiegato in [Parte 1](#parte-1--nuovo-utente-ricevere-aprire-e-usare-la-pagina); la guida dei
pulsanti 🧭 Esplora, 💬 Chiedi e ❔ Guida è la [Parte 2](#parte-2--guida-della-pagina-web).

#### 🛠️ Developer

Doppio clic su **`AVVIA_DEVELOPER.bat`** (oppure `python asktrainmind_dev.py`) apre il
**terminale developer**:

```
  ── OPZIONE 0 (aggiornamento incrementale dal foglio CONFIG + pagina DBFlotte1000.html)
    0) OPZIONE 0 TOTAL: aggiorna DB Flotte e pagina web dopo una modifica di Codice/Rev nel foglio CONFIG
   0C) OPZIONE 0 CREA DB CONFIG: crea solo la memoria Codice/Rev del foglio CONFIG
  ── ANALISI DEL DB FLOTTE (aggiornano il file Excel)
    1) Analisi completa FRS: sintesi AI delle funzioni + estrazione e confronto requisiti
    2) Ricostruisci l'indice delle funzioni dai PDF FRS
    3) Ricalcola il riferimento di pagina di ogni funzione nei PDF
    4) Confronto mirato dei requisiti per uno o più DOC ID
    5) Elenca i requisiti diversi fra configurazioni, con note AI
   18) Completa le Description mancanti nel foglio «Requisiti» (rilegge i PDF)
  ── INTELLIGENZA ARTIFICIALE (addestramento e conoscenza)
    6) Addestra l'AI: leggi i documenti tecnici (PDF/DOCX/TXT) e impara sigle e concetti
    7) Rispondi alle domande dell'AI (conferma, correggi o completa ciò che ha capito)
   15) Genera il foglio Excel «questionAI» con le domande dell'AI (da compilare con calma)
   16) Carica il foglio «questionAI» compilato: l'AI legge, cataloga e impara le tue risposte
    8) Insegna o correggi un concetto (sigla, loop, sensore, centralina, configurazione…)
    9) Consulta la conoscenza dell'AI (cerca, conferma le proposte, verifica i file)
   10) Prova la sezione «Chiedi» con la conoscenza aggiornata
   17) Verifica l'AI: la conoscenza appresa e la lettura dei documenti arrivano in «Chiedi»?
  ── CONFIGURAZIONE E PUBBLICAZIONE
   11) CONFIG: visualizza e modifica i parametri del programma (config.py)
   12) Verifica i prerequisiti (Python, pacchetti, Ollama, modello AI, Excel, documenti)
   13) Aggiorna la cartella User (pagina web offline + Excel per gli utenti)
   14) Apri l'anteprima web developer (server locale, con AI Ollama e ricerca nei PDF)
```

- `h N` descrive la voce N; `python asktrainmind_dev.py --run N` la esegue direttamente; `q` esce
  (la voce `0` è ora l'OPZIONE 0 TOTAL). Le voci si possono scrivere in minuscolo (`0c` = `0C`).
- **Voci 0 e 0C** (`python opzione0.py` / `python opzione0.py --crea-db-config`): aggiornamento incrementale
  dopo una modifica di Codice o Rev nel foglio CONFIG, descritto in
  [OPZIONE 0 — aggiornamento incrementale](#opzione-0--aggiornamento-incrementale-dal-foglio-config).
- Le voci 1-5 eseguono `funzioni_ai_filter.py --mode N --ask`, descritto sotto. Dopo la scelta vengono
  elencati e poi chiesti i parametri dell'opzione, come nel menu originale: aggiornamento del DB Flotte o solo
  file RESULTS e **ambito dell'analisi** — FRS, funzioni degli FRS scelti, configurazioni di treno — (tutte,
  vedi [Ambito dell'analisi](#ambito-dellanalisi-opzioni-1-5)); ripresa da interruzione, numero massimo di
  celle, sovrascrittura A/S/N, FUNC ID di partenza e Reqs not matched (opzione 1); ripresa da interruzione
  (opzione 3). I valori proposti con Invio sono quelli di CONFIG.
- **L'addestramento dell'AI** (voci 6-10, 15 e 16) è spiegato in **[Parte 4](#parte-4--lai-come-ragiona-e-come-si-addestra)**.
  Il modo più veloce per rispondere alle domande dell'AI è il **questionario Excel «questionAI»**:
  voce 15 per crearlo, compilazione libera della colonna gialla *LA TUA RISPOSTA*, voce 16 per caricarlo
  (`python asktrainmind_dev.py --questionai-export` / `--questionai-import "percorso.xlsx" [--from-id N]`).
  Se il caricamento si interrompe, quanto appreso resta salvato e il programma indica l'ID da cui ricaricare.
  La conoscenza è salvata in `knowledge/` (file JSON modificabili anche a mano) ed è usata
  in Chiedi, in Esplora e nei prompt delle analisi 1-5.
- **Voce 18** (`python req_desc_backfill.py [--dry-run]`): le celle del foglio *Requisiti* che riportano solo
  l'etichetta (`MISS VZI_BASE REQ…`, differenze) senza il testo ricevono la *Description* riletta dal PDF della
  configurazione; il file originale viene archiviato in `_OLD/`. Le nuove analisi (opzione 1) scrivono già sempre
  la Description nelle celle.
- **Voce 17** (`python verify_ai.py`): verifica che Chiedi mostri i concetti appresi (risposte del developer) e che
  le domande sul contenuto dei documenti citino il requisito atteso; rapporto in `RESULTS/verify_ai.txt`.
- **CONFIG** (voce 11): le modifiche vengono salvate in `config_overrides.json` e
  `config.py` non viene modificato.
- Dopo ogni voce che modifica dati o conoscenza la cartella `User/` viene rigenerata
  (`USER_AUTO_EXPORT`). Si può rigenerare anche a mano con la voce 13 o con `python export_user.py`.
- La voce 14 (`python asktrainmind_web.py --port 8765`) avvia il server web
  locale con le stesse pagine e in più la spiegazione AI con Ollama e la ricerca full-text nei PDF.

Installazione (solo developer): Python 3.10+ e `python -m pip install -r requirements.txt`; per le sintesi AI e
la spiegazione nell'anteprima web serve [Ollama](https://ollama.com) con il modello indicato in CONFIG
(`ollama pull <modello>`). La voce **12** verifica tutti i prerequisiti.

---

### Architettura dei file

| File | Ruolo |
|---|---|
| `funzioni_ai_filter.py` | Entry point e orchestratore principale |
| `excel_scanner.py` | Legge il foglio Excel e produce i `FillTarget` da compilare |
| `document_handler.py` | Scarica e estrae il testo dai PDF/DOCX |
| `ai_synthesizer.py` | Chiama Ollama e produce il testo per la cella |
| `llm_json.py` | Lettura tollerante del JSON prodotto dal modello (ripara le risposte troncate) |
| `requirements_extractor.py` | Estrae i requisiti dalle tabelle dei PDF (layout orizzontale e verticale) |
| `function_parser.py` | Parsing strutturato del testo estratto |
| `deterministic_comparator.py` | Confronto oggettivo (valori numerici, timer) senza LLM |
| `support_loader.py` | Carica i fogli di supporto Excel (Cartelle, Configurazioni) |
| `url_builder.py` | Costruisce gli URL SharePoint dai dati Excel |
| `index_funzioni.py` | Opzione 2 "Ricerca Funzioni": crea il foglio "Index Funzioni" |
| `func_id_proposer.py` | Opzione 2: FUNC ID e DESCRIZIONE FUNZIONE ricopiati o proposti per le funzioni dell'indice |
| `confronto_reqs.py` | Opzione 4 "Confronto specifico Funzioni-Requisiti": crea il foglio "Confronto Reqs" |
| `reqs_not_matched.py` | Opzione 5 (e fine opzione 1): ricrea il foglio "Reqs not matched" |
| `requisiti_sorter.py` | Ordina i blocchi del foglio Requisiti come i FUNC ID del foglio Funzioni |
| `old_archive.py` | Copia la versione precedente del file Excel in `_OLD/<data>_Opzione_<N>/` con `RICHIESTA.txt` |
| `run_options.py` | Parametri dell'opzione 1, file RESULTS (DB non modificato), elenco celle aggiornate, commenti "Not updated" |
| `opzione0.py` | Voci 0 e 0C: OPZIONE 0 TOTAL (STEP 0-5) e OPZIONE 0 CREA DB CONFIG |
| `config_db.py` | Memoria «FOGLIO CONFIG CODICE-REV FRS PER CONFIGURAZIONE» (`db_config/`), confronto fra versioni, ricerca dei file nelle cartelle `<configurazione>/CONFIG/<tipo>` |
| `rif_pagina.py` | Calcolo del "Rif. Pagina" dall'indice dei PDF (opzione 3 e inizio opzione 1) |
| `app_logging.py` | Log unico `asktrainmind.log` condiviso da tutto il codice (anche storico e script di debug), troncato automaticamente |
| `interrupt_guard.py` | Salvataggio dei progressi su interruzione (Ctrl+C), salvataggi automatici e punti di ripresa |
| `config.py` | Parametri globali (percorsi, modello AI, soglie) — vedi [Opzioni di configurazione](#opzioni-di-configurazione-configpy); in fondo applica i valori forzati di `config_overrides.json` |
| `AVVIA_WEB.bat` | Utente: apre `User/AskTrainMind.html` (pagina offline) |
| `asktrainmind_dev.py`, `AVVIA_DEVELOPER.bat` | Terminale developer: opzioni 1-5, addestramento AI, CONFIG, pubblicazione |
| `export_user.py` | Genera la cartella `User/` (pagina HTML autonoma con dati, conoscenza e guida + copia dell'Excel) |
| `asktrainmind_web.py` | Server web locale per il developer (anteprima con AI Ollama) |
| `webapp/server.py` | Server locale (Flask/waitress) e API della pagina web |
| `webapp/workbook.py` | Lettura del file Excel per la pagina web, con cache compressa e ricarica automatica quando il file cambia |
| `webapp/documents.py` | Ricerca dei PDF locali, pagine della funzione, anteprime, figure/tabelle, indice full-text SQLite |
| `webapp/qa.py` | Sezione "Chiedi": interpretazione delle domande, risposte (anche per tutte le configurazioni), ricerca veloce nei documenti e spiegazione AI in streaming |
| `webapp/explorer.py` | Sezione "Esplora": riepilogo compatto configurazioni → FRS → funzioni e dettaglio della singola funzione |
| `docsearch.py` | Lettura dei documenti per Chiedi: indice del testo di requisiti e paragrafi dei PDF di ogni funzione (incluso nella pagina offline come `dx`) e ricerca BM25 con traduzione italiano → termini inglesi dei documenti; replicata in JavaScript in `offline.js` |
| `req_desc_backfill.py` | Voce 18: completa le Description mancanti nel foglio Requisiti rileggendo i PDF |
| `verify_ai.py` | Voce 17: verifica automatica della conoscenza e della lettura dei documenti in Chiedi |
| `knowledge.py` | Conoscenza dell'AI: addestramento sui documenti, schede dei concetti, domande al developer, aggiunta dei concetti confermati ai prompt di Ollama (vedi [Parte 4](#parte-4--lai-come-ragiona-e-come-si-addestra)) |
| `knowledge/` | File della conoscenza: `glossario.json`, `domande.json`, `passaggi.json`, `fonti.json` |
| `webapp/tools.py` | Prerequisiti, CONFIG (descrizioni e valori forzati) e lancio delle opzioni, usati dal terminale developer |
| `webapp/static/` | Pagina web (HTML, CSS, JavaScript senza dipendenze esterne: `app.js` struttura/Chiedi/Guida, `explore.js` Esplora con PDF affiancati e requisiti, `offline.js` motore di risposta della pagina offline) |
| `README.md` | Unica guida del progetto; la Parte 2 è la guida della pagina web (pulsante ❔ Guida) |
| `understand.py` | Comprensione della domanda di Chiedi (tipo di richiesta, grandezza, documento, perimetro) e «🎓 Risposta AI»; replicato in `offline.js` |

---

### Flusso di esecuzione

```
Excel (ws_write) ──► excel_scanner.scan() ──► FillTarget[]
                                                    │
                         ┌──────────────────────────┘
                         ▼
              document_handler.download()     ← cerca file su OneDrive
              document_handler.extract_page_text()  ← estrae testo PDF
                         │
                         ▼
              function_parser.parse_function_structure()   ← parsing regex
              deterministic_comparator.compare_all()       ← diff oggettive
                         │
                         ▼
              ai_synthesizer.synthesize_with_comparison()  ← Ollama (1 chiamata/gruppo)
                         │
                         ▼
              ws_write.cell().value = testo formattato
              colore cella (Verde/Rosso/Nero/Grigio)
```

---

### Fogli necessari e fogli creati automaticamente

| Foglio | Se manca |
|---|---|
| **Funzioni** | **Obbligatorio.** Tutte le opzioni si fermano con un errore che elenca i fogli presenti. |
| **Requisiti** | Viene creato dopo "Funzioni" con le colonne FUNC ID, DESCRIZIONE, FRS, REQUISITO, CONFIGURAZIONE APPARTENENZA e una colonna per configurazione (prima VZI_Base, poi le configurazioni lette da CONFIG e Funzioni). Lo compila l'opzione 1; per le opzioni 4 e 5 serve che sia già compilato. |
| **Reqs not matched** | Viene creato e compilato dall'opzione 5 e alla fine dell'opzione 1. Se "Requisiti" è vuoto, il foglio nasce con la sola intestazione. |
| **Index Funzioni** | Viene creato e compilato dall'opzione 2, dopo "Reqs not matched", "Requisiti" o "Funzioni". |

### Ambito dell'analisi (opzioni 1-5)

Ogni opzione di analisi chiede, dopo la scelta DB Flotte/RESULTS, su cosa
lavorare (modulo `analysis_scope.py`):

1. **FRS** — elenco numerato dei DOC ID (col B del foglio CONFIG / col D del
   foglio Funzioni), es. `FRS_Line Voltage`;
2. **funzioni degli FRS scelti** — FUNC ID del foglio Funzioni collegati a
   quegli FRS, con la descrizione, es. `LV_Pantograph_Lifting`,
   `LV_Pantograph_Selection`;
3. **configurazioni di treno** — es. `VZI_Base, VZI_New14, VZ_FR`.

Si rispondono numeri dell'elenco, intervalli (`5-8`), nomi o una parte
univoca del nome (`pantograph lifting`), separati da virgola. **Invio** =
valore proposto, `*` = tutti. Un nome non riconosciuto o ambiguo
(es. `line volt` → `FPD_Line Voltage` / `FRS_Line Voltage`) annulla
l'esecuzione da riga di comando e viene richiesto nel terminale.
Da riga di comando: `--frs`, `--funcs` (`-f`), `--configs` (`-c`).

| Opzione | Effetto dell'ambito |
|---|---|
| 1 | solo le celle "Funzioni AI" e i requisiti delle funzioni/FRS/configurazioni scelti; **VZI_Base** (`REQ_BASE_CONFIG`) è sempre elaborata come riferimento del confronto. Nel foglio Requisiti le colonne e le voci di col E delle configurazioni non scelte restano invariate |
| 2 | foglio Index Funzioni ricreato solo con i DOC ID, le configurazioni e i FUNC ID scelti (commento `Elenco PARZIALE` in A1) |
| 3 | solo le celle "Rif. Pagina" dell'ambito |
| 4 | DOC ID da confrontare = FRS scelti (almeno uno; default `CONFRONTO_REQS_DOC_IDS`), solo le configurazioni scelte; con funzioni scelte solo i requisiti che il foglio Requisiti attribuisce a quelle funzioni (eseguire prima l'opzione 1) |
| 5 | solo i requisiti degli FRS/funzioni scelti, fra le configurazioni scelte (almeno due; default `REQS_NOT_MATCHED_CONFIGS`) |

Nei fogli ricreati (opzioni 2, 4, 5) un ambito limitato è indicato dal
commento in A1. Nell'opzione 1 le celle fuori ambito ricevono il commento
`Not updated` (vedi sotto).

---

### OPZIONE 0 — aggiornamento incrementale dal foglio CONFIG

Quando aggiorni nel foglio **CONFIG** il **Codice** (colonne con «File/Codice» o «Codice» in riga 3) o la
**Rev** (colonne con «Rev» in riga 3) di un documento per una configurazione (riga 1: `VZI_Base`, `VZI-6_R1`…),
l'**OPZIONE 0 TOTAL** aggiorna solo le funzioni e i requisiti toccati da quel documento e pubblica la pagina
web. Tutte le richieste all'utente compaiono nella console in **giallo**: dicono cosa fare nel file Excel e
come confermare.

| Voce | Comando | Cosa fa |
|---|---|---|
| **0** OPZIONE 0 TOTAL | `python opzione0.py` | esegue gli STEP 0-5 descritti sotto |
| **0C** OPZIONE 0 CREA DB CONFIG | `python opzione0.py --crea-db-config` | esegue solo lo STEP 0: legge il foglio CONFIG e salva la memoria, senza modificare il DB |

**Memoria «FOGLIO CONFIG CODICE-REV FRS PER CONFIGURAZIONE».** Per ogni documento del foglio CONFIG la memoria
contiene: DOC ID (colonna B), tipo di documento (sezione del foglio: FRS, FPD, FS, WT, EPL, GEN, ICD),
configurazione, Codice e Rev. È salvata in `db_config/config_db.json`, con una copia leggibile in
`db_config/config_db.csv`; la versione precedente resta in `db_config/config_db_prev.json`. Un documento
risulta **cambiato** se, per una configurazione, il Codice o la Rev sono diversi da quelli in memoria.
Conta anche un documento aggiunto o tolto.

**STEP 0 · Memoria.** Il programma legge la tabella attuale dal foglio CONFIG e la confronta con la memoria,
poi elenca i documenti cambiati.
- Alla **prima esecuzione**, se non c'è ancora una memoria, la crea come riferimento, non modifica il DB e
  passa allo STEP 5.
- Se nessun documento è cambiato, passa direttamente allo STEP 5.

**STEP 1 · Pulizia delle funzioni dei documenti FRS cambiati.** Per ogni funzione del foglio *Funzioni* con
quel DOC ID e quella configurazione, il programma cerca il file `<Codice>.pdf`
nella cartella `<configurazione>/CONFIG/FRS` sotto `ONEDRIVE_DOCS_ROOT` (DOC_FLOTTE) e sotto `docs/` del progetto.

| Situazione | Rif. Pagina | Funzioni AI | Link |
|---|---|---|---|
| file presente e link presente | svuotato | testo tolto, sfondo **bianco** | invariato |
| file assente, o link mancante | svuotato | **LINK DOCUMENTALE NON INSERITO** (sfondo salmone) | tolto se il file non c'è |

In entrambi i casi il programma svuota nel foglio *Requisiti* le celle della configurazione per i requisiti di
quelle funzioni e documento. Aggiorna anche la colonna dell'elenco delle configurazioni. Se, dopo la pulizia,
nessuna configurazione descrive più un requisito, la riga del requisito viene **eliminata**.

**Documenti non FRS cambiati** (FS, FPD, WT, EPL, GEN, ICD collegati da un link aggiuntivo nel foglio
*Funzioni*):
- Il loro *Rif. Pagina* (la cella subito sotto il link) diventa una **X rossa in grassetto**. La console
  elenca le celle da sanare.
- Inserisci a mano la pagina nuova al posto della X. Finché resta la X, la pagina web non mostra quel PDF e
  lo segnala con ✖.
- La X non blocca l'opzione: viene ricordata anche allo STEP 5 e alle esecuzioni successive.

**STEP 2 · Riferimento di pagina.** Per le funzioni dei documenti cambiati che hanno un file, il programma
ricalcola il *Rif. Pagina* con la stessa logica della voce 3.

1. I valori numerici trovati vengono scritti nel foglio.
2. Se restano riferimenti mancanti o non numerici (per esempio `14 utente - 1413`), la console elenca le
   celle. Inseriscile nel file Excel, salva e chiudi, poi rispondi **S** alla domanda *«Posso controllare il
   file excel per valutare se tutte le funzioni con link hanno un riferimento di pagina?»*.
3. Il programma ricontrolla:
   - i valori non numerici vengono chiesti di nuovo;
   - le celle lasciate vuote danno **FUNZIONE NON PRESENTE** in *Funzioni AI* (sfondo giallo);
   - le funzioni con pagina corretta ricevono *Funzioni AI* vuoto con sfondo bianco, e i loro requisiti
     vengono puliti come allo STEP 1.

**STEP 3 · CHECK.** Ogni funzione dei documenti cambiati deve trovarsi in uno di questi casi, e le sue celle
nel foglio *Requisiti* devono essere vuote (righe eliminate se non resta nessuna configurazione):

| Caso | Link | Rif. Pagina | Funzioni AI |
|---|---|---|---|
| **CASO 1** | assente | — | **LINK DOCUMENTALE NON INSERITO**, sfondo salmone |
| **CASO 2** | presente | vuoto | **FUNZIONE NON PRESENTE**, sfondo giallo |
| **CASO 3** | presente | numero di pagina | vuoto, sfondo bianco (da ricalcolare) |

Se c'è un'anomalia, la console indica la cella e il problema. Hai due modi per risolverla:
- correggila nel file Excel e rispondi **S**;
- rispondi **C** per far applicare al programma la correzione automatica.

**STEP 4 · Funzioni AI e Requisiti.** Per le sole celle del CASO 3 viene eseguita l'analisi della voce 1:
- sintesi *Funzioni AI*, similarità e match dei *Requisiti*;
- ambito limitato a DOC ID, funzioni e configurazioni aggiornati, più la base `VZI_Base` per il confronto;
- le altre celle non vengono toccate.

**STEP 5 · Pubblicazione.** Il file Excel è già aggiornato. Il programma crea la cartella
`dist/<AAAA-MM-GG>/` con:

| File | Contenuto |
|---|---|
| `DBFlotte1000.html` | la pagina web offline, con le stesse funzioni della pagina utente: Esplora, PDF affiancati, requisiti, approfondimenti e altri documenti CONFIG |
| copia del file Excel del DB Flotte | il DB aggiornato |
| `LEGGIMI.txt` | istruzioni per aprire la pagina |

Infine la memoria del foglio CONFIG viene aggiornata.

> Se interrompi l'opzione, rispondendo **q** o con Ctrl+C, la memoria **non** viene aggiornata: alla prossima
> esecuzione gli stessi documenti risultano ancora cambiati e il lavoro riprende da capo. La versione
> precedente del file Excel viene archiviata in `_OLD/` come per le altre opzioni.

### Opzione 1 — cosa succede nel file Excel

Passi eseguiti da `python funzioni_ai_filter.py` → scelta **1**, visti dal
punto di vista del file Excel (`EXCEL_PATH` in `config.py`).

0. **Parametri dell'elaborazione** — dal menu interattivo vengono chiesti
   (Invio = valore proposto; da riga di comando vedi
   [Come eseguire](#come-eseguire)):

   | Domanda | Default | Opzione CLI |
   |---|---|---|
   | Aggiornare il file DB Flotte o creare solo il file RESULTS | aggiorna il DB | `--results-only` |
   | Numero massimo di celle "Funzioni AI" da compilare | tutte | `--max-cells N` |
   | Sovrascrivere le celle "Funzioni AI" già compilate: `A` automatico (solo se il documento è cambiato), `S` rielabora tutte, `N` solo celle vuote | `A` | `--overwrite A/S/N` |
   | FUNC ID da cui partire | inizio foglio | `--start FUNC_ID` |
   | FRS da compilare (DOC ID: col B del foglio CONFIG / col D del foglio Funzioni, es. `FRS_Line Voltage`) — vedi [Ambito](#ambito-dellanalisi-opzioni-1-5) | tutti | `--frs "FRS_Line Voltage, FRS_Air Supply"` |
   | Funzioni degli FRS scelti | tutte | `--funcs "LV_Pantograph_Lifting"` |
   | Configurazioni di treno (VZI_Base sempre inclusa come riferimento) | tutte | `--configs "VZ_FR, VZ_ES"` |
   | Aggiornare il foglio "Reqs not matched" al termine (se no il foglio non viene toccato) | sì | `--no-reqs-not-matched` |

   **Esecuzione parziale** (solo alcuni FRS, funzioni o configurazioni, numero di celle limitato,
   FUNC ID di partenza, solo celle vuote, interruzione): le celle elaborate
   seguono la logica normale; le celle "Funzioni AI" con testo **non**
   elaborate e la cella FUNC ID delle funzioni non elaborate nel foglio
   Requisiti ricevono il commento **`Not updated`** (con data e motivo).
   I commenti dell'utente non vengono sovrascritti; il commento viene tolto
   quando la cella viene rielaborata e da un'esecuzione completa. Con il
   filtro FRS anche il "Rif. Pagina" dinamico è calcolato solo per gli FRS
   scelti, e i requisiti degli altri FRS della stessa funzione non vengono
   eliminati.
1. **Controlli iniziali** — verifica che Ollama sia attivo e che il file
   Excel esista; altrimenti si ferma senza toccare nulla.
2. **Apertura del file** — il file viene aperto due volte: una copia in sola
   lettura dei *valori* (per leggere link e formule già calcolati) e una
   copia di *scrittura*, l'unica che verrà salvata.
3. **Lettura dei fogli di supporto**
   - **Cartelle** cella D5 → radice dei percorsi dei documenti;
   - **CONFIG** e **MAN_CPR** → per ogni DOC ID e configurazione, il codice
     del documento da aprire.
4. **Aggiornamento "Rif. Pagina"** (se `RIF_PAGINA_DYNAMIC = True`) — per
   ogni funzione del foglio **Funzioni** la pagina viene ricavata
   dall'indice del PDF e scritta nella riga "Rif. Pagina":
   - verde se coincide con quella scritta a mano o se la cella era vuota;
   - rossa nel formato `32 utente - 34 dinamico` se diverge;
   - non toccata se non è calcolabile.
5. **Scansione del foglio Funzioni** — riga per riga si riconoscono:
   - riga funzione (col A = FUNC ID, col B = descrizione);
   - riga documento (col C = cartella `CONFIG`/`MAN_CPR`/…, col D = DOC ID,
     una colonna per configurazione con il link);
   - righe di dettaglio (col E = "Rif. Pagina", "Funzioni AI", …).

   Diventa un *obiettivo* ogni cella "Funzioni AI" la cui configurazione ha un
   link valido nella riga documento. Gli obiettivi sono raggruppati per
   (FUNC ID, DOC ID) così ogni funzione si analizza una volta per tutte le
   configurazioni. Con `--start FUNC_ID` le funzioni precedenti sono saltate.
6. **Controllo incrementale** (`RECHECK_MODE`) — per ogni gruppo:
   - livello 1: dimensione e data del PDF uguali all'ultima esecuzione →
     gruppo saltato, celle invariate;
   - livello 2: impronta del testo della sezione e della lista requisiti
     uguale → gruppo saltato; diversa → blocco "STORICO" nel log unico e
     rianalisi.
7. **Ricerca della sezione nel PDF** — partendo da "Rif. Pagina" si cerca il
   paragrafo della funzione nell'indice e se ne estrae il testo fino al
   paragrafo successivo (stesso livello o superiore: `3.3.4` termina a
   `3.3.5` o `3.4`; nei documenti senza numerazione al titolo successivo
   dell'indice, vedi [Strategia T](#strategia-t--paragrafi-senza-indice-numerico)).
   **Se il Rif. Pagina manca o non è valido** (anche dopo il calcolo
   dinamico) la configurazione viene saltata: funzione e requisiti non
   vengono analizzati né scritti.
8. **Estrazione dei requisiti** dalle tabelle e dal testo della sezione
   (gli ID citati dentro una Description non diventano nuovi requisiti).
   Nomi requisito equivalenti:
   - spazio dopo il punto: `2F_06.03.Zefiro Europe.CONCEPT. 165` =
     `2F_06.03.Zefiro Europe.CONCEPT.165`;
   - `Zefiro Europe`, `ZefiroEurope`, `Zefiro-Europe` (scritti sempre
     come `Zefiro-Europe`): `A.Zefiro Europe.B` = `A.Zefiro-Europe.B`;
   - ID spezzato su due righe della tabella (es. `2F _06 .03 .Zefiro-` /
     `EuropeCONCEPT393`): le due celle vengono ricomposte in un unico ID.
   Se due sezioni iniziano sulla stessa pagina, la prima termina al titolo
   della seconda (i requisiti della sezione successiva non vengono
   attribuiti alla funzione precedente).
9. **Foglio Requisiti**
   - cerca la riga della funzione (col A = FUNC ID, oppure col B =
     descrizione); se manca la crea;
   - col C = **FRS** (DOC ID del foglio Funzioni): sulla riga funzione
     tutti gli FRS della funzione, sulle righe requisito l'FRS da cui è
     stato estratto. Se manca, la colonna viene inserita automaticamente
     alla prima esecuzione dell'opzione 1 o 5;
   - sotto di essa, una riga per requisito: col D = numero requisito,
     col E = configurazioni in cui compare (colorate). I requisiti già
     presenti vengono aggiornati, i nuovi inseriti in coda al blocco;
   - colonne configurazione (da col F):
     - VZI_Base → testo completo del requisito, nero;
     - altre → `MATCHED` verde se identico alla base, altrimenti differenze
       in rosso;
     - VZI_Base assente → `MISS VZI_BASE REQ, MATCHED` (verde) o
       `MISS VZI_BASE REQ, FOUND DIFF` (rosso).
   - a fine esecuzione (anche se interrotta) il foglio viene **aggiornato
     e riordinato**:
     - i requisiti non più presenti nei documenti vengono eliminati
       (`REQ_REMOVE_STALE_ROWS`; solo per le funzioni analizzate per intero
       e le righe le cui configurazioni sono state tutte rianalizzate);
     - i blocchi funzione vengono disposti nell'ordine dei FUNC ID del
       foglio **Funzioni** (prima tutte le LV, poi AUX, BAT, …;
       `REQ_SORT_LIKE_FUNZIONI`). Una funzione assente dal foglio Funzioni
       va dopo l'ultima funzione con lo stesso prefisso;
     - il foglio **Reqs not matched** viene ricreato su tutte le
       configurazioni (`REQS_NOT_MATCHED_AFTER_OPTION1`, vedi opzione 5),
       salvo che l'utente abbia risposto di no alla domanda iniziale.
10. **Cella "Funzioni AI"** del foglio Funzioni:
    - VZI_Base → riassunto della funzione generato da Ollama, nero;
    - altre configurazioni → `RIFERIMENTO VZI_BASE, % SIMILARITY = X`,
      colorata in base alla percentuale (verde ≥ 90, verde ≥ 80,
      arancio ≥ 50, rosso sotto);
    - VZI_Base assente → `MISS VZI_BASE` + riassunto, nero;
    - in coda viene aggiunta la nota con la pagina usata.
11. **Salvataggio** — cache, storico e file Excel. Se il file è aperto in
    Excel si riprova ogni 5 s per 60 s, poi si salva
    `<nome>_backup.xlsx`. Log: `asktrainmind.log` (vedi [Log](#log-unico)).

Dettaglio di MATCHED e % SIMILARITY: [Parte 5](#parte-5--come-vengono-calcolati-matched-e--similarity).

---

### Opzione 2 — Ricerca Funzioni (foglio "Index Funzioni")

`python funzioni_ai_filter.py` → scelta **2** (oppure `--mode 2`).
Legge gli indici dei PDF; Ollama serve solo per proporre le descrizioni
delle funzioni nuove (`INDEX_FUNC_DESC_MODE = "ai"`, vedi punto 6).

1. **Lettura di CONFIG** — sezione *Functional Requirement Specification
   (FRS)*, righe da `FRS_Drive Control` a `FRS_EMS` (colonna B = DOC ID).
   Per ogni configurazione della riga 1 (VZI_Base, VZI_New14, VZ_FR, …) si
   legge:
   - il codice documento (prima colonna del gruppo);
   - la nota (terza colonna del gruppo, es. `manca`).

   Le celle `\` o `_` significano "nessun documento".
2. **Ricerca del file** in `ONEDRIVE_DOCS_ROOT`: prima nel percorso standard
   `<config>\CONFIG\FRS\<codice>.pdf`, poi per nome in tutte le
   sottocartelle (preferendo quelle con il nome della configurazione).
3. **Lettura delle funzioni** — nel sommario del PDF (prime pagine) si
   cerca il capitolo **Functional requirements**; sono funzioni:
   - i suoi figli diretti (es. `3.1 Coupling`, `3.2 Decoupling`);
   - i nipoti (es. `3.2.1 Pantograph - Lifting`) se
     `INDEX_FUNC_MAX_DEPTH = 2`.

   Le voci generiche (`Function Design`, `Requirements`, `Normal
   condition`, …) sono escluse. Se la numerazione non è gerarchica
   (documenti VSI) il livello si ricava dal rientro del titolo.
4. **Costruzione dell'elenco per DOC ID**:
   - prima tutte le funzioni di **VZI_Base**, nell'ordine dell'indice;
   - poi, configurazione per configurazione, si aggiungono in coda solo le
     funzioni **non già presenti**.

   Due titoli sono la stessa funzione se coincidono ignorando maiuscole,
   spazi e punteggiatura, oppure se la somiglianza è ≥
   `INDEX_FUNC_FUZZY_MATCH`.
5. **Scrittura del foglio** (rigenerato da zero a ogni esecuzione):

| Riga | Col A | Col B | Col C | Col D | Col E, F, … (una per configurazione) |
|---|---|---|---|---|---|
| 1 | `DOC ID / Funzione` | `Paragrafo` | `FUNC ID` | `DESCRIZIONE FUNZIONE` | nome configurazione |
| titolo blocco | DOC ID (es. `FRS_Air Supply`) | — | prefisso FUNC ID (es. `AIR`) | — | documento di riferimento (es. `3EST000225-7915`) |
| righe sotto | titolo funzione | paragrafo dell'indice (es. `3.1`, `3.2.1`) | FUNC ID | descrizione | `MATCHED` / `NOT FOUND` / `N/A` |

   Con `INDEX_FUNC_PROPOSE_IDS = False` le colonne C e D non vengono
   create e le configurazioni partono dalla colonna C (solo MATCHED,
   titolo e paragrafo).

   Il **Paragrafo** è quello del documento da cui la funzione è stata presa
   (VZI_Base se presente, altrimenti la prima configurazione che la
   contiene; il commento della cella indica configurazione, documento e
   pagina). Il paragrafo nelle altre configurazioni è nel commento della
   rispettiva cella `MATCHED`. Per i documenti VSI senza numerazione
   gerarchica il paragrafo è ricostruito dal rientro del sommario.

   Valori nella riga titolo:

| Valore | Significato |
|---|---|
| `codice` | documento trovato e letto (commento = percorso del file) |
| `codice (manca)` | documento segnato `manca` in CONFIG e non trovato |
| `codice (file non trovato)` | codice presente in CONFIG ma file assente |
| `codice (indice 'Functional requirements' non trovato)` | PDF senza quel capitolo nel sommario |
| `\` | nessun documento per quella configurazione |

   Valori nelle righe funzione:

| Valore | Significato |
|---|---|
| `MATCHED` (verde) | la funzione è presente nel documento della configurazione (commento = paragrafo e pagina) |
| `NOT FOUND` (rosso) | documento letto ma funzione assente |
| `N/A` (grigio) | documento non disponibile per la configurazione |

   Le sotto-funzioni sono rientrate e non in grassetto.
6. **FUNC ID e DESCRIZIONE FUNZIONE** (colonne C e D, se
   `INDEX_FUNC_PROPOSE_IDS = True`) — sono i valori da riportare nelle
   colonne A e B del foglio **Funzioni**:
   - funzione **già presente** nel foglio Funzioni (stesso DOC ID e FUNC ID
     corrispondente al titolo del paragrafo) → valori **ricopiati**, in nero;
   - funzione **nuova** → valori **proposti**, in blu corsivo. La
     convenzione è appresa dalle funzioni già presenti:
     - **FUNC ID** = `<PREFISSO>_<titolo del paragrafo>`: il prefisso è
       quello usato dalle funzioni dello stesso documento
       (`FRS_Air Supply` → `AIR`), il titolo ha spazi e ` - ` sostituiti da
       `_` (`Provision for Tilt system` → `AIR_Provision_for_Tilt_system`).
       Per le sotto-funzioni si antepone il titolo del **paragrafo padre**
       se le funzioni esistenti lo fanno, se il titolo è troppo generico
       (`Activation` → `BAT_Battery_Contactors_Activation`) o se il FUNC ID
       è già usato. Senza funzioni esistenti il prefisso si ricava dal
       titolo del documento (`INDEX_FUNC_ID_PREFIX_MAP` per imporlo);
     - **DESCRIZIONE** = una frase in italiano generata da Ollama nello
       stile delle descrizioni esistenti (passate come esempi), a partire
       dal titolo del documento, dal paragrafo padre e dal testo del
       paragrafo letto alla pagina dell'indice. Se Ollama non è disponibile
       si usa `INDEX_FUNC_DESC_TEMPLATE`. Le descrizioni generate sono
       salvate in `INDEX_FUNC_DESC_CACHE_FILE` e riusate alle esecuzioni
       successive.

   Il commento della cella FUNC ID indica l'origine (riga del foglio
   Funzioni, oppure prefisso, paragrafo padre e modalità della descrizione).
7. **Salvataggio** del file Excel (stessa logica dell'opzione 1).

---

### Opzione 3 — Cerca riferimento pagina

`python funzioni_ai_filter.py` → scelta **3** (oppure `--mode 3`).
Non usa Ollama.

Esegue da solo il passaggio "Rif. Pagina" che l'opzione 1 compie
all'inizio (punto 4 dell'opzione 1): per ogni funzione del foglio
**Funzioni** con un link documento valido, la pagina viene ricavata
dall'indice del PDF e scritta nella riga "Rif. Pagina" (verde se coincide
con il valore a mano o se la cella era vuota, rossa `32 utente - 34
dinamico` se diverge, non toccata se non calcolabile). Accetta `--start
FUNC_ID` per partire da una funzione. Si usa dopo aver inserito nel foglio
Funzioni le nuove funzioni e i link dei documenti, prima dell'opzione 1.

**Lettura dell'indice resiliente al formato.** L'indice del PDF viene letto
con più metodi e si tiene il più completo:
- indice nativo (segnalibri) o testo "Contents" con indici numerici;
- indici su una riga e titolo/pagina sulla successiva (documenti Hitachi,
  es. FA020026053, FA020025419, FA020026562/3, FA020025252);
- indice senza numeri di paragrafo, con font/rientri diversi (documenti
  VSI, es. FA020022675): i livelli vengono ricavati dal rientro dei titoli
  e il paragrafo è riconosciuto nel corpo dal **titolo**;
- numerazione piatta (1, 2, 3…) ricostruita come gerarchia.

La funzione viene cercata anche tra i **sottoindici** (es. `3.3.4 Level 1
Alarm` per `BOG_Level_1_Alarm`): titolo del paragrafo e titolo del padre
concorrono al punteggio e i numeri nel FUNC ID devono coincidere (Level 1
≠ Level 2).

**Riepilogo finale.** Al termine viene stampato (console e log) un
riepilogo a tabella con:
- ❌ **riferimenti non trovati** — FUNC ID, configurazione, DOC ID, pagina
  utente e motivo; la cella resta invariata e, senza Rif. Pagina,
  l'opzione 1 non analizza quella funzione;
- ⚠ **riferimenti divergenti** — pagina utente, pagina dinamica e
  paragrafo trovato, da verificare;
- il numero dei documenti non applicabili (senza indice funzionale).

---

### Opzione 4 — Confronto specifico Funzioni-Requisiti (foglio "Confronto Reqs")

`python funzioni_ai_filter.py` → scelta **4** (oppure `--mode 4`, o
direttamente `--doc "FRS_Coupler"`). Non usa Ollama.

Serve a verificare se i requisiti di un documento sono presenti, con la
**stessa Description**, nei documenti di tutte le configurazioni.

1. **Scelta del DOC ID** — è l'FRS dell'[ambito](#ambito-dellanalisi-opzioni-1-5)
   (elenco numerato dei DOC ID; numeri, nomi o parte univoca, es. `FRS_Coup`),
   insieme alle funzioni e alle configurazioni da confrontare.
   Con `--doc`/`--frs` la scelta si passa da riga di comando; con `--mode 4`
   fuori da un terminale si usa `CONFRONTO_REQS_DOC_IDS` di `config.py`.
2. **Documenti** — dalla riga del DOC ID in CONFIG si legge il codice del
   documento di ogni configurazione e lo si cerca in `ONEDRIVE_DOCS_ROOT`
   (stessa ricerca dell'opzione 2).
3. **Requisiti** — da ogni documento si estraggono tutti i requisiti
   (tabelle con colonna **Nr** e blocchi verticali con campo **ID**) con il
   campo **Description**.
4. **Confronto** — ogni requisito (partendo da VZI_Base) viene cercato negli
   altri documenti per Description (uguale ignorando maiuscole, spazi,
   virgolette e trattini). Le Description vuote o in
   `CONFRONTO_REQS_IGNORE_DESCRIPTIONS` (`DELETED`) si confrontano per Nr/ID.
5. **Foglio "Confronto Reqs"** — rigenerato a ogni esecuzione, subito dopo
   **Index Funzioni**. Per ogni DOC ID una riga titolo (codice del documento
   e numero di requisiti per configurazione), poi una riga per requisito:

| Colonna | Significato |
|---|---|
| `DOC ID / Requisito` | Nr/ID del requisito |
| `Nr / ID` | campo da cui è letto: `Nr` (tabella orizzontale) o `ID` (tabella verticale) |
| `Description` | testo confrontato |
| una per configurazione | `MATCHED` (verde) = stessa Description e stesso Nr/ID; `MATCHED DIFFERENT ID` (arancio) + Nr/ID della configurazione = stessa Description con Nr/ID diverso; `MISS` (rosso) = Description non trovata (commento se lo stesso Nr/ID esiste con Description diversa); `N/A` = la configurazione non ha il documento |

   Un requisito con `MATCHED` in tutte le configurazioni ha la stessa
   Description in tutti i documenti del DOC ID.
6. **Salvataggio** del file Excel (stessa logica dell'opzione 1).

---

### Opzione 5 — Requisiti non MATCHED tra configurazioni (foglio "Reqs not matched")

`python funzioni_ai_filter.py` → scelta **5** (oppure `--mode 5`, o
direttamente `--configs "VZI_Base, VZI_New14, VZ_FR"`). Viene eseguita anche
in automatico al termine dell'opzione 1 con **tutte** le configurazioni.

1. **Scelta delle configurazioni** (con FRS e funzioni: vedi
   [Ambito](#ambito-dellanalisi-opzioni-1-5)) — viene mostrato l'elenco numerato delle
   configurazioni. Si
   indicano, separati da virgola, nomi (maiuscole indifferenti) o numeri;
   **Invio = tutte** (o `REQS_NOT_MATCHED_CONFIGS` di `config.py`). Servono
   almeno due configurazioni.
2. **Analisi del foglio Requisiti** — un requisito è *non MATCHED* fra le
   configurazioni scelte se:
   - manca in almeno una configurazione (cella vuota e configurazione non
     elencata in col E);
   - oppure è presente ma con testo diverso: celle con differenze in rosso,
     `MISS VZI_BASE REQ, FOUND DIFF`, `MISS VZI_BASE REQ`. Due configurazioni
     entrambe `MATCHED` (o entrambe `MISS VZI_BASE REQ, MATCHED`) sono uguali
     fra loro.
3. **Foglio "Reqs not matched"** — cancellato e ricreato a ogni chiamata,
   subito dopo **Requisiti**; righe nell'ordine del foglio Funzioni:

| Colonna | Contenuto |
|---|---|
| `FUNC ID` / `DESCRIZIONE FUNZIONE` | Funzione del requisito |
| `FRS` | DOC ID da cui è estratto il requisito (colonna FRS del foglio Requisiti) |
| `REQUISITO` | Nr/ID del requisito |
| una per configurazione scelta | `X` dove il requisito è presente |
| `Descrizione` | Testo (Description) del requisito |
| `Note AI` | Differenze rilevate (es. `Requisito non trovato per la configurazione VZ_FR.`, `VZ_FR: requisito diverso da VZI_Base — …`) seguite da una breve spiegazione in italiano, generata da Ollama, del requisito e della differenza funzionale, tecnica od operativa |

   Quando a una funzione mancano **tutti** i requisiti di una configurazione
   la nota invita a verificare documento e Rif. Pagina. Le note AI sono in
   cache (`REQS_NOT_MATCHED_AI_CACHE_FILE`) e i prompt identici vengono
   elaborati una sola volta. Il foglio contiene **sempre tutti** i requisiti
   non MATCHED: con `REQS_NOT_MATCHED_AI_MAX_CALLS = 0` (default) non c'è
   limite alle note AI; se si imposta un limite, le righe oltre il limite
   vengono comunque scritte con la nota «[Nota AI non generata: limite …]»
   (warning nel log) e le esecuzioni successive le completano.
   Senza Ollama la nota riporta solo le differenze.
   La Description dei requisiti `MATCHED` viene letta dall'archivio
   `REQ_DESC_CACHE_FILE` alimentato dall'opzione 1 oppure dalla stessa ID
   presente in un'altra riga del foglio Requisiti. Se un requisito manca in
   una configurazione per la funzione ma, in quella configurazione, compare
   sotto un'altra funzione, la nota lo indica (probabile sconfinamento di
   sezione: verificare il Rif. Pagina).
   - **Link documentale mancante**: se per una configurazione il foglio
     Funzioni non ha il link al documento dell'FRS, la nota riporta
     «Mancanza link documentale per l'FRS <FRS> nella configurazione <cfg>
     (inserire il link nel foglio Funzioni).» e la cella della
     configurazione è colorata in arancio chiaro con un commento.
   - **Requisiti simili**: al termine, i requisiti con ID diverso ma
     Description simile (≥ `REQS_NOT_MATCHED_SIMILAR_MIN`, stesso confronto
     di somiglianza del programma) vengono messi in righe contigue, con
     l'ID evidenziato in giallo chiaro e la nota «Requisito simile a <ID>
     (somiglianza …; presente in …)».
4. **Salvataggio** del file Excel (stessa logica dell'opzione 1).

---

### Archivio _OLD (versioni precedenti del file Excel)

Ogni opzione, **prima** di salvare per la prima volta il file Excel, ne
copia la versione precedente in

```
<cartella del file Excel>/_OLD/<AAAA-MM-GG_hh-mm-ss>_Opzione_<N>/
    DB Flotte ETR1000 Ver_1.8.xlsx   file su cui è stata richiesta l'opzione
    RICHIESTA.txt                    dettaglio della richiesta (vedi sotto)
```

`RICHIESTA.txt` contiene:
- **opzione richiesta** e data;
- **parametri scelti dall'utente** (aggiornamento DB o RESULTS, numero di
  celle, sovrascrittura, FUNC ID di partenza, FRS, "Reqs not matched", DOC
  ID, configurazioni);
- **ambito dell'elaborazione** (celle candidate, funzioni, FRS,
  configurazioni confrontate) e fogli ricreati/aggiornati;
- **aggiornamento del file**: DB aggiornato direttamente oppure percorso del
  file RESULTS da cui copiare le celle;
- **celle aggiornate**, per foglio e per funzione/FRS (es.
  `LV_Pantograph_Lifting / FRS_Line Voltage: F23, H23`, blocchi del foglio
  Requisiti come `A13:L79`, Rif. Pagina modificati, fogli ricreati per
  intero) e numero di celle marcate `Not updated`;
- **esito** (completata / interrotta).

Una sola copia per esecuzione (gli autosalvataggi non creano altre
cartelle); se l'opzione non modifica il file non viene archiviato nulla.
Il file aggiornato resta in `EXCEL_PATH`. Parametri: `OLD_ARCHIVE_ENABLED`,
`OLD_ARCHIVE_DIR`, `OLD_ARCHIVE_MAX_CELL_LINES`.

---

### File RESULTS (DB Flotte non modificato)

Se all'avvio si risponde **n** alla domanda "Aggiornare direttamente il file
DB Flotte?" (o si usa `--results-only`), il DB Flotte **non viene
modificato** e i fogli impattati dall'opzione vengono scritti in

```
<cartella del file Excel>/RESULTS/RESULTS_<AAAA-MM-GG_hh-mm-ss>_Opzione_<N>.xlsx
```

- lo storico incrementale non viene aggiornato, cosi' una successiva
  esecuzione che aggiorna il DB rielabora comunque le celle;
- solo i fogli impattati (es. opzione 1: Funzioni, Requisiti, Reqs not
  matched), con lo **stesso layout** del DB Flotte (stesse righe, colonne,
  formati e commenti `Not updated`): le celle si copiano direttamente;
- le formule sono sostituite dal loro valore (i fogli di origine non sono
  inclusi);
- il foglio **RESULTS info** riporta parametri e celle aggiornate.

La richiesta viene comunque tracciata in `_OLD` (copia del DB di partenza +
`RICHIESTA.txt` con il percorso del file RESULTS). Parametri:
`UPDATE_DB_DEFAULT`, `RESULTS_DIR`.

---

### Interruzione e ripresa dell'esecuzione

Con `SAVE_PROGRESS = True` (predefinito) l'esecuzione può essere fermata in
qualsiasi momento con **Ctrl+C** (o Ctrl+Break) senza perdere il lavoro:

| Opzione | Cosa viene salvato all'interruzione | Alla ripartenza |
|---|---|---|
| 1 — Funzioni AI e Requisiti | Celle "Funzioni AI" e righe "Requisiti" già scritte, Rif. Pagina già calcolati, storico, cache dei confronti requisiti. Le righe requisito inserite ma non completate vengono tolte | Riparte dalla funzione interrotta; le celle già compilate e invariate vengono saltate (`RECHECK_MODE`) |
| 2 — Ricerca Funzioni | Foglio "Index Funzioni" con i DOC ID analizzati fino a quel momento (commento "Elenco PARZIALE" in A1), analisi dei PDF e descrizioni AI in cache | Rigenera il foglio completo; i PDF già analizzati e le descrizioni già generate vengono ripresi dalla cache |
| 3 — Cerca riferimento pagina | Celle "Rif. Pagina" già calcolate | Riparte dalla funzione interrotta |
| 4 — Confronto specifico Funzioni-Requisiti | Foglio "Confronto Reqs" con i DOC ID già confrontati | Rilanciare l'opzione |
| 5 — Requisiti non MATCHED | Foglio "Reqs not matched" completo; le note AI non ancora generate riportano solo le differenze | Rilanciare l'opzione (le note già generate sono in cache) |

Inoltre:

- nell'opzione 1 il file viene salvato anche ogni `AUTOSAVE_EVERY_N_GROUPS`
  funzioni, così anche una chiusura brusca (finestra chiusa, PC spento) perde al
  massimo le ultime funzioni;
- il file Excel viene scritto su un file temporaneo e poi sostituito: un
  secondo Ctrl+C durante il salvataggio viene rimandato alla sua conclusione;
- dal menu interattivo viene chiesto se riprendere dalla funzione interrotta;
  con `--mode` la ripresa è automatica, `--start` ha sempre la precedenza;
- nessuna colonna viene aggiunta ai fogli: i dati di ripresa stanno in
  `%LOCALAPPDATA%\FunzioniAI\progress_state.json`;
- il programma termina con codice di uscita `130` quando è stato interrotto.

Per disattivare tutto: `SAVE_PROGRESS = False`. Per ricominciare da capo
anziché riprendere, rispondere `n` alla domanda del menu oppure cancellare
`progress_state.json`.

---

### Struttura della cella "Funzioni AI"

#### Schema attuale (sigla di similarità)

| Configurazione | Contenuto della cella | Colore |
|---|---|---|
| `VZI_Base` | riassunto della funzione | nero |
| altre configurazioni | `RIFERIMENTO VZI_BASE, % SIMILARITY = X, X>90%` (oppure `X<90%`) + eventuale elenco `DIFFERENZE RILEVANTI:` | verde grassetto ≥ 90 · verde ≥ 80 · arancione ≥ 50 · rosso ≥ 25 · rosso grassetto < 25 |
| base assente | `MISS VZI_BASE` + riassunto | nero |
| nessun link al documento | `LINK DOCUMENTALE NON INSERITO` (esclusa dal confronto) | nero grassetto |
| link presente ma documento non trovato | `RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO` (esclusa dal confronto) | nero grassetto |

La percentuale è una **similarità funzionale**: misura se le due funzioni hanno lo stesso significato,
senza contare l'impaginazione. Le grandi differenze funzionali o d'impianto (valori e soglie diversi,
requisiti presenti in una sola configurazione, contenuto molto diverso, centraline e apparecchiature
diverse) abbassano la percentuale e vengono elencate in cella. Il calcolo è descritto in
[Parte 5](#parte-5--come-vengono-calcolati-matched-e--similarity) (§ 4).

#### Schema precedente (percorso LLM di riserva)

Il percorso LLM, non più usato di default, compila la cella in **tre sezioni**:

#### Sezione 1 — Descrizione funzionale
Breve descrizione in italiano (3-5 frasi) di cosa fa la funzione
in quella specifica configurazione, basata sul testo del documento.

```
Il sistema di alzamento pantografo gestisce la selezione e il sollevamento
del pantografo corretto in base al paese di operazione e al sistema di
tensione di linea selezionato dal conducente. Il TCMS invia il comando
al PCU tramite bus IP specificando il tipo di pantografo da alzare.
```

#### Sezione 2 — Confronto con altre configurazioni
Testo leggibile in italiano che spiega se la configurazione è uguale
o diversa rispetto alle altre e **perché**, con motivazione tecnica esplicita.

Esempi:
```
CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_Base è equivalente a VZI_FR: entrambe le configurazioni implementano
la stessa logica di alzamento con gli stessi valori di soglia (750 kPa, 35 s).

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_ES è differente da VZI_Base a causa dei differenti valori parametrici
nel funzionamento nominale: la soglia di pressione è 800 kPa invece di
750 kPa e il timeout di rilevamento guasto è 40 s invece di 35 s.
```

#### Sezione 3 — Dettaglio tecnico
Checklist delle categorie funzionali analizzate, differenze parametriche
rilevate automaticamente, score di equivalenza (0-100).

```
ANALISI FUNZIONALE:
  • Scopo funzionale: IDENTICAL
  • Logica operativa: IDENTICAL
  • Prestazioni: DIFFERENT
  • Comportamento in guasto: IDENTICAL

DIFFERENZE PARAMETRICHE (rilevate automaticamente):
  • parametri numerici: soglia pressione 800 vs 750 kPa

Score equivalenza funzionale: 68/100
```

---

### Colorazione celle

> La tabella si riferisce al percorso LLM di riserva. Per la sigla di similarità attuale valgono i colori
> dello [schema attuale](#schema-attuale-sigla-di-similarità).

| Colore | Significato | Condizione |
|---|---|---|
| 🟢 **Verde** | Configurazioni equivalenti | Score ≥ 75, nessuna diff. funzionale critica |
| 🔴 **Rosso** | Differenze funzionali reali | Score < 75 o ≥ 2 categorie DIFFERENT o ≥ 3 diff. parametriche |
| ⚫ **Nero** | Incerto o unica configurazione | Score borderline, o unica config disponibile |
| ⬜ **Grigio** | Errore | Documento non trovato, PDF scansionato, errore LLM |

---

### Logica di estrazione testo dal PDF

#### Strategia A — Indice trovato (caso normale)
1. Cerca tutti gli indici numerici nella pagina iniziale (es. `3.2.1`)
2. Abbina l'indice al `func_id` tramite confronto parole chiave
3. Legge le pagine successive includendo tutti i figli (`3.2.1.x`)
4. Si ferma al primo indice fratello o superiore (`3.2.2`, `3.3`)

Le sotto-funzioni sono gestite: se nel foglio Funzioni è indicata
`3.3.4 Level 1 Alarm`, il testo include `3.3.4.x` e si ferma a `3.3.5`
(sottoindice successivo) o a `3.4` (livello superiore).

#### Strategia T — Paragrafi senza indice numerico
Alcuni documenti (es. FA020022675) non numerano i paragrafi: la funzione è
identificata solo dal titolo (es. "Car ID and Vehicle Type", pag. 13–14).
In questo caso il paragrafo viene localizzato nell'indice del PDF tramite
`rif_pagina.locate_section`, il testo parte dal titolo e si ferma al titolo
successivo dello stesso livello o superiore ("MCM Enabling"). I titoli
standard interni a ogni funzione ("Function Design", "Requirements",
"Failure cases"…) non chiudono la sezione. Gli stessi confini delimitano
la ricerca dei requisiti nelle tabelle.

#### Strategia B — Nessun indice abbinabile (fallback)
Usata quando il titolo del documento è in una lingua diversa
dal `func_id` e non c'è corrispondenza testuale.
Calcola la similarità keyword tra pagine successive e la pagina
iniziale. Si ferma sotto la soglia `SIMILARITY_THRESHOLD`.

#### Pagine parziali
- **Pagina iniziale parziale**: la pagina inizia con un'altra sezione
  prima della nostra funzione → il testo prima dell'indice viene escluso
- **Pagina finale parziale**: l'ultima pagina contiene sia la nostra
  funzione sia l'inizio della successiva → il testo viene troncato
  all'inizio della nuova sezione

La nota pagina nella cella riflette questi casi:
```
Pag. iniziale: parte di pag.8 — Pag. finale: parte di pag.14.
Pag. iniziale: pag.8 — Pag. finale: pag.14.
Pag. di riferimento: pag.8.
```

---

### Casistiche possibili nelle celle

#### Caso 1 — Funzione identica in tutte le configurazioni 🟢
```
[Descrizione funzionale...]

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_Base è equivalente a VZI_FR e VZI_ES: tutte le configurazioni
implementano la stessa logica con gli stessi parametri operativi.

ANALISI FUNZIONALE:
  • Scopo funzionale: IDENTICAL
  • Logica operativa: IDENTICAL
  • Prestazioni: IDENTICAL
  ...
Score equivalenza funzionale: 92/100
Pag. iniziale: pag.8 — Pag. finale: pag.14.
```

#### Caso 2 — Differenze parametriche tra configurazioni 🔴
```
[Descrizione funzionale...]

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_ES è differente da VZI_Base a causa dei differenti valori parametrici:
la soglia di pressione è 800 kPa invece di 750 kPa.

ANALISI FUNZIONALE:
  • Prestazioni: DIFFERENT
  ...
DIFFERENZE PARAMETRICHE (rilevate automaticamente):
  • parametri numerici: 800 kPa vs 750 kPa
Score equivalenza funzionale: 62/100
Pag. iniziale: pag.13 — Pag. finale: parte di pag.19.
```

#### Caso 3 — Caso borderline (revisione manuale) ⚫
```
[Descrizione funzionale...]

CONFRONTO CON ALTRE CONFIGURAZIONI:
VZI_FR presenta una differenza parziale rispetto a VZI_Base nella
gestione del guasto: il comportamento è simile ma con una sequenza
di reset leggermente diversa.

⚪ Caso non classificabile con certezza: revisione manuale raccomandata.
Score equivalenza funzionale: 67/100
Pag. di riferimento: pag.8.
```

#### Caso 4 — Unica configurazione disponibile ⚫
```
[Descrizione funzionale...]

Unica configurazione disponibile — nessun confronto effettuato.
Pag. iniziale: pag.5 — Pag. finale: pag.9.
```

#### Caso 5 — Link mancante o documento non trovato ⚫ (nero grassetto)
```
LINK DOCUMENTALE NON INSERITO
```
oppure
```
RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO
```
Il primo testo compare quando nel foglio *Funzioni* manca il link al documento della configurazione. Il secondo
compare quando il link c'è ma è `#N/A`, l'URL non si può costruire o il PDF non si trova. La configurazione
viene **esclusa dal confronto** con le altre (nessuna similarità e nessun requisito confrontato). Con
`FUNC_MARK_LINK_ISSUES = False` si torna al comportamento precedente: configurazione saltata, cella intatta,
oppure `[Testo non estratto: pag.13 di FA020022045]` in grigio.

#### Caso 6 — PDF scansionato (immagine senza testo) ⬜ (grigio)
```
[Testo non disponibile nel documento per questa pagina]
```

---

### Opzioni di configurazione (`config.py`)

Tutte le impostazioni stanno in **`config.py`**: è l'unico file da modificare.
Ogni opzione è una normale assegnazione Python; per cambiarla si modifica il
valore e si salva il file, che verrà riletto all'esecuzione successiva.

```python
# Esempi di modifica
MAX_CELLS_PER_RUN  = 0                    # numero  → nessun limite
START_FROM_FUNC_ID = ""                   # testo   → parti dall'inizio
SAVE_PROGRESS      = False                # booleano: True / False
INDEX_FUNC_ID_PREFIX_MAP = {"FRS_Drive Control": "DRV"}   # dizionario
EXCEL_PATH = Path(r"D:\Dati\DB Flotte ETR1000.xlsx")      # percorso (r"..." per i \)
```

Regole generali: i testi vanno tra virgolette, i booleani sono `True`/`False`
(maiuscola iniziale), le soglie 0–1 sono frazioni (`0.9` = 90 %), le soglie
0–100 sono percentuali. Se un'opzione viene cancellata, i moduli che la
leggono con `getattr` usano il valore predefinito indicato qui sotto.

#### Percorsi e fogli

| Opzione | Valore | Significato |
|---|---|---|
| `EXCEL_PATH` | `C:\__SCRIPTS\AskTrainMind\DB Flotte ETR1000 Ver_1.8.xlsx` | File Excel da compilare |
| `ONEDRIVE_DOCS_ROOT` | cartella `DOC_FLOTTE` di OneDrive | Radice dei documenti PDF sincronizzati |
| `SHEET_FUNZIONI` / `SHEET_REQUISITI` / `SHEET_CONFIG` / `SHEET_CARTELLE` / `SHEET_MAN_CPR` / `SHEET_INDEX_FUNZIONI` | `"Funzioni"`, `"Requisiti"`, `"CONFIG"`, `"Cartelle"`, `"MAN_CPR"`, `"Index Funzioni"` | Nomi dei fogli (cambiarli solo se si rinominano i fogli nel file) |
| `FUNZIONI_AI_LABEL` | `"Funzioni AI"` | Etichetta (colonna E) delle righe da compilare |
| `CARTELLE_BASE_URL_ROW` / `_COL` | `5` / `4` | Cella del foglio Cartelle con l'URL SharePoint di base |

#### Modello AI (Ollama)

| Opzione | Valore | Significato |
|---|---|---|
| `OLLAMA_MODEL` | `"qwen2.5:7b-instruct"` | Modello locale; es. `"qwen2.5:14b-instruct"` se c'è RAM/VRAM sufficiente |
| `OLLAMA_KEEP_ALIVE` | `"30m"` | Tempo per cui il modello resta caricato fra due chiamate |
| `OLLAMA_NUM_CTX` | `8192` | Finestra di contesto (token) |
| `OLLAMA_NUM_PREDICT` / `OLLAMA_NUM_PREDICT_MAX` | `300` / `1536` | Token minimi in uscita / tetto del budget calcolato automaticamente |
| `LLM_PARALLEL_WORKERS` | `3` | Chiamate contemporanee (1 = sequenziale; GPU 3–4, CPU 2) |

#### Esecuzione

| Opzione | Valore | Significato |
|---|---|---|
| `MAX_CELLS_PER_RUN` | `4` | Celle "Funzioni AI" per esecuzione (0 = nessun limite) |
| `AI_CALL_DELAY_SECONDS` | `0.0` | Pausa fra un gruppo e l'altro |
| `START_FROM_FUNC_ID` | `"BOG_Hotbox_Detection"` | FUNC ID da cui partono le opzioni 1 e 3 (`""` = inizio foglio); `--start` ha la precedenza |
| `SIMILARITY_THRESHOLD` | `0.26` | Soglia della Strategia B (sezione trovata per somiglianza testuale) |
| `MAX_SECTION_PAGES` | `25` | Pagine lette al massimo dopo l'inizio di una sezione |
| `LLM_SCORE_GREEN` / `LLM_SCORE_RED` | `80` / `60` | Score del vecchio percorso di sintesi: ≥ verde, < rosso |

#### Salvataggio dei progressi e ripresa

| Opzione | Valore | Significato |
|---|---|---|
| `SAVE_PROGRESS` | `True` | Salva il lavoro su interruzione, scrittura atomica del file Excel, punti di ripresa. `False` = comportamento originale |
| `AUTOSAVE_EVERY_N_GROUPS` | `5` | Opzione 1: salva il file Excel ogni N funzioni (0 = mai) |
| `RESUME_FROM_CHECKPOINT` | `True` | Opzioni 1 e 3: ripartono dalla funzione interrotta |
| `PROGRESS_STATE_FILE` | `%LOCALAPPDATA%\FunzioniAI\progress_state.json` | File dei punti di ripresa |
| `INDEX_FUNC_DOC_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\index_doc_cache.json` | Opzione 2: analisi dei PDF già lette |

Esempio: per salvare ogni funzione `AUTOSAVE_EVERY_N_GROUPS = 1` (più sicuro ma
più lento: ogni salvataggio riscrive l'intero file).

#### Storico e controllo incrementale

| Opzione | Valore | Significato |
|---|---|---|
| `RECHECK_MODE` | `"fast"` | Celle già compilate: `"off"` = saltate; `"fast"` = rianalizzate solo se il PDF è cambiato (dimensione/data); `"deep"` = confronta anche il testo |
| `RECHECK_DEEP_EVERY_DAYS` | `30` | In `"fast"`, ogni quanti giorni forzare un controllo `"deep"` |
| `HISTORY_DIR` / `HISTORY_STATE_FILE` / `HISTORY_LOG_FILE` | `%LOCALAPPDATA%\FunzioniAI\…` | Impronte dei documenti e storico delle differenze |

#### Log unico

| Opzione | Valore | Significato |
|---|---|---|
| `LOG_FILE` | `asktrainmind.log` | Unico file di log, accanto allo script: opzioni 1-4, storico differenze, report degli script in `debug/` |
| `LOG_MAX_LINES` | `20000` | Superato questo numero di righe il file viene troncato… |
| `LOG_KEEP_LINES` | `10000` | …conservando solo le ultime righe indicate |

#### Rif. Pagina

| Opzione | Valore | Significato |
|---|---|---|
| `RIF_PAGINA_DYNAMIC` | `True` | Opzione 1: ricalcola il Rif. Pagina dall'indice dei PDF prima dell'analisi (`False` = usa i valori manuali). L'opzione 3 lo esegue sempre |

#### Cella "Funzioni AI" (confronto funzioni)

| Opzione | Valore | Significato |
|---|---|---|
| `FUNC_SIMILARITY_GREEN` / `_HIGH` / `_MEDIUM` / `_DIFF` | `90` / `80` / `50` / `25` | Soglie % di similarità con VZI_Base: verde grassetto / verde / arancione / rosso; sotto = rosso grassetto |
| `FUNC_SIM_WEIGHTS` | `(0.45, 0.25, 0.30)` | Pesi della similarità funzionale: sequenza delle parole di contenuto, lessico, requisiti in comune |
| `FUNC_SIM_PENALTY_VALUE` / `_REQ` / `_COMPONENT` / `_MAX` | `3` / `1` / `0.5` / `30` | Penalità per valore diverso, requisito in una sola config, sigla d'impianto diversa; tetto totale |
| `FUNC_SIM_MAJOR_MIN_REQS` / `FUNC_SIM_MAJOR_MIN_COMPONENTS` | `2` / `3` | Da quanti requisiti / sigle diversi la differenza è «rilevante» (elencata in cella, mai verde grassetto) |
| `FUNC_APPEND_DIFF_DETAIL` / `FUNC_TXT_MAJOR_DIFF` | `True` / `"DIFFERENZE RILEVANTI:"` | Elenco delle differenze rilevanti sotto la sigla |
| `FUNC_MARK_LINK_ISSUES` / `FUNC_TXT_LINK_MISSING` / `FUNC_TXT_DOC_NOT_FOUND` | `True` / `"LINK DOCUMENTALE NON INSERITO"` / `"RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO"` | Messaggio in nero grassetto per le configurazioni senza documento (escluse dal confronto) |
| `FUNC_SIMILARITY_DECIMALS` | `1` | Decimali della percentuale in cella |
| `FUNC_TXT_REF_BASE_OK` / `FUNC_TXT_REF_BASE_DIFF` / `FUNC_TXT_MISS_BASE` | `"RIFERIMENTO VZI_BASE, % SIMILARITY = {pct}, …"`, `"MISS VZI_BASE"` | Testi della cella (`{pct}` = percentuale) |
| `FUNC_SUMMARY_SENTENCES` / `FUNC_SUMMARY_INPUT_CHARS` / `FUNC_SUMMARY_MAX_CHARS` | `5` / `6000` / `1200` | Frasi del riassunto, testo inviato al modello, lunghezza massima in cella |
| `FUNC_LLM_SCORE_MATCH` / `FUNC_TEXT_SIMILARITY_MATCH` | `80` / `0.95` | Soglie di MATCHED del confronto di funzione |
| `FUNC_USE_REQ_VERDICT` / `FUNC_REQ_DIFF_FORCES_DIFF` | `True` / `True` | L'esito dei requisiti forza MATCHED / DIFF della funzione |
| `FUNC_DIFF_MAX_CHARS` | `900` | Lunghezza massima del testo di differenze |

#### Foglio Requisiti

| Opzione | Valore | Significato |
|---|---|---|
| `REQ_HEADER_ROW` | `1` | Riga di intestazione |
| `REQ_FUNC_ID_COL` / `REQ_DESC_COL` / `REQ_FRS_COL` / `REQ_NUMBER_COL` / `REQ_CONFIG_COL` | `1` / `2` / `3` / `4` / `5` | Colonne A–E (FUNC ID, descrizione, FRS, Nr requisito, configurazione) |
| `REQ_CONFIG_COLS_START` | `6` | Prima colonna delle configurazioni (F) |
| `REQ_BASE_CONFIG` | `"VZI_Base"` | Configurazione di riferimento (usata anche dalle opzioni 1 e 2) |
| `REQ_TXT_MATCHED` / `REQ_TXT_MISS_MATCHED` / `REQ_TXT_MISS_DIFF` / `REQ_TXT_MISS_ONLY` | `"MATCHED"`, … | Testi scritti nelle celle |
| `REQ_COLOR_GREEN` / `_RED` / `_BLACK` | `"FF008000"`, … | Colori ARGB del testo |
| `REQ_FIELD_SEP` / `REQ_FIELD_LABEL` / `REQ_FIELD_LABEL_V` | — | Separatore ed etichette dei campi riportati in cella |
| `REQ_PRIMARY_FIELD` | `"description"` | Campo che decide se due requisiti differiscono |
| `REQ_DESC_SIMILARITY_MATCH` / `REQ_DESC_SIMILARITY_DIFF` | `0.94` / `0.55` | Sopra = MATCHED senza AI; sotto = DIFF senza AI; in mezzo decide Ollama |
| `REQ_LLM_SCORE_MATCH` | `80` | Score di Ollama oltre cui il requisito è MATCHED |
| `REQ_NO_DIFF_MARKERS` | elenco di frasi | Risposte del modello che significano "nessuna differenza" |
| `REQ_DIFF_STYLE` | `"narrativo"` | Differenze come paragrafo (`"narrativo"`) o elenco (`"puntuale"`) |
| `REQ_DIFF_MAX_CHARS` / `REQ_DIFF_DETAIL_MAX` / `REQ_DIFF_SNIPPET_LEN` | `700` / `3` / `160` | Lunghezza e dettaglio delle differenze |
| `REQ_ONE_ROW_PER_CONFIG` | `False` | `True` = una riga per (ID, configurazione) |
| `REQ_PROGRESSIVE_NUMBER` | `False` | Antepone "1) ", "2) " al Nr requisito |
| `REQ_CREATE_MISSING_FUNCTION` | `True` | Crea la riga funzione se manca nel foglio |
| `REQ_SORT_LIKE_FUNZIONI` | `True` | A fine opzione 1 ordina i blocchi come i FUNC ID del foglio Funzioni |
| `REQ_REMOVE_STALE_ROWS` | `True` | A fine opzione 1 elimina i requisiti non più presenti nei documenti rianalizzati |
| `REQ_DESC_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\req_desc_cache.json` | Archivio delle Description (usato dal foglio "Reqs not matched") |

#### Estrazione dei requisiti dai PDF

| Opzione | Valore | Significato |
|---|---|---|
| `REQ_ID_MARKER` | `"zefiro"` | Testo obbligatorio in un ID requisito reale |
| `REQ_USE_MATRIX_PARSER` | `True` | Lettura delle tabelle con `find_tables` (`False` = solo testo) |
| `REQ_H_HEADER_MIN_MATCH` | `2` | Intestazioni minime per riconoscere una tabella orizzontale |
| `REQ_PROSE_PREFIXES` / `REQ_MAX_ALPHA_RUN` | elenco / `24` | Filtri che scartano frasi scambiate per ID |
| `REQ_DEBUG_DUMP_VERTICAL` / `REQ_DEBUG_LOG_EACH` | `False` | Log diagnostici dettagliati |

#### Colori delle configurazioni

| Opzione | Valore | Significato |
|---|---|---|
| `CONFIG_COLOR_MAP` | `{"VZI_Base": "1F4E79", …}` | Colore (RGB esadecimale) di ogni configurazione nota |
| `CONFIG_COLOR_PALETTE` | elenco di colori | Colori assegnati alle configurazioni non in mappa |

Esempio: `CONFIG_COLOR_MAP["VZ_NEW"] = "FF8C00"` dà l'arancione alla nuova configurazione.

#### Ricerca Funzioni (opzione 2, foglio "Index Funzioni")

| Opzione | Valore | Significato |
|---|---|---|
| `INDEX_FUNC_FIRST_DOC_ID` / `INDEX_FUNC_LAST_DOC_ID` | `"FRS_Drive Control"` / `"FRS_EMS"` | Righe di CONFIG analizzate (estremi inclusi) |
| `INDEX_FUNC_CHAPTER_TITLES` | `["Functional requirements", …]` | Capitolo dell'indice che contiene le funzioni |
| `INDEX_FUNC_MAX_DEPTH` | `2` | 1 = solo funzioni, 2 = anche sotto-funzioni |
| `INDEX_FUNC_GENERIC_TITLES` | `Function Design`, `Requirements`, … | Sotto-titoli da non considerare funzioni |
| `INDEX_FUNC_FUZZY_MATCH` | `0.92` | Somiglianza minima tra titoli per dire "stessa funzione" |
| `INDEX_FUNC_TOC_MAX_PAGES` | `12` | Pagine iniziali in cui cercare il sommario |
| `INDEX_FUNC_MISSING_NOTE` | `"manca"` | Nota di CONFIG che indica un documento mancante |
| `INDEX_FUNC_PROPOSE_IDS` | `True` | Colonne FUNC ID e DESCRIZIONE FUNZIONE (`False` = solo MATCHED, titolo e paragrafo) |
| `INDEX_FUNC_ID_LEARN_FROM_SHEET` | `True` | Prefisso FUNC ID appreso dalle funzioni esistenti dello stesso DOC ID |
| `INDEX_FUNC_ID_PREFIX_MAP` | `{}` | Prefissi imposti, es. `{"FRS_Drive Control": "DRV"}` |
| `INDEX_FUNC_ID_PARENT_MODE` | `"auto"` | Padre nel FUNC ID delle sotto-funzioni: `auto` / `always` / `never` |
| `INDEX_FUNC_ID_SHORT_TITLE_WORDS` | `1` | In `auto`, titoli con al massimo N parole ricevono il padre |
| `INDEX_FUNC_ID_EXISTING_FUZZY` | `0.9` | Somiglianza titolo/FUNC ID per riconoscere una funzione esistente |
| `INDEX_FUNC_DESC_MODE` | `"ai"` | Descrizione delle funzioni nuove: `ai` / `template` / `off` |
| `INDEX_FUNC_DESC_TEMPLATE` | `"Funzione per gestire {title} ({doc_title}, §{paragraph})"` | Modello di riserva (segnaposto `{title} {doc_title} {doc_id} {paragraph} {parent}`) |
| `INDEX_FUNC_DESC_EXAMPLES` / `_MAX_CHARS` / `_INPUT_CHARS` | `6` / `300` / `3000` | Esempi di stile, lunghezza massima, testo del paragrafo inviato |
| `INDEX_FUNC_DESC_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\index_desc_cache.json` | Cache delle descrizioni AI |

#### Confronto specifico Funzioni-Requisiti (opzione 4, foglio "Confronto Reqs")

| Opzione | Valore | Significato |
|---|---|---|
| `SHEET_CONFRONTO_REQS` | `"Confronto Reqs"` | Nome del foglio generato |
| `CONFRONTO_REQS_DOC_IDS` | `[]` | DOC ID proposti di default (es. `["FRS_Coupler"]`): usati premendo Invio nella scelta o con `--mode 4` fuori da un terminale |
| `CONFRONTO_REQS_IGNORE_DESCRIPTIONS` | `["DELETED"]` | Description che non identificano un requisito: confronto per Nr/ID |

#### Requisiti non MATCHED (opzione 5, foglio "Reqs not matched")

| Opzione | Valore | Significato |
|---|---|---|
| `SHEET_REQS_NOT_MATCHED` | `"Reqs not matched"` | Nome del foglio generato |
| `REQS_NOT_MATCHED_CONFIGS` | `[]` | Configurazioni proposte di default (vuoto = tutte) |
| `REQS_NOT_MATCHED_AFTER_OPTION1` | `True` | Ricrea il foglio, con tutte le configurazioni, a fine opzione 1 |
| `REQS_NOT_MATCHED_AI_NOTES` | `True` | Spiegazione generata da Ollama nella colonna "Note AI" |
| `REQS_NOT_MATCHED_AI_MAX_CHARS` / `REQS_NOT_MATCHED_NOTE_MAX_CHARS` | `350` / `900` | Lunghezza della spiegazione AI / della cella |
| `REQS_NOT_MATCHED_AI_MAX_CALLS` | `0` | Note AI nuove per esecuzione (0 = nessun limite); le righe oltre il limite restano nel foglio con nota "non generata" |
| `REQS_NOT_MATCHED_AI_CACHE_FILE` | `%LOCALAPPDATA%\FunzioniAI\reqs_not_matched_ai_cache.json` | Cache delle note AI |
| `REQS_NOT_MATCHED_SIMILAR_MIN` | `0.80` | Requisiti con ID diverso e Description simile (≥ soglia) affiancati e annotati «Requisito simile a …» (1.0 = solo testo identico, 0 = disattivato) |

Se una configurazione non ha il link al documento dell'FRS nel foglio Funzioni,
la nota indica «Mancanza link documentale per l'FRS … nella configurazione …»
e la cella è colorata in arancio chiaro, invece di segnalare il requisito come mancante.

#### Archivio _OLD

| Opzione | Valore | Significato |
|---|---|---|
| `OLD_ARCHIVE_ENABLED` | `True` | Copia la versione precedente del file Excel prima di ogni modifica |
| `OLD_ARCHIVE_DIR` | `None` | Cartella dell'archivio (`None` = `_OLD` accanto al file Excel) |
| `OLD_ARCHIVE_MAX_CELL_LINES` | `400` | Righe massime dell'elenco celle aggiornate in `RICHIESTA.txt` |

#### Aggiornamento del DB / file RESULTS

| Opzione | Valore | Significato |
|---|---|---|
| `UPDATE_DB_DEFAULT` | `True` | Risposta proposta alla domanda "Aggiornare il DB Flotte?" |
| `RESULTS_DIR` | `None` | Cartella dei file RESULTS (`None` = `RESULTS` accanto al file Excel) |
| `NOT_UPDATED_COMMENT` | `"Not updated"` | Commento delle celle escluse da un'esecuzione parziale |

#### Interfaccia web

| Opzione | Valore | Significato |
|---|---|---|
| `WEB_HOST` / `WEB_PORT` | `"127.0.0.1"` / `8765` | Indirizzo e porta del server (solo questo PC) |
| `WEB_OPEN_BROWSER` | `True` | Apre il browser all'avvio |
| `WEB_CACHE_DIR` | `None` | Cache dei fogli, indice PDF, figure e risposte (`None` = `HISTORY_DIR/web_cache`) |
| `WEB_EXTRA_DOC_DIRS` | `[]` | Altre cartelle di PDF per le risposte e la ricerca nei documenti |
| `WEB_PDF_INDEX_MAX_PAGES` | `0` | Pagine massime indicizzate per PDF (0 = tutte) |
| `WEB_PDF_INDEX_AT_START` | `True` | Costruisce/aggiorna l'indice dei PDF in background all'avvio (ricerca immediata) |
| `WEB_QA_USE_AI` | `True` | Spiegazione con l'AI locale nella sezione Chiedi |
| `WEB_QA_MAX_SECTION_PAGES` | `12` | Pagine massime analizzate per funzione (figure, testo) |
| `CONFIG_OVERRIDES_FILE` | `config_overrides.json` | Valori forzati dalla sezione CONFIG della pagina web |

#### Conoscenza (glossario appreso)

| Opzione | Valore | Significato |
|---|---|---|
| `KNOWLEDGE_FILE` | `HISTORY_DIR/knowledge.json` | Glossario dei termini insegnati all'AI |
| `KNOWLEDGE_USE_IN_ANALYSIS` | `True` | Aggiunge ai prompt di Ollama le definizioni dei termini presenti nel testo |
| `KNOWLEDGE_MAX_TERMS_IN_PROMPT` | `25` | Termini massimi aggiunti a un prompt |
| `KNOWLEDGE_MAX_QUESTIONS` | `40` | Domande massime per sessione di apprendimento |
| `KNOWLEDGE_MAX_PAGES` | `80` | Pagine massime lette per sessione |
| `KNOWLEDGE_MAX_ANSWERS_PER_TERM` | `30` | Spiegazioni dell'esperto (risposte libere del questionAI) conservate per concetto |
| `QUESTION_SHEET_DIR` / `QUESTION_SHEET_MAX` | `""` / `200` | Cartella di `questionAI.xlsx` (vuoto = cartella del programma) e domande per questionario (0 = tutte) |
| `QUESTION_SHEET_USE_AI` / `QUESTION_SHEET_SAVE_EVERY` / `QUESTION_SHEET_SAVE_SECONDS` | `True` / `10` / `20` | Struttura con Ollama le risposte discorsive lunghe; righe caricate fra due salvataggi e intervallo minimo in secondi fra due salvataggi |

#### Parametri presenti ma non più usati

Restano in `config.py` per compatibilità, ma modificarli non ha effetto:
`OLLAMA_TIMEOUT`, `CACHE_DIR`, `MS_CLIENT_ID`, `MS_SCOPES`, `CRITICAL_CHECKLIST_KEYS`,
`RIF_PAGINA_LABEL`, `FUNC_TXT_MATCHED`, `FUNC_TXT_MISS_*`, `FUNC_SIMILARITY_DIFF`,
`FUNC_APPEND_DIFF_DETAIL`, `REQ_SECONDARY_FIELDS`, `REQ_WRITE_EXTRA_FIELDS`,
`REQ_EXTRA_FIELDS_START_COL`, `REQ_ACCEPT_LOOSE_IDS`, `REQ_ID_MIN_SEGMENTS`,
`REQ_ID_FALLBACK_PATTERNS`, `REQ_ID_BLACKLIST_SUBSTR`, `REQ_ID_ANCHORED_FALLBACK`,
`REQ_H_HEADER_*` (tranne `REQ_H_HEADER_MIN_MATCH`), `REQ_V_HEADER_*`, `REQ_V_LOOKAHEAD`,
`REQ_H_MAX_BLANK_LINES`, `REQ_H_SKIP_REPEATED_HEADER`, `REQ_TABLE_END_PATTERNS`.

---

### Come eseguire

```bash
# Interfaccia web (esplora, fogli, domande, conoscenza, strumenti): http://127.0.0.1:8765
python asktrainmind_web.py

# Menu interattivo (1 = Funzioni AI e Requisiti, 2 = Ricerca Funzioni,
#                  3 = Cerca riferimento pagina,
#                  4 = Confronto specifico Funzioni-Requisiti,
#                  5 = Requisiti non MATCHED tra configurazioni)
python funzioni_ai_filter.py

# Senza menu
python funzioni_ai_filter.py --mode 1    # Funzioni AI e Requisiti
python funzioni_ai_filter.py --mode 2    # Ricerca Funzioni -> foglio "Index Funzioni"
python funzioni_ai_filter.py --mode 3    # Cerca riferimento pagina -> celle "Rif. Pagina"
python funzioni_ai_filter.py --mode 3 --start "AIR_Air_Dryer"
python funzioni_ai_filter.py --mode 4    # Confronto Funzioni-Requisiti -> foglio "Confronto Reqs"
python funzioni_ai_filter.py --mode 5    # Requisiti non MATCHED -> foglio "Reqs not matched"

# Opzione 4: DOC ID indicati da riga di comando (foglio CONFIG, col B)
python funzioni_ai_filter.py --doc "FRS_Coupler"
python funzioni_ai_filter.py -m 4 -d "FRS_Coupler, FRS_Horn"

# Opzione 5: configurazioni indicate da riga di comando
python funzioni_ai_filter.py --configs "VZI_Base, VZI_New14, VZ_FR"
python funzioni_ai_filter.py -m 5 -c "VZI_New14, VZ_FR"

# Ambito (opzioni 1-5): FRS, funzioni degli FRS e configurazioni di treno
python funzioni_ai_filter.py -m 5 --frs "FRS_Line Voltage" -f "LV_Pantograph_Lifting, LV_Pantograph_Selection" -c "VZI_Base, VZ_FR"
python funzioni_ai_filter.py -m 4 --frs "FRS_Line Voltage" -f "pantograph lifting" -c "1-3"
python funzioni_ai_filter.py -m 3 --frs "FRS_Line Voltage" -c "VZ_FR"

# Opzione 1: riprendi da una funzione specifica
python funzioni_ai_filter.py --mode 1 --start "LV_Pantograph_Lifting"
python funzioni_ai_filter.py -m 1 -s "LV_Pantograph_Lifting"

# Opzione 1: solo alcuni FRS, al massimo 20 celle, rielaborando anche le
# celle gia' compilate, senza aggiornare "Reqs not matched"
python funzioni_ai_filter.py --frs "FRS_Line Voltage" --max-cells 20 --overwrite S --no-reqs-not-matched

# Qualsiasi opzione senza modificare il DB: solo file RESULTS
python funzioni_ai_filter.py --mode 5 --configs "VZI_Base, VZ_FR" --results-only
```

---

### Diagnostica problemi comuni

#### Il codice usa Strategia B invece di A
**Causa**: `func_id` non passato o titolo del documento in lingua diversa.
**Soluzione**: Verifica che `target.func_id` sia valorizzato in `excel_scanner.py`
e che venga passato a `extract_page_text(func_id=...)`.

#### Gli indici del PDF non vengono rilevati
**Causa più comune**: gli indici si trovano oltre riga 60 della pagina.
**Debug**: esegui `debug/debug_pdf_indexes.py <file.pdf> <pag_inizio> <pag_fine>`
(output anche nel log unico).
Cerca le righe `>>>` nell'output per vedere come fitz estrae il testo.

#### Riferimenti incrociati trattati come nuovi indici
**Esempio**: `"see chapter 3.2.5"` viene erroneamente interpretato come
l'inizio della sezione 3.2.5.
**Gestione**: `_is_section_heading_line()` e `_filter_progressive_indexes()`
in `document_handler.py` filtrano questi casi controllando:
- L'indice deve essere all'inizio della riga
- La riga precedente non deve contenere parole come "see", "chapter"
- La riga successiva non deve iniziare con virgolette `"`
- La sequenza degli indici deve essere progressiva (gap ≤ 3 tra fratelli)

#### Il testo viene troncato troppo presto
**Causa**: un indice estraneo viene trovato prima della fine reale della sezione.
**Debug**: aggiungi log a `_truncate_at_new_section()` per vedere quale
indice causa il troncamento.

#### File Excel bloccato
Lo script attende fino a 60 secondi che il file venga chiuso.

---

### WARNING ed ERROR nel log: come vanno letti

`asktrainmind.log` non deve contenere WARNING in condizioni normali (fa
eccezione `Rif. Pagina assente o non valido`, che segnala una funzione
saltata perché priva di riferimento pagina).
Di seguito le cause storiche, tutte risolte, e il comportamento atteso oggi.

#### `[Requisiti] Errore estrazione tabelle: 'req_id'`
**Causa**: `realign_header()` scartava la colonna "Nr" quando risultava
vuota nelle righe dati (ID scivolato sotto l'intestazione adiacente, o
tabella fatta di sole righe di continuazione). La testata perdeva il campo
`req_id` e `_parse_horizontal()` sollevava `KeyError`.
L'eccezione risaliva fino al ciclo sulle pagine di `extract_from_tables()`,
interrompendo la scansione di **tutte le pagine successive** della sezione.

**Oggi**: la colonna degli ID non si perde mai — se la testata non la
espone viene dedotta dai dati (colonna di soli ID, con `Derived to`
esclusa perché contiene ID per definizione). Gli errori sono inoltre
isolati per singola tabella e per singola pagina: la scansione prosegue
sempre fino all'ultima pagina della sezione.

#### `[Summary] parsing fallito su <funzione>: Unterminated string ...`
**Causa**: `OLLAMA_NUM_PREDICT` valeva 300 token a fronte di riassunti da
1200 caratteri (`FUNC_SUMMARY_MAX_CHARS`). Ollama interrompeva la
generazione a metà stringa e il JSON risultava illeggibile, così **ogni**
riassunto degradava a semplice estratto testuale
(`riassunto LLM non disponibile, usato estratto testuale`).

**Oggi**: ogni chiamata dichiara il budget di token di cui ha bisogno
(`_token_budget()`) e le risposte eventualmente troncate vengono
recuperate da `llm_json.parse_json_relaxed()`, che chiude la stringa e le
parentesi aperte conservando il testo già prodotto dal modello. Il
troncamento viene segnalato a livello INFO, non WARNING.

#### `Errore Ollama: prediction aborted, token repeat limit reached`
**Causa**: con `temperature=0` e `repeat_penalty=1.05` il modello poteva
entrare in ripetizione e Ollama abortiva la generazione con HTTP 500.

**Oggi**: `_call_ollama()` ritenta automaticamente fino a tre volte
alzando la penalità di ripetizione (1.05 → 1.25 → 1.40). L'ERROR compare
solo se tutti i tentativi falliscono.

#### `STORICO — differenza rilevata`
Non è un'anomalia ma la notifica attesa di una differenza rispetto
all'esecuzione precedente: viene registrata a livello INFO.
Se il timeout scade, salva un backup con suffisso `_backup`.

---

## Parte 4 — L'AI: come ragiona e come si addestra

Questa guida è per il **developer**. Spiega come l'AI di AskTrainMind acquisisce conoscenza tecnica ferroviaria, come le si risponde, come si corregge ciò che ha imparato e come la conoscenza arriva agli utenti.

> In breve: **AVVIA_DEVELOPER.bat** → **6** (leggi i documenti) → **7** (rispondi alle sue domande) oppure **15 → 16** (rispondi in blocco nel foglio Excel «questionAI») → **8** (insegna o correggi) → **10** (prova «Chiedi») → **13** (pubblica per gli utenti).

---

### 1. Come ragiona l'AI

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

### 2. Dove si trova la conoscenza (file modificabili)

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

### 3. Il ciclo di addestramento (terminale developer)

Avvia **`AVVIA_DEVELOPER.bat`**, oppure `python asktrainmind_dev.py`. Scrivi `h N` per leggere la descrizione della voce N. Per eseguire direttamente una voce: `python asktrainmind_dev.py --run 6`.

#### Voce 6 — Leggi i documenti tecnici

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

#### Voce 7 — Rispondi alle domande dell'AI

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

#### Voci 15 e 16 — Questionario Excel «questionAI» (il modo più veloce)

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

#### Voce 8 — Insegna o correggi un concetto

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

#### Voce 9 — Consulta la conoscenza

- Mostra lo stato (concetti confermati e proposti, domande, documenti letti) e **controlla i file**.
- Scrivi un testo per **cercare** fra le schede e vederne il contenuto completo.
- `p` elenca le **proposte** da confermare in blocco: `1,4,7-12`, oppure `tutti`.
- `cats` mostra il numero di concetti per categoria.

#### Voce 10 — Prova «Chiedi»

Fai una domanda come la farebbe l'utente e vedi la risposta con la conoscenza **aggiornata**, prima di pubblicarla.

```
  Domanda: come funziona il loop DNRA sul VZI_Base?
  🧠 Cosa so di «LOOP» …   🧠 Cosa so di «DNRA» …
  ⚙️ Funzioni collegate: BRK_Detection_of_Non-Rotating_Axle_(DNRA), CON_DNRA_Alarm …
```

Le parole che restano in **«🤔 Non conosco ancora…»** sono le prossime da insegnare con la voce 8.

Alla prima domanda la voce 10 prepara l'indice del testo dei documenti (circa un minuto): le risposte includono anche **«📄 Dai documenti»**, cioè il requisito o il paragrafo del PDF che risponde alla domanda.

#### Voce 17 — Verifica l'AI

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

### 4. Esempio completo: «come funziona il loop DNRA sul VZI_Base?»

1. **Voce 6**: l'AI legge i FRS in `docs/`, trova «DNRA» con la definizione e crea la scheda *proposta*. Crea anche la scheda *VZI_Base* dal DB Flotte.
2. **Voce 10**: provi la domanda. L'AI riconosce DNRA e VZI_Base, ma segnala *«Non conosco ancora: loop»*.
3. **Voce 8 → `loop`**: insegni che cos'è un loop. In alternativa, con la **voce 6** le dai un documento che ne parla, come un manuale o un `.txt` con la tua spiegazione.
4. **Voce 7, filtro `DNRA`**: confermi il significato (`s`), scegli la categoria *funzione* o *loop* e rispondi alle domande successive (sensori coinvolti, centralina che lo gestisce, soglie di taratura, eventi TCMS).
5. **Voce 7, filtro `VZI_BASE`**: rispondi su costruttore, anno, treni e linee.
6. **Voce 10**: ora la risposta contiene le schede *loop*, *DNRA* e *VZI_Base* con relazioni e fonti, oltre alle funzioni del DB Flotte.
7. **Voce 13**: pubblichi la conoscenza per gli utenti.

Lo stesso vale per *«Cos'è un pantografo?»*, *«Cos'è una configurazione dell'ETR1000?»* e simili.

---

### 5. Dove viene usata la conoscenza

| Dove | Come |
|---|---|
| **💬 Chiedi** (web) | schede «🧠 Cosa so di…» con relazioni, fonti e funzioni collegate; elenco delle parole sconosciute. Le sigle apprese e i loro alias (es. *MR = main reservoir*) ampliano anche la **lettura dei documenti** («📄 Dai documenti») |
| **🧭 Esplora** (web) | nel dettaglio funzione, barra **🧠 Concetti**; nei testi i termini noti sono sottolineati e cliccabili |
| **Analisi da terminale** (voci 1-5) | le schede **confermate** che riguardano la funzione analizzata vengono aggiunte al prompt dell'AI locale (`KNOWLEDGE_USE_IN_ANALYSIS`, max `KNOWLEDGE_MAX_TERMS_IN_PROMPT`). Le sintesi diventano così tecniche e non solo letterali |

---

### 5b. Come l'AI legge i documenti (`docsearch.py`)

Oltre alla conoscenza, Chiedi **legge il testo dei documenti**:

1. **Indice** (alla voce 13 per la pagina offline; in background al primo uso nell'anteprima): per ogni funzione del DB Flotte vengono raccolti i **requisiti** (Description per ogni variante di testo, con le configurazioni, il documento e la pagina di ciascuna) e i **paragrafi** delle pagine della funzione nei PDF. Intestazioni e piè di pagina ripetuti vengono scartati. Circa 20.000 passaggi da 66 documenti.
2. **Domanda → concetti**: le parole italiane vengono tradotte nei termini inglesi dei documenti con il dizionario `SYN` di `docsearch.py` (es. *pressione → pressure*, *attivarsi → run/start/activate*, *compressore → compressor*), estendibile a mano, e ridotte alla radice. Le sigle apprese aggiungono i loro alias.
3. **Contesto e contenuto**: le parole che nominano il documento (*FRS Air Supply*) o la funzione (*Controllo del compressore principale*) servono a scegliere **dove** cercare; le altre (*pressione*, *attivarsi*) sono **cosa** cercare. Le configurazioni citate (*VZI_New14*) filtrano i passaggi e scelgono il PDF da citare.
4. **Punteggio** BM25 con bonus per la funzione o il documento citati, per la configurazione e, se la domanda chiede un valore, per i passaggi con numeri e unità (*kPa*, *s*, *km/h*…).
5. **Risposta**: il passaggio migliore viene citato («il requisito … stabilisce che …») e, nell'anteprima con Ollama, i passaggi vengono passati anche all'AI per la spiegazione.

La stessa ricerca è replicata in JavaScript nella pagina offline (`offline.js → DocSearch`), con risultati identici.

### 5c. Come Chiedi capisce la domanda e compone le due sezioni (`understand.py`)

Chiedi non risponde per parole chiave: prima **capisce la domanda in italiano**, poi legge conoscenza e documenti
**nello stesso passaggio**, guidato da ciò che ha capito.

1. **Cosa chiede** (`ask_type`): un valore (*che valori…, a che pressione…, quanto…*), una condizione (*quando…*),
   un significato (*cos'è…*), il funzionamento, le differenze, i requisiti, i documenti.
2. **Di quale grandezza** (`QTY`): pressione (kPa, bar), temperatura (°C), tempo (s, min), velocità (km/h), tensione,
   corrente, frequenza, potenza, percentuale; *massima/minima* sceglie il valore estremo.
3. **Dove** (perimetro): il documento nominato (*FRS Air Supply* → `FRS_Air Supply`, con le sue funzioni e i codici per
   configurazione), la funzione (FUNC ID o descrizione), le configurazioni (*VZI_Base*). Le parole che indicano il
   perimetro o la forma della domanda (*all'interno di, ci sono, per il…*) non vengono cercate nel testo.
4. **Argomento**: le parole restanti, tradotte nei termini inglesi dei documenti (`docsearch.SYN`) e unite alle sigle
   apprese (glossario).
5. **Lettura**: per *«che valori di X ci sono in …»* vengono letti **tutti** i passaggi del perimetro che contengono la
   grandezza; per le domande precise, i passaggi più pertinenti (BM25). Da ogni passaggio si estraggono i **valori**
   (con intervalli, unità e confronti ≥ < …), la **condizione** (es. *serbatoio principale (MR) ≥ 1000 kPa*) e
   **cosa avviene**, tradotto in italiano (*shall stop → arresto*, *ordered to run → avvio*, eventi diagnostici…).
6. **🎓 Risposta AI**: *«Ho capito che chiedi…»*, poi il dato (**Risposta: 1000 kPa** con significato e requisito)
   o l'elenco ragionato per funzione con tabella riepilogativa, oppure la scheda del concetto o la sintesi della
   funzione (sezione Funzioni AI del DB Flotte).
7. **📄 Sezione documentale**: passaggi citati (clic = PDF alla pagina), schede 🧠, dati della funzione, funzioni citate.

La logica è identica nel server (`understand.py` + `webapp/qa.py`) e nella pagina offline (`offline.js`, modulo `U`).
La voce **17** (`verify_ai.py`) controlla anche la 🎓 Risposta AI su domande di esempio (`AI_CASES`). Per far capire
parole nuove basta aggiungerle a `SYN` in `docsearch.py` (o insegnarle come concetti) e rigenerare `User/`.

### 5d. Spiegazione con Ollama (anteprima web del developer)

Con la voce **14** (`python asktrainmind_web.py --port 8765`) la pagina viene servita dal server locale: oltre alle due
sezioni, il pulsante di spiegazione passa all'AI locale **Ollama** la domanda, la 🎓 Risposta AI e i passaggi dei
documenti, per una spiegazione discorsiva. Serve Ollama in esecuzione con il modello configurato (voce 11, sezione
*Modello AI*). La pagina offline degli utenti non usa Ollama.

### 6. Pubblicare per gli utenti

Gli utenti **non** hanno l'AI in addestramento: vedono una **fotografia** della conoscenza, inclusa nella pagina `User/AskTrainMind.html` al momento della pubblicazione.

- **Voce 13** rigenera la cartella `User/`: pagina web offline con dati, conoscenza e guida, più una copia dell'Excel.
- Con `USER_AUTO_EXPORT = True` la cartella User viene aggiornata automaticamente dopo ogni voce che modifica i dati o la conoscenza (1-9).
- Con `USER_EXPORT_PROPOSED = True` anche le schede *proposte* vengono pubblicate, con l'avviso «non ancora confermato». Imposta `False` per pubblicare solo quelle confermate.
- In alto a destra nella pagina utente compare la data della fotografia.

---

### 7. Parametri (voce 11 → sezione Conoscenza / Utente)

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

---

## Parte 5 — Come vengono calcolati MATCHED e % SIMILARITY

*(MATCHED per i Requisiti, % SIMILARITY per le Funzioni)*

Pipeline per ogni funzione (orchestrata da `funzioni_ai_filter.py`).
**Ordine obbligatorio: prima i Requisiti, poi le Funzioni.**

---

### 1. Estrazione del testo della sezione (`document_handler._extract_pdf`)

1. Si apre il PDF alla pagina indicata nel foglio Excel (`Rif. Pagina`).
2. Si cerca l'**indice di sezione** della funzione (es. `3.2.1`) confrontandolo con `FUNC ID` / descrizione.
   - **Strategia A** (indice trovato): il testo prima dell'indice viene scartato; si leggono le pagine
     successive finché compare un indice fratello o superiore (es. `3.2.2`), poi STOP. Le pagine senza
     indice sono continuazioni della sezione. L'ultima pagina viene troncata all'inizio della nuova sezione.
   - **Strategia B** (indice non trovato): si prosegue finché la sovrapposizione di parole chiave con la
     pagina iniziale resta ≥ `SIMILARITY_THRESHOLD` (0.26).
3. Massimo `MAX_SECTION_PAGES` (25) pagine aggiuntive. Il risultato è il testo della sezione con i marker
   `[Pagina N]`.

### 2. Estrazione dei requisiti (`requirements_extractor.py`)

Due strategie **fuse** (non alternative):

1. **Matrice di celle** (`extract_from_tables`, PyMuPDF `find_tables()`), con ritaglio verticale sulla
   sezione per non prendere requisiti della funzione successiva:
   - **Orizzontale**: testata `Nr | Description | Type/ApplicabilityDetails | Derived to | User Interface | SIL`,
     una riga per requisito.
   - **Verticale**: blocchi `ID / Description / Safety level`.
2. **Testo lineare** (`extract`): recupera i requisiti non rilevati da `find_tables()` (blocchi senza cornice).
3. Classificazione: **accettati** gli ID della colonna `Nr`/`ID` (contenenti `Zefiro`); **scartati** gli ID
   della colonna `Derived to` (sono la provenienza, non requisiti).
4. Deduplica per ID → lista di `Requirement` per configurazione.

**Casi particolari gestiti** (necessari perché un requisito presente in due configurazioni non risulti
«solo in una» nel foglio *Reqs not matched*):

- **Sezione che continua su più pagine**: il ritaglio verticale usa il titolo della funzione come bordo
  superiore **solo sulla pagina in cui la sezione inizia**. Sulle pagine successive un titolo discendente
  (es. `3.1.2.1` dentro `3.1`) è un sotto-paragrafo: le tabelle sopra di esso appartengono ancora alla funzione.
  Prima venivano perse, per esempio `2F_06.03.Zefiro-Europe.CONCEPT.165` (pag. 9 di `3EST000225-7915`,
  AIR_Control_of_Main_Compressor, VZI_Base) e `2F_03.Zefiro-Europe.CONCEPT.213` / `CONCEPT.80`
  (pag. 25-26 di `3EST000225-7906`, VZI_Base).
- **ID spezzato su più righe della tabella** (`2F_03.Zefiro-` / `Europe.CONCEPT.` / `80`): le righe vengono
  ricomposte in un unico ID. Un ID troncato (`2F_06.03.Zefiro`) non viene mai accettato come requisito.
- **Blocco verticale `ID | 2F_…` dentro una tabella orizzontale**: riconosciuto come inizio di un nuovo requisito.
- **Parole incollate** nel testo delle celle (`Ifthepressuredecreasesbelowlimit4`): il testo viene riletto dal
  livello di testo della pagina, che conserva gli spazi.

### 3. Requisiti → MATCHED (`requisiti_writer.py` + `req_ai_comparator.py`)

1. I requisiti di tutte le configurazioni vengono uniti per ID (una riga per requisito nel foglio `Requisiti`).
2. Si confronta **solo la Description** (gli altri campi sono contesto e non generano mai differenze).
   Normalizzazione: minuscole, spazi compattati, punteggiatura rimossa (cifre, `% . / -` conservati).
3. Confronto base (`VZI_Base`) vs ciascuna altra configurazione:

   | Condizione | Esito | LLM |
   |---|---|---|
   | Description identica dopo normalizzazione | **MATCHED** | no |
   | Similarità (`SequenceMatcher`) ≥ `REQ_DESC_SIMILARITY_MATCH` (0.94) | **MATCHED** | no |
   | Description assente in una sola config | DIFF "verifica manuale" | no |
   | Similarità < `REQ_DESC_SIMILARITY_DIFF` (0.55) | DIFF + frammenti divergenti | no |
   | 0.55 ≤ sim < 0.94 | il modello restituisce `score` + `differenze` | sì |

4. Con LLM: **MATCHED** se `differenze` è vuoto (o contiene solo frasi "identico/uguale…", post-filtro)
   **e** `score ≥ REQ_LLM_SCORE_MATCH` (80). Altrimenti DIFF con paragrafo + confronto testuale.
5. Scrittura cella:
   - `VZI_Base` → dump dei campi in nero; altre config → `MATCHED` verde grassetto o differenze in rosso.
   - Base assente, più config: tutte simili → `MISS VZI_BASE REQ, MATCHED`, altrimenti `MISS VZI_BASE REQ, FOUND DIFF`.
   - Base assente, una sola config → `MISS VZI_BASE REQ` + Description.
   - In **ogni** cella, dopo l'esito (MATCHED, differenze o MISS…), segue sempre il separatore e il
     dump della configurazione con la **Description**: così Esplora mostra il testo di ogni configurazione.
     Per i file scritti prima di questa regola: `python req_desc_backfill.py` (voce 18 del terminale).
6. L'esito (`last_verdict`: n. requisiti, n. divergenti, config divergenti) viene passato alle Funzioni.

### 3b. Esito dei requisiti in Esplora (`reqs_not_matched.row_view` + `explore.js → reqStatus`)

La pagina web ricalcola l'esito **fra le configurazioni scelte dall'utente** (non solo base vs altre):

1. Per ogni configurazione si ricava la Description dalla cella (`description_from_cell`) e si raggruppano
   le configurazioni con **lo stesso testo** (gruppi A, B, C…; il gruppo 0 è quello di VZI_Base, se presente).
   Le celle MATCHED senza testo ereditano il testo della base; le celle senza testo ricavabile sono `?`.
2. Riferimento: **VZI_Base** (★) se mostrata e presente; altrimenti la prima configurazione che contiene il
   requisito (☆, riferimento sostitutivo).
3. Esito:

   | Esito | Condizione |
   |---|---|
   | ✔ MATCHED | presente in tutte le configurazioni mostrate, un solo testo |
   | ✖ NOT MATCHED · solo in una | presente in una sola configurazione (con ≥ 2 mostrate) |
   | ✖ NOT MATCHED · manca in alcune | presente in più di una ma non in tutte (anche se nella maggioranza) |
   | ✖ NOT MATCHED · testo diverso | presente in tutte, più di un testo |
   | ? DA VERIFICARE | presente in tutte, un solo testo noto ma qualche testo non ricavabile |

### 4. Funzioni → % SIMILARITY (`funzioni_ai_filter.py` + `func_ai_comparator.functional_similarity`)

Due funzioni sono **analoghe se il loro significato è analogo**. Impaginazione, intestazioni e piè di pagina
del PDF, righe spezzate e tabelle riformattate non sono differenze. Le **grandi differenze funzionali o
d'impianto**, invece, abbassano la percentuale e vengono **marcate** in cella. Il calcolo è deterministico e
**non richiede chiamate LLM**.

1. **Pulizia**: vengono rimossi `[Pagina N]`, codici documento, intestazioni e piè di pagina ripetuti
   (`Document state`, `Revision`, copyright, intestazioni VSI «Progetto / Titolo / Codice documento / Pagina
   N di M»).
2. **Similarità di significato** (0-100), media pesata (`FUNC_SIM_WEIGHTS`, default 0.45 / 0.25 / 0.30) di:
   - **sequenza** delle parole di contenuto (stesso discorso nello stesso ordine; stopword e suffissi
     rimossi);
   - **lessico** di contenuto (stessi concetti, anche se riordinati; coseno sulle frequenze);
   - **requisiti in comune** (Jaccard sugli ID `2F_…`; ignorato se nessuna delle due sezioni ha requisiti).
3. **Penalità per differenze funzionali/d'impianto** (massimo `FUNC_SIM_PENALTY_MAX` = 30 punti):

   | Differenza | Penalità | Marcata come rilevante |
   |---|---|---|
   | valore/soglia con unità diverso (`18.5 kV` → `30 kV`, `2 s` → `500 ms`) | 3 punti ciascuno (max 6) | sempre |
   | requisito presente in una sola configurazione | 1 punto ciascuno (max 10) | da `FUNC_SIM_MAJOR_MIN_REQS` (2) |
   | contenuto molto diverso (rapporto di lunghezza < 0.7 / < 0.5) | 5 / 10 punti | sempre |
   | sigla d'impianto (centralina, apparecchiatura) presente in una sola configurazione | 0.5 punti ciascuna (max 10) | da `FUNC_SIM_MAJOR_MIN_COMPONENTS` (3) |

   I rimandi agli hazard (`HRnn`), i nomi delle carrozze (`DM1`, `M3`), i connettivi (`AND`/`OR`) e i nomi delle
   configurazioni non contano come sigle d'impianto. Con almeno una **differenza rilevante** la percentuale
   resta sotto `FUNC_SIMILARITY_GREEN`: la funzione non risulta mai verde grassetto.
4. Scrittura cella `Funzioni AI` (colori del foglio, `FONT_*` in `funzioni_ai_filter.py`):
   - `VZI_Base` → riassunto LLM della funzione, in nero.
   - Altre config → `RIFERIMENTO VZI_BASE, % SIMILARITY = X, X>90%` oppure `... X<90%`:

     | X | Colore |
     |---|---|
     | ≥ `FUNC_SIMILARITY_GREEN` (90) | **verde grassetto** (funzione analoga) |
     | ≥ `FUNC_SIMILARITY_HIGH` (80) | verde |
     | ≥ `FUNC_SIMILARITY_MEDIUM` (50) | arancione |
     | ≥ `FUNC_SIMILARITY_DIFF` (25) | rosso |
     | < 25 | **rosso grassetto** |

     Se ci sono differenze rilevanti e `FUNC_APPEND_DIFF_DETAIL = True`, sotto la sigla compare
     `DIFFERENZE RILEVANTI:` con l'elenco puntato, per esempio:

     ```
     RIFERIMENTO VZI_BASE, % SIMILARITY = 54.2%, X<90%
     DIFFERENZE RILEVANTI:
     • Valori/soglie diversi: VZI_Base 18.5 kV → VZ_FR 2.05 kV, 30 kV, 34 kV, 4.5 kV
     • Requisiti diversi: 2 solo in VZI_Base, 9 solo in VZ_FR
     ```
   - Base assente → `MISS VZI_BASE` + riassunto di ogni configurazione.
   - **Documento della configurazione mancante** → in **nero grassetto** `LINK DOCUMENTALE NON INSERITO`
     (nessun link nel foglio *Funzioni*) oppure `RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO` (link presente
     ma `#N/A`, URL non costruibile o PDF non trovato). La configurazione è **esclusa dal confronto**:
     nessuna similarità, nessun requisito confrontato (`FUNC_MARK_LINK_ISSUES`).

L'interfaccia web usa gli stessi colori: ✔ verde (≥ 80), ≈ arancione (50-80), ≠ rosso (< 50), ⚠ documento non
disponibile. Mostra inoltre le differenze rilevanti nella scheda della configurazione.

Tutte le soglie sono in `config.py`.

---

### Debug delle tabelle requisito

Script: **`debug/debug_requisiti.py`** (stessa logica di `requirements_extractor.py`, output su console e in
nel log unico `asktrainmind.log`). Dalla root del progetto:

```bash
# Scansione completa: elenca le pagine che contengono requisiti
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf"

# Analisi dettagliata delle pagine 7–8 (tabelle, campi, accettati/scartati)
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf" 7 8

# Come sopra + dump delle celle grezze di find_tables()
python debug/debug_requisiti.py "docs/3EGH489028-2358.pdf" 7 8 -raw
```

Requisito: `pip install pymupdf`.
