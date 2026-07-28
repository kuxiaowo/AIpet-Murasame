"""Compatibility alias for :mod:`aipet.core.tts_service`."""

from __future__ import annotations

import sys

from aipet.core import tts_service as _implementation

sys.modules[__name__] = _implementation
