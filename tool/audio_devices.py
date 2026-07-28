"""Compatibility alias for :mod:`aipet.core.audio_devices`."""

from __future__ import annotations

import sys

from aipet.core import audio_devices as _implementation

sys.modules[__name__] = _implementation
