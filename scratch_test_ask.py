import subprocess
import json
import tempfile
import os
import sys

from pathlib import Path
base_dir = Path(__file__).parent.resolve()
sys.path.append(str(base_dir))

source_ids = [
    "48716ce2-a88b-4ebd-bcf2-3347f5adca1b",
    "27b92204-f4f6-4c58-a2e3-5ad95a41c710",
    "43ada8b3-c344-4455-9514-d3c6cf0b1c79",
    "f45728ce-5892-4d00-b91e-4cba0476d37d"
]

# Leggi la sezione 1.1 appena generata
sec_file = base_dir / "output" / "Sezione_1_1.md"
if not sec_file.exists():
    print(f"⚠️ Errore: Il file {sec_file} non esiste. Assicurati di generarlo prima.")
    sys.exit(1)

with open(sec_file, "r", encoding="utf-8") as f:
    section_content = f.read()

import prompts
prompt_qa = prompts.QA_GENERATOR_PROMPT.format(
    section_number="1.1",
    section_title="Introduzione all'Antropologia e Metodologia",
    section_content=section_content
)

print(f"Dimensione prompt: {len(prompt_qa)} caratteri")

with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as temp_file:
    temp_file.write(prompt_qa)
    temp_file_path = temp_file.name

try:
    cmd = ["notebooklm", "ask", "--json", "--new", "-y"]
    for s_id in source_ids:
        cmd += ["-s", s_id]
    cmd += ["--prompt-file", temp_file_path]
    
    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"Return code: {res.returncode}")
    print("Stdout (first 500 chars):")
    print(res.stdout[:500])
    print("Stderr:")
    print(res.stderr)
finally:
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)
