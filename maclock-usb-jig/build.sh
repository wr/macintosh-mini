#!/bin/sh
# Runs the tests, then writes maclock-usb-jig.{step,stl}.
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "run: python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2; exit 1; }
command -v "${OPENSCAD:-openscad}" >/dev/null 2>&1 ||
    echo "OpenSCAD isn't installed, so the tests can't check maclock-usb-jig.scad still matches." >&2
"$PY" -m unittest discover -p 'test_*.py' -v
"$PY" export.py
