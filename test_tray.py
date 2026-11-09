import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from app import Window
import test_ui as ui
from test_core import item


class TrayTests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def test_tray_open_keeps_selection_and_notice_opens_its_actual_page(self):
        profile = self.store.profile() | {'page_size': 5}
        self.store.set('profile', profile)
        practice = [item(f'practice-{i}', title=f'Practice {i}', category='Getting Started',
                         deadline=f'2099-12-{i:02}T00:00:00Z') for i in range(1, 8)]
        self.store.sync([item('regular', title='Visible regular', deadline='2099-12-01T00:00:00Z'), *practice], profile)
        w = self.window
        w.search.setText('Visible regular')
        w.notice_ref = 'practice-7'
        w.tray.contextMenu().actions()[0].trigger()
        self.assertEqual(w.selected, 'regular')
        self.assertEqual(w.notice_ref, 'practice-7')
        w.tray.messageClicked.emit()
        self.assertEqual(w.selected, 'practice-7')
        self.assertIn(w.selected, w.current_page_refs)
        self.assertEqual(w.collection_tabs.currentIndex(), 1)
        self.assertEqual(w.page_index, 1)

    def test_notice_for_missing_item_opens_history(self):
        self.window.notice_ref = 'removed'
        self.window.tray.messageClicked.emit()
        self.assertEqual(self.window.mode, 2)

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
