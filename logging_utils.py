import datetime
import re
from pathlib import Path

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

def log_warning(msg: str):
    print(msg)
    _log_to_file("WARNING", msg)

def log_error(msg: str):
    print(msg)
    _log_to_file("ERROR", msg)
