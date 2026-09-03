#!/usr/bin/env python3
"""Compatibility entry point for ``enchiridion rules render``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enchiridion.render_rules import main  # noqa: E402

if __name__ == "__main__":
    main()
