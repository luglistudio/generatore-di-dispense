# NotebookLM Dispensa Generator 📚🤖

Uno strumento CLI potente, resiliente e autogestito in Python per convertire lezioni registrate (file audio), slide e note di corsi universitari caricate in **Google NotebookLM** in dispense di studio complete e strutturate, corredate da schede concettuali collegate (in formato Obsidian Wikilink) e PDF esportabili con un layout grafico professionale di alta qualità.

---

## 🌟 Caratteristiche Principali

1. **Profilazione & Pianificazione Didattica Multi-Step**:
   * Suddivide il processo di stesura in 5 step incrementali (Profilazione, Struttura Capitoli, Sotto-Sezioni, Audit Sillabo, Verifica Fonti).
   * Evita i limiti di token e le risposte incomplete di NotebookLM costringendolo a pianificare batch di sezioni progressivamente, supportando stesure su vasta scala.
2. **Resilienza e Ripresa (State Machine Checkpoints)**:
   * Lo stato viene salvato progressivamente in `blueprint_state.json`. In caso di interruzioni di rete, errori API o crash, il programma riprenderà esattamente dal capitolo o dallo step in cui si è fermato, senza perdere il lavoro pregresso.
3. **Resistenza ai Limiti API & Backoff**:
   * Implementa un algoritmo di retry con **backoff esponenziale e jitter** basato sull'orologio di sistema (nanosecondi) per evitare conflitti o blocchi temporanei dovuti a rate-limiting.
   * Timeout configurato su ciascuna chiamata per prevenire blocchi indefiniti.
4. **Audit di Copertura Automatico**:
   * Esegue un controllo di consistenza confrontando la bozza della dispensa pianificata con le slide e il sillabo ufficiale. Identifica automaticamente eventuali argomenti d'esame tralasciati e li inietta nel blueprint prima di scrivere il testo.
5. **Schede Concettuali per Obsidian Vault**:
   * Estrae i termini e i concetti chiave da ciascuna sezione e genera schede di glossario dedicate in formato Markdown.
   * Supporta la sintassi nativa degli Obsidian Wikilink con alias (`[[Concetto|Alias]]` e `[[path/to/Page]]`) per consentire la visualizzazione e navigazione tramite il grafo semantico nativo di Obsidian.
6. **Compilazione Premium HTML & PDF**:
   * Unifica tutte le sezioni scritte in un'unica dispensa finale.
   * Genera automaticamente una **Table of Contents (TOC)** nidificata ed elegante (capitoli e paragrafi) basata su regole CSS premium.
   * Compila il file finale in PDF tramite Weasyprint, Google Chrome Headless, o Pandoc/LaTeX a seconda di cosa è installato sul sistema ospite.
7. **Simulazione CLI (`--dry-run`)**:
   * Permette di testare l'intera pipeline di stesura e generazione delle schede per verificare il conteggio stimato delle parole e l'elenco dei concetti mancanti senza effettuare chiamate API effettive.

---

## 📂 Struttura del Progetto

```text
dispensa_generator/
├── config.py              # Gestione della configurazione locale e autenticazione NotebookLM CLI
├── prompts.py             # Raccolta dei prompt strutturati in italiano per la generazione didattica
├── logging_utils.py       # Utilità di logging condivisa, thread-safe e formattata per file e console
├── main.py                # Core application: gestione CLI, pipeline, state machine e API
├── compiler.py            # Parser Markdown, Wikilink resolver e compilatore HTML/PDF
├── run.sh                 # Script wrapper bash con direttive di hardening (set -euo pipefail)
├── requirements.txt       # Dipendenze Python minimali necessarie
├── LICENSE                # Licenza MIT del software
└── README.md              # Documentazione del progetto (questo file)
```

---

## 🛠️ Requisiti di Sistema

* **Python**: versione `3.9` o superiore.
* **NotebookLM CLI**: La CLI ufficiale di Google NotebookLM installata sul sistema e autenticata con il proprio account Google Cloud/Workspace.
* **Compilatore PDF (Opzionale)**: Google Chrome / Chromium (consigliato su Mac/Windows per un rendering fedele di MathJax/Mermaid) oppure `weasyprint` o `pandoc` con `xelatex`.

---

## 🚀 Installazione e Primo Avvio

1. Clona la repository o copia i file in una cartella locale.
2. Rendi eseguibile lo script wrapper:
   ```bash
   chmod +x run.sh
   ```
3. Installa le dipendenze Python:
   ```bash
   pip install -r requirements.txt
   ```
4. Inizializza la struttura delle cartelle locali e verifica l'autenticazione a Google NotebookLM:
   ```bash
   ./run.sh --action init
   ```
   Questo comando verificherà l'autenticazione CLI e creerà le seguenti cartelle nella root del progetto:
   * `raw_sources/`: cartella dove posizionare le trascrizioni (.txt), slide (.pdf) o note.
   * `output/`: cartella in cui verranno posizionati il blueprint, il log di sistema e i file finali.

---

## 📖 Guida all'Utilizzo

Il generatore si pilota interamente tramite argomenti da terminale. Di seguito sono elencati i comandi principali:

### 1. Generazione del Blueprint (Pianificazione)
Analizza il materiale nel notebook e stila la struttura dei capitoli e delle singole sezioni, eseguendo l'audit di copertura sul sillabo.
```bash
./run.sh -n "Nome_Notebook" --action blueprint
```

### 2. Micro-stesura delle Sezioni
Avvia la scrittura automatizzata di ciascuna sezione pianificata nel blueprint. Ciascuna sezione viene salvata singolarmente come file `.md` all'interno di `output/sections/`.
```bash
./run.sh -n "Nome_Notebook" --action write
```
* **Rigenerare una singola sezione**: Puoi rigenerare una specifica sezione (es. la `1.2`) forzando la scrittura:
  ```bash
  ./run.sh -n "Nome_Notebook" --action write --section 1.2 --force
  ```

### 3. Generazione Schede Concettuali (Obsidian)
Scansiona i testi scritti per trovare concetti racchiusi tra doppie parentesi quadre `[[...]]` e interroga NotebookLM per compilare una scheda di definizione per ciascun concetto.
```bash
./run.sh -n "Nome_Notebook" --action concepts --concept-chunk-size 5
```

### 4. Compilazione Finale HTML/PDF
Unisce la dispensa, applica gli stili grafici avanzati, risolve i link interni, crea la Table of Contents e compila in HTML e PDF.
```bash
./run.sh --action compile
```

### 5. Esecuzione Completa
Per eseguire tutti gli step in sequenza ordinata:
```bash
./run.sh -n "Nome_Notebook" --action all
```

### 🧪 Modalità Simulazione (Dry-run)
Aggiungi `--dry-run` a qualsiasi comando di generazione per vedere in anteprima cosa accadrebbe senza effettuare chiamate reali o consumare quote API:
```bash
./run.sh -n "Nome_Notebook" --action write --dry-run
```

---

## 🛡️ Sicurezza e Best Practices

* **Nessun Dato Sensibile**: Non caricare mai chiavi API o password nella repository. Il file `.env` locale viene automaticamente ignorato dal controllo di versione di Git grazie al file `.gitignore`.
* **Mappatura delle Fonti**: Assicurati che i nomi delle fonti indicati nel blueprint corrispondano esattamente o inizino con gli stessi caratteri dei titoli dei file caricati nel notebook su Google NotebookLM per garantire una precisione del 100% durante l'estrazione.

---

## 📄 Licenza

Questo progetto è rilasciato sotto i termini della licenza **MIT**. Consulta il file `LICENSE` per ulteriori dettagli.
