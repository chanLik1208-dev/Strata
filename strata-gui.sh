#!/usr/bin/env bash
# Strata's desktop launcher (strata_gui.py). Needs Python's tkinter (Ubuntu: sudo apt install python3-tk).
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then exec .venv/bin/python strata_gui.py "$@"; fi
exec python3 strata_gui.py "$@"
