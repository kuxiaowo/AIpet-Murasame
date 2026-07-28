"""Compatibility alias for :mod:`aipet.core.tts_assets`."""

from __future__ import annotations

import sys

from aipet.core import tts_assets as _implementation

sys.modules[__name__] = _implementation
