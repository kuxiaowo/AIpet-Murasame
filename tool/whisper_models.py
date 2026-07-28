"""Compatibility alias for :mod:`aipet.core.whisper_models`."""

from __future__ import annotations

import sys

from aipet.core import whisper_models as _implementation

sys.modules[__name__] = _implementation
