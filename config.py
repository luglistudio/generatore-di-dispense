import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Carica il file .env sia dalla directory locale che da quella principale del workspace
env_locations = [
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent / ".env",
    Path.cwd() / ".env",
]

for env_path in env_locations:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

# Configurazione di base per dispensa_generator

def check_notebooklm_auth() -> bool:
    """Verifica se l'utente è autenticato su NotebookLM tramite la CLI."""
    try:
        res = subprocess.run(
            ["notebooklm", "auth", "check", "--test", "--json"],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode != 0:
            return False
        
        import json
        data = json.loads(res.stdout)
        return data.get("status") == "ok"
    except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError):
        # Fallback nel caso in cui la CLI non sia installata o ritorni errori strani
        return False

def get_notebooklm_profile() -> str:
    """Ritorna il profilo attivo di NotebookLM se disponibile."""
    return os.environ.get("NOTEBOOKLM_PROFILE", "default")
