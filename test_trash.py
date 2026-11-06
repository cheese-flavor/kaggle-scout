import copy
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import timedelta
from core import DEFAULT, Store, date, trash_cutoff
from test_core import AT, item


class TrashTests(unittest.TestCase):
    def setUp(self):
        Path('work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir='work')
        self.addCleanup(self.tmp.cleanup)
        clock = patch('core.now', return_value=AT)
        clock.start()
        self.addCleanup(clock.stop)
        self.store = Store(self.tmp.name)
        self.profile = copy.deepcopy(DEFAULT)

    def test_trash_restore_preserves_interest_and_does_not_generate_new_alert(self):
        value = item()
        self.store.sync([value], self.profile, AT)
        self.store.flag('example', 'starred', True)
        self.store.flag('example', 'hidden', True)
        self.assertTrue(self.store.trash('example', AT))
        self.assertEqual(self.store.rows(), [])
        self.assertEqual(len(self.store.trash_rows(AT)), 1)
        self.assertTrue(self.store.restore('example', AT))
        self.assertTrue(self.store.rows()[0]['starred'])
        self.assertFalse(self.store.rows()[0]['hidden'])
        self.assertEqual(self.store.sync([value], self.profile, AT)[1], [])

    def test_kst_previous_day_boundary_is_not_twenty_four_hours_before(self):
        value = item(deadline='2026-11-06T00:00:00Z')  # Nov 6, 09:00 KST
        self.assertEqual(trash_cutoff(value), date('2026-11-05T15:00:00Z'))
        self.store.sync([value], self.profile, AT)
        self.store.trash('example', AT)
        self.assertTrue(self.store.restore('example', date('2026-11-05T14:59:59Z')))
        self.store.trash('example', date('2026-11-05T14:59:59Z'))
        self.assertFalse(self.store.restore('example', date('2026-11-05T15:00:00Z')))
        self.assertEqual(self.store.trash_rows(date('2026-11-05T15:00:00Z')), [])

    def test_utc_deadline_crossing_kst_midnight_uses_kst_date(self):
        value = item(deadline='2026-11-06T23:00:00Z')  # Nov 7, 08:00 KST
        self.assertEqual(trash_cutoff(value), date('2026-11-06T15:00:00Z'))

    def test_recollection_updates_trash_but_never_reactivates_or_notifies(self):
        value = item()
        self.store.sync([value], self.profile, AT)
        self.store.flag('example', 'starred', True)
        self.store.trash('example', AT)
        changed = {**value, 'description': 'Changed', 'deadline': (AT + timedelta(days=3)).isoformat()}
        self.assertEqual(self.store.sync([changed], self.profile, AT)[1], [])
        self.assertEqual(self.store.rows(), [])
        row = self.store.trash_rows(AT)[0]
        self.assertEqual(row['trash_until'], trash_cutoff(changed).isoformat())
        self.assertEqual(self.store.notification_batch(self.profile, AT), [])

    def test_expired_payload_is_purged_and_tombstone_prevents_reappearance(self):
        value = item(deadline=(AT + timedelta(days=2)).isoformat())
        self.store.sync([value], self.profile, AT)
        self.store.trash('example', AT)
        expired = AT + timedelta(days=3)
        self.assertEqual(self.store.cleanup_trash(expired), 1)
        self.assertEqual(self.store.rows(include_deleted=True), [])
        extended = {**value, 'deadline': (expired + timedelta(days=100)).isoformat()}
        self.assertEqual(self.store.sync([extended], self.profile, expired)[1], [])
        self.assertEqual(self.store.rows(include_deleted=True), [])
        self.assertFalse(self.store.restore('example', expired))

    def test_unknown_deadline_stays_recoverable_until_deadline_is_known(self):
        value = item(deadline=None)
        self.store.sync([value], self.profile, AT)
        self.store.trash('example', AT)
        self.assertIsNone(self.store.trash_rows(AT)[0]['trash_until'])
        self.assertEqual(self.store.cleanup_trash(AT + timedelta(days=100)), 0)
        changed = {**value, 'deadline': (AT + timedelta(days=2)).isoformat()}
        self.store.sync([changed], self.profile, AT)
        self.assertIsNotNone(self.store.trash_rows(AT)[0]['trash_until'])

    def test_deletion_cancels_queued_alert_even_after_restore(self):
        self.store.sync([], self.profile, AT)
        self.store.sync([item()], self.profile, AT)
        self.assertEqual(len(self.store.notification_batch(self.profile, AT)), 1)
        self.store.trash('example', AT)
        self.store.restore('example', AT)
        self.assertEqual(self.store.notification_batch(self.profile, AT), [])

    def test_restart_expires_trash_without_network_or_new_sync(self):
        self.store.sync([item(deadline=(AT + timedelta(days=2)).isoformat())], self.profile, AT)
        self.store.trash('example', AT)
        with patch('core.now', return_value=AT + timedelta(days=3)):
            restarted = Store(self.tmp.name)
        self.assertEqual(restarted.rows(include_deleted=True), [])

    def test_unknown_and_repeated_operations_are_idempotent(self):
        self.assertFalse(self.store.trash('missing', AT))
        self.assertFalse(self.store.restore('missing', AT))
        self.store.sync([item()], self.profile, AT)
        self.assertTrue(self.store.trash('example', AT))
        self.assertFalse(self.store.trash('example', AT))
        self.assertTrue(self.store.restore('example', AT))
        self.assertFalse(self.store.restore('example', AT))

    def test_old_schema_migration_preserves_flags_and_body(self):
        folder = Path(self.tmp.name) / 'old'
        folder.mkdir()
        with sqlite3.connect(folder / 'scout.sqlite3') as con:
            con.executescript("CREATE TABLE items(ref TEXT PRIMARY KEY,body TEXT NOT NULL,hash TEXT NOT NULL,first_seen TEXT,last_seen TEXT,starred INTEGER DEFAULT 0,hidden INTEGER DEFAULT 0); INSERT INTO items VALUES('legacy','{}','hash',NULL,NULL,1,1);")
        con.close()
        migrated = Store(folder)
        row = migrated.rows()[0]
        self.assertEqual((row['body'], row['starred'], row['hidden']), ('{}', 1, 1))
        self.assertIsNone(row['trashed_at'])
