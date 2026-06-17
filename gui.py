#!/usr/bin/env python3
import os
import sys
import time
import queue
import json
import threading
import webbrowser
import subprocess
from pathlib import Path
from flask import Flask, Response, render_template_string, jsonify, request

# Silenzia il warning di deprecazione di macOS per Tkinter
os.environ["TK_SILENCE_DEPRECATION"] = "1"

# Aggiungi directory locale
sys.path.append(str(Path(__file__).parent))

import main
import compiler
from logging_utils import add_log_callback

# Coda thread-safe per catturare i log dal sistema
log_queue = queue.Queue()
running_lock = threading.Lock()
is_running = False
current_action = None
active_thread = None

def gui_log_callback(level: str, msg: str):
    # Rimuove ritorni a capo finali per evitare doppie righe vuote nella console web
    msg_stripped = msg.rstrip('\n')
    log_queue.put((level, msg_stripped))

# Registra la callback dei log
add_log_callback(gui_log_callback)

app = Flask(__name__)

# Template HTML della Dashboard con stili moderni di design (Dark mode, Glassmorphism, font premium)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dispensa Generator Dashboard 📚</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #090d16;
            --bg-card: rgba(17, 24, 39, 0.7);
            --bg-terminal: #030712;
            --border: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-orange: #f59e0b;
            --accent-red: #ef4444;
            --shadow-glow: rgba(59, 130, 246, 0.15);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-main);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 40px;
            border-bottom: 1px solid var(--border);
            background: rgba(9, 13, 22, 0.85);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 10;
        }

        .logo-section h1 {
            font-size: 22px;
            font-weight: 800;
            background: linear-gradient(135deg, #3b82f6 0%, #10b981 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .logo-section p {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 2px;
            font-weight: 500;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.03);
            padding: 8px 16px;
            border-radius: 20px;
            border: 1px solid var(--border);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
        }

        .status-dot.running {
            background-color: var(--accent-orange);
            box-shadow: 0 0 8px var(--accent-orange);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { opacity: 0.4; }
            50% { opacity: 1; }
            100% { opacity: 0.4; }
        }

        main {
            display: grid;
            grid-template-columns: 380px 1fr;
            gap: 24px;
            padding: 24px 40px;
            flex-grow: 1;
            max-width: 1600px;
            width: 100%;
            margin: 0 auto;
        }

        .card {
            background: var(--bg-card);
            border-radius: 16px;
            border: 1px solid var(--border);
            backdrop-filter: blur(16px);
            padding: 28px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
            gap: 24px;
            height: fit-content;
        }

        .section-title {
            font-size: 13px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--accent-blue);
            margin-bottom: 4px;
        }

        .input-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .input-group label {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
        }

        select {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 16px;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 14px;
            outline: none;
            cursor: pointer;
            transition: all 0.2s;
            width: 100%;
        }

        select:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px var(--shadow-glow);
        }

        select option {
            background-color: var(--bg-main);
            color: var(--text-primary);
        }

        .input-group input {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 16px;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 14px;
            transition: all 0.2s;
        }

        .input-group input:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px var(--shadow-glow);
        }

        .switches {
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 8px 0;
        }

        .switch-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            user-select: none;
        }

        .switch-label {
            font-size: 14px;
            font-weight: 500;
            color: var(--text-secondary);
        }

        .switch-control {
            position: relative;
            width: 44px;
            height: 24px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            transition: background-color 0.2s;
        }

        .switch-row input {
            display: none;
        }

        .switch-row input:checked + .switch-control {
            background-color: var(--accent-blue);
        }

        .switch-control::after {
            content: '';
            position: absolute;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: white;
            top: 3px;
            left: 3px;
            transition: transform 0.2s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        .switch-row input:checked + .switch-control::after {
            transform: translateX(20px);
        }

        .button-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .btn {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 12px 18px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-align: left;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .btn:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.15);
            transform: translateY(-1px);
        }

        .btn:active:not(:disabled) {
            transform: translateY(0);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-arrow {
            opacity: 0.4;
            font-size: 12px;
            transition: transform 0.2s;
        }

        .btn:hover:not(:disabled) .btn-arrow {
            opacity: 1;
            transform: translateX(3px);
        }

        .btn-primary {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border: none;
            color: white;
            padding: 15px 20px;
            font-size: 14px;
            font-weight: 700;
            text-align: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
            letter-spacing: 0.5px;
        }

        .btn-primary:hover:not(:disabled) {
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            box-shadow: 0 6px 16px rgba(16, 185, 129, 0.3);
        }

        .btn-danger {
            background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
            border: none;
            color: white;
            padding: 15px 20px;
            font-size: 14px;
            font-weight: 700;
            text-align: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
            letter-spacing: 0.5px;
        }

        .btn-danger:hover:not(:disabled) {
            background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
            box-shadow: 0 6px 16px rgba(239, 68, 68, 0.3);
        }

        .terminal-container {
            display: flex;
            flex-direction: column;
            background: var(--bg-terminal);
            border-radius: 16px;
            border: 1px solid var(--border);
            overflow: hidden;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
        }

        .terminal-header {
            background: rgba(255, 255, 255, 0.02);
            padding: 14px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .terminal-title {
            font-size: 12px;
            font-weight: 800;
            color: var(--text-secondary);
            font-family: 'Outfit', sans-serif;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .terminal-dots {
            display: flex;
            gap: 6px;
        }

        .terminal-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #475569;
        }

        .terminal-dot.red { background: #ef4444; }
        .terminal-dot.yellow { background: #f59e0b; }
        .terminal-dot.green { background: #10b981; }

        .terminal-body {
            flex-grow: 1;
            padding: 24px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            line-height: 1.6;
            overflow-y: auto;
            color: #cbd5e1;
            height: calc(100vh - 200px);
            scroll-behavior: smooth;
        }

        .log-line {
            margin-bottom: 5px;
            white-space: pre-wrap;
        }

        .log-info { color: #e2e8f0; }
        .log-warning { color: #f59e0b; font-weight: 600; }
        .log-error { color: #f87171; font-weight: 600; }
        .log-system { color: #60a5fa; opacity: 0.9; }

        /* Custom Scrollbar */
        .terminal-body::-webkit-scrollbar {
            width: 8px;
        }

        .terminal-body::-webkit-scrollbar-track {
            background: var(--bg-terminal);
        }

        .terminal-body::-webkit-scrollbar-thumb {
            background: #1e293b;
            border-radius: 4px;
        }

        .terminal-body::-webkit-scrollbar-thumb:hover {
            background: #334155;
        }
    </style>
</head>
<body>

    <header>
        <div class="logo-section">
            <h1>NotebookLM Dispensa Generator 📚</h1>
            <p>Pannello di controllo visivo ed interattivo</p>
        </div>
        <div class="status-badge">
            <div id="statusDot" class="status-dot"></div>
            <span id="statusText">Pronto</span>
        </div>
    </header>

    <main>
        <!-- Colonna Controlli -->
        <div class="card">
            <!-- Selezione notebook dinamica -->
            <div class="input-group">
                <label for="nbSelect">Seleziona il NotebookLM</label>
                <select id="nbSelect" onchange="toggleNbInput()">
                    <option value="">Caricamento in corso...</option>
                </select>
                
                <div id="newNbContainer" style="display: none; margin-top: 10px;">
                    <label for="nbName" style="font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: 5px;">Nome Nuovo Notebook:</label>
                    <input type="text" id="nbName" placeholder="es. Psicologia dello Sviluppo">
                </div>
            </div>

            <div class="switches">
                <label class="switch-row">
                    <span class="switch-label">Forza sovrascrittura (--force)</span>
                    <input type="checkbox" id="forceSwitch">
                    <span class="switch-control"></span>
                </label>
                <label class="switch-row">
                    <span class="switch-label">Simulazione (--dry-run)</span>
                    <input type="checkbox" id="dryrunSwitch">
                    <span class="switch-control"></span>
                </label>
            </div>

            <hr style="border: 0; border-top: 1px solid var(--border)">

            <div class="button-list">
                <div class="section-title">Azioni Manuali</div>
                <button class="btn action-btn" onclick="runAction('init')">
                    <span>1. Inizializza Cartelle</span>
                    <span class="btn-arrow">➔</span>
                </button>
                <button class="btn action-btn" onclick="runAction('blueprint')">
                    <span>2. Genera Indice</span>
                    <span class="btn-arrow">➔</span>
                </button>
                <button class="btn action-btn" onclick="runAction('write')">
                    <span>3. Scrivi Capitoli</span>
                    <span class="btn-arrow">➔</span>
                </button>
                <button class="btn action-btn" onclick="runAction('concepts')">
                    <span>4. Genera Concetti (Obsidian)</span>
                    <span class="btn-arrow">➔</span>
                </button>
                <button class="btn action-btn" onclick="runAction('compile')">
                    <span>5. Compila PDF & HTML</span>
                    <span class="btn-arrow">➔</span>
                </button>
                
                <button class="btn btn-primary action-btn" onclick="runAction('all')" style="margin-top: 10px;">
                    ▶️ CREA DISPENSA COMPLETA
                </button>
                
                <button id="stopBtn" class="btn btn-danger" onclick="stopAction()" style="margin-top: 10px;" disabled>
                    🛑 INTERROMPI OPERAZIONE
                </button>
            </div>
        </div>

        <!-- Colonna Console Log -->
        <div class="terminal-container">
            <div class="terminal-header">
                <div class="terminal-title">
                    <span style="color: var(--accent-green)">●</span> console.log
                </div>
                <div class="terminal-dots">
                    <div class="terminal-dot red"></div>
                    <div class="terminal-dot yellow"></div>
                    <div class="terminal-dot green"></div>
                </div>
            </div>
            <div class="terminal-body" id="terminal"></div>
        </div>
    </main>

    <script>
        const terminal = document.getElementById('terminal');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const actionButtons = document.querySelectorAll('.action-btn');
        const stopBtn = document.getElementById('stopBtn');

        // Caricamento dei notebook dinamici all'avvio
        function loadNotebooks() {
            fetch('/get_notebooks')
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById('nbSelect');
                    select.innerHTML = '';
                    
                    const createOpt = document.createElement('option');
                    createOpt.value = '__new__';
                    createOpt.textContent = '➕ Crea nuovo notebook...';
                    select.appendChild(createOpt);
                    
                    if (data.notebooks && data.notebooks.length > 0) {
                        data.notebooks.forEach(nb => {
                            const opt = document.createElement('option');
                            opt.value = nb.title;
                            opt.textContent = nb.title;
                            select.appendChild(opt);
                        });
                        
                        // Imposta il primo notebook trovato come predefinito
                        select.value = data.notebooks[0].title;
                        document.getElementById('newNbContainer').style.display = 'none';
                    } else {
                        select.value = '__new__';
                        document.getElementById('newNbContainer').style.display = 'block';
                    }
                })
                .catch(err => {
                    appendLog('ERROR', 'Impossibile caricare i notebook da NotebookLM.');
                });
        }

        function toggleNbInput() {
            const select = document.getElementById('nbSelect');
            const container = document.getElementById('newNbContainer');
            if (select.value === '__new__') {
                container.style.display = 'block';
                document.getElementById('nbName').focus();
            } else {
                container.style.display = 'none';
            }
        }

        window.addEventListener('DOMContentLoaded', loadNotebooks);

        function appendLog(level, msg) {
            const line = document.createElement('div');
            line.classList.add('log-line');
            
            if (level === 'WARNING') {
                line.classList.add('log-warning');
                line.textContent = `[⚠️ ATTENZIONE] ${msg}`;
            } else if (level === 'ERROR') {
                line.classList.add('log-error');
                line.textContent = `[❌ ERRORE] ${msg}`;
            } else if (level === 'SYSTEM') {
                line.classList.add('log-system');
                line.textContent = `[⚙️] ${msg}`;
            } else {
                line.classList.add('log-info');
                line.textContent = msg;
            }
            
            terminal.appendChild(line);
            terminal.scrollTop = terminal.scrollHeight;
        }

        // Connessione in streaming SSE per i log in tempo reale
        const eventSource = new EventSource('/stream_logs');
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.msg) {
                appendLog(data.level, data.msg);
            }
        };

        // Verifica periodica dello stato di esecuzione
        function checkStatus() {
            fetch('/status')
                .then(r => r.json())
                .then(data => {
                    if (data.is_running) {
                        statusDot.classList.add('running');
                        statusText.textContent = `Esecuzione: ${data.action.toUpperCase()}`;
                        actionButtons.forEach(btn => btn.disabled = true);
                        stopBtn.disabled = false;
                    } else {
                        statusDot.classList.remove('running');
                        statusText.textContent = 'Pronto';
                        actionButtons.forEach(btn => btn.disabled = false);
                        stopBtn.disabled = true;
                    }
                });
        }
        
        setInterval(checkStatus, 1000);
        checkStatus();

        function runAction(action) {
            const select = document.getElementById('nbSelect');
            let nbName = "";
            
            if (select.value === '__new__') {
                nbName = document.getElementById('nbName').value.trim();
                if (!nbName) {
                    appendLog('ERROR', 'Inserisci un nome valido per il nuovo notebook.');
                    return;
                }
            } else {
                nbName = select.value;
            }

            appendLog('SYSTEM', `Avvio comando '${action.toUpperCase()}' sul notebook '${nbName}'...`);

            fetch('/run_action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, nb_name: nbName, force: document.getElementById('forceSwitch').checked, dry_run: document.getElementById('dryrunSwitch').checked })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'started') {
                    checkStatus();
                } else {
                    appendLog('ERROR', data.error || 'Impossibile avviare il processo.');
                }
            })
            .catch(err => {
                appendLog('ERROR', 'Errore di connessione al server locale.');
            });
        }

        function stopAction() {
            if (confirm("Sei sicuro di voler interrompere l'operazione in corso? Questo equivale a un'interruzione di emergenza (Ctrl+C).")) {
                appendLog('SYSTEM', 'Invio richiesta di interruzione...');
                fetch('/stop_action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'stopped' || data.status === 'stopping') {
                        appendLog('SYSTEM', 'Interruzione inviata con successo.');
                        checkStatus();
                    } else {
                        appendLog('ERROR', data.error || 'Impossibile inviare il comando di stop.');
                    }
                })
                .catch(err => {
                    appendLog('ERROR', 'Errore di connessione al server locale durante lo stop.');
                });
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/status')
def status():
    return jsonify({
        "is_running": is_running,
        "action": current_action
    })

@app.route('/get_notebooks')
def get_notebooks():
    """Endpoint che esegue 'notebooklm list --json' e restituisce i notebook."""
    res = subprocess.run(["notebooklm", "list", "--json"], capture_output=True, text=True)
    notebooks = []
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            if isinstance(data, list):
                notebooks = data
            elif isinstance(data, dict):
                notebooks = data.get("notebooks", []) or data.get("items", []) or []
        except Exception:
            pass
            
    result = [{"title": nb.get("title"), "id": nb.get("id")} for nb in notebooks if nb.get("title")]
    return jsonify({"notebooks": result})

@app.route('/run_action', methods=['POST'])
def run_action():
    global is_running, current_action, active_thread
    
    if is_running:
        return jsonify({"status": "error", "error": "Un'operazione è già in corso."}), 400
        
    data = request.json or {}
    action = data.get('action')
    nb_name = data.get('nb_name', 'Dispensa_Corso_Autonoma').strip()
    force = data.get('force', False)
    dry_run = data.get('dry_run', False)
    
    if not action:
        return jsonify({"status": "error", "error": "Azione non specificata."}), 400
        
    is_running = True
    current_action = action
    
    active_thread = threading.Thread(target=execute_backend_action, args=(action, nb_name, force, dry_run))
    active_thread.daemon = True
    active_thread.start()
    
    return jsonify({"status": "started"})

@app.route('/stop_action', methods=['POST'])
def stop_action():
    global is_running, active_thread
    if not is_running or not active_thread or not active_thread.is_alive():
        return jsonify({"status": "error", "error": "Nessuna operazione in corso."}), 400
        
    import ctypes
    thread_id = active_thread.ident
    if thread_id:
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), ctypes.py_object(KeyboardInterrupt))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), None)
            return jsonify({"status": "error", "error": "Errore durante il tentativo di interrompere l'operazione."}), 500
        
        is_running = False
        log_queue.put(("WARNING", "⚠️ Richiesta di interruzione inviata (Ctrl+C). Attesa arresto..."))
        return jsonify({"status": "stopping"})
        
    return jsonify({"status": "error", "error": "Impossibile identificare il thread dell'operazione."}), 500

