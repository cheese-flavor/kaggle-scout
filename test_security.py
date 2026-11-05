import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import requests
from PySide6.QtCore import Qt, QUrl
from app import label, SafeTextBrowser
from core import Store, Kaggle, DEFAULT, validate_profile, read_json_file, validate_credentials
from test_ui import APP

def response(code, body=b'{}'):
    r = requests.Response()
    r.status_code = code
    r._content = body
    r._content_consumed = True
    return r

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='work')
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)

    def test_external_markup_is_plain_text_and_resources_are_blocked(self):
        text = '<img src="file:///C:/private.txt"><b>title</b>'
        widget = label(text)
        self.assertEqual(widget.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(widget.text(), text)
        browser = SafeTextBrowser()
        self.assertIsNone(browser.loadResource(2, QUrl('file:///C:/private.txt')))
        self.assertFalse(browser.openLinks())
        self.assertFalse(browser.openExternalLinks())

    def test_request_is_read_only_https_verified_and_does_not_follow_redirects(self):
        api = Kaggle({'token': 'fixture-secret'})
        self.assertFalse(api.session.trust_env)
        with patch.object(api.session, 'post', return_value=response(200)) as post:
            api.call('ListCompetitions', {})
            args, kwargs = post.call_args
            self.assertTrue(args[0].startswith('https://api.kaggle.com/'))
            self.assertTrue(kwargs['verify'])
            self.assertFalse(kwargs['allow_redirects'])
        with patch.object(api.session, 'post', return_value=response(302)):
            with self.assertRaisesRegex(RuntimeError, '주소 변경'):
                api.call('ListCompetitions', {})
        with self.assertRaises(RuntimeError):
            api.call('../untrusted', {})

    def test_api_error_does_not_echo_response_secret(self):
        api = Kaggle({'token': 'fixture-secret'})
        with patch.object(api.session, 'post', return_value=response(401, b'fixture-secret')):
            with self.assertRaises(RuntimeError) as error:
                api.call('ListCompetitions', {})
        self.assertNotIn('fixture-secret', str(error.exception))

    def test_large_response_is_rejected(self):
        api = Kaggle({'token': 'fixture'})
        api.MAX_RESPONSE_BYTES = 10
        with patch.object(api.session, 'post', return_value=response(200, b'x' * 11)):
            with self.assertRaisesRegex(RuntimeError, '한도'):
                api.call('ListCompetitions', {})

    def test_profile_import_bounds_and_credential_whitelist(self):
        bad = {**copy.deepcopy(DEFAULT), 'page_size': True}
        with self.assertRaises(ValueError):
            validate_profile(bad)
        with self.assertRaises(ValueError):
            validate_profile({**DEFAULT, 'exclude_keywords': ['x' * 81]})
        with self.assertRaises(ValueError):
            validate_profile({**DEFAULT, 'audiences': [['general']]})
        profile = validate_profile({**DEFAULT, 'token': 'should-not-export', 'credentials': 'secret'})
        self.assertNotIn('token', profile)
        self.assertNotIn('credentials', profile)
        path = Path(self.tmp.name) / 'oversized.json'
        path.write_bytes(b' ' * 65537)
        with self.assertRaises(ValueError):
            read_json_file(path)

    def test_corrupt_credentials_recover_and_disconnect_preserves_data(self):
        self.store.set('credentials', 'invalid base64!')
        with self.assertRaises(RuntimeError):
            self.store.credentials()
        self.store.save_credentials({'token': 'fixture-only'})
        self.store.set('profile', {'gpu': 'keep me'})
        self.store.clear_credentials()
        self.assertIsNone(self.store.credentials())
        self.assertEqual(self.store.profile()['gpu'], 'keep me')
        with self.assertRaises(ValueError):
            validate_credentials({'token': 'abc\r\nInjected: header'})

if __name__ == '__main__':
    unittest.main()
