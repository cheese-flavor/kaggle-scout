"""Collect notices for the Windows distribution from the pinned build environment."""
from importlib.metadata import distribution
from pathlib import Path
from shutil import copy2, copytree
import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion


def bundle_licenses():
    root = Path(__file__).resolve().parent
    qt_version = '6.11.3'
    if pyside_version != qt_version or qVersion() != qt_version or distribution('shiboken6').version != qt_version:
        raise RuntimeError('Qt runtime version does not match the bundled notices and source links.')

    licenses = root / 'dist' / 'KaggleScout' / 'licenses'
    copytree(root / 'licenses', licenses, dirs_exist_ok=True)
    copy2(Path(sys.base_prefix) / 'LICENSE.txt', licenses / 'CPython-LICENSE.txt')
    for name in ('requests', 'urllib3', 'certifi', 'idna', 'charset-normalizer', 'packaging', 'setuptools'):
        package = distribution(name)
        files = [file for file in package.files or ()
                 if file.parts[0].endswith('.dist-info')
                 and file.name.upper().startswith(('LICENSE', 'NOTICE', 'COPYING'))]
        if not files:
            raise RuntimeError(f'No license files found for {name}.')
        folder = licenses / f'{name}-{package.version}'
        folder.mkdir(exist_ok=True)
        for file in files:
            copy2(package.locate_file(file), folder / file.name)


if __name__ == '__main__':
    bundle_licenses()
