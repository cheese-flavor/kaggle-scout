"""Per-user data paths and non-destructive legacy database migration."""
import os
from pathlib import Path
import sqlite3
import uuid

def data_directory(root, frozen=False, portable=False, preview=False):
    override = os.environ.get('SCOUT_DATA_DIR')
    if override:
        return Path(override)
    root = Path(root)
    if preview:
        return root / 'preview-data'
    if frozen and not portable:
        return Path(os.environ['LOCALAPPDATA']) / 'KaggleScout'
    return root / 'data'

def migrate_database(source_folder, target_folder):
    source = Path(source_folder).resolve() / 'scout.sqlite3'
    target_folder = Path(target_folder).resolve()
    destination = target_folder / 'scout.sqlite3'
    if destination.exists() or not source.exists():
        return False
    target_folder.mkdir(parents=True, exist_ok=True)
    temporary = target_folder / ('.migration-' + uuid.uuid4().hex + '.sqlite3')
    try:
        source_connection = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
        try:
            if source_connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('기존 데이터베이스 검사에 실패했습니다.')
            target_connection = sqlite3.connect(temporary)
            try:
                source_connection.backup(target_connection)
                if target_connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('이전 데이터베이스 검사에 실패했습니다.')
            finally:
                target_connection.close()
        finally:
            source_connection.close()
        # Atomic creation without replacing an existing destination, even after a race.
        os.link(temporary, destination)
        return True
    finally:
        if temporary.exists():
            temporary.unlink()

def backup_legacy_for_build(project_root=None):
    root = Path(project_root or Path.cwd()).resolve()
    source = root / 'dist' / 'KaggleScout' / 'data'
    if not (source / 'scout.sqlite3').exists():
        return None
    backups = root / 'work' / 'private-data-backups'
    target = backups / uuid.uuid4().hex
    migrate_database(source, target)
    (backups / 'latest.txt').write_text(str(target), encoding='utf8')
    return target
