"""Compatibility entrypoint for the Windows console log viewer."""

from __future__ import annotations

import sys

from aipet.platforms.windows import log_viewer as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
