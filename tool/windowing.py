"""Compatibility alias for the Windows platform windowing implementation."""

from __future__ import annotations

import sys

from aipet.platforms.windows import windowing as _implementation

sys.modules[__name__] = _implementation
