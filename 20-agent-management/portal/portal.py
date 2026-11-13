#!/usr/bin/env python3
"""Compat shim — Python portal lives in python/portal.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "python" / "portal.py"

print(
    "Note: portal entry moved to portal/python/portal.py — launching that.",
    flush=True,
)
os.execv(sys.executable, [sys.executable, str(TARGET), *sys.argv[1:]])
