from datetime import timedelta
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import test_ui as ui
from core import now
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


    def test_long_competition_and_alert_text_wrap_at_minimum_window(self):
        profile = self.store.profile()
        value = item('long',
                     title='한국어와 English가 섞인 긴 대회 제목 ' * 3,
                     description='Python web development application을 비교하는 대회입니다. ' * 5,
                     deadline=(now() + timedelta(hours=30)).isoformat(),
                     pages=('LongRuleToken' * 150) + ' 규칙 끝')
        self.store.sync([value], profile)
        self.store.flag('long', 'starred', True)
        self.store.sync([{**value, 'reward': 'LongRewardToken' * 10}], profile)
        self.window.resize(960, 680)
        self.window.show()
        self.window.render()
        QTest.qWait(50)
        self.assertEqual(self.window.size().toTuple(), (960, 680))
        self.assertEqual(self.window.list_scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual(self.window.detail.horizontalScrollBar().maximum(), 0)
        self.assertGreater(self.window.detail.verticalScrollBar().maximum(), 0)
        self.assertIn('규칙 끝', self.window.detail.toPlainText())
        self.assertTrue(self.window.original_button.isVisible())
        self.window.navigate(2)
        QTest.qWait(50)
        self.assertEqual(self.window.events.horizontalScrollBar().maximum(), 0)
        self.assertIn('LongRewardToken' * 10, self.window.events.toPlainText())
