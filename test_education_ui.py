import json
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from app import ExclusionDialog, Window
from core import Store
import test_ui as ui
from test_core import item


class EducationUITests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def seed(self):
        self.store.sync([item('general', title='일반 대회', category='Featured', deadline='2099-12-01T00:00:00Z'),
                         item('education', title='입문 실습', category='Getting Started', deadline='2099-12-01T00:00:00Z'),
                         item('play', title='정기 Playground', category='Playground', deadline='2099-12-01T00:00:00Z')], self.store.profile())
        self.window.render()

    def test_groups_are_disjoint_and_education_stays_bookmarkable(self):
        self.seed()
        self.assertEqual(set(self.window.current_page_refs), {'general', 'play'})
        self.window.collection_tabs.setCurrentIndex(1)
        self.assertEqual(self.window.current_page_refs, ['education'])
        self.assertIn('Getting Started', self.window.detail.toPlainText())
        self.assertIn('API상 마감', self.window.detail.toPlainText())
        self.window.toggle_bookmark('education')
        self.window.navigate(1)
        self.assertEqual(self.window.current_page_refs, ['education'])
        self.assertEqual(len(self.store.rows()), 3)

    def test_settings_merge_and_playground_move_without_collecting(self):
        self.seed()
        self.window.education_playground.setChecked(True)
        with patch.object(self.window, 'refresh') as refresh:
            self.window.save_settings()
            refresh.assert_not_called()
        self.assertEqual(self.window.current_page_refs, ['general'])
        self.window.collection_tabs.setCurrentIndex(1)
        self.assertEqual(set(self.window.current_page_refs), {'education', 'play'})
        self.window.separate_education.setChecked(False)
        self.window.save_settings()
        self.assertTrue(self.window.collection_tabs.isHidden())
        self.assertEqual(set(self.window.current_page_refs), {'general', 'education', 'play'})

    def test_switching_group_resets_pagination_and_search_applies(self):
        rows = [item(f'{kind}-{i}', title=f'{kind} {i}', category=category, deadline='2099-12-01T00:00:00Z')
                for kind, category in [('general', 'Featured'), ('education', 'Getting Started')]
                for i in range(12)]
        self.store.sync(rows, self.store.profile())
        self.window.display_size.setCurrentIndex(self.window.display_size.findData(5))
        self.window.move_page(1)
        self.assertEqual(self.window.page_index, 1)
        self.window.collection_tabs.setCurrentIndex(1)
        self.assertEqual(self.window.page_index, 0)
        self.assertEqual(len(self.window.current_page_refs), 5)
        self.assertTrue(all(ref.startswith('education-') for ref in self.window.current_page_refs))
        self.window.search.setText('education 10')
        self.assertEqual(self.window.current_page_refs, ['education-10'])
        self.window.choose_chip('전체')
        self.assertEqual(self.window.current_page_refs, ['education-10'])

    def test_exclusion_dialog_opens_correct_group(self):
        self.store.sync([item('edu', title='교육 VRAM', category='Getting Started', description='Requires 64 GB VRAM.', deadline='2099-12-01T00:00:00Z')], self.store.profile())
        dialog = ExclusionDialog(self.window)
        try:
            dialog.view()
            self.assertEqual(self.window.collection_tabs.currentIndex(), 1)
            self.assertIn('edu', self.window.current_page_refs)
            self.assertIn('최소 VRAM', self.window.detail.toPlainText())
        finally:
            dialog.close()

    def test_import_and_reopen_preserve_all_education_settings(self):
        profile = {**self.store.profile(), 'separate_education': False,
                   'education_playground': True, 'notify_education': True}
        path = Path(self.tmp.name) / 'profile.json'
        path.write_text(json.dumps(profile), encoding='utf8')
        with patch('app.QFileDialog.getOpenFileName', return_value=(str(path), 'JSON')):
            self.window.import_profile()
        self.assertEqual(self.window.read_form(), profile)
        self.window.save_settings()
        reopened = Window(Store(self.tmp.name), preview=True)
        try:
            self.assertFalse(reopened.separate_education.isChecked())
            self.assertTrue(reopened.education_playground.isChecked())
            self.assertTrue(reopened.notify_education.isChecked())
        finally:
            reopened.quitting = True
            reopened.close()
            reopened.deleteLater()

    def test_compact_full_information_remains_available_without_switching(self):
        self.seed()
        self.window.collection_tabs.setCurrentIndex(1)
        self.window.show()
        self.window.resize(960, 680)
        QTest.qWait(30)
        self.assertIn('대회 일정', self.window.detail.toPlainText())
        self.assertIn('평가 지표', self.window.detail.toPlainText())
        self.assertIn('참가 조건·내 환경', self.window.detail.toPlainText())
        self.assertTrue(self.window.star_button.isVisible())
        self.assertTrue(self.window.delete_button.isVisible())
