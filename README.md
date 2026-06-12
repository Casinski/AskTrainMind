# AskTrainMind

Applicazione desktop Windows (PySide6) per interrogare il database Excel ETR1000 e confrontare le configurazioni di flotta.

---

## Per gli utenti finali (eseguire l'EXE)

### Dove scaricare AskTrainMind.exe
- **Da una GitHub Release**: vai nella sezione *Releases* del repository → clicca sull'ultima versione → scarica `AskTrainMind.exe` dagli *Assets*.
- **Da un artifact CI**: vai in *Actions* → seleziona l'ultima run della workflow *Build Windows EXE* → scarica `AskTrainMind-windows.zip` (contiene `AskTrainMind.exe`).

### Avvio
- **L'EXE è portatile**: non richiede installazione. Basta un doppio clic su `AskTrainMind.exe`.
- Al primo avvio Windows SmartScreen potrebbe mostrare "Windows ha protetto il PC": clicca **Ulteriori informazioni** → **Esegui comunque**.
- Analogamente, alcuni antivirus possono contrassegnare un eseguibile non firmato; aggiungi un'eccezione o contatta l'IT.

### Primo avvio e connessione SharePoint
- All'avvio l'app prova a scaricare automaticamente il file Excel dal SharePoint aziendale.
- Comparirà una finestra di login Microsoft: accedi con il tuo **account aziendale** (@gruppofsitaliane.com o equivalente).
- Se la connessione non è disponibile (rete assente, VPN non attiva, permessi), comparirà il pulsante **Import excel file DB fleets** (icona Excel): clicca per selezionare manualmente il file `.xlsx`.

### Dove vengono salvati dati, config e cache
| Tipo | Percorso |
|------|----------|
| Configurazione AI e impostazioni | `%APPDATA%\AskTrainMind\config.json` |
| Knowledge base (note utente) | `%APPDATA%\AskTrainMind\knowledge.json` |
| Cache documenti SharePoint | `%LOCALAPPDATA%\AskTrainMind\documents\` |

---

## Come funziona l'app

### Workflow principale: Find → Ask → Risultati

1. **Find**: digita nella textbox principale una domanda in linguaggio naturale (es. *"Come funziona il FAM? Componente GG-A024"*) e clicca **Find**. L'app estrae le parole chiave e mostra una lista di ID-Funzione candidati.
2. **Selezione**: seleziona uno o più ID dalla lista (puoi fare selezione multipla).
3. **Ask**: clicca il pulsante verde **Ask** (con icona treno). L'app recupera i documenti collegati in background, poi apre la finestra **Risultati**.
   - Se modifichi la domanda dopo un Find, il pulsante Ask si ri-disabilita (devi rifare Find).

### Finestra Risultati
- **LINK**: tutti i link ai documenti SharePoint per gli ID selezionati, suddivisi per configurazione di flotta. Quando è disponibile un *Rif. Pagina*, compare anche il link 📖 *Apri a pagina N*.
- **INFO**: sintesi delle funzioni/ID selezionati per tutte le configurazioni di flotta. Con AI configurata: testo elaborato dal modello; offline: sintesi deterministica.
- **DIFFERENZE** (sezione principale): confronto tra configurazioni — tabella con legenda colori:
  - 🟢 verde = uguale tra le configurazioni
  - 🟡 ambra = parziale (alcune configurazioni senza documento/valore)
  - 🔴 rosso = diverso

### AI opzionale (Azure OpenAI / OpenAI)
Da **Settings → AI Provider...** configura provider, endpoint, model/deployment e API key.  
Senza configurazione, l'app funziona comunque in **modalità offline deterministica** (NullProvider) — nessun crash.

#### Vision
Attivabile in Settings. Quando attiva con modello compatibile (es. `gpt-4o`), le immagini del workbook e dei documenti vengono inviate al modello.

### "Improve Mind" — Knowledge Base
- La textbox piccola + pulsante **Improve Mind** salvano una nota strutturata associata agli ID-Funzione selezionati.
- Le note sono persistite in `%APPDATA%\AskTrainMind\knowledge.json`.
- Nelle ricerche successive, le note pertinenti compaiono nella sezione **INFO** sotto il blocco *📝 Note utente / Knowledge base*.
- Se era presente il vecchio file `~\.asktrainmind_notes.txt` (versione precedente), le note vengono migrate automaticamente al primo avvio.

---

## Per chi costruisce l'EXE (sviluppatore)

### Prerequisiti
- Python 3.11+
- `pip`
- (Facoltativo) PyInstaller

### Installazione dipendenze
```bash
pip install -r requirements.txt
```

### Avvio in modalità sviluppo
```bash
python -m asktrainmind.main
```

### Eseguire i test
```bash
pytest -q tests
```
I test non richiedono rete né chiave AI.

### Build dell'EXE

#### Metodo consigliato: file `.spec`
```bash
pip install pyinstaller
pyinstaller --noconfirm build/AskTrainMind.spec
```
Output: `dist/AskTrainMind.exe`

#### Alternativa: comando one-file esplicito
```bash
pyinstaller --noconfirm --onefile --windowed --name AskTrainMind \
  --add-data "asktrainmind/ui/style.qss;asktrainmind/ui" \
  --add-data "asktrainmind/resources;asktrainmind/resources" \
  --hidden-import fitz --hidden-import fitz._fitz \
  --collect-submodules openpyxl \
  asktrainmind/main.py
