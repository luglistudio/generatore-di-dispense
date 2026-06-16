import datetime
import re
from pathlib import Path
from typing import Callable, List

# Hook per interfacce grafiche (ricevono: level, clean_msg)
_log_callbacks: List[Callable[[str, str], None]] = []

def add_log_callback(callback: Callable[[str, str], None]):
    """Aggiunge una funzione che verrà chiamata ad ogni log."""
    _log_callbacks.append(callback)

def _dispatch_callbacks(level: str, msg: str):
    # Rimuove sequenze di escape ANSI per il testo visualizzato nella GUI
    clean_msg = re.sub(r'\x1b\[[0-9;-]*m', '', msg)
    for cb in _log_callbacks:
        try:
            cb(level, clean_msg)
        except Exception:
            pass

def _log_to_file(level: str, msg: str):
    try:
        log_dir = Path(__file__).parent.resolve() / "output"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "generator.log"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Rimuove sequenze di escape ANSI per i colori dal log su file
        clean_msg = re.sub(r'\x1b\[[0-9;-]*m', '', msg)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} [{level}] {clean_msg}\n")
    except Exception:
        pass

def log_info(msg: str):
    print(msg)
    _log_to_file("INFO", msg)
    _dispatch_callbacks("INFO", msg)

def log_warning(msg: str):
    print(msg)
    _log_to_file("WARNING", msg)
    _dispatch_callbacks("WARNING", msg)

def log_error(msg: str):
    print(msg)
    _log_to_file("ERROR", msg)
    _dispatch_callbacks("ERROR", msg)
