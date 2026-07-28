"""Compatibility alias for :mod:`aipet.ui.pet`."""

from __future__ import annotations

import sys

from aipet.ui import pet as _implementation

sys.modules[__name__] = _implementation
