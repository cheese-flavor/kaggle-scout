import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import test_ui as ui
from test_core import item

class DesignInteractionTests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def test_topic_and_exclusion_filters_are_independent(self):
        self.store.sync([item('text', description='Natural language processing NLP', deadline='2099-12-01T00:00:00Z'),
                         item('large', description='Requires 64 GB VRAM.', deadline='2099-12-01T00:00:00Z')], self.store.profile())
        self.window.topic.setCurrentText('LLM · NLP')
        self.assertEqual(self.window.current_page_refs, ['text'])
        self.window.show_excluded.setChecked(True)
        self.assertEqual(self.window.current_page_refs, ['text'])
        self.assertEqual(self.window.filter_button.text(), '필터 (1)')
        self.window.topic.setCurrentIndex(0)
        self.assertEqual(set(self.window.current_page_refs), {'text', 'large'})
        self.window.show_excluded.setChecked(False)
        self.assertEqual(self.window.current_page_refs, ['text'])

    def test_keyboard_card_selection_and_bookmark(self):
        self.store.sync([item('a', deadline='2099-12-01T00:00:00Z'), item('b', deadline='2099-12-01T00:00:00Z')], self.store.profile())
        self.window.render()
        QTest.keyClick(self.window.card_frames['b'], Qt.Key.Key_Return)
        self.assertEqual(self.window.selected, 'b')
        self.assertTrue(self.window.card_frames['b'].property('selected'))
        self.window.toggle_bookmark('b')
        self.assertTrue(self.window.selected_row()['starred'])

    def test_settings_tabs_keep_one_shared_profile(self):
        self.assertEqual(self.window.settings_tabs.count(), 4)
        self.window.settings_tabs.setCurrentIndex(3)
        self.window.notify_kind_checks['새 추천'].setChecked(False)
        self.window.settings_tabs.setCurrentIndex(0)
        self.window.vram_input.setValue(24)
        self.window.save_settings()
        self.assertEqual(self.store.profile()['vram'], 24)
        self.assertNotIn('새 추천', self.store.profile()['notify_kinds'])

    def test_primary_navigation_has_real_icons(self):
        self.assertTrue(all(not b.icon().isNull() for b in self.window.nav))
        self.assertFalse(self.window.original_button.icon().isNull())
        self.window.resize(960, 680)
        self.window.show()
        QTest.qWait(50)
        self.assertFalse(self.window.more_button.isHidden())
        self.assertTrue(self.window.rules_button.isHidden())
