"""Compatibility alias for :mod:`aipet.core.runtime_logging`."""

from __future__ import annotations

import sys

from aipet.core import runtime_logging as _implementation

sys.modules[__name__] = _implementation
