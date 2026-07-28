"""Compatibility alias for :mod:`aipet.core.cache`."""

from __future__ import annotations

import sys

from aipet.core import cache as _implementation

sys.modules[__name__] = _implementation
