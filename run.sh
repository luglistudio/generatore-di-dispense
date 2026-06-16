#!/bin/bash
set -euo pipefail

# Script di avvio compatto per la dispensa generator
uv run --with python-dotenv --with markdown --with jinja2 --with notebooklm-py python3 main.py "$@"
