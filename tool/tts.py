"""Compatibility alias for :mod:`aipet.core.tts`."""

from __future__ import annotations

import sys

from aipet.core import tts as _implementation

sys.modules[__name__] = _implementation
