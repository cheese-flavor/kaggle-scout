import unittest
from core import DEFAULT, exclusion_details
from app import ExclusionDialog
import test_ui as ui
from test_core import item

class ExclusionTests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown
    def test_reason_dialog_covers_score_and_multiple_rules(self):
        p = {**self.store.profile(), 'min_score': 90}
        self.store.set('profile', p)
        value = item('large', title='Large GPU', description='Students only. Requires 24 GB VRAM.', deadline='2099-12-01T00:00:00Z')
        self.store.sync([value], p)
        self.window.render()
        self.assertEqual(self.window.current_page_refs, [])
        dialog = ExclusionDialog(self.window)
        try:
            self.assertEqual(dialog.items.count(), 1)
            codes = {d['code'] for d in dialog.entries[0][2]}
            self.assertTrue({'audience', 'gpu', 'score'} <= codes)
            self.assertIn('24', dialog.explanation.toPlainText())
            dialog.view()
            self.assertIn('large', self.window.current_page_refs)
            self.assertIn('최소 90점', self.window.detail.toPlainText())
        finally:
            dialog.close()

    def test_hidden_items_do_not_inflate_reason_counts(self):
        value = item(description='Requires 64 GB VRAM.', deadline='2099-12-01T00:00:00Z')
        self.store.sync([value], self.store.profile())
        self.store.flag('example', 'hidden', True)
        dialog = ExclusionDialog(self.window)
        self.assertEqual(dialog.items.count(), 0)
        self.assertFalse(dialog.view_button.isEnabled())
        dialog.close()