def execute_backend_action(action: str, nb_name: str, force: bool, dry_run: bool):
    global is_running, current_action
    project_dir = Path(__file__).parent.resolve()
    
    try:
        # Inizializzazione Ambiente
        if action in ["init", "all"]:
            main.setup_directories(project_dir)
            main.check_env()
            if action == "init":
                log_queue.put(("INFO", "✅ Cartelle inizializzate e requisiti ambientali verificati."))
                return
                
        # Requisiti preliminari
        main.check_env()
        main.setup_directories(project_dir)
        main.create_obsidian_config(project_dir, nb_name)
        
        if not dry_run and action != "compile":
            main.get_or_create_notebook(nb_name)
            main.upload_new_sources(project_dir)
            
        # Generazione Blueprint
        if action in ["blueprint", "all"]:
            main.generate_blueprint(project_dir, notebook_name=nb_name, force=force, dry_run=dry_run)
            if action == "blueprint":
                log_queue.put(("INFO", "✅ Blueprint (Indice) creato con successo! Ora puoi procedere allo step successivo: '3. Scrivi Capitoli'."))
            
        # Micro-stesura Sezioni
        if action in ["write", "all"]:
            main.write_sections(project_dir, notebook_name=nb_name, force=force, dry_run=dry_run)
            if action == "write":
                log_queue.put(("INFO", "✅ Capitoli scritti con successo! Ora puoi procedere allo step successivo: '4. Genera Concetti (Obsidian)'."))
            
        # Generazione Concetti
        if action in ["concepts", "all"]:
            main.generate_concept_cards(project_dir, notebook_name=nb_name, force=force, chunk_size=5, dry_run=dry_run)
            if action == "concepts":
                log_queue.put(("INFO", "✅ Schede dei concetti generate con successo! Ora puoi procedere allo step successivo: '5. Compila PDF & HTML'."))
            
        # Compilazione Dispensa Completa
        if action in ["compile", "all"] and not dry_run:
            output_dir = main.get_output_dir(project_dir, nb_name)
            blueprint_path = output_dir / "blueprint.json"
            compiler.compile_dispensa(blueprint_path, output_dir)
            if action == "compile":
                log_queue.put(("INFO", f"✅ Dispensa compilata in PDF e HTML con successo! Trovi i file nella cartella 'output/{output_dir.name}'."))
            
        if action == "all":
            output_dir = main.get_output_dir(project_dir, nb_name)
            log_queue.put(("INFO", f"🎉 Generazione della dispensa completa conclusa con successo! Trovi tutti i file (PDF, HTML, file markdown e concetti per Obsidian) nella cartella 'output/{output_dir.name}'."))
        else:
            log_queue.put(("INFO", f"🎉 Operazione '{action.upper()}' conclusa con successo!"))
        
    except KeyboardInterrupt:
        log_queue.put(("WARNING", f"⚠️ Operazione '{action.upper()}' interrotta dall'utente (Ctrl+C)."))
    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        log_queue.put(("ERROR", f"Errore durante l'azione '{action.upper()}': {e}\n{err_trace}"))
    finally:
        is_running = False
        current_action = None

@app.route('/stream_logs')
def stream_logs():
    def event_stream():
        # Svuota i log precedenti in coda prima di avviare il feed
        while not log_queue.empty():
            try:
                log_queue.get_nowait()
            except queue.Empty:
                break
                
        log_queue.put(("SYSTEM", "Connessione stabilita con il motore log di background. Pronto."))
        
        while True:
            try:
                level, msg = log_queue.get(timeout=10)
                data_json = json.dumps({"level": level, "msg": msg})
                yield f"data: {data_json}\n\n"
            except queue.Empty:
                # Keep-alive per evitare timeout del browser
                yield "data: {\"level\": \"PING\", \"msg\": \"\"}\n\n"
            except Exception:
                break
                
    return Response(event_stream(), mimetype="text/event-stream")

def start_server():
    app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)

if __name__ == '__main__':
    print("🚀 Avvio del server web locale per la Dashboard...")
    
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Aspetta 1 secondo che il server Flask sia avviato
    time.sleep(1)
    
    url = "http://127.0.0.1:5001"
    print(f"🌐 Apertura automatica del browser all'indirizzo: {url}")
    webbrowser.open(url)
    
    # Mantieni attivo il thread principale
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Chiusura della Dashboard.")
