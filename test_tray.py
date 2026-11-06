import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from app import Window
import test_ui as ui


class TrayTests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def test_compact_menu_opens_window_and_quits_without_refresh(self):
        with patch.object(Window, 'quit_app') as quit_app, patch.object(Window, 'refresh') as refresh:
            window = Window(self.store, preview=True)
            try:
                actions = window.tray.contextMenu().actions()
                self.assertEqual([a.text() for a in actions], ['앱 열기', '종료'])
                self.assertTrue(all(not a.isSeparator() for a in actions))
                self.assertFalse(window.isVisible())
                actions[0].trigger()
                QTest.qWait(20)
                self.assertTrue(window.isVisible())
                actions[1].trigger()
                quit_app.assert_called_once()
                refresh.assert_not_called()
            finally:
                window.quitting = True
                window.close()
                window.deleteLater()
