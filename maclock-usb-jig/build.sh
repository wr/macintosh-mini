#!/bin/sh
# Runs the tests, then writes maclock-usb-jig.{step,stl}.
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "run: python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2; exit 1; }
"$PY" -m unittest discover -p 'test_*.py' -v
"$PY" export.py
