"""Archive explicit fixture screenshots without replacing prior version images."""
import argparse
import json
from pathlib import Path
import re
from render_gallery import render

def archive(version, files, fixture=False):
    if not fixture or not re.fullmatch(r'v?\d+\.\d+\.\d+', version):
        raise ValueError('Valid version and explicit fixture-only confirmation required')
    version = 'v' + version.removeprefix('v')
    project = Path(__file__).resolve().parent
    docs = project / 'docs'
    root = docs / 'version-gallery'
    folder = root / version
    paths = [Path(f).resolve() for f in files]
    for path in paths:
        if not path.is_relative_to(docs.resolve()) or path.suffix.lower() != '.png':
            raise ValueError('Only explicit PNG files inside project docs may be archived')
        destination = folder / path.name
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            raise FileExistsError('Existing version image differs; refusing to overwrite ' + str(destination))
    manifest_file = root / 'sources.json'
    entries = json.loads(manifest_file.read_text(encoding='utf8')) if manifest_file.exists() else []
    folder.mkdir(parents=True, exist_ok=True)
    for path in paths:
        destination = folder / path.name
        if not destination.exists():
            destination.write_bytes(path.read_bytes())
        key = f'{version}/{path.name}'
        if not any(e['image'] == key for e in entries):
            entries.append({'version': version, 'source': f'{version}:{path.relative_to(project).as_posix()}',
                            'image': key, 'data': 'illustrative fixtures'})
    manifest_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding='utf8')
    render(root)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--fixture-only', action='store_true')
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()
    archive(args.version, args.files, args.fixture_only)
