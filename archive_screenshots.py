"""Archive explicit fixture screenshots without replacing prior version images."""
import argparse
import json
from pathlib import Path
import re

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
    text = '# 버전별 프로그램 화면\n\n릴리스의 예시 데이터 화면 원본을 보관합니다. 실제 개인 계정 화면은 포함하지 않습니다. 기존 버전 이미지는 덮어쓰지 않습니다. 출처는 sources.json에 기록합니다.\n\n'
    text += '새 릴리스에는 실제 앱에서 만든 예시 화면을 `docs`에 저장하고 다음 명령으로 추가합니다. 동일 버전에서 화면을 더 남길 때는 다른 파일명을 사용합니다. 서로 다른 내용의 기존 파일을 덮어쓰려 하면 중단합니다.\n\n```powershell\npython archive_screenshots.py --version 0.5.0 --fixture-only docs/dashboard-final-v050.png\n```\n\n'
    for tag in dict.fromkeys(e['version'] for e in entries):
        text += f'## {tag}\n\n'
        for entry in entries:
            if entry['version'] == tag:
                text += f"![{tag} {Path(entry['image']).stem}]({entry['image']})\n\n"
    (root/'README.md').write_text(text.rstrip() + '\n', encoding='utf8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--fixture-only', action='store_true')
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()
    archive(args.version, args.files, args.fixture_only)
