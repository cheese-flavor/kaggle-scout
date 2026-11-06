import copy
import tempfile
import unittest
from pathlib import Path
from datetime import timedelta
from core import DEFAULT, Store, assess, validate_profile, education_info
from test_core import AT, item


class EducationTests(unittest.TestCase):
    def setUp(self):
        Path('work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir='work')
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.profile = copy.deepcopy(DEFAULT)

    def test_category_is_evidence_and_distant_deadline_is_not(self):
        for category in ('Getting Started', 'gettingStarted', 'HOST_SEGMENT_GETTING_STARTED'):
            self.assertTrue(education_info(item(category=category), self.profile)[0])
        self.assertFalse(education_info(item(category='Featured', deadline='2099-01-01T00:00:00Z'), self.profile)[0])
        self.assertFalse(education_info(item(title='Beginner-friendly Titanic research'), self.profile)[0])
        self.assertFalse(education_info(item(category='Not Getting Started'), self.profile)[0])

    def test_playground_is_explicit_opt_in_and_slug_fallback_is_conservative(self):
        value = item(category='Playground')
        self.assertFalse(education_info(value, self.profile)[0])
        self.profile['education_playground'] = True
        self.assertTrue(education_info(value, self.profile)[0])
        self.assertTrue(education_info(item('https://www.kaggle.com/competitions/titanic'), self.profile)[0])
        self.assertFalse(education_info(item('titanic', category='Featured'), self.profile)[0])

    def test_old_profiles_gain_defaults_and_validate_import_types(self):
        original = {'vram': 24}
        p = validate_profile(original)
        self.assertTrue(p['separate_education'])
        self.assertFalse(p['education_playground'])
        self.assertFalse(p['notify_education'])
        self.assertEqual(original, {'vram': 24})
        for key in ('separate_education', 'education_playground', 'notify_education'):
            with self.assertRaises(ValueError):
                validate_profile({key: 'false'})

    def test_education_is_stored_and_not_an_exclusion(self):
        value = item(category='Getting Started')
        self.store.sync([value], self.profile, AT)
        self.assertEqual(len(self.store.rows()), 1)
        verdict = assess(value, self.profile, AT)
        self.assertTrue(verdict['education'])
        self.assertEqual(verdict['excluded'], [])

    def test_new_education_alerts_opt_in_without_replaying_old_items(self):
        self.store.sync([], self.profile, AT)
        a = item('a', category='Getting Started')
        self.assertEqual(self.store.sync([a], self.profile, AT)[1], [])
        self.profile['notify_education'] = True
        self.assertEqual(self.store.sync([a], self.profile, AT)[1], [])
        b = item('b', category='Getting Started')
        self.assertEqual(len(self.store.sync([b], self.profile, AT)[1]), 1)
        self.assertEqual(len(self.store.notification_batch(self.profile, AT)), 1)
        self.profile['notify_education'] = False
        self.assertEqual(self.store.notification_batch(self.profile, AT), [])

    def test_starred_education_changes_and_deadlines_still_notify(self):
        value = item(category='Getting Started', deadline=(AT + timedelta(days=2)).isoformat())
        self.store.sync([value], self.profile, AT)
        self.store.flag('example', 'starred', True)
        changed = {**value, 'description': 'Changed tutorial'}
        kinds = [n[0] for n in self.store.sync([changed], self.profile, AT)[1]]
        self.assertEqual(set(kinds), {'정보 변경', '마감 임박'})
        self.assertEqual({n['kind'] for n in self.store.notification_batch(self.profile, AT)}, set(kinds))
