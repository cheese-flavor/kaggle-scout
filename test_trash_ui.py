from datetime import timedelta
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
from app import TrashDialog, ExclusionDialog
from core import date
import test_ui as ui
from test_core import item


class TrashUITests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def seed(self):
        self.store.sync([item('a', title='분석 대회', deadline='2099-12-01T00:00:00Z'),
                         item('b', title='입문 실습', category='Getting Started', deadline='2099-12-03T00:00:00Z')], self.store.profile())
        self.window.render()

    def test_deleted_items_stay_out_of_all_views_and_exclusion_counts(self):
        self.seed()
        self.window.delete_competition('a')
        self.assertEqual(self.window.current_page_refs, [])
        self.window.show_excluded.setChecked(True)
        self.window.show_hidden.setChecked(True)
        self.assertEqual(self.window.current_page_refs, [])
        self.assertIn('(1)', self.window.trash_button.text())
        self.window.collection_tabs.setCurrentIndex(1)
        self.assertEqual(self.window.current_page_refs, ['b'])
        dialog = ExclusionDialog(self.window)
        self.assertFalse(any(entry[0] == 'a' for entry in dialog.entries))
        dialog.close()

    def test_restore_from_trash_keeps_bookmark_and_removes_trash_entry(self):
        self.seed()
        self.window.toggle_bookmark('a')
        self.window.delete_competition('a')
        dialog = TrashDialog(self.window)
        try:
            self.assertEqual(dialog.items.count(), 1)
            self.assertIn('2099.11.30 23:59', dialog.explanation.toPlainText())
            dialog.restore_selected()
            self.assertEqual(dialog.items.count(), 0)
            self.assertFalse(dialog.restore_button.isEnabled())
            self.assertTrue(next(r for r in self.store.rows() if r['ref'] == 'a')['starred'])
            self.window.navigate(1)
            self.assertEqual(self.window.current_page_refs, ['a'])
        finally:
            dialog.close()

    def test_trash_search_and_unknown_deadline_description(self):
        self.store.sync([item('a', title='<img src=file:///private> 교육', deadline=None)], self.store.profile())
        self.window.delete_competition('a')
        dialog = TrashDialog(self.window)
        try:
            self.assertIn('종료일 미확인', dialog.explanation.toPlainText())
            self.assertIn('<img', dialog.items.item(0).text())
            dialog.search.setText('없는 단어')
            self.assertEqual(dialog.items.count(), 0)
            self.assertFalse(dialog.restore_button.isEnabled())
            dialog.search.clear()
            self.assertEqual(dialog.items.count(), 1)
        finally:
            dialog.close()

    def test_nonrecoverable_deletion_can_be_cancelled(self):
        self.store.sync([item('old', deadline='2001-01-01T00:00:00Z')], self.store.profile())
        with patch('app.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            self.window.delete_competition('old')
        self.assertEqual(len(self.store.rows()), 1)
        with patch('app.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            self.window.delete_competition('old')
        self.assertEqual(self.store.rows(include_deleted=True), [])

    def test_card_delete_targets_its_own_record(self):
        self.seed()
        self.window.separate_education.setChecked(False)
        self.window.save_settings()
        self.window.select('a')
        self.window.delete_competition('b')
        self.assertEqual(self.window.selected, 'a')
        self.assertEqual(self.window.current_page_refs, ['a'])

    def test_tick_purges_expired_trash_without_collection(self):
        self.seed()
        self.window.delete_competition('a')
        until = date(self.store.trash_rows()[0]['trash_until'])
        with patch('core.now', return_value=until + timedelta(seconds=1)):
            self.window.tick()
        self.assertEqual(self.store.rows(include_deleted=True)[0]['ref'], 'b')
        self.assertIn('(0)', self.window.trash_button.text())
