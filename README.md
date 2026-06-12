# AskTrainMind

Applicazione desktop Windows (PySide6) per interrogare il database Excel ETR1000 e confrontare le configurazioni di flotta.

## 1) Prerequisiti
- Python 3.11+
- `pip`

## 2) Installazione dipendenze e avvio in sviluppo
```bash
pip install -r requirements.txt
python -m asktrainmind.main
```
(Alternativa: `python asktrainmind/main.py`)

## 3) SharePoint + fallback import manuale
All'avvio l'app tenta il download automatico da SharePoint con autenticazione aziendale (MSAL, login interattivo/device-code).  
Se non riesce (rete, permessi, login, file non trovato), l'app non va in crash e mostra il pulsante **Import excel file DB fleets** (icona Excel) per selezionare manualmente il `.xlsx`.

## 4) AI opzionale (Azure OpenAI / OpenAI)
Da **Settings → AI Provider...** puoi configurare provider, endpoint, model/deployment e API key.  
Configurazione salvata in profilo utente (`%APPDATA%/AskTrainMind/config.json` su Windows).  
Se non configuri chiavi, l'app usa automaticamente modalità deterministica offline (NullProvider) e continua a funzionare.

### INFO + DIFFERENZE (Phase 2)
- **INFO** mostra una sintesi HTML delle funzioni/ID selezionate, raggruppata per documenti/configurazioni.
- **DIFFERENZE** è la sezione principale: include una tabella di confronto tra configurazioni (config dinamiche del file Excel) con legenda:
  - **verde = uguale**
  - **ambra = parziale** (alcune configurazioni senza valore/documento)
  - **rosso = diverso**
- Sia INFO sia DIFFERENZE possono mostrare immagini estratte dal workbook (`Funzioni`) rilevanti alla selezione.

### Vision (opzionale)
- In **Settings → AI Provider...** puoi attivare **Abilita Vision**.
- Quando attiva e con modello compatibile (es. `gpt-4o`, `gpt-4o-mini`), le immagini vengono inviate anche al provider AI.
- Se Vision è disattivata, modello non compatibile, libreria `openai` mancante o chiavi assenti, il comportamento degrada in modo sicuro a testo/offline senza crash.

## 5) Build EXE portatile (PyInstaller)
Installa PyInstaller:
```bash
pip install pyinstaller
```

### One-file (portatile singolo exe)
```bash
pyinstaller --noconfirm --onefile --windowed --name AskTrainMind --add-data "asktrainmind/ui/style.qss;asktrainmind/ui" --add-data "asktrainmind/resources;asktrainmind/resources" asktrainmind/main.py
```

### Con file `.spec`
```bash
pyinstaller build/AskTrainMind.spec
```

Output principale: `dist/AskTrainMind.exe`.
Distribuisci direttamente questo exe ai colleghi.
Lo spec continua a includere `asktrainmind/ui/style.qss` e `asktrainmind/resources`.

### Nota antivirus e alternativa onedir
Con `--onefile` possono comparire falsi positivi antivirus. In quel caso usa `--onedir` (cartella distribuibile) e valuta firma del codice per ridurre warning di sicurezza.

## 6) Document Intelligence (Phase 3)

### Documenti collegati: quali link vengono aperti
Dopo ogni **Ask**, l'app recupera in background (senza bloccare la UI) i documenti collegati trovati nel foglio `Funzioni`:
- **Colonne F–L** (`config_links`): un link per ogni configurazione di flotta per ogni `DOC ID`.
- **Colonna GENERALE** (`generale_link`): cartella o documento supplementare a livello di ID-Funzione.

Il recupero avviene tramite lo stesso login aziendale SharePoint usato per scaricare il file Excel (MSAL, MS Graph API `/shares/{token}/driveItem`). Se offline, permessi negati o login rifiutato, i documenti vengono saltati con un messaggio inline — nessun crash, la finestra Risultati si apre comunque.

Puoi disabilitare il recupero automatico dei documenti in `Settings → AI Provider... → Scarica documenti collegati` (impostazione `fetch_documents`).

### Deep-link a `Rif. Pagina`
Il terzo livello del foglio `Funzioni` può contenere righe **Rif. Pagina** con valori come `12`, `p. 12`, `pag 12-14`, `12, 15`.

Nella sezione **LINK** dei Risultati, per ogni configurazione che ha un documento e un `Rif. Pagina`, compare il link **📖 Apri a pagina N** (uno per pagina/range) che apre il PDF localmente alla pagina specificata via `file://...#page=N` (supportato da Acrobat, Okular, ecc.).

### Estrazione testo e immagini dai documenti
- **PDF** (principale): testo per pagina e immagini incorporate via **PyMuPDF** (`pymupdf`). Se PyMuPDF non è installato, il documento viene saltato con una nota informativa — il resto dell'app funziona normalmente.
- **DOCX** (opzionale): testo via `python-docx` se installato; altrimenti saltato.
- **PPTX / XLSX / altri**: non supportati in questa fase (Phase 3). Deferred a Phase 4.
- **OCR** per PDF scansionati: deferred a Phase 4.

### Dipendenza opzionale: PyMuPDF
```bash
pip install pymupdf
```
Inclusa in `requirements.txt`. Se mancante al runtime (es. build `--onefile` senza hook), l'app degrada gracefully: mostra una nota "PyMuPDF non installato" nel messaggio dei risultati.

#### Note per la build PyInstaller con PyMuPDF
Aggiungi i hidden imports allo `.spec` o alla riga di comando:
```bash
pyinstaller ... --hidden-import=fitz --hidden-import=fitz._fitz
```
oppure nel file `build/AskTrainMind.spec`:
```python
hiddenimports=['fitz', 'fitz._fitz'],
```
Verifica che il file `mupdf` (e `.dll` su Windows) sia incluso nella cartella di output.

### Testo ed immagini dei documenti in INFO/DIFFERENZE
Quando i documenti vengono scaricati e analizzati:
- Il testo delle pagine di riferimento (da `Rif. Pagina`) è incluso nel grounding del prompt AI (INFO e DIFFERENZE).
- In modalità offline/deterministica, il testo estratto compare direttamente nelle sezioni INFO e DIFFERENZE (HTML, con distinto blocco `doc-extracts`).
- Le immagini dei documenti vengono passate al provider AI se Vision è attiva e il modello la supporta (stesso comportamento delle immagini del workbook, Phase 2).

### Barra di progresso documenti
Durante il recupero in background, la finestra principale mostra una riga di stato (`⏳ Scaricando: …`). Al termine (`✅ N documento/i processato/i`) si apre automaticamente la finestra Risultati. Se il recupero fallisce su tutti i documenti, la finestra si apre comunque con i dati dal solo workbook.

