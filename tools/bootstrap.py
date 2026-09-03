#!/usr/bin/env python3
"""Compatibility entry point for ``enchiridion bootstrap``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enchiridion.bootstrap import main  # noqa: E402
from enchiridion.harness import remove_harness  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--remove":
        remove_harness(sys.argv[2])
    else:
        main()
