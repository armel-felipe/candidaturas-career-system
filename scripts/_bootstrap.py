from __future__ import annotations

import sys
from pathlib import Path


def bootstrap() -> Path:
    root = Path(__file__).resolve().parent.parent
    src = root / "src"
    scripts = root / "scripts"
    for candidate in (str(src), str(scripts), str(root)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    return root

