import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from PySide6.QtCore import QTime
from core import Store, DEFAULT, notification_window_open, validate_profile, KST
from test_core import item, AT
import test_ui as ui

def local(hour, minute=0):
    return datetime(2026, 11, 5, hour, minute, tzinfo=KST)

class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='work')
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.profile = {**DEFAULT, 'notify_schedule': 'window', 'notify_start': '09:00', 'notify_end': '22:00'}
        self.store.sync([item('baseline')], self.profile, local(7))

    def test_start_inclusive_end_exclusive_and_overnight(self):
        self.assertFalse(notification_window_open(self.profile, local(8, 59)))
        self.assertTrue(notification_window_open(self.profile, local(9)))
        self.assertFalse(notification_window_open(self.profile, local(22)))
        p = {**self.profile, 'notify_start': '22:00', 'notify_end': '08:00'}
        self.assertTrue(notification_window_open(p, local(23)))
        self.assertTrue(notification_window_open(p, local(7)))
        self.assertFalse(notification_window_open(p, local(8)))
        self.assertEqual(notification_window_open(p, local(23).astimezone(timezone.utc)), True)

    def test_quiet_queue_survives_restart_and_sends_once(self):
        self.store.sync([item('new')], self.profile, local(8))
        self.assertEqual(self.store.notification_batch(self.profile, local(8)), [])
        reopened = Store(self.tmp.name)
        batch = reopened.notification_batch(self.profile, local(9))
        self.assertEqual(len(batch), 1)
        reopened.mark_notified([e['id'] for e in batch])
        self.assertEqual(reopened.notification_batch(self.profile, local(10)), [])

    def test_disabled_kind_is_recorded_without_later_backfill(self):
        self.store.sync([item('new')], self.profile, local(8))
        p = {**self.profile, 'notify_kinds': ['마감 임박']}
        self.assertEqual(self.store.notification_batch(p, local(9)), [])
        self.assertEqual(self.store.notification_batch(self.profile, local(10)), [])
        with self.store.connect() as con:
            self.assertEqual(con.execute('SELECT delivery FROM events').fetchone()[0], 'skipped')

    def test_global_off_and_new_profile_filter_cancel_pending(self):
        self.store.sync([item('new')], self.profile, local(8))
        self.assertEqual(self.store.notification_batch({**self.profile, 'notify': False}, local(9)), [])
        self.store.sync([item('another')], self.profile, local(9))
        self.assertEqual(self.store.notification_batch({**self.profile, 'min_score': 100}, local(10)), [])

    def test_expired_or_rescheduled_reminder_is_not_delivered(self):
        value = item(deadline=local(8, 30).isoformat())
        self.store.sync([value], self.profile, local(7))
        self.store.flag('example', 'starred', True)
        self.store.sync([value], self.profile, local(8))
        self.assertEqual(self.store.notification_batch(self.profile, local(9)), [])

    def test_legacy_history_is_not_replayed(self):
        folder = Path(self.tmp.name)/'legacy'
        folder.mkdir()
        con = sqlite3.connect(folder/'scout.sqlite3')
        con.execute('CREATE TABLE events(id INTEGER PRIMARY KEY, created TEXT, kind TEXT, ref TEXT, message TEXT)')
        con.execute("INSERT INTO events VALUES(1,'old','새 추천','example','old')")
        con.commit(); con.close()
        store = Store(folder)
        self.assertEqual(store.notification_batch(self.profile, local(9)), [])

    def test_profile_validation_and_old_profile_defaults(self):
        self.assertEqual(validate_profile({})['notify_schedule'], 'always')
        for change in [{'notify_start': '25:00'}, {'notify_schedule': 'window', 'notify_start': '09:00', 'notify_end': '09:00'}, {'notify_kinds': ['invalid']}]:
            with self.assertRaises(ValueError):
                validate_profile(change)

class NotificationUITests(unittest.TestCase):
    setUp = ui.UITests.setUp
    tearDown = ui.UITests.tearDown

    def test_schedule_and_kind_form_persists(self):
        self.window.notify_kind_checks['새 추천'].setChecked(False)
        self.window.notify_schedule.setCurrentIndex(1)
        self.window.notify_start.setTime(QTime(22, 0))
        self.window.notify_end.setTime(QTime(8, 0))
        self.window.save_settings()
        p = self.store.profile()
        self.assertNotIn('새 추천', p['notify_kinds'])
        self.assertEqual(p['notify_start'], '22:00')
        self.assertEqual(p['notify_end'], '08:00')
        self.assertTrue(self.window.notify_start.isEnabled())

    def test_dispatch_acknowledges_only_successfully_requested_batch(self):
        self.store.sync([item('baseline', deadline='2099-12-01T00:00:00Z')], self.store.profile())
        self.store.sync([item('new', deadline='2099-12-01T00:00:00Z')], self.store.profile())
        self.window.preview = False
        with patch.object(self.window.tray, 'isVisible', return_value=True), patch.object(self.window, 'notify', return_value=True) as notify:
            self.window.flush_notifications()
            self.window.flush_notifications()
            notify.assert_called_once()
        self.window.preview = True
