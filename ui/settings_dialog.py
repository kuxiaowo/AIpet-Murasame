"""Compatibility alias for :mod:`aipet.ui.settings_dialog`."""

from __future__ import annotations

import sys

from aipet.ui import settings_dialog as _implementation

sys.modules[__name__] = _implementation
