"""Render side-by-side release comparisons while keeping archived PNGs intact."""
import json
from pathlib import Path


def render(root=None):
    root = Path(root or Path(__file__).parent / 'docs' / 'version-gallery')
    entries = json.loads((root / 'sources.json').read_text(encoding='utf8'))
    releases = json.loads((root / 'releases.json').read_text(encoding='utf8'))
    images = {e['image'] for e in entries}
    lines = ['# 버전별 화면 비교', '',
             '왼쪽은 이전 버전, 오른쪽은 다음 버전입니다. 이미지를 누르면 원본 크기로 볼 수 있습니다. '
             '모든 화면은 실제 앱의 예시 데이터이며, 화면 크기와 예시 대회는 버전마다 다를 수 있습니다.', '',
             '최신 변경부터 보여줍니다. 각 버전의 전체 원본은 아래 **원본 화면 보관함**에 그대로 남깁니다.', '']
    for previous, current in reversed(list(zip(releases, releases[1:]))):
        before, after = previous['image'], current['image']
        if before not in images or after not in images:
            raise ValueError('Comparison images must be archived first')
        lines += [f"## {previous['version']} → {current['version']}", '',
                  f"| 이전 · {previous['version']} | 이후 · {current['version']} |",
                  '|---|---|',
                  f'| [![이전 화면]({before})]({before}) | [![이후 화면]({after})]({after}) |', '']
        lines += ['- ' + note for note in current['changes']]
        lines += ['']
    lines += ['## 원본 화면 보관함', '',
              '기존 이미지를 덮어쓰지 않습니다. 출처 태그와 경로는 [sources.json](sources.json)에 기록합니다.', '']
    for tag in dict.fromkeys(e['version'] for e in entries):
        lines += ['<details>', f'<summary>{tag} 전체 화면</summary>', '']
        for entry in entries:
            if entry['version'] == tag:
                lines += [f"![{tag} {Path(entry['image']).stem}]({entry['image']})", '']
        lines += ['</details>', '']
    lines += ['## 다음 릴리스에 추가하기', '',
              '실제 앱에서 예시 데이터로 촬영한 PNG만 추가합니다. 실계정·개인 기록은 포함하지 않습니다. '
              '동일 버전에 추가 화면을 남길 때는 새 파일명을 사용하세요. 기존 이미지와 다르면 보관 스크립트가 중단합니다.', '',
              '```powershell', 'python archive_screenshots.py --version 0.6.0 --fixture-only docs/dashboard-v060.png',
              '```', '',
              '새 버전의 대표 이미지와 짧은 변경 설명을 `releases.json`에 추가한 뒤 '
              '`python render_gallery.py`를 실행하면 비교 표도 갱신됩니다.']
    (root / 'README.md').write_text('\n'.join(lines).rstrip() + '\n', encoding='utf8')


if __name__ == '__main__':
    render()
