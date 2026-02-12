"""Entry-point wrapper for the Qt UI."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ui_qt.main import main


if __name__ == "__main__":
    main()
