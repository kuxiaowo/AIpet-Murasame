"""Compatibility alias for :mod:`aipet.core.workers`."""

from __future__ import annotations

import sys

from aipet.core import workers as _implementation

sys.modules[__name__] = _implementation
