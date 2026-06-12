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
