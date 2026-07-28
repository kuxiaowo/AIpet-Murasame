"""Compatibility alias for the Windows voice trigger implementation."""

from __future__ import annotations

import sys

from aipet.platforms.windows import voice_trigger as _implementation

sys.modules[__name__] = _implementation