```

#### Cosa include lo spec
- `asktrainmind/ui/style.qss` (fogli di stile)
- `asktrainmind/resources/` (icone SVG)
- Hidden imports: `openpyxl`, `fitz` (PyMuPDF), `docx`, `msal`, `openai`, PySide6

#### `--onefile` vs `--onedir`
| Modalità | Pro | Contro |
|----------|-----|--------|
| `--onefile` (default spec) | Un solo file, facilmente distribuibile | Avvio più lento (decompressione in temp); più falsi positivi AV |
| `--onedir` | Avvio più rapido; meno falsi positivi AV | Cartella da distribuire (comprimere in ZIP) |

Per distribuire in onedir: usa `dist/AskTrainMind/` (intera cartella).

#### Firma del codice (opzionale)
Per eliminare il warning SmartScreen, firma `AskTrainMind.exe` con un certificato code-signing aziendale tramite `signtool.exe` (Windows SDK).

### Come usare la GitHub Action (CI/CD)

La workflow `.github/workflows/build-windows-exe.yml`:
1. **Esegue i test** su `windows-latest`.
2. **Costruisce `dist/AskTrainMind.exe`** con PyInstaller.
3. **Carica l'EXE** come artifact `AskTrainMind-windows` (scaricabile da *Actions*).
4. **Allega l'EXE alla Release** su GitHub quando il trigger è un tag `v*` o un *release published*.

#### Come rilasciare una nuova versione
```bash
git tag v1.2.3
git push origin v1.2.3
```
Oppure crea una Release su GitHub (pulsante *Draft a new release*) e pubblica con un tag `v*`.  
In alternativa, avvia la workflow manualmente da *Actions → Build Windows EXE → Run workflow*.

#### Scaricare l'artifact
- Vai in *Actions* → seleziona la run → sezione *Artifacts* → `AskTrainMind-windows`.

---

## Struttura del progetto

```
asktrainmind/
  app/
    ai_engine.py        # Provider AI (OpenAI/Azure/Null) + AnalysisEngine
    comparison.py       # Motore di confronto deterministico tra configurazioni
    config.py           # AIConfig, appdata_dir, cache_dir, resource_path
    document_extractor.py # Estrazione testo/immagini da PDF/DOCX
    document_fetcher.py   # Download documenti SharePoint (MS Graph)
    excel_loader.py     # Caricamento workbook + immagini
    excel_model.py      # Modello dati: FunctionRecord, DocumentRecord, DetailRecord
    image_extractor.py  # Selezione immagini rilevanti dal workbook
    keyword_extractor.py # Estrazione keyword + ranking ID-Funzione
    knowledge_base.py   # Knowledge base persistente (add/search/list/migrate)
    page_reference.py   # Parsing Rif. Pagina + deep-link PDF
    sharepoint.py       # Auth MSAL + download file da SharePoint
  ui/
    main_window.py      # Finestra principale (Find/Ask/Improve Mind)
    results_view.py     # Finestra Risultati (LINK/INFO/DIFFERENZE)
    settings_dialog.py  # Dialog Settings AI
    style.qss           # Foglio di stile Qt
    widgets.py          # Widget riutilizzabili (icon_button)
  main.py               # Entry point
build/
  AskTrainMind.spec     # Spec PyInstaller
tests/                  # Test pytest (offline, no AI)
requirements.txt
README.md
```

---

## Dipendenze principali

| Libreria | Uso |
|----------|-----|
| PySide6 | GUI desktop Qt |
| openpyxl | Lettura file Excel (.xlsx) |
| msal | Autenticazione Microsoft (SharePoint) |
| requests | HTTP (download documenti) |
| pymupdf | Estrazione testo/immagini PDF |
| python-docx | Estrazione testo DOCX (opzionale) |
| openai | Provider AI (opzionale) |
| pyinstaller | Build EXE (solo sviluppatori) |

---

## Note e limitazioni note

- **OCR per PDF scansionati**: non supportato (deferred).
- **PPTX/XLSX collegati**: non estratti (deferred).
- **Firma codice**: non inclusa nella workflow (aggiungi `signtool` se necessario).
- L'app funziona completamente **offline** (senza rete e senza chiave AI); SharePoint e AI sono opzionali.
