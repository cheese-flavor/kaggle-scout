import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from app import Connect, Window, STYLE
from core import Store, Kaggle
from test_core import item

APP = QApplication.instance() or QApplication([])
APP.setStyleSheet(STYLE)

class UITests(unittest.TestCase):
    def setUp(self):
        Path('work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir='work')
        self.store = Store(self.tmp.name)
        self.window = Window(self.store, preview=True)

    def tearDown(self):
        if self.window.job:
            self.window.job.wait(5000)
        self.window.quitting = True
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.tmp.cleanup()

    def wait_job(self, dialog):
        for _ in range(100):
            APP.processEvents()
            if not dialog.job.isRunning():
                APP.processEvents()
                return
            QTest.qWait(10)
        self.fail('Connection worker did not finish')

    def test_successful_onboarding_saves_only_encrypted_credential(self):
        dialog = Connect(self.store, self.window)
        with patch.object(Kaggle, 'call', return_value={'competitions': []}):
            dialog.verify({'token': 'ui-fixture-not-a-real-token'})
            self.wait_job(dialog)
        self.assertEqual(dialog.result(), 1)
        self.assertEqual(self.store.credentials()['token'], 'ui-fixture-not-a-real-token')
        self.assertNotIn('ui-fixture-not-a-real-token', self.store.get('credentials'))

    def test_failed_reconnection_preserves_existing_credential(self):
        self.store.save_credentials({'token': 'original-fixture'})
        dialog = Connect(self.store, self.window)
        with patch.object(Kaggle, 'call', side_effect=RuntimeError('인증 실패')):
            dialog.verify({'token': 'invalid-fixture'})
            self.wait_job(dialog)
        self.assertEqual(self.store.credentials()['token'], 'original-fixture')
        self.assertTrue(dialog.submit.isEnabled())
        self.assertIn('인증 실패', dialog.status.text())

    def test_profile_form_changes_runtime_preferences(self):
        self.window.gpu_input.setText('다른 GPU')
        self.window.vram_input.setValue(24)
        self.window.paid.setChecked(True)
        self.window.interval.setValue(120)
        self.window.save_settings()
        profile = self.store.profile()
        self.assertEqual(profile['gpu'], '다른 GPU')
        self.assertEqual(profile['vram'], 24)
        self.assertTrue(profile['paid_api'])
        self.assertEqual(profile['interval'], 120)

    def test_pagination_covers_every_item_and_resets_after_search(self):
        self.store.sync([item(f'competition-{i:02}', title=f'대회 {i:02}', deadline='2099-12-01T00:00:00Z') for i in range(23)], self.store.profile())
        self.window.render()
        self.assertEqual(len(self.window.current_page_refs), 10)
        found = list(self.window.current_page_refs)
        self.window.move_page(1)
        found += self.window.current_page_refs
        self.window.move_page(1)
        found += self.window.current_page_refs
        self.assertEqual(len(set(found)), 23)
        self.assertFalse(self.window.next_page.isEnabled())
        self.window.search.setText('대회 01')
        self.assertEqual(self.window.page_index, 0)
        self.assertEqual(self.window.current_page_refs, ['competition-01'])

    def test_page_size_saved_and_used_by_settings(self):
        self.window.display_size.setCurrentIndex(self.window.display_size.findData(5))
        self.assertEqual(self.store.profile()['page_size'], 5)
        self.assertEqual(self.window.read_form()['page_size'], 5)

    def test_audience_form_is_saved(self):
        self.window.audience_checks['general'].setChecked(False)
        self.window.audience_checks['university'].setChecked(True)
        self.window.unknown_audience.setChecked(False)
        self.window.save_settings()
        p = self.store.profile()
        self.assertEqual(p['audiences'], ['university'])
        self.assertFalse(p['include_unknown_audience'])

    def test_slider_exact_values_and_large_vram_survive(self):
        control = self.window.vram_input
        control.slider.setValue(24)
        self.assertEqual(control.value(), 24)
        control.setValue(128)
        self.assertEqual(control.value(), 128)
        self.assertEqual(control.slider.value(), 64)
        self.assertEqual(self.window.read_form()['vram'], 128)
        control.setValue(17)
        self.assertEqual(control.slider.value(), 17)
        QTest.keyClick(control.slider, Qt.Key.Key_Right)
        self.assertEqual(control.value(), 18)

    def test_interval_slider_keeps_custom_numeric_value(self):
        control = self.window.interval
        control.slider.setValue(2)
        self.assertEqual(control.value(), 60)
        control.setValue(90)
        self.assertEqual(self.window.read_form()['interval'], 90)

    def test_candidate_preview_uses_unsaved_draft_without_network(self):
        self.store.sync([item('large', description='Requires 24 GB VRAM.', deadline='2099-12-01T00:00:00Z')], self.store.profile())
        self.window.vram_input.setValue(16)
        self.window.preview_settings()
        self.assertIn('추천 후보 0개', self.window.settings_status.text())
        self.window.vram_input.setValue(32)
        self.window.preview_settings()
        self.assertIn('저장 전', self.window.settings_status.text())
        self.assertIn('추천 후보 1개', self.window.settings_status.text())
        self.assertEqual(self.store.profile()['vram'], 16)

    def test_normal_save_stays_in_settings_and_does_not_refresh(self):
        self.window.navigate(3)
        self.window.vram_input.setValue(24)
        with patch.object(self.window, 'refresh') as refresh:
            self.window.save_settings()
            refresh.assert_not_called()
        self.assertEqual(self.window.mode, 3)
        self.assertEqual(self.store.profile()['vram'], 24)

    def test_onboarding_save_still_starts_first_collection(self):
        self.window.await_profile = True
        self.window.credentials = {'token': 'fixture-only'}
        with patch.object(self.window, 'refresh') as refresh:
            self.window.save_settings()
            refresh.assert_called_once()
        self.assertFalse(self.window.await_profile)
        self.assertEqual(self.window.mode, 0)

    def test_search_empty_state_has_recovery_and_no_dead_actions(self):
        self.store.sync([item(deadline='2099-12-01T00:00:00Z')], self.store.profile())
        self.window.search.setText('nonexistent')
        self.assertEqual(self.window.empty_title, '검색 결과 없음')
        self.assertFalse(self.window.original_button.isEnabled())
        self.window.clear_search_filters()
        self.assertEqual(self.window.current_page_refs, ['example'])
        self.assertTrue(self.window.original_button.isEnabled())

    def test_saved_custom_slider_values_survive_reopening(self):
        self.window.vram_input.setValue(128)
        self.window.interval.setValue(90)
        self.window.save_settings()
        reopened = Window(Store(self.tmp.name), preview=True)
        try:
            self.assertEqual(reopened.vram_input.value(), 128)
            self.assertEqual(reopened.interval.value(), 90)
        finally:
            reopened.quitting = True
            reopened.close()
            reopened.deleteLater()

if __name__ == '__main__':
    unittest.main()
