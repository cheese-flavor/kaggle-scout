import unittest
from PySide6.QtTest import QTest
import test_ui as ui


class PersonalizationTests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def test_saved_display_name_controls_interest_heading_only(self):
        self.window.show()
        self.window.name_input.setText('민수')
        self.window.save_settings()
        self.window.navigate(1)
        QTest.qWait(30)
        self.assertEqual(self.window.heading.text(), '민수의 관심 대회')
        self.assertIn('관심 등록 대회 목록', self.window.hero_text.text())
        self.window.navigate(0)
        self.assertEqual(self.window.heading.text(), '대회 탐색')

    def test_saved_kaggle_username_is_used_without_display_name(self):
        self.window.show()
        self.window.credentials = {'username': 'kaggle_demo', 'key': 'fixture'}
        self.window.navigate(1)
        QTest.qWait(30)
        self.assertEqual(self.window.heading.text(), 'kaggle_demo의 관심 대회')
        self.window.name_input.setText('민수')
        self.window.save_settings()
        self.window.navigate(1)
        self.assertEqual(self.window.heading.text(), '민수의 관심 대회')

    def test_token_is_never_used_as_a_name_and_blank_name_has_noun_fallback(self):
        self.window.show()
        self.window.credentials = {'token': 'fixture-secret-not-a-user-name'}
        self.window.navigate(1)
        QTest.qWait(30)
        self.assertEqual(self.window.heading.text(), '관심 대회')
        self.assertNotIn('fixture-secret', self.window.heading.toolTip())

    def test_long_name_preserves_function_suffix_and_minimum_window(self):
        self.window.name_input.setText('가나다라마바사아자차카타파하' * 6)
        self.window.save_settings()
        self.window.show()
        self.window.resize(960, 680)
        self.window.navigate(1)
        QTest.qWait(30)
        self.assertEqual(self.window.width(), 960)
        self.assertEqual(self.window.height(), 680)
        self.assertTrue(self.window.heading.text().endswith('의 관심 대회'))
        self.assertIn('…', self.window.heading.text())
        self.assertEqual(self.window.heading.toolTip(), self.store.profile()['name'] + '의 관심 대회')
