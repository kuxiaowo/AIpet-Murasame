"""Compatibility alias for :mod:`aipet.core.config`."""

from __future__ import annotations

import sys

from aipet.core import config as _implementation

sys.modules[__name__] = _implementation
