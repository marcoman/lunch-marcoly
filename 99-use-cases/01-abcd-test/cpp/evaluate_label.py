#!/usr/bin/env python3
"""Helper for the C++ implementation: evaluate the count label via abcd_eval."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from abcd_eval import close_client, evaluate_count_label, init_client  # noqa: E402


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    if not username:
        print("Count")
        return
    init_client()
    try:
        print(evaluate_count_label(username))
    finally:
        close_client()


if __name__ == "__main__":
    main()
