import copy
import unittest
from PySide6.QtGui import QTextDocument
from core import DEFAULT, assess, exclusion_details
from detail_view import detail_document
from test_core import item, AT
from ui_theme import TONES
from test_ui import APP
import test_ui as ui


class DetailDocumentTests(unittest.TestCase):
    def render(self, value, **overrides):
        verdict = assess(value, copy.deepcopy(DEFAULT), AT)
        arguments = dict(item=value, verdict=verdict, exclusions=exclusion_details(value, DEFAULT, verdict),
                         last_seen=AT.isoformat(), countdown='D-20', deadline_colors=TONES['slate'], topic_ink=TONES['blue']['ink'])
        arguments.update(overrides)
        html = detail_document(**arguments)
        document = QTextDocument()
        document.setHtml(html)
        return html, document.toPlainText()

    def test_all_supplied_fields_and_zero_team_count_are_preserved(self):
        value = item(title='전체 대회', enabledDate='2026-11-01T01:00:00Z',
                     newEntrantDeadline='2026-11-15T02:00:00Z', mergerDeadline='2026-11-16T03:00:00Z',
                     evaluationMetric='RMSE', maxTeamSize=5, teamCount=0, reward='$1,000',
                     isKernelsSubmissionsOnly=True, pages='규칙 첫 줄\n규칙 마지막 줄')
        _, plain = self.render(value)
        for content in ('2026-11-01 10:00 KST', '2026-11-15 11:00 KST', '2026-11-16 12:00 KST',
                        '2026-11-25 09:00 KST', 'RMSE', '5', '참여 팀', '0', '$1,000',
                        'Notebook 코드 제출', '규칙 첫 줄', '규칙 마지막 줄', 'GPU', 'API', '추천 이유', '확인 기록'):
            self.assertIn(content, plain)

    def test_external_fields_are_escaped_and_cannot_become_active_markup(self):
        payload = '<img src="file:///private"><a href="https://example.invalid">raw</a>'
        value = item(title=payload, reward=payload, evaluationMetric='<script>run()</script>',
                     description='첫 줄<br>설명', pages='첫 줄\n끝 <script>run()</script>')
        html, plain = self.render(value)
        self.assertNotIn('<img', html)
        self.assertNotIn('<a ', html)
        self.assertNotIn('<script', html)
        self.assertIn(payload, plain)
        self.assertIn('run()', plain)
        self.assertIn('첫 줄', plain)

    def test_education_unknown_values_and_exclusions_remain_explicit(self):
        value = item(category='Getting Started', deadline='2099-12-01T00:00:00Z',
                     description='Requires 64 GB VRAM.')
        _, plain = self.render(value, long_practice=True)
        for content in ('API상 마감', 'Getting Started', '확인 필요', '현재 제외 이유', '64'):
            self.assertIn(content, plain)
        self.assertNotIn('D-20', plain)


class DetailReadingTests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def test_bookmark_preserves_reading_position_and_new_selection_resets_it(self):
        values = [item(ref, title=ref, deadline='2099-12-01T00:00:00Z', pages=('긴 규칙\n' * 150)) for ref in ('a', 'b')]
        self.store.sync(values, self.store.profile())
        self.window.render()
        self.window.show()
        APP.processEvents()
        self.window.select('a')
        APP.processEvents()
        self.window.detail.verticalScrollBar().setValue(250)
        position = self.window.detail.verticalScrollBar().value()
        self.assertGreater(position, 0)
        self.window.star_button.click()
        APP.processEvents()
        self.assertTrue(self.window.selected_row()['starred'])
        self.assertEqual(self.window.detail.verticalScrollBar().value(), position)
        self.window.select('b')
        APP.processEvents()
        self.assertEqual(self.window.detail.verticalScrollBar().value(), 0)
