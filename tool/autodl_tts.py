"""Compatibility alias for :mod:`aipet.core.autodl_tts`."""

from __future__ import annotations

import sys

from aipet.core import autodl_tts as _implementation

sys.modules[__name__] = _implementation
