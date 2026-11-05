import copy
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from core import Store, DEFAULT, Kaggle, assess, date, fingerprint, protect

AT = datetime(2026, 11, 5, tzinfo=timezone.utc)

def item(ref='example', **values):
    return {'ref': ref, 'title': 'Tabular prediction', 'description': 'Python regression',
            'deadline': (AT + timedelta(days=20)).isoformat(), **values}

class CoreTests(unittest.TestCase):
    def setUp(self):
        Path('work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir='work')
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.profile = copy.deepcopy(DEFAULT)

    def test_baseline_new_dedup_and_restart(self):
        self.assertEqual(self.store.sync([item()], self.profile, AT), (True, []))
        _, notices = self.store.sync([item(), item('second')], self.profile, AT)
        self.assertEqual([n[0] for n in notices], ['새 추천'])
        restarted = Store(self.tmp.name)
        self.assertEqual(restarted.sync([item(), item('second')], self.profile, AT)[1], [])

    def test_population_changes_do_not_notify_but_deadlines_do(self):
        self.store.sync([item(teamCount=1)], self.profile, AT)
        self.store.flag('example', 'starred', True)
        self.assertEqual(self.store.sync([item(teamCount=200)], self.profile, AT)[1], [])
        notices = self.store.sync([item(deadline=(AT+timedelta(days=25)).isoformat())], self.profile, AT)[1]
        self.assertEqual(notices[0][0], '정보 변경')

    def test_reminder_catch_up_exactly_once_and_next_bucket(self):
        value = item(deadline=(AT+timedelta(days=6)).isoformat())
        self.store.sync([value], self.profile, AT)
        self.store.flag('example', 'starred', True)
        self.assertEqual(len(self.store.sync([value], self.profile, AT)[1]), 1)
        self.assertEqual(len(self.store.sync([value], self.profile, AT)[1]), 0)
        self.assertEqual(len(self.store.sync([value], self.profile, AT+timedelta(days=4))[1]), 1)

    def test_hidden_starred_items_do_not_notify(self):
        self.store.sync([item()], self.profile, AT)
        self.store.flag('example', 'starred', True)
        self.store.flag('example', 'hidden', True)
        self.assertEqual(self.store.sync([item(description='Changed')], self.profile, AT)[1], [])

    def test_general_eligibility_and_hardware_are_not_invented(self):
        v = assess(item(), self.profile, AT)
        self.assertIn('확인 필요', v['eligibility'])
        self.assertIn('확인 필요', v['gpu'])
        self.assertIn('확인 필요', v['api'])

    def test_restrictions_and_profile_hardware(self):
        value = item(description='Students only. Requires 24 GB VRAM. Paid API is required.')
        v = assess(value, self.profile, AT)
        self.assertEqual(len(v['excluded']), 3)
        p = {**self.profile, 'vram': 32, 'paid_api': True, 'exclude_students': False}
        self.assertEqual(assess(value, p, AT)['excluded'], [])
        self.assertIn('용량 조건 내 후보', assess(value, p, AT)['gpu'])

    def test_entry_deadline_and_existing_participant(self):
        value = item(newEntrantDeadline=(AT-timedelta(hours=1)).isoformat())
        self.assertTrue(assess(value, self.profile, AT)['excluded'])
        value['userHasEntered'] = True
        self.assertEqual(assess(value, self.profile, AT)['excluded'], [])

    def test_kst_dates_and_sdk_offset_z(self):
        self.assertEqual(date('2026-11-05T09:00:00+09:00'), AT)
        self.assertEqual(date('2026-11-05T00:00:00+00:00Z'), AT)
        self.assertIsNone(date('not-a-date'))

    def test_windows_credential_encryption_round_trip(self):
        self.store.save_credentials({'token': 'unit-test-secret-only'})
        self.assertNotIn('unit-test-secret-only', self.store.get('credentials'))
        self.assertEqual(self.store.credentials()['token'], 'unit-test-secret-only')

    def test_pagination_preserves_every_page(self):
        client = Kaggle({'token': 'test-only'})
        with patch.object(client, 'call', side_effect=[{'competitions': [item()], 'nextPageToken': 'next'}, {'competitions': [item('second')]}]) as call:
            self.assertEqual(len(client.collect()), 2)
            self.assertEqual(call.call_args_list[1].args[1]['pageToken'], 'next')

    def test_failed_second_page_never_commits_partial_results(self):
        self.store.sync([item()], self.profile, AT)
        client = Kaggle({'token': 'test-only'})
        with patch.object(client, 'call', side_effect=[{'competitions': [item('new')], 'nextPageToken': 'next'}, RuntimeError('offline')]):
            with self.assertRaises(RuntimeError):
                self.store.sync(client.collect(), self.profile, AT)
        self.assertEqual([r['ref'] for r in self.store.rows()], ['example'])

    def test_expired_and_keyword_exclusion(self):
        self.assertTrue(assess(item(deadline=AT.isoformat()), self.profile, AT)['excluded'])
        p = {**self.profile, 'exclude_keywords': ['medical']}
        self.assertIn('제외 키워드: medical', assess(item(description='medical prediction'), p, AT)['excluded'])

if __name__ == '__main__':
    unittest.main()
