#!/usr/bin/env python3
"""Compatibility entry point for ``enchiridion doctor``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enchiridion.doctor import main  # noqa: E402

if __name__ == "__main__":
    main()
