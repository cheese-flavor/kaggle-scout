import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core import Store
from installation import data_directory, migrate_database, backup_legacy_for_build

class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='work')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_migration_preserves_credentials_and_never_overwrites(self):
        old = Store(self.root / 'old')
        old.save_credentials({'token': 'migration-fixture-only'})
        old.set('profile', {'gpu': 'keep me'})
        target = self.root / 'new'
        self.assertTrue(migrate_database(old.folder, target))
        new = Store(target)
        self.assertEqual(new.credentials(), old.credentials())
        self.assertEqual(new.profile()['gpu'], 'keep me')
        new.set('profile', {'gpu': 'updated'})
        self.assertFalse(migrate_database(old.folder, target))
        self.assertEqual(new.profile()['gpu'], 'updated')
        self.assertEqual(old.profile()['gpu'], 'keep me')

    def test_paths_separate_install_data_portable_and_preview(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.root)}, clear=True):
            self.assertEqual(data_directory(self.root/'app', True), self.root/'KaggleScout')
            self.assertEqual(data_directory(self.root/'app', True, portable=True), self.root/'app'/'data')
            self.assertEqual(data_directory(self.root/'app', True, preview=True), self.root/'app'/'preview-data')
        with patch.dict(os.environ, {'SCOUT_DATA_DIR': str(self.root/'isolated')}):
            self.assertEqual(data_directory(self.root/'app', True), self.root/'isolated')

    def test_build_backs_up_old_distribution_before_it_can_be_replaced(self):
        old = Store(self.root/'dist'/'KaggleScout'/'data')
        old.save_credentials({'token': 'fixture-only'})
        backup = backup_legacy_for_build(self.root)
        self.assertEqual(Store(backup).credentials(), old.credentials())
        pointer = self.root/'work'/'private-data-backups'/'latest.txt'
        self.assertEqual(Path(pointer.read_text(encoding='utf8')), backup)

if __name__ == '__main__':
    unittest.main()
