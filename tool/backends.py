"""Compatibility alias for :mod:`aipet.core.backends`."""

from __future__ import annotations

import sys

from aipet.core import backends as _implementation

sys.modules[__name__] = _implementation
