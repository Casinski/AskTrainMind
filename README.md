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

### Primo avvio
- All'avvio non viene eseguito alcun download automatico del database workbook.
- Usa sempre il pulsante **Import excel file DB fleets** (icona Excel) per caricare manualmente il file `.xlsx`.

### Dove vengono salvati dati, config e cache
| Tipo | Percorso |
|------|----------|
| Configurazione AI e impostazioni | `%APPDATA%\AskTrainMind\config.json` |
| Knowledge base (note utente) | `%APPDATA%\AskTrainMind\knowledge.json` |
| Cache documenti SharePoint | `%LOCALAPPDATA%\AskTrainMind\documents\` |

---

## Come funziona l'app

### Workflow principale: Find → Ask → Risultati

1. **Find (blu)**: digita nella textbox principale una domanda in linguaggio naturale (es. *"Come funziona il FAM? Componente GG-A024"*) e clicca **Find**. L'app estrae le parole chiave e mostra una lista di ID-Funzione candidati.
2. **Selezione**: seleziona uno o più ID dalla lista (puoi fare selezione multipla).
3. **Ask (verde / grigio se disabilitato)**: clicca **Ask** (con icona treno). Il pulsante si abilita solo dopo **Find + selezione di almeno un ID**.
   - Se la domanda è vuota, Ask resta disabilitato.
   - Se modifichi la domanda dopo un Find, Ask si ri-disabilita (devi rifare Find e riselezionare).
4. I risultati si aprono in una tab separata **Risultati** (chiudibile), senza sovrascrivere la tab principale AskTrainMind.

### Tab Risultati
- **LINK**: link raggruppati per configurazione/flotta, con titolo documento. Il resolver valuta le formule Excel (`HYPERLINK`, `CONCATENATE`, operatore `&`, riferimenti di cella) per costruire URL reali e cliccabili.
  - Solo gli URL validi (http/https/file/www/UNC/percorso Windows) diventano link cliccabili; il testo semplice non-URL è mostrato come testo (nessun link morto).
  - Un clic apre il target nel browser/applicazione predefinita. La sezione "📖 Apri a pagina N" è attiva solo per URL reali e, se il documento è in cache locale, lo apre direttamente alla pagina anche offline.
  - È presente anche il gruppo **Generale / Documenti supplementari**.
- **DIFFERENZE** (sezione principale): due sottosezioni distinte.
  - **Discorso complessivo** (visibile): un unico testo discorsivo in italiano che spiega come il gruppo dell'ID-Funzione selezionato si comporta al variare delle configurazioni — con parti comuni e parti differenti, riferimenti ai DOC ID, ai nomi flotta/configurazione e ai riferimenti incrociati tra ID. Può contenere liste, ma resta un discorso unico per tutte le configurazioni.
  - **Analisi dettagliata** (nascosta per default): comprimibile con il pulsante "▸ Mostra analisi dettagliata". Contiene l'analisi strutturata della Mente locale (componenti comuni/extra, descrizione circuitale, righe che variano, riferimenti incrociati tra ID) più la tabella a colori di confronto:
    - 🟢 verde = uguale tra le configurazioni
    - 🟡 ambra = parziale (alcune configurazioni senza documento/valore)
    - 🔴 rosso = diverso
- Le sezioni LINK e DIFFERENZE restano compilate anche completamente offline (senza internet e senza chiave AI). Con un provider AI (OpenAI/Azure) il discorso complessivo è generato dal modello, mentre l'analisi dettagliata è sempre quella deterministica dai dati Excel.

### AI opzionale (Azure OpenAI / OpenAI)
Da **Settings → AI Provider...** configura provider, endpoint, model/deployment e API key.  
Senza configurazione, l'app funziona comunque in **modalità locale/offline** con analisi deterministica dai dati Excel — nessun crash.

#### Vision
Attivabile in Settings. Quando attiva con modello compatibile (es. `gpt-4o`), le immagini del workbook e dei documenti vengono inviate al modello.

### "Improve Mind" — Knowledge Base
- La textbox piccola + pulsante **Improve Mind** salvano una nota strutturata associata agli ID-Funzione selezionati.
- Le note sono persistite in `%APPDATA%\AskTrainMind\knowledge.json`.
- Nelle ricerche successive, le note pertinenti vengono usate come contesto nell'analisi.
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
    sharepoint.py       # Auth MSAL + helper Graph condivisi
  ui/
    main_window.py      # Finestra principale (Find/Ask/Improve Mind)
    results_view.py     # Tab Risultati (LINK/DIFFERENZE)
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
