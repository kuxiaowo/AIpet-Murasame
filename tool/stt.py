"""Compatibility alias for :mod:`aipet.core.stt`."""

from __future__ import annotations

import sys

from aipet.core import stt as _implementation

sys.modules[__name__] = _implementation
