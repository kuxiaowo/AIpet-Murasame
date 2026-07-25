from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from classes.murasame_class import Murasame
from tool.config import AppSettings
from ui.settings_dialog import SettingsDialog


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_dialog_and_pet_construct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("AIPET_DATA_DIR")
            os.environ["AIPET_DATA_DIR"] = directory
            try:
                settings = AppSettings()
                dialog = SettingsDialog(settings)
                pet = Murasame(settings)
                self.assertGreater(pet.width(), 0)
                self.assertGreater(pet.height(), 0)
                self.assertEqual(
                    dialog._form_settings().mode,
                    "ollama",
                )
                pet.shutdown()
                dialog.close()
            finally:
                if previous is None:
                    os.environ.pop("AIPET_DATA_DIR", None)
                else:
                    os.environ["AIPET_DATA_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
