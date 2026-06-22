#!/usr/bin/env python3
"""Exercise the ABCD navigation count label test (Python console application)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiment_common import main

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    main([sys.executable, str(here / "01-abcd-test.py")])
