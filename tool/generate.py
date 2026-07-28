"""Compatibility alias for :mod:`aipet.core.generate`."""

from __future__ import annotations

import sys

from aipet.core import generate as _implementation

sys.modules[__name__] = _implementation
